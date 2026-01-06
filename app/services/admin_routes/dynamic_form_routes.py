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

from app.services.admin_services.keystone_service import upload_keystone_file
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


# =====================================


# @router.post("/keystone/upload")
# async def upload_keystone(
#     file: UploadFile = File(...),
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     if current_user.role.lower() != "admin":
#         raise HTTPException(status_code=401, detail="Unauthorized")

#     if not file.filename.endswith((".xls", ".xlsx")):
#         raise HTTPException(status_code=400, detail="Only Excel files allowed")

#     file_bytes = await file.read()

#     path = f"uploads/{uuid.uuid4()}_{file.filename}"
#     with open(path, "wb") as f:
#         f.write(file_bytes)

#     extracted_text = extract_xls_text(path)

#     db.query(KeystoneFile).filter(
#         KeystoneFile.admin_id == current_user.id,
#         KeystoneFile.is_active == True
#     ).update({"is_active": False})

#     keystone = KeystoneFile(
#         admin_id=current_user.id,
#         filename=file.filename,
#         file_path=path,
#         extracted_text=extracted_text,
#         is_active=True
#     )

#     db.add(keystone)
#     db.commit()

#     return {"status": "success"}

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
def delete_keystone_file(
    keystone_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1️⃣ Only admins allowed
    if current_user.role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete Keystone files"
        )

    # 2️⃣ Fetch Keystone file
    keystone = db.query(KeystoneFile).filter(
        KeystoneFile.id == keystone_id,
        KeystoneFile.admin_id == current_user.id
    ).first()

    if not keystone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Keystone file not found"
        )

    # 3️⃣ Prevent deleting active Keystone
    if keystone.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Active Keystone file cannot be deleted. Please activate another file first."
        )

    # 4️⃣ Delete record
    db.delete(keystone)
    db.commit()

    return {
        "status": "success",
        "message": "Keystone file deleted successfully"
    }



@router.get("/keystone/files/{keystone_id}/view")
def view_keystone_file(
    keystone_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1️⃣ Admin only
    if current_user.role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view Keystone files"
        )

    # 2️⃣ Fetch Keystone file
    keystone = db.query(KeystoneFile).filter(
        KeystoneFile.id == keystone_id,
        KeystoneFile.admin_id == current_user.id
    ).first()

    if not keystone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Keystone file not found"
        )

    # 3️⃣ Ensure file exists on disk
    if not os.path.exists(keystone.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Keystone file not found on server"
        )

    # 4️⃣ Return file
    return FileResponse(
        path=keystone.file_path,
        filename=keystone.filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

