from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, joinedload, selectinload
from app.models.rfp_models import RFPDocument, RFPQuestion, Reviewer, User
from app.services.llm_services.llm_service import get_next_index
from app.schemas.schema import QuestionInput, AdminEditRequest

async def filter_question_service(rfp_id: int, db: AsyncSession, current_user):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can FILTER."
            )

        rfp_result = await db.execute(
            select(RFPDocument)
            .options(joinedload(RFPDocument.questions))
            .filter(RFPDocument.id == rfp_id)
        )
        rfp = rfp_result.scalars().first() 

        if not rfp:
            raise HTTPException(status_code=404, detail="RFP document not found")

        all_questions = rfp.questions
        assigned_questions = []
        unassigned_questions = []

        for question in all_questions:
            reviewers_result = await db.execute(
                select(Reviewer).filter(Reviewer.ques_id == question.id)
            )
            reviewers = reviewers_result.scalars().all()

            if reviewers:

                reviewer_list = []
                for r in reviewers:
                    user_result = await db.execute(
                        select(User).filter(User.id == r.user_id)
                    )
                    user = user_result.scalars().first()
                    reviewer_list.append({
                        "user_id": r.user_id,
                        "username": user.username if user else None, 
                        "status": r.status,
                        "submitted_at": r.submitted_at
                    })

                assigned_questions.append({
                    "id": question.id,
                    "text": question.question_text,
                    "reviewers": reviewer_list
                })
            else:
                unassigned_questions.append({
                    "id": question.id,
                    "text": question.question_text
                })

        return {
            "rfp_id": rfp.id,
            "pdf_filename": rfp.filename,
            "project_name": rfp.project_name,
            "total_questions": len(all_questions),
            "assigned_count": len(assigned_questions),
            "unassigned_count": len(unassigned_questions),
        }

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to filter questions: {str(e)}"
        )

async def admin_filter_questions_by_status_service(status_filter: str, db: AsyncSession, current_user):
    try:
        if current_user.role.lower() != "admin":
            raise HTTPException(
                status_code=403,
                detail="Only admins can access this endpoint."
            )

        valid_statuses = ["submitted", "not submitted", "process"]
        status_filter = status_filter.strip().lower()

        if status_filter not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail="Invalid status. Must be one of: submitted, not submitted, process."
            )

        reviewers_result = await db.execute(
            select(Reviewer).options(selectinload(Reviewer.user)).join(User)
        )
        reviewers = reviewers_result.scalars().all()
        if not reviewers:
            raise HTTPException(
                status_code=404,
                detail="No reviewer data found for this admin."
            )

        filtered_questions = []
        for r in reviewers:
            current_status = r.submit_status.strip().lower() if r.submit_status else "not submitted"
            if current_status == status_filter:
                filtered_questions.append({
                    "question_id": r.ques_id,
                    "question": r.question,
                    "submit_status": r.submit_status,
                    "submitted_at": r.submitted_at,
                    "user_id": r.user_id,
                    "username": r.user.username if r.user else None,
                    "rfp_id": r.file_id
                })

        return {
            "admin_id": current_user.id,
            "status_filter": status_filter,
            "total_matched": len(filtered_questions),
            "questions": filtered_questions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def add_ques(
    rfp_id: int,
    request: QuestionInput,
    db: AsyncSession,
    current_user: User
):
    try:
        if current_user.role.lower() != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can add questions"
            )

        rfp = await db.execute(select(RFPDocument).filter(RFPDocument.id == rfp_id))
        rfp = rfp.scalar()
        if not rfp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="RFP not found"
            )

        if not request.questions or len(request.questions) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please provide at least one question"
            )

        created_ids = []

        for q in request.questions:
            que_with_index = await get_next_index(rfp_id, current_user.id, q, db)

            new_question = RFPQuestion(
                rfp_id=rfp_id,
                question_text=que_with_index,
                admin_id=current_user.id
            )
            db.add(new_question)
            await db.flush()
            created_ids.append(new_question.id)

        await db.commit()

        return {
            "message": "Questions added successfully",
            "question_ids": created_ids,
            "count": len(created_ids)
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )

async def edit_question_by_admin_service(request: AdminEditRequest, db: AsyncSession):
    assignment_result = await db.execute(
        select(RFPQuestion, Reviewer)
        .join(Reviewer, RFPQuestion.id == Reviewer.ques_id)
        .where(RFPQuestion.id == request.question_id)
    )
    assignment = assignment_result.first()

    if assignment is None:
        raise HTTPException(status_code=404, detail="Question not found.")

    question, reviewer = assignment
    reviewer.ans = request.answer
    await db.commit()

    return {
        "message": "Answer updated successfully by admin.",
        "question_id": question.id,
        "updated_answer": reviewer.ans,
    }

async def delete_question(question_id: int, db: AsyncSession, current_user):

    if current_user.role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can delete questions"
        )

    question = await db.execute(
        select(RFPQuestion).filter(RFPQuestion.id == question_id)
    )
    question = question.scalar()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    if question.assigned_user_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question is already assigned to a reviewer and cannot be deleted"
        )

    reviewer_exists = await db.execute(
        select(Reviewer).filter(Reviewer.ques_id == question_id)
    )
    reviewer_exists = reviewer_exists.scalar()

    if reviewer_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question has reviewer assignment and cannot be deleted"
        )

    await db.delete(question)
    await db.commit()

    return {
        "status": "success",
        "message": "Question deleted successfully",
        "question_id": question_id
    }
