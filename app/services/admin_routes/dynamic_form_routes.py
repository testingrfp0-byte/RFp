from fastapi import UploadFile, File, Depends, HTTPException, APIRouter,status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os 
from typing import List
from app.db.database import get_db
from app.schemas.schema import (KeystoneFileResponse)
from app.models.rfp_models import User,KeystoneFile
from app.api.routes.utils import get_current_user
from app.services.admin_services.keystone_service import upload_keystone_file,delete_keystone_file,view_keystone_file
router = APIRouter()

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
