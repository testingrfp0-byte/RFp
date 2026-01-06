import io
import uuid
import pandas as pd
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session
from app.models.rfp_models import KeystoneData,User,KeystoneFile
from app.schemas.schema import KeystoneDynamicFormRequest, KeystonePatchRequest
from app.services.llm_services.llm_service import extract_xls_text

async def extract_col(file: UploadFile, current_user):
    try:
        if current_user.role.lower() != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can delete Keystone Data."
            )

        content = await file.read()
        excel_bytes = io.BytesIO(content)

        df = pd.read_excel(excel_bytes, nrows=0)

        clean_columns = []
        for col in df.columns:
            if str(col).startswith("Unnamed:"):
                clean_columns.append("Unnamed")
            else:
                clean_columns.append(str(col))

        ui_fields = []
        for col in clean_columns:
            ui_fields.append({
                "field_key": col,
                "label": col,
                "type": "textarea" if "answer" in col.lower() else "text"
            })

        return {
            "status": "success",
            "columns": clean_columns,
            "ui_form_schema": ui_fields
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Excel file: {str(e)}")

def save_form(request: KeystoneDynamicFormRequest, db: Session, current_user):

    if current_user.role.lower() != "admin":
        raise HTTPException(status_code=403, detail="Only admins can save Keystone form data.")
    
    new_row = KeystoneData(
        section=request.section,
        field_group=request.field_group,
        field_detail=request.field_detail,
        field_type=request.unnamed,
        default_answer=request.ringer_answer
    )

    db.add(new_row)
    db.commit()
    db.refresh(new_row)

    return {
        "status": "success",
        "message": "Form saved successfully.",
        "data": {
            "id": new_row.id,
            "section": new_row.section,
            "field_group": new_row.field_group,
            "field_detail": new_row.field_detail,
            "Ringer_Answer": new_row.default_answer,
            "unnamed": request.unnamed
        }
    }

def fetch_form(db: Session, current_user):

    if current_user.role.lower() != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only admins can fetch Keystone forms."
        )

    records = (
        db.query(KeystoneData)
        .order_by(KeystoneData.id)
        .all()
    )

    if not records:
        return {
            "status": "success",
            "forms": []
        }

    forms_list = []

    for record in records:
        form = {
            "id": record.id,
            "Section": record.section,
            "Field_Group": record.field_group,
            "Field_Detail": record.field_detail,
            "Ringer_Answer": record.default_answer,
            "Unnamed": record.field_type
        }
        forms_list.append(form)

    return {
        "status": "success",
        "forms": forms_list
    }

def update_form(form_id: int, request: KeystonePatchRequest, db: Session, current_user):

    if current_user.role.lower() != "admin":
        raise HTTPException(status_code=403, detail="Only admins can update Keystone form data.")

    record = db.query(KeystoneData).filter(KeystoneData.id == form_id).first()

    if not record:
        raise HTTPException(status_code=404, detail="Form entry not found")

    if request.section is not None:
        record.section = request.section

    if request.field_group is not None:
        record.field_group = request.field_group

    if request.field_detail is not None:
        record.field_detail = request.field_detail

    if request.ringer_answer is not None:
        record.default_answer = request.ringer_answer

    if request.unnamed is not None:
        record.field_type = request.unnamed

    db.commit()
    db.refresh(record)

    return {
        "status": "success",
        "message": "Form updated successfully.",
        "data": {
            "id": record.id,
            "section": record.section,
            "field_group": record.field_group,
            "field_detail": record.field_detail,
            "ringer_answer": record.default_answer
        }
    }

def delete_form(form_id: int, db: Session, current_user):

    if current_user.role.lower() != "admin":
        raise HTTPException(status_code=403, detail="Only admins can delete Keystone data.")

    record = db.query(KeystoneData).filter(KeystoneData.id == form_id).first()

    if not record:
        raise HTTPException(status_code=404, detail="Form not found.")

    db.delete(record)
    db.commit()

    return {
        "status": "success",
        "message": f"Form with ID {form_id} deleted successfully."
    }

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