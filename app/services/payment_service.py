from pydantic import HttpUrl
from sqlalchemy.future import select
import asyncio
# from augmintcore.app.api import payment_routes
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
import stripe 
from app.core.config import get_settings
from app.db.session import get_async_session
from app.models.user import User,Subscription,Transaction,SubscriptionStatus
# from fastapi import HTTPException
settings = get_settings()
stripe.api_key = settings.STRIPE_SECRET_KEY

class PaymentService:

    async def create_stripe_customer_id(self,user):

        customer = stripe.Customer.create(email=user.email)
        customer_id = customer.id
        return customer_id 

    async def checkout_session(self,user,data):
        customer_id = user.stripe_customer_id
        if not customer_id:
            cutsomer = stripe.Customer.create(email=user.email)
            customer_id = cutsomer.id
            user.stripe_customer_id =customer_id

        plan_name= data.plan_name
        plan_duration = data.plan_duration   
        if plan_duration == "monthly":
            if plan_name =="premium":
                price_id = settings.PRICE_ID_MONTHLY["premium"]
            elif plan_name =="business":
                price_id = settings.PRICE_ID_MONTHLY["business"]
        elif plan_duration == "yearly":
            if plan_name =="premium":
                price_id = settings.PRICE_ID_YEARLY["premium"]
            elif plan_name =="business":
                price_id = settings.PRICE_ID_YEARLY["business"]
        metadata = {
                "user_id":int(user.id),
                "plan_name":plan_name,
                "plan_duration":plan_duration,
            }

        

        #step2 creating checkout session 
        session = stripe.checkout.Session.create(
            customer=user.stripe_customer_id,
            payment_method_types = ['card'],
            mode = 'subscription', #Recurring Payment 
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            # success_url = "https://augmint.itechnolabs.tech/en/dashboard?payment=success",
            success_url = "https://augmint.itechnolabs.tech/en/payment-success?payment=success",
            cancel_url = "https://augmint.itechnolabs.tech/en/choose-your-plan?payment=failed",
            metadata = metadata
            
        )
        print("here")
        return session
    @staticmethod
    def construct_event(payload: bytes,sig_header: str, webhook_secret: str):
        return stripe.Webhook.construct_event(
            payload,
            sig_header,
            webhook_secret
        )

    async def handle_subscription(self,
        user_id,
        db,
        plan_name:str,
        plan_type:str,
        price: int,
        status ,
        plan_start:datetime,
        plan_end:datetime,
        event_id ,
        subscription_id
    ):
        result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
        subscription = result.scalar_one_or_none()
        # result_transaction = await db.execute(select(Transaction).where(Transaction.subscription_id == subscription.id))
        # transaction = result_transaction.scalar_one_or_none()

        if subscription and subscription.cancel_at_period_end == False:
            subscription.plan_name=plan_name
            subscription.plan_type=plan_type
            subscription.status = status
            subscription.price = price
            subscription.period_start = plan_start
            subscription.period_end = plan_end
            subscription.stripe_subscription_id = subscription_id
            print("in if - updating existing subscription")
            db.add(subscription)
            #Also have to create the transaction 
            transaction_obj = Transaction(
                user_id = user_id,
                subscription_id = subscription.id,
                amount = price,
                currency = "usd",
                stripe_event_id = event_id,
                type = "invoice.paid"
            )
            db.add(transaction_obj)
            await db.commit()
            await db.refresh(subscription)
            await db.refresh(transaction_obj)
        else :
            subscription = Subscription(
                user_id = user_id,
                plan_name = plan_name,
                plan_type = plan_type,
                price = price,
                status = status,
                period_start = plan_start,
                period_end = plan_end,
                stripe_subscription_id = subscription_id,
                
            )
            db.add(subscription)
            transaction_new = Transaction(
                user_id = user_id,
                subscription_id = subscription.id,
                amount = price,
                currency = "usd",
                stripe_event_id = event_id,
                type = "invoice.paid"
            )
            db.add(transaction_new)
            await db.commit()
            await db.refresh(subscription)
            await db.refresh(transaction_new)
        return subscription

    async def handle_subscription_updated(
        self,
        db: AsyncSession,
        stripe_subscription_id: str,
        cancel_at_period_end: bool
    ):
        result = await db.execute(select(Subscription).where(Subscription.stripe_subscription_id == stripe_subscription_id))
        subscription = result.scalar_one_or_none()
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        if cancel_at_period_end:
            subscription.status = "cancelled" # Mark as cancelled (but still active until period end)
            subscription.cancel_at_period_end= True
            subscription.cancellation_date = datetime.utcnow()
        else:
            subscription.status= "active"
            subscription.cancel_at_period_end = False
            subscription.cancellation_date = None
        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)

        return subscription

    async def handle_subscription_deleted(
        self,
        db:AsyncSession,
        stripe_subscription_id: str,
        event_data: dict

    ):
        # Handle customer.subscription.deleted event
        result = db.execute(select(Subscription).where(Subscription.stripe_subscription_id==stripe_subscription_id))
        subscription = result.scalar_one_or_none()
        if not subscription :
            raise HTTPException(status_code=404, detail="Subscription not found")

        subscription.status = "deleted"
        subscription.cancel_at_period_end = True
        subscription.final_cancellation_date = datetime.utcnow()
        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)

        return subscription

    async def handle_auto_renewal(
        self,
        db: AsyncSession,
        event_data: dict,
        event_id: str
    ):

        # Handle invoice.payment_succeeded event

        stripe_subscription_id= event_data.get("subscription")
        invoice_amount = event_data.get("amount_paid")
        if not stripe_subscription_id:
            raise HTTPException(status_code=400, detail="Subscription ID not found")

        result = db.execute(select(Subscription).where(Subscription.stripe_subscription_id==stripe_subscription_id))
        subscripton = result.scalar_one_or_none()
        if not subscripton:
            raise HTTPException(status_code=404, detail="Subscription not found")

        stripe_sub = await asyncio.to_thread(
            stripe.Subscription.retrieve,
            stripe_subscription_id
        )
        subscripton.status = stripe_sub.get("status")
        subscription.period_start = datetime.utcfromtimestamp(
            stripe_sub.get("current_period_start")
        )
        subscription.period_end = datetime.utcfromtimestamp(
            stripe_sub.get("current_period_end")
        )

        # Record the transaction for this renewal
        transaction = Transaction(
            user_id = subscripton.user_id,
            subscripton_id  = subscripton.id,
            amount = invoice_amount,
            currency = "usd",
            stripe_event_id = event_id,
            type = "invoice.payment_succeeded"
        )
        db.add(transaction)
        await db.commit()
        await db.refresh(transaction)
        return subscripton

    async def handle_cancel_subscription_at_period_end(
        self,
        db : AsyncSession,
        user_id : int
    ): 
        result = await db.execute(select(Subscription).where(Subscription.user_id==user_id))
        subscription = result.scalar_one_or_none()
        
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        await asyncio.to_thread(stripe.Subscription.modify,subscription.stripe_subscription_id,cancel_at_period_end=True)
        subscription.status = "canceled"
        subscription.cancel_at_period_end = True
        subscription.final_cancellation_date = datetime.utcnow()
        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)
        return subscription

    


    
        

        




        
    
        


            


payment_service = PaymentService()
