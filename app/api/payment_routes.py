from datetime import datetime, timezone
from importlib import metadata
from app.db.session import get_async_session,AsyncSessionLocal
import stripe 
from fastapi import APIRouter,Depends, HTTPException, Security
from app.core.config import get_settings
from app.schemas.user import CheckoutSessionSchemas,CheckoutSessionResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.payment_service import payment_service
from app.auth.user import auth_user
from app.models.user import User,Transaction,Subscription
from sqlalchemy import select
from fastapi import Request
from fastapi.responses import PlainTextResponse
import asyncio
settings = get_settings()

router = APIRouter(prefix="/payment", tags=["Payment"])

@router.post("/create-checkout-session",response_model=CheckoutSessionResponse)
async def create_checkout_session(data:CheckoutSessionSchemas,db:AsyncSession =Depends(get_async_session),current_user=Security(auth_user.get_current_user)):
    user = current_user
    user_id = user.id
    result = await db.execute(select(User).where(User.id==user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    #Calling the stripe checkout session
    session = await payment_service.checkout_session(user,data)
    checkout_url = session.url 
    return {
        "checkout_url":checkout_url,
        "status_code":200
    }

@router.post("/cancel-subscription")
async def cancel_subscription(db:AsyncSession = Depends(get_async_session),current_user=Depends(auth_user.get_current_user)):
    user = current_user
    user_id = user.id 
    try:
        subscription = await payment_service.handle_cancel_subscription_at_period_end(db,user_id)
        return {
        "status_code":200,
        "message":"Subscription cancelled successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stripe_webhook", include_in_schema=False)
async def stripe_webhook(request:Request):
    print("Received webhook")
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=400, detail="Webhook not configured")

    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    try:
        event = payment_service.construct_event(payload,sig_header,settings.STRIPE_WEBHOOK_SECRET)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid payload")

    event_type = event['type']
    event_data = event["data"] ["object"]
     
    if event_type =="checkout.session.completed":
        print("webhhok come in if condition")
        metadata= event_data["metadata"]
        user_id = int(metadata['user_id'])
        plan_name = metadata['plan_name']
        plan_type =metadata['plan_duration']
        subscription_id = event_data['subscription']
        print("sub_id========>",subscription_id)
        event_id = event['id']

        stripe_sub = await asyncio.to_thread(stripe.Subscription.retrieve,subscription_id)
        print(stripe_sub,"stripe_sub ======")
        # plan_name = stripe_sub["items"]["data"][0]["price"]["nickname"]
        price = stripe_sub["items"]["data"][0]["price"]["unit_amount"]
        amount_price = price / 100  # Convert cents to dollars
        status = stripe_sub["status"]
        # plan_type = stripe_sub["items"]["data"][0]["price"]["product"]
        print("here")

        plan_start_timestamp = stripe_sub["items"]["data"][0]["current_period_start"]
        plan_start = datetime.fromtimestamp(plan_start_timestamp)
        
        

        plan_end_timestamp = stripe_sub["items"]["data"][0]["current_period_end"]
        plan_end = datetime.fromtimestamp(plan_end_timestamp)

        async with AsyncSessionLocal() as session:
            await payment_service.handle_subscription(user_id,session,plan_name,plan_type,amount_price,status,plan_start,plan_end,event_id,subscription_id)
            print("Subscription handled successfully")

    # Auto -Renewal

    elif event_type =="invoice.payment_succeeded":
        print("webhhok come in invoice.payment_succeeded")
        billing_reason = event_data.get("billing_reason")
        if billing_reason == "subscription_cycle":
            return
        if billing_reason == "recurring":
            try :
                subscription_id = event.data.get("subscription")

                async with AsyncSessionLocal() as session:
                    subscription = await payment_service.handle_auto_renewal(db =session,event_data=event_data,event_id = event['id'])
            
            except Exception as e:
                print(f"[WEBHOOK ERROR] invoice.payment_succeeded: {str(e)}")
        
    # SUBSCRIPTION DELETD PERMANENTLY

    elif event_type =="customer.subscription.deleted":
        try:
            subscription_id = event_data.get("id")
            async with AsyncSessionLocal() as session:
                await payment_service.handle_subscription_deleted(subscription_id,session)
                if subscription:
                    print(f"[WEBHOOK] Subscription {subscription_id} fully deleted")
        except Exception as e:
            print(f"[WEBHOOK ERROR] customer.subscription.deleted: {str(e)}")

    # SUBSCRIPTION UPDATED

    elif event_type =="customer.subscription.updated":
        try:
            subscription_id = event_data.get("id")
            cancel_at_period_end = event_data.get('cancel_at_period_end', False)
            async with AsyncSessionLocal() as session:
                subscription = await payment_service.handle_subscription_updated(
                    db=session,
                    stripe_subscription_id=subscription_id,
                    cancel_at_period_end=cancel_at_period_end
                )
                
                if subscription:
                    if cancel_at_period_end:
                        print(f"[WEBHOOK] Subscription {subscription_id} scheduled for cancellation")
                    else:
                        print(f"[WEBHOOK] Subscription {subscription_id} reactivated")

        except Exception as e:
            print(f"[WEBHOOK ERROR] customer.subscription.updated: {str(e)}")


        
    



    


    

