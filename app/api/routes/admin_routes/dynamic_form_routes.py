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
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
router = APIRouter()

@router.post("/keystone/upload")
async def upload_keystone(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    
    return await upload_keystone_file(
        file=file,
        db=db,
        current_user=current_user
    )

@router.get("/keystone/files", response_model=List[KeystoneFileResponse])
async def list_keystone_files(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view Keystone files"
        )

    files = await db.execute(
        select(KeystoneFile)
        .filter(KeystoneFile.admin_id == current_user.id)
        .order_by(KeystoneFile.uploaded_at.desc())
     )
    files = files.scalars().all()

    return files

@router.delete("/keystone/delete/{keystone_id}")
async def delete_keystone(
    keystone_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await delete_keystone_file(
        keystone_id=keystone_id,
        db=db,
        current_user=current_user
    )

@router.get("/keystone/files/{keystone_id}/view")
async def view_keystone(
    keystone_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await view_keystone_file(
        keystone_id=keystone_id,
        db=db,
        current_user=current_user
    )
