import os
from datetime import datetime
from typing import List
from fastapi import (
    UploadFile, File, Form, Depends, HTTPException, APIRouter, status, Request)
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.config import GENERATED_FOLDER
from app.db.database import get_db
from app.models.rfp_models import User, RFPDocument
from app.api.routes.utils import get_current_user
from app.utils.admin_function import upload_documents

router = APIRouter()

@router.post("/generate-rfp-doc/")
async def generate_rfp_doc(
    rfp_id: int,
    request: Request, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role.lower() != "admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    rfp_doc = db.query(RFPDocument).filter(RFPDocument.id == rfp_id).first()
    if not rfp_doc:
        raise HTTPException(status_code=404, detail="RFP not found")

    unanswered = []
    for q in rfp_doc.questions:
        has_reviewer_ans = any(rev.submit_status == "submitted" for rev in q.reviewers)
        has_ai_ans = bool(q.answer_versions)
        if not (has_reviewer_ans or has_ai_ans):
            unanswered.append(q.question_text)

    if unanswered:
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"Report cannot be generated. {len(unanswered)} question(s) are not analyzed yet.",
                "unanswered_questions": unanswered
            }
        )

    summary_obj = rfp_doc.summary
    if not summary_obj:
        raise HTTPException(status_code=404, detail="Executive summary not found")
    executive_summary = summary_obj.summary_text

    company_name = getattr(rfp_doc, "client_name", "Ringer")

    doc = Document()

    try:
        logo_path = "image.png" 
        doc.add_picture(logo_path, width=Inches(1.5))
        last_paragraph = doc.paragraphs[-1]
        last_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    except Exception as e:
        print("Logo could not be added:", e)

    doc.add_heading("RFP Proposal Response", level=0)
    doc.add_paragraph(f"Presented by Ringer")
    doc.add_paragraph(f"Client: {company_name}")
    doc.add_paragraph(f"Generated on {datetime.utcnow().strftime('%Y-%m-%d')}")

    doc.add_page_break()
    doc.add_heading("Executive Summary", level=1)
    doc.add_paragraph(executive_summary)

    os.makedirs(GENERATED_FOLDER, exist_ok=True)
    original_pdf_name = rfp_doc.filename
    base_name = os.path.splitext(original_pdf_name)[0]
    file_name = f"{base_name}_response.docx"
    file_path = os.path.join(GENERATED_FOLDER, file_name)
    doc.save(file_path)

    base_url = str(request.base_url).rstrip("/")
    download_url = f"{base_url}/download/{file_name}"

    return {
        "message": "RFP proposal generated successfully",
        "download_url": download_url
    }

@router.get("/list-rfp-docs/")
async def list_rfp_docs(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        if current_user.role.lower() != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized - only admins can access this endpoint"
            )

        if not os.path.exists(GENERATED_FOLDER):
            return JSONResponse(content={
                "message": "No documents found",
                "role": current_user.role,
                "docs": []
            })

        files = os.listdir(GENERATED_FOLDER)
        files = [f for f in files if f.endswith(".docx") or f.endswith(".pdf")]

        docs = []
        for f in files:
            docs.append({
                "file_name": f,
                "download_url": f"{request.base_url}download/{f}"
            })

        return {
            "message": f"{len(docs)} document(s) found",
            "role": current_user.role,
            "docs": docs
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "message": "An error occurred while listing documents",
                "error": str(e),
                "docs": []
            }
        )

@router.post("/upload-library")
def upload_library_new(
    files: List[UploadFile] = File(...),
    project_name: str = Form(...),
    category: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only admins can upload library documents."
        )

    try:
        uploaded_docs = upload_documents(files, project_name, category, current_user, db)
        return {
            "message": f"{len(uploaded_docs)} file(s) uploaded successfully",
            "documents": uploaded_docs
        }

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=409,
            detail="This RFP already exist."
        )

