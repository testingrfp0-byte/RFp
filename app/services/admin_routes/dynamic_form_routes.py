from fastapi import UploadFile, File, Depends, HTTPException, APIRouter,status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os 
from typing import List
from app.db.database import get_db
from app.schemas.schema import (
    KeystoneDynamicFormRequest, KeystonePatchRequest,KeystoneFileResponse)
from app.models.rfp_models import User,KeystoneFile
from app.api.routes.utils import get_current_user
from app.utils.admin_function import (
    extract_col, save_form, fetch_form, update_form, delete_form)

from app.services.admin_services.keystone_service import upload_keystone_file,delete_keystone_file,view_keystone_file
router = APIRouter()

# @router.post("/dynamic/extract-columns")
# async def extract_columns(
#     file: UploadFile = File(...),
#     current_user: User = Depends(get_current_user)
# ):
#     try:
#         return await extract_col(file,current_user)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/dynamic/save-form")
# def save_keystone_form(
#     request: KeystoneDynamicFormRequest,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     return save_form(request, db, current_user)

# @router.get("/dynamic/get-form")
# def get_keystone_form(
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     return fetch_form(db, current_user)

# @router.patch("/dynamic/form/{form_id}")
# def update_keystone_form(
#     form_id: int,
#     request: KeystonePatchRequest,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     return update_form(form_id, request, db, current_user)

# @router.delete("/dynamic/form/{form_id}")
# def delete_keystone_form(
#     form_id: int,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     return delete_form(form_id, db, current_user)


# =====================================
@router.post("/keystone/upload")
async def upload_keystone(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    
    return await upload_keystone_file(
        file=file,
        db=db,
        current_user=current_user
    )

@router.get("/keystone/files", response_model=List[KeystoneFileResponse])
def list_keystone_files(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view Keystone files"
        )

    files = (
        db.query(KeystoneFile)
        .filter(KeystoneFile.admin_id == current_user.id)
        .order_by(KeystoneFile.uploaded_at.desc())
        .all()
    )

    return files

@router.delete("/keystone/delete/{keystone_id}")
def delete_keystone(
    keystone_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return delete_keystone_file(
        keystone_id=keystone_id,
        db=db,
        current_user=current_user
    )

@router.get("/keystone/files/{keystone_id}/view")
def view_keystone(
    keystone_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return view_keystone_file(
        keystone_id=keystone_id,
        db=db,
        current_user=current_user
    )
