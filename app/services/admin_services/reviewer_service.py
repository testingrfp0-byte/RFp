import re
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from fastapi_mail import FastMail, MessageSchema, MessageType
from app.models.rfp_models import User, Reviewer, RFPQuestion, ReviewerAnswerVersion
from app.services.llm_services.llm_service import get_similar_context, client,get_active_keystone_text
from app.schemas.schema import AssignReviewer, ReviewerOut, ReassignReviewerRequest
from app.config import mail_config, LOGIN_URL

def assign_multiple_review(request: AssignReviewer, db: Session, current_user):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can assign reviewers."
            )

        assigned_questions = []

        for uid in request.user_id:
            user = db.query(User).filter(User.id == uid).first()
            if not user:
                continue
            if not user.is_verified:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"User {user.email} has not completed email verification and cannot be assigned."
                )

            for ques_id in request.ques_ids:
                question = db.query(RFPQuestion).filter(
                    RFPQuestion.id == ques_id,
                    RFPQuestion.rfp_id == request.file_id
                ).first()
                if not question:
                    continue

                existing = db.query(Reviewer).filter_by(
                    user_id=uid,
                    ques_id=ques_id
                ).first()
                if existing:
                    continue

                reviewer_entry = Reviewer(
                    user_id=uid,
                    ques_id=ques_id,
                    question=question.question_text,
                    status=request.status,
                    file_id=request.file_id,
                    admin_id=current_user.id,
                    submit_status="process"
                )

                db.add(reviewer_entry)
                question.assigned_at = datetime.utcnow()

                assigned_questions.append({
                    "user_id": uid,
                    "question_id": ques_id,
                    "submit_status": "process"
                })

        db.commit()

        return {
            "message": "Reviewer(s) assigned to multiple questions successfully",
            "assigned_questions": assigned_questions
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_reviewers_by_file_service(file_id: int, db: Session):
    try:
        results = (
            db.query(Reviewer)
            .join(RFPQuestion, Reviewer.ques_id == RFPQuestion.id)
            .join(User, Reviewer.user_id == User.id)
            .filter(RFPQuestion.rfp_id == file_id)
            .all()
        )

        output = [
            ReviewerOut(
                ques_id=r.ques_id,
                question=r.question,
                user_id=r.user_id,
                username=r.user.username,
                status=r.status
            )
            for r in results
        ]

        return output

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def check_submissions_service(db: Session, current_user):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Only admins can view submissions."
            )

        reviewers = db.query(Reviewer).all()
        data = []

        for i in reviewers:
            if i.status is None:
                continue

            file_name = (
                i.question_ref.rfp.filename
                if i.question_ref and i.question_ref.rfp
                else "Unknown"
            )

            data.append({
                "user_id": i.user_id,
                "username": i.user.username,
                "question_id": i.ques_id,
                "question": i.question,
                "answer": i.ans,
                "status": i.submit_status,
                "submitted_at": i.submitted_at,
                "file_id": i.file_id,
                "filename": file_name
            })

        return {
            "message": "Status fetched successfully",
            "data": data
        }

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_assign_user_status_service(db: Session, current_user):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can access check user status"
            )

        reviewers = db.query(Reviewer).all()
        if not reviewers:
            return {
                "message": "No reviewers found",
                "data": []
            }

        data = []
        for reviewer in reviewers:
            file_name = (
                reviewer.question_ref.rfp.filename
                if reviewer.question_ref and reviewer.question_ref.rfp
                else "Unknown"
            )

            data.append({
                "username": reviewer.user.username,
                "question_id": reviewer.ques_id,
                "question": reviewer.question,
                "filename": file_name,
                "answer": reviewer.ans,
                "status": reviewer.submit_status,
                "submitted_at": reviewer.submitted_at
            })

        return {
            "message": "Assign details fetched successfully",
            "data": data
        }

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def remove_user_service(ques_id: int, user_id: int, db: Session, current_user):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can remove the user."
            )

        assign = (
            db.query(Reviewer)
            .filter(Reviewer.ques_id == ques_id, Reviewer.user_id == user_id)
            .first()
        )
        if not assign:
            raise HTTPException(
                status_code=404,
                detail="Reviewer assignment not found."
            )
        user = db.query(User).filter(User.id == user_id).first()
        question = db.query(RFPQuestion).filter(RFPQuestion.id == ques_id).first()

        ans = (
            db.query(ReviewerAnswerVersion)
            .filter(
                ReviewerAnswerVersion.ques_id == ques_id,
                ReviewerAnswerVersion.user_id == user_id
            )
            .first()
        )
        if ans:
            db.delete(ans)

        db.delete(assign)
        db.commit()

        if user and user.email and question:
            fm = FastMail(mail_config)
            message = MessageSchema(
                subject="RFP Question Unassignment Notification",
                recipients=[user.email],
                body=f"""
                    Hello {user.username},

                    You have been unassigned from the following RFP question:

                    Question ID: {question.id}
                    Section: {question.section or 'N/A'}
                    Question: {question.question_text}

                    If you believe this was done in error, please contact the administrator.

                    Best regards,  
                    RFP Automation System
                """,
                subtype=MessageType.plain
            )
            await fm.send_message(message)

        return {"message": "Reviewer user removed and notified successfully."}

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to remove reviewer: {str(e)}"
        )

