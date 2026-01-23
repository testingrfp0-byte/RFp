import os
import uuid
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse
from app.models.rfp_models import User,KeystoneFile
from fastapi import UploadFile, HTTPException, status
from app.services.llm_services.llm_service import extract_xls_text

async def upload_keystone_file(
    file: UploadFile,
    db: Session,
    current_user: User
):
    if current_user.role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized"
        )

    if not file.filename.endswith((".xls", ".xlsx")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Excel files allowed"
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty"
        )

    path = f"uploads/{uuid.uuid4()}_{file.filename}"
    with open(path, "wb") as f:
        f.write(file_bytes)

    extracted_text = extract_xls_text(path)

    db.query(KeystoneFile).filter(
        KeystoneFile.admin_id == current_user.id,
        KeystoneFile.is_active.is_(True)
    ).update({"is_active": False})

    keystone = KeystoneFile(
        admin_id=current_user.id,
        filename=file.filename,
        file_path=path,
        extracted_text=extracted_text,
        is_active=True
    )

    db.add(keystone)
    db.commit()
    db.refresh(keystone)

    return {
        "status": "success",
        "keystone_id": keystone.id,
        "filename": keystone.filename
    }

def delete_keystone_file(
    keystone_id: int,
    db: Session,
    current_user: User,
):
    if current_user.role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete Keystone files"
        )

    keystone = (
        db.query(KeystoneFile)
        .filter(
            KeystoneFile.id == keystone_id,
            KeystoneFile.admin_id == current_user.id
        )
        .first()
    )

    if not keystone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Keystone file not found"
        )

    if keystone.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Active Keystone file cannot be deleted. Please activate another file first."
        )

    db.delete(keystone)
    db.commit()

    return {
        "status": "success",
        "message": "Keystone file deleted successfully"
    }

def view_keystone_file(
    keystone_id: int,
    db: Session,
    current_user: User,
):
    if current_user.role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view Keystone files"
        )

    keystone = (
        db.query(KeystoneFile)
        .filter(
            KeystoneFile.id == keystone_id,
            KeystoneFile.admin_id == current_user.id
        )
        .first()
    )

    if not keystone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Keystone file not found"
        )
    if not keystone.file_path or not os.path.exists(keystone.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Keystone file not found on server"
        )

    return FileResponse(
        path=keystone.file_path,
        filename=keystone.filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
