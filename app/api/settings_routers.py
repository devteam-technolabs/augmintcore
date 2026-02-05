from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.user import auth_user
from app.constants.accordion_data import (
    getting_started_data,
    market_analysis_data,
    security_data,
    trading_strategies_data,
)
from app.db.session import get_async_session
from app.schemas.settings_schema import AddressUpdateRequest, UserUpdateRequest
from app.services.settings_service import (
    get_user_address,
    get_user_profile,
    update_user_address,
    update_user_profile,
)

settings_router = APIRouter(prefix="/settings", tags=["settings"])


@settings_router.get("/getting-started-data", status_code=status.HTTP_200_OK)
async def get_getting_started_data():
    return {"success": True, "data": getting_started_data}


@settings_router.get("/trading-strategies-data", status_code=status.HTTP_200_OK)
async def get_trading_strategies_data():
    return {"success": True, "data": trading_strategies_data}


@settings_router.get("/market-analysis-data", status_code=status.HTTP_200_OK)
async def get_market_analysis_data():
    return {"success": True, "data": market_analysis_data}


@settings_router.get("/security-data", status_code=status.HTTP_200_OK)
async def get_security_data():
    return {"success": True, "data": security_data}


@settings_router.get("/get-user-profile")
async def user_detail(
    request: Request,
    user=Depends(auth_user.get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    return {"success": True, "data": await get_user_profile(user, request)}


@settings_router.patch("/update-user-profile")
async def update_user(
    request: Request,
    data: UserUpdateRequest = Depends(),
    image: UploadFile = File(None),
    user=Depends(auth_user.get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    updated = await update_user_profile(db, user, data, image, request)

    return {"success": True, "message": "Profile updated successfully", "data": updated}


@settings_router.get("/get-user-address")
async def address_detail(
    user=Depends(auth_user.get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    address = await get_user_address(db, user.id)

    return {"success": True, "data": address}


@settings_router.patch("/update-user-address")
async def address_update(
    payload: AddressUpdateRequest,
    user=Depends(auth_user.get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    address = await get_user_address(db, user.id)

    updated = await update_user_address(db, address, payload)

    return {"success": True, "message": "Address updated successfully", "data": updated}
