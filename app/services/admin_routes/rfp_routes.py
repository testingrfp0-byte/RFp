from typing import List
from fastapi import (
    UploadFile, File, Form, Depends, HTTPException, APIRouter, status)
from sqlalchemy.orm import Session
from collections import defaultdict
from app.db.database import get_db
from app.schemas.schema import (
    FileDetails, RFPDocumentGroupedQuestionsOut, 
    GroupedRFPQuestionOut, QuestionOut, QuestionInput)
from app.models.rfp_models import User, RFPDocument, Reviewer
from app.api.routes.utils import get_current_user
from app.utils.admin_function import (
    process_rfp_file, fetch_file_details,
    filter_question_service, delete_rfp_document_service,
    view_rfp_document_service, add_ques, restore_rfp_doc,
    permanent_delete_rfp, get_trash_documents, delete_question)

router = APIRouter()

@router.post("/search-related-summary/")
async def search_related_summary(
    file: UploadFile = File(...),
    project_name: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only admins can access summary docs."
        )
    
    return await process_rfp_file(file, project_name, db, current_user)

@router.get("/filedetails", response_model=List[FileDetails])
def get_file_details(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only admins can access File details."
        )

    return fetch_file_details(db)

@router.get("/rfpdetails/{document_id}/{status}", response_model=RFPDocumentGroupedQuestionsOut)
def get_rfp_details(
    document_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only admins can access RFP details."
        )

    valid_statuses = ["assigned", "unassigned", "total question"]
    if status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Allowed values: {valid_statuses}"
        )

    document = (
        db.query(RFPDocument)
        .filter(RFPDocument.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RFP Document not found or access denied."
        )

    grouped = defaultdict(list)

    for q in sorted(document.questions, key=lambda x: x.id):
        reviewers = db.query(Reviewer).filter(Reviewer.ques_id == q.id).all()

        if status == "assigned" and not reviewers:
            continue
        elif status == "unassigned" and reviewers:
            continue
        elif status == "total-question":
            pass

        grouped[q.section].append({
            "id": q.id,
            "question_text": q.question_text
        })

    grouped_questions = [
        GroupedRFPQuestionOut(
            section=section,
            questions=[QuestionOut(**q) for q in questions]
        )
        for section, questions in grouped.items()
    ]

    return {
        "id": document.id,
        "filename": document.filename,
        "uploaded_at": document.uploaded_at,
        "summary": document.summary,
        "questions_by_section": grouped_questions
    }

@router.get("/rfp-documents/{rfp_id}/view")
def view_rfp_document(
    rfp_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only admins can view documents."
        )

    return view_rfp_document_service(rfp_id, db)

@router.delete("/rfp/{rfp_id}")
def delete_rfp_document(
    rfp_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return delete_rfp_document_service(rfp_id, db, current_user)

@router.get("/filter/{rfp_id}")
def filter_question(
    rfp_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return filter_question_service(rfp_id, db, current_user)

@router.post("/add/questions/{rfp_id}")
def add_questions(
    rfp_id: int,
    request: QuestionInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return add_ques(rfp_id, request, db, current_user)

@router.post("/rfp/{rfp_id}/restore")
def restore_rfp_document(
    rfp_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return restore_rfp_doc(rfp_id, db, current_user)

@router.delete("/rfp/{rfp_id}/permanent")
def permanent_delete_doc(
    rfp_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return permanent_delete_rfp(rfp_id, db, current_user)

@router.get("/rfp/trash")
def get_trash_doc(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_trash_documents(db, current_user)

@router.delete("/delete/questions/{question_id}")
def delete_ques_workin_progress(
    question_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    return delete_question(question_id,db,current_user)