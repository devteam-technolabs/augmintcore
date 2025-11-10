from fastapi import APIRouter, Depends

from app.crud.user import get_user
from app.schemas.user import UserOut

router = APIRouter()


@router.get("/{user_id}", response_model=UserOut)
def read_user(user_id: int):
    return get_user(user_id)