async def reassign_reviewer_service(request: ReassignReviewerRequest, db: Session, current_user):
    user = db.query(User).filter(User.id == request.user_id).first()
    if not user or not user.email:
        raise HTTPException(status_code=404, detail="User not found or email missing")

    question = db.query(RFPQuestion).filter(
        RFPQuestion.id == request.ques_id,
        RFPQuestion.rfp_id == request.file_id
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    existing = db.query(Reviewer).filter_by(
        user_id=request.user_id,
        ques_id=request.ques_id
    ).first()

    if existing:
        existing.submit_status = "process"
        existing.time = datetime.utcnow()
        existing.question = question.question_text
    else:
        reviewer_entry = Reviewer(
            user_id=request.user_id,
            ques_id=request.ques_id,
            question=question.question_text,
            file_id=request.file_id,
            admin_id=current_user.id,
            submit_status="process"
        )
        db.add(reviewer_entry)
        existing = reviewer_entry

    question.assigned_at = datetime.utcnow()
    db.commit()

    fm = FastMail(mail_config)
    message = MessageSchema(
        subject="RFP Question Reassignment Notification",
        recipients=[user.email],
        body=f"""
            Hello {user.username},

            You have been reassigned to the following RFP question:

            Question ID: {question.id}
            Section: {question.section or 'N/A'}
            Question: {question.question_text}

            Please log in to the system to review and provide your response.
            <p>Please click the button below to log in and Rereview:</p>
            <a href="{LOGIN_URL}" 
               style="display:inline-block; padding:10px 20px; font-size:16px; 
                      color:#fff; background-color:#007BFF; text-decoration:none; 
                      border-radius:5px;">
                Log In
            </a>
            <p>Best regards,<br>RFP Automation System</p>
        """,
        subtype=MessageType.html
    )
    await fm.send_message(message)

    existing.status = "notified"
    db.commit()

    return {
        "message": "Reviewer reassigned successfully and notified via email",
        "user_id": request.user_id,
        "question_id": request.ques_id,
        "status": existing.status,
        "submit_status": existing.submit_status
    }

async def regenerate_answer_with_chat_service(request, db: Session):
    user_id = request.user_id
    ques_id = request.ques_id
    chat_message = request.chat_message

    reviewer = db.query(Reviewer).filter_by(
        user_id=user_id,
        ques_id=ques_id
    ).first()

    if not reviewer:
        raise HTTPException(
            status_code=404,
            detail="Reviewer not assigned to this question"
        )

    question = db.query(RFPQuestion).filter_by(id=ques_id).first()
    if not question:
        raise HTTPException(
            status_code=404,
            detail="Question not found"
        )

    base_answer = reviewer.ans or ""

    keystone_text = get_active_keystone_text(
        db=db,
        admin_id=question.admin_id
    )

    rfp_context = get_similar_context(
        question.question_text,
        question.rfp_id,
        top_k=5
    )

    system_prompt = (
        "You are a senior proposal writer refining an RFP response.\n\n"

        "### KEYSTONE DATA (PRIMARY SOURCE — DO NOT VIOLATE):\n"
        f"{keystone_text}\n\n"

        "### NON-NEGOTIABLE RULES:\n"
        "- Keystone Data is the single source of truth for company facts\n"
        "- Do NOT modify, remove, or invent company details\n"
        "- Do NOT add new services, certifications, locations, or metrics\n"
        "- If reviewer feedback conflicts with Keystone Data, Keystone wins\n\n"

        "### Rewrite Mode (Highest Priority):\n"
        "- If feedback includes rewrite / shorten / summarize / rephrase,\n"
        "  follow those instructions exactly\n"
        "- Do NOT add new content when shortening\n"
        "- Preserve meaning only\n\n"

        "### General Rules:\n"
        "- Improve clarity and flow when not in rewrite mode\n"
        "- Produce plain text only (no markdown)\n"
        "- Do NOT repeat the question text\n"
        "- Output must be client-ready and professional\n"
    )

    user_prompt = f"""
Question:
{question.question_text}

Existing Answer:
{base_answer}

Reviewer Feedback:
{chat_message}

RFP Context:
{rfp_context}

Regenerate the answer while strictly respecting Keystone Data.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
    )

    refined_answer = response.choices[0].message.content.strip()
    refined_answer = re.sub(r"(\*\*|##+)", "", refined_answer)

    new_version = ReviewerAnswerVersion(
        user_id=user_id,
        ques_id=ques_id,
        answer=refined_answer,
        generated_at=datetime.utcnow()
    )
    db.add(new_version)

    reviewer.ans = refined_answer
    db.commit()
    db.refresh(new_version)

    return {
        "status": "success",
        "message": "Answer regenerated using Keystone Data",
        "new_answer_version": {
            "id": new_version.id,
            "ques_id": ques_id,
            "user_id": user_id,
            "answer": refined_answer,
            "generated_at": new_version.generated_at,
        }
    }