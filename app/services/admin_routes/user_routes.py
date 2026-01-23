from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.rfp_models import User
from fastapi import Depends, APIRouter, Form
from app.api.routes.utils import get_current_user
from app.utils.admin_function import (
    get_all_users, get_assigned_users,
    get_user_by_id_service, check_submissions_service,
    get_assign_user_status_service, update_profile_service)

router = APIRouter()

@router.get("/userdetails")
def get_user(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_all_users(db, current_user)

@router.get("/get_assign_users")
def get_assigned(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_assigned_users(db, current_user)

@router.get("/userdetails/{user_id}")
def get_user_by_id_route(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_user_by_id_service(user_id, db)

@router.put("/update-profile")
async def update_profile(
    username: str | None = Form(None),
    email: str | None = Form(None),
    image_name: str | None = Form(None),
    image_base64: str | None = Form(None),
    db: Session = Depends(get_db),
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
def check(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return check_submissions_service(db, current_user)

@router.get("/assign_user_status")
def assign_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_assign_user_status_service(db, current_user)