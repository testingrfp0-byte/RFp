from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.rfp_models import User
from fastapi import Depends, APIRouter, Form, Request
from app.api.routes.utils import get_current_user
from app.services.admin_services import (
    get_all_users, get_assigned_users,
    get_user_by_id_service, check_submissions_service,
    get_assign_user_status_service, update_profile_service)
from sqlalchemy.ext.asyncio import AsyncSession
# from slowapi import Limiter
from app.core.rate_limiter import limiter

router = APIRouter()

# @limiter.limit("2/minute")

@router.get("/userdetails")
async def get_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await get_all_users(db, current_user)

@router.get("/get_assign_users")
async def get_assigned(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await get_assigned_users(db, current_user)

@router.get("/userdetails/{user_id}")
async def get_user_by_id_route(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await get_user_by_id_service(user_id, db)

@router.put("/update-profile")
async def update_profile(
    username: str | None = Form(None),
    email: str | None = Form(None),
    image_name: str | None = Form(None),
    image_base64: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await update_profile_service(
        db=db,
        current_user=current_user,
        username=username,
        email=email,
        image_name=image_name,
        image_base64=image_base64,
    )

@router.get("/check_submit")
async def check(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await check_submissions_service(db, current_user)

@router.get("/assign_user_status")
async def assign_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await get_assign_user_status_service(db, current_user)