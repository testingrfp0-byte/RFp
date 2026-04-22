from typing import List
from fastapi import (
    UploadFile, File, Form, Depends, HTTPException, APIRouter, status)
from collections import defaultdict
from app.db.database import get_db
from app.schemas.schema import (
    FileDetails, RFPDocumentGroupedQuestionsOut, 
    GroupedRFPQuestionOut, QuestionOut, QuestionInput)
from app.models.rfp_models import User, RFPDocument, RFPQuestion, Reviewer
from app.api.routes.utils import get_current_user
from app.services.admin_services import (
    process_rfp_file, fetch_file_details,
    filter_question_service, delete_rfp_document_service,
    view_rfp_document_service, add_ques, restore_rfp_doc,
    permanent_delete_rfp, get_trash_documents, delete_question)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from starlette import status as http_status
router = APIRouter()

@router.post("/search-related-summary/")
async def search_related_summary(
    file: UploadFile = File(...),
    project_name: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider: str = Form(...),
    custom_message: str = Form(None)
):
    # print(f"Received file: {file.filename}, project_name: {project_name}, provider: {provider}")
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only admins can access summary docs."
        )
    
    return await process_rfp_file(file, project_name, db, current_user, provider,custom_message)

@router.get("/filedetails", response_model=List[FileDetails])
async def get_file_details(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only admins can access File details."
        )

    return await fetch_file_details(db)


@router.get("/rfpdetails/{document_id}/{rfp_status}", response_model=RFPDocumentGroupedQuestionsOut)
async def get_rfp_details(
    document_id: int,
    rfp_status: str,          # ✅ renamed from 'status' to avoid conflict
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Only admins can access RFP details."
        )

    valid_statuses = ["assigned", "unassigned", "total question"]
    if rfp_status not in valid_statuses:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Allowed values: {valid_statuses}"
        )

    document_result = await db.execute(
        select(RFPDocument)
        .options(selectinload(RFPDocument.summary))
        .filter(RFPDocument.id == document_id)
    )
    document = document_result.scalars().first()

    if not document:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="RFP Document not found or access denied."
        )

    # ✅ extract all values while session is still active
    doc_id = document.id
    doc_filename = document.filename
    doc_uploaded_at = document.uploaded_at
    doc_summary = document.summary

    questions_result = await db.execute(
        select(RFPQuestion)
        .filter(RFPQuestion.rfp_id == document_id)
        .order_by(RFPQuestion.id.asc())
    )
    questions = questions_result.scalars().all()

    grouped = defaultdict(list)

    for q in questions:
        reviewers_result = await db.execute(
            select(Reviewer).filter(Reviewer.ques_id == q.id)
        )
        reviewers = reviewers_result.scalars().all()

        if rfp_status == "assigned" and not reviewers:
            continue
        elif rfp_status == "unassigned" and reviewers:
            continue

        grouped[q.section].append({
            "id": q.id,
            "question_text": q.question_text
        })

    grouped_questions = [
        GroupedRFPQuestionOut(
            section=section,
            questions=[QuestionOut(**q) for q in qs]  # ✅ fixed variable name (was shadowing `questions`)
        )
        for section, qs in grouped.items()
    ]

    return {
        "id": doc_id,
        "filename": doc_filename,
        "uploaded_at": doc_uploaded_at,
        "summary": doc_summary,          # ✅ already extracted above
        "questions_by_section": grouped_questions
    }

@router.get("/rfp-documents/{rfp_id}/view")
async def view_rfp_document(
    rfp_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only admins can view documents."
        )

    return await view_rfp_document_service(rfp_id, db)

@router.delete("/rfp/{rfp_id}")
async def delete_rfp_document(
    rfp_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await delete_rfp_document_service(rfp_id, db, current_user)

@router.get("/filter/{rfp_id}")
async def filter_question(
    rfp_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await filter_question_service(rfp_id, db, current_user)

@router.post("/add/questions/{rfp_id}")
async def add_questions(
    rfp_id: int,
    request: QuestionInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await add_ques(rfp_id, request, db, current_user)

@router.post("/rfp/{rfp_id}/restore")
async def restore_rfp_document(
    rfp_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await restore_rfp_doc(rfp_id, db, current_user)

@router.delete("/rfp/{rfp_id}/permanent")
async def permanent_delete_doc(
    rfp_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await permanent_delete_rfp(rfp_id, db, current_user)

@router.get("/rfp/trash")
async def get_trash_doc(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await get_trash_documents(db, current_user)

@router.delete("/delete/questions/{question_id}")
async def delete_ques_workin_progress(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await delete_question(question_id, db, current_user)
