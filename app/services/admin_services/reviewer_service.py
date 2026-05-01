import re
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from fastapi_mail import FastMail, MessageSchema, MessageType
from app.models.rfp_models import KeystoneFile, User, Reviewer, RFPQuestion, ReviewerAnswerVersion
from app.services.llm_services.llm_service import (
    _sanitize_short_name,
    get_short_name,
    get_similar_context,
    _complete_with_fallback,
)
from app.schemas.schema import AssignReviewer, ReviewerOut, ReassignReviewerRequest
from app.config import mail_config,  LOGIN_URL
from sqlalchemy.orm import selectinload
from app.core.prompts import regenerate_answer_prompt

async def assign_multiple_review(request: AssignReviewer, db: AsyncSession, current_user: User):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can assign reviewers."
            )

        assigned_questions = []
        for uid in request.user_id:
            user = await db.execute(select(User).filter(User.id == uid))
            user = user.scalar()
            if not user:
                continue
            if not user.is_verified:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"User {user.email} has not completed email verification and cannot be assigned."
                )

            for ques_id in request.ques_ids:
                question = await db.execute(select(RFPQuestion).filter(
                    RFPQuestion.id == ques_id,
                    RFPQuestion.rfp_id == request.file_id
                ))
                question = question.scalar()
                if not question:
                    continue

                existing = await db.execute(select(Reviewer).filter_by(
                    user_id=uid,
                    ques_id=ques_id
                ))
                existing = existing.scalar()
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

        await db.commit()

        return {
            "message": "Reviewer(s) assigned to multiple questions successfully",
            "assigned_questions": assigned_questions
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def get_reviewers_by_file_service(file_id: int, db: AsyncSession):
    try:
        results = await db.execute(
            select(Reviewer)
            .join(RFPQuestion, Reviewer.ques_id == RFPQuestion.id)
            .join(User, Reviewer.user_id == User.id)
            .options(
                selectinload(Reviewer.user)  
            )
            .filter(RFPQuestion.rfp_id == file_id)
        )
        results = results.scalars().all()

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

async def check_submissions_service(db: AsyncSession, current_user: User):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Only admins can view submissions."
            )

        reviewers = await db.execute(
            select(Reviewer)
            .options(
                selectinload(Reviewer.user),                             
                selectinload(Reviewer.question_ref).selectinload(RFPQuestion.rfp) 
            )
        )
        reviewers = reviewers.scalars().all()
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
       
async def get_assign_user_status_service(db: AsyncSession, current_user: User):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can access check user status"
            )

        # reviewers = await db.execute(select(Reviewer))
        reviewers = await db.execute(
            select(Reviewer).options(
                selectinload(Reviewer.user),
                selectinload(Reviewer.question_ref)
                .selectinload(RFPQuestion.rfp)
            )
        )

        reviewers = reviewers.scalars().all()
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

async def remove_user_service(ques_id: int, user_id: int, db: AsyncSession, current_user):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can remove the user."
            )

        assign_result = await db.execute(
            select(Reviewer).filter(Reviewer.ques_id == ques_id, Reviewer.user_id == user_id)
        )
        assign = assign_result.scalars().first()
        if not assign:
            raise HTTPException(
                status_code=404,
                detail="Reviewer assignment not found."
            )
        user = await db.execute(select(User).filter(User.id == user_id))
        user = user.scalar()
        question = await db.execute(select(RFPQuestion).filter(RFPQuestion.id == ques_id))
        question = question.scalar()

        ans_result = await db.execute(
            select(ReviewerAnswerVersion).filter(
                ReviewerAnswerVersion.ques_id == ques_id,
                ReviewerAnswerVersion.user_id == user_id
            )
        )
        ans = ans_result.scalars().first()
        if ans:
            await db.delete(ans)

        await db.delete(assign)
        await db.commit()

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
            try:
                await fm.send_message(message)
            except Exception as e:
                print("Email failed:", e)

        return {"message": "Reviewer user removed and notified successfully."}

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to remove reviewer: {str(e)}"
        )

