from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.models.rfp_models import RFPDocument, RFPQuestion, Reviewer, User
from app.services.llm_services.llm_service import get_next_index
from app.schemas.schema import QuestionInput, AdminEditRequest

def filter_question_service(rfp_id: int, db: Session, current_user):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can FILTER."
            )

        rfp = (
            db.query(RFPDocument)
            .options(joinedload(RFPDocument.questions))
            .filter(RFPDocument.id == rfp_id)
            .first()
        )

        if not rfp:
            raise HTTPException(status_code=404, detail="RFP document not found")

        all_questions = rfp.questions
        assigned_questions = []
        unassigned_questions = []

        for question in all_questions:
            reviewers = db.query(Reviewer).filter(Reviewer.ques_id == question.id).all()
            if reviewers:
                assigned_questions.append({
                    "id": question.id,
                    "text": question.question_text,
                    "reviewers": [
                        {
                            "user_id": r.user_id,
                            "username": db.query(User)
                                .filter(User.id == r.user_id)
                                .first()
                                .username,
                            "status": r.status,
                            "submitted_at": r.submitted_at
                        }
                        for r in reviewers
                    ]
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

def admin_filter_questions_by_status_service(status_filter: str, db: Session, current_user):
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

        reviewers = db.query(Reviewer).join(User).all()
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

def add_ques(
    rfp_id: int,
    request: QuestionInput,
    db: Session,
    current_user: User
):
    try:
        if current_user.role.lower() != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can add questions"
            )

        rfp = db.query(RFPDocument).filter(RFPDocument.id == rfp_id).first()
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
            que_with_index = get_next_index(rfp_id, current_user.id, q, db)

            new_question = RFPQuestion(
                rfp_id=rfp_id,
                question_text=que_with_index,
                admin_id=current_user.id
            )
            db.add(new_question)
            db.flush()
            created_ids.append(new_question.id)

        db.commit()

        return {
            "message": "Questions added successfully",
            "question_ids": created_ids,
            "count": len(created_ids)
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )

def edit_question_by_admin_service(request: AdminEditRequest, db: Session):
    assignment = (
        db.query(RFPQuestion, Reviewer)
        .join(Reviewer, RFPQuestion.id == Reviewer.ques_id)
        .filter(RFPQuestion.id == request.question_id)
        .first()
    )

    if assignment is None:
        raise HTTPException(status_code=404, detail="Question not found.")

    question, reviewer = assignment
    reviewer.ans = request.answer
    db.commit()

    return {
        "message": "Answer updated successfully by admin.",
        "question_id": question.id,
        "updated_answer": reviewer.ans,
    }

def delete_question(question_id: int, db: Session, current_user):

    if current_user.role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can delete questions"
        )

    question = db.query(RFPQuestion).filter(
        RFPQuestion.id == question_id
    ).first()

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

    reviewer_exists = db.query(Reviewer).filter(
        Reviewer.ques_id == question_id
    ).first()

    if reviewer_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question has reviewer assignment and cannot be deleted"
        )

    db.delete(question)
    db.commit()

    return {
        "status": "success",
        "message": "Question deleted successfully",
        "question_id": question_id
    }