from fastapi import UploadFile, File, Depends, HTTPException, APIRouter
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.schema import (
    KeystoneDynamicFormRequest, KeystonePatchRequest)
from app.models.rfp_models import User
from app.api.routes.utils import get_current_user
from app.utils.admin_function import (
    extract_col, save_form, fetch_form, update_form, delete_form)

router = APIRouter()

@router.post("/dynamic/extract-columns")
async def extract_columns(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    try:
        return await extract_col(file,current_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/dynamic/save-form")
def save_keystone_form(
    request: KeystoneDynamicFormRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return save_form(request, db, current_user)

@router.get("/dynamic/get-form")
def get_keystone_form(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return fetch_form(db, current_user)

@router.patch("/dynamic/form/{form_id}")
def update_keystone_form(
    form_id: int,
    request: KeystonePatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return update_form(form_id, request, db, current_user)

@router.delete("/dynamic/form/{form_id}")
def delete_keystone_form(
    form_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return delete_form(form_id, db, current_user)