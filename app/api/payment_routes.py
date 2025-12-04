import datetime
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
    subscription = await db.execute(select(Subscription).where(Subscription.user_id ==user_id))
    subscription_obj = subscription.scalar_one_or_none()
    if not subscription_obj:
        raise HTTPException(status_code=404, detail="Subscription not found")
    import asyncio
    await asyncio.to_thread(stripe.Subscription.modify,subscription_obj.stripe_subscription_id, cancel_at_period_end=True)
    subscription_obj.status ="cancelled"
    await db.commit()
    await db.refresh(subscription_obj)
    return {
        "status_code":200,
        "message":"Subscription cancelled successfully"
    }
    

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
        metadata= event_data["metadata"]
        user_id = int(metadata['user_id'])
        plan_name = metadata['plan_name']
        plan_type =metadata['plan_duration']
        subscription_id = event_data['subscription']
        event_id = event['id']

        stripe_sub = await asyncio.to_thread(stripe.Subscription.retrieve,subscription_id)
        print(stripe_sub,"stripe_sub ======")
        # plan_name = stripe_sub["items"]["data"][0]["price"]["nickname"]
        price = stripe_sub["items"]["data"][0]["price"]["unit_amount"]
        status = stripe_sub["status"]
        # plan_type = stripe_sub["items"]["data"][0]["price"]["product"]
        print("here")

        plan_start = (
            datetime.utcfromtimestamp(stripe_sub["current_period_start"])
            if stripe_sub.get("current_period_start")
            else None
        )

        plan_end = (
            datetime.utcfromtimestamp(stripe_sub.get("current_period_end"))
            if stripe_sub.get("current_period_end")
            else None
        )

        async with AsyncSessionLocal() as session:
            await payment_service.handle_subscription(user_id,session,plan_name,plan_type,price,status,plan_start,plan_end,event_id)
            print("Subscription handled successfully")

    # Auto -Renewal

    elif event_type =="invoice.payment_succeeded":
        try :
            subscription_id = event.data.get("subscription")

            async with AsyncSessionLocal() as session:
                subscription = await payment_service.handle_auto_renewal(db =session,event_data=event_data,event_id = event['id'])
            
        except Exception as e:
            print(f"[WEBHOOK ERROR] invoice.payment_succeeded: {str(e)}")

    


    

