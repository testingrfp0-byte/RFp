from fastapi import UploadFile, File, Depends, HTTPException, APIRouter
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.schema import (
    KeystoneDynamicFormRequest, KeystonePatchRequest)
from app.models.rfp_models import User,KeystoneFile
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


# =====================================
import uuid

@router.post("/keystone/upload")
async def upload_keystone(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role.lower() != "admin":
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not file.filename.endswith((".xls", ".xlsx")):
        raise HTTPException(status_code=400, detail="Only Excel files allowed")

    file_bytes = await file.read()

    path = f"uploads/{uuid.uuid4()}_{file.filename}"
    with open(path, "wb") as f:
        f.write(file_bytes)

    extracted_text = extract_xls_text(path)

    # deactivate old keystone
    db.query(KeystoneFile).filter(
        KeystoneFile.admin_id == current_user.id,
        KeystoneFile.is_active == True
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

    return {"status": "success"}

# ==========================
import pandas as pd

def extract_xls_text(file_path: str) -> str:
    sheets = pd.read_excel(file_path, sheet_name=None)
    output = []

    for sheet_name, df in sheets.items():
        output.append(f"\n=== {sheet_name} ===\n")
        for _, row in df.iterrows():
            row_text = " | ".join(
                str(cell) for cell in row if pd.notna(cell)
            )
            if row_text.strip():
                output.append(row_text)

    return "\n".join(output)