async def reassign_reviewer_service(request: ReassignReviewerRequest, db: AsyncSession, current_user):
    user_result = await db.execute(select(User).filter(User.id == request.user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.email:
        raise HTTPException(status_code=404, detail="User not found or email missing")

    question = await db.execute(
        select(RFPQuestion).filter(
            RFPQuestion.id == request.ques_id,
            RFPQuestion.rfp_id == request.file_id
        )
    )
    question = question.scalar()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    existing = await db.execute(
        select(Reviewer).filter_by(
            user_id=request.user_id,
            ques_id=request.ques_id
        )
    )
    existing = existing.scalar()

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
    await db.commit()

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
    try:
        await fm.send_message(message)
    except Exception as e:
        print("Email failed:", e)

    existing.status = "notified"
    await db.commit()

    return {
        "message": "Reviewer reassigned successfully and notified via email",
        "user_id": request.user_id,
        "question_id": request.ques_id,
        "status": existing.status,
        "submit_status": existing.submit_status
    }

async def regenerate_answer_with_chat_service(request, db: AsyncSession):
    user_id = request.user_id
    ques_id = request.ques_id
    chat_message = request.chat_message
    provider = request.provider

    # Fetch reviewer
    reviewer_result = await db.execute(
        select(Reviewer).where(
            Reviewer.user_id == user_id,
            Reviewer.ques_id == ques_id
        )
    )
    reviewer = reviewer_result.scalar_one_or_none()

    if not reviewer:
        raise HTTPException(
            status_code=404,
            detail="Reviewer not assigned to this question"
        )

    # Fetch question
    question_result = await db.execute(
        select(RFPQuestion).where(RFPQuestion.id == ques_id)
    )
    question = question_result.scalar_one_or_none()
    if not question:
        raise HTTPException(
            status_code=404,
            detail="Question not found"
        )

    base_answer = reviewer.ans or ""

    rfp_result = await db.execute(
        select(KeystoneFile).where(KeystoneFile.id == question.rfp_id)
    )
    rfp_record = rfp_result.scalar_one_or_none()

    raw_filename = rfp_record.filename if rfp_record and rfp_record.filename else ""
    short_name = _sanitize_short_name(get_short_name(raw_filename)) if raw_filename else "the City"

    # Fetch Keystone data
    keystone_result = await db.execute(
        select(KeystoneFile)
        .where(KeystoneFile.admin_id == question.admin_id)
        .order_by(KeystoneFile.uploaded_at.desc())
    )
    keystone = keystone_result.scalars().first()
    if not keystone:
        raise HTTPException(
            status_code=400,
            detail="Keystone Data not uploaded. Please upload Keystone XLS."
        )
    keystone_text = keystone.extracted_text

     # Fetch RFP context 
    rfp_context, _ = await get_similar_context(
        question.question_text,
        question.rfp_id,
        top_k=5
    )

    chat_lower = chat_message.lower()

    system_prompt, user_prompt = regenerate_answer_prompt(
        chat_lower=chat_lower,
        chat_message=chat_message,
        short_name=short_name,
        keystone_text=keystone_text,
        question=question.question_text,
        base_answer=base_answer,
        rfp_context=rfp_context
    )    

    refined_answer = await _complete_with_fallback(
        provider=provider or "gpt-4o-mini",
        prompt=user_prompt,
        system_prompt=system_prompt,
        fallback_providers=["gpt-5.4", "claude-sonnet-4-6"],
    )
    refined_answer = refined_answer.strip()
    refined_answer = re.sub(r"(\*\*|##+|\*)", "", refined_answer)

    new_version = ReviewerAnswerVersion(
        user_id=user_id,
        ques_id=ques_id,
        answer=refined_answer,
        generated_at=datetime.utcnow()
    )
    db.add(new_version)

    reviewer.ans = refined_answer
    await db.commit()
    await db.refresh(new_version)

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
