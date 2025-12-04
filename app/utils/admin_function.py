import hashlib
import os,re
import mimetypes
import shutil
from datetime import datetime
from fastapi import UploadFile, HTTPException, status
from fastapi.responses import FileResponse
from fastapi_mail import FastMail, MessageSchema, MessageType
from sqlalchemy.orm import Session, joinedload
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sqlalchemy import func
from app.config import mail_config,LOGIN_URL
from app.models.rfp_models import (
    User, Reviewer, RFPDocument, RFPQuestion,
    CompanySummary, ReviewerAnswerVersion
)
from app.services.llm_service import (
    extract_text_from_pdf, extract_company_background_from_rfp,
    extract_questions_with_llm, get_next_index, summarize_results_with_llm,
    generate_search_queries, search_with_serpapi, analyze_answer_score_only,
    client, parse_rfp_summary, get_embedding, extract_text_from_file,
    get_similar_context,generate_summary,delete_rfp_embeddings
)
from app.schemas.schema import (
    AssignReviewer, ReviewerOut, AdminEditRequest, UserOut,reviwerdelete, ReassignReviewerRequest,QuestionInput
)
from app.config import pc,index,UPLOAD_FOLDER
import traceback

async def process_rfp_file(file: UploadFile, project_name: str, db: Session, current_user):
    try:
        file_bytes = await file.read()
        file_hash = hashlib.md5(file_bytes).hexdigest()

        existing_rfp = db.query(RFPDocument).filter(RFPDocument.file_hash == file_hash).first()
        if existing_rfp:
            raise HTTPException(
                status_code=208,
                detail={
                    "status": "duplicate",
                    "message": "This RFP already exists.",
                    "existing_rfp_id": existing_rfp.id
                }
            )

        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        dummy_filename = f"rfp_{timestamp}.pdf"
        file_path = os.path.join(UPLOAD_FOLDER, dummy_filename)
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        rfp_text = extract_text_from_pdf(file_bytes)
        if not rfp_text.strip():
            return {"error": "PDF text is empty or not readable."}

        search_queries = generate_search_queries(rfp_text)
        questions_grouped = extract_questions_with_llm(rfp_text)
        company_rfp_text = extract_company_background_from_rfp(rfp_text)

        all_snippets = []
        for query in search_queries:
            results = search_with_serpapi(query)
            for item in results:
                if snippet := item.get("snippet"):
                    all_snippets.append(snippet)

        raw_summary = summarize_results_with_llm(all_snippets, rfp_company_text=company_rfp_text)
        structured_summary = parse_rfp_summary(raw_summary)

        new_rfp = RFPDocument(
            filename=file.filename,
            file_path=file_path,
            file_hash=file_hash,
            extracted_text=rfp_text,
            admin_id=current_user.id,
            category="history",
            project_name=project_name
        )
        db.add(new_rfp)
        db.commit()
        db.refresh(new_rfp)

        new_summary = CompanySummary(
            rfp_id=new_rfp.id,
            summary_text=raw_summary,
            admin_id=current_user.id
        )
        db.add(new_summary)

        for group_number, data in questions_grouped.items():
            section_name = data.get("section", f"Section {group_number}")
            for q in data.get("questions", []):
                db.add(RFPQuestion(
                    rfp_id=new_rfp.id,
                    question_text=q,
                    section=section_name,
                    admin_id=current_user.id
                ))

        db.commit()

        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        chunks = splitter.split_text(rfp_text)

        for i, chunk in enumerate(chunks):
            try:
                embedding_response = client.embeddings.create(
                    model="text-embedding-3-small",
                    input=chunk
                )
                embedding_vector = embedding_response.data[0].embedding
                index.upsert([
                    {
                        "id": str(uuid.uuid4()),
                        "values": embedding_vector,
                        "metadata": {
                            "file_id": str(new_rfp.id),
                            "chunk_index": i,
                            "text": chunk
                        }
                    }
                ])
            except Exception as embed_err:
                print(f"[Embedding Error] Chunk {i}: {embed_err}")

        return {
            "status": "new",
            "rfp_id": new_rfp.id,
            "saved_file": file_path,
            "category": new_rfp.category,
            "project_name": project_name,
            "summary": structured_summary,
            "total_questions": questions_grouped,
            "embedded_chunks": len(chunks)
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

def fetch_file_details(db: Session):
    try:
        documents = (
            db.query(RFPDocument)
            .filter(RFPDocument.category.isnot(None))
            .filter(func.trim(RFPDocument.category) != '')
            .all()
        )
        return documents
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )
    
def get_all_users(db: Session, current_user: User):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can access User details."
            )

        users = db.query(User).all()

        return [
            UserOut(
                user_id=user.id,
                username=user.username,
                email=user.email,
                role=user.role,
                is_verified=user.is_verified
            )
            for user in users
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_assigned_users(db: Session, current_user: User):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can access assigned user details."
            )
        assigned_user_ids = (
            db.query(RFPQuestion.assigned_user_id)
            .filter(RFPQuestion.assigned_user_id != None)  
            .distinct()
            .all()
        )

        user_ids = [uid[0] for uid in assigned_user_ids]

        if not user_ids:
            return {"message": "No users assigned to any question", "users": []}

        users = db.query(User).filter(User.id.in_(user_ids)).all()

        return [
            {
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "is_assigned": True
            }
            for user in users
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_user_by_id_service(user_id: int, db: Session):
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return {
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "image_url": f"uploads/{user.image}" if user.image else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
def assign_multiple_review(request: AssignReviewer, db: Session, current_user: User):
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

def check_submissions_service(db: Session, current_user: User):
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
    
def get_assign_user_status_service(db: Session, current_user: User):
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

# def delete_rfp_document_service(rfp_id: int, db: Session, current_user: User):
#     try:
#         if current_user.role != "admin":
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Only admins can delete docs."
#             )

#         rfp = db.query(RFPDocument).filter(RFPDocument.id == rfp_id).first()
#         if not rfp:
#             raise HTTPException(
#                 status_code=404,
#                 detail="RFP document not found."
#             )
#         if os.path.exists(rfp.file_path):
#             os.remove(rfp.file_path)
#             # print(f" Deleted file from disk: {rfp.file_path}")

#         delete_rfp_embeddings(rfp_id)

#         db.delete(rfp)
#         db.commit()

#         return {"message": "RFP document and all related embeddings deleted successfully."}

#     except HTTPException as http_exc:
#         raise http_exc
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to delete RFP document: {str(e)}"
#         ) 

def delete_rfp_document_service(rfp_id: int, db: Session, current_user: User):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can delete docs."
            )

        rfp = db.query(RFPDocument).filter(RFPDocument.id == rfp_id).first()
        if not rfp:
            raise HTTPException(
                status_code=404,
                detail="RFP document not found."
            )

        rfp.is_deleted = True
        rfp.deleted_at = datetime.utcnow()
        db.commit()

        return {
            "message": "RFP moved to trash. Work-in-progress is safely retained."
        }

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to move RFP to trash: {str(e)}"
        )

async def remove_user_service(ques_id: int, user_id: int, db: Session, current_user: User):
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

def filter_question_service(rfp_id: int, db: Session, current_user: User):
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
            # if needed you can uncomment:
            # "assigned_questions": assigned_questions,
            # "unassigned_questions": unassigned_questions
        }

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to filter questions: {str(e)}"
        )    

def admin_filter_questions_by_status_service(status: str, db: Session, current_user: User):
    try:
        if current_user.role.lower() != "admin":
            raise HTTPException(
                status_code=403,
                detail="Only admins can access this endpoint."
            )

        valid_statuses = ["submitted", "not submitted", "process"]
        status = status.strip().lower()

        if status not in valid_statuses:
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
            if current_status == status:
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
            "status_filter": status,
            "total_matched": len(filtered_questions),
            "questions": filtered_questions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def analyze_overall_score_service(rfp_id: int, db: Session):
    try:
        questions = db.query(RFPQuestion).filter(RFPQuestion.rfp_id == rfp_id).all()
        if not questions:
            raise HTTPException(status_code=404, detail="No questions found for this RFP.")

        incomplete_questions = []
        for question in questions:
            reviewers = db.query(Reviewer).filter(
                Reviewer.ques_id == question.id,
                Reviewer.ans.isnot(None),
                Reviewer.ans != ""
            ).all()
            if not reviewers:
                incomplete_questions.append({
                    "question_id": question.id,
                    "question": question.question_text
                })

        if incomplete_questions:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Some questions do not have any submitted answers yet.",
                    "incomplete_questions": incomplete_questions
                }
            )

        all_scores = []
        for question in questions:
            reviewers = db.query(Reviewer).filter(
                Reviewer.ques_id == question.id,
                Reviewer.ans.isnot(None),
                Reviewer.ans != ""
            ).all()

            for review in reviewers:
                score = analyze_answer_score_only(
                    question_text=question.question_text,
                    answer_text=review.ans
                )
                if score is not None:
                    all_scores.append(score)

        if not all_scores:
            raise HTTPException(status_code=400, detail="No valid answers to analyze.")

        overall_score = round(sum(all_scores) / len(all_scores), 2)

        return {
            "rfp_id": rfp_id,
            "total_questions": len(questions),
            "total_answers_analyzed": len(all_scores),
            "overall_score": overall_score
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def view_rfp_document_service(rfp_id: int, db: Session):
    try:
        rfp_doc = db.query(RFPDocument).filter(RFPDocument.id == rfp_id).first()
        if not rfp_doc:
            raise HTTPException(status_code=404, detail="RFP document not found")

        if not rfp_doc.file_path or not os.path.exists(rfp_doc.file_path):
            raise HTTPException(status_code=404, detail="File not found on server")

        media_type, _ = mimetypes.guess_type(rfp_doc.file_path)
        if not media_type:
            media_type = "application/octet-stream"

        return FileResponse(
            path=rfp_doc.file_path,
            filename=rfp_doc.filename,
            media_type=media_type
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

async def update_profile_service(
    db: Session, current_user: User, username: str, email: str, image: UploadFile = None
):
    try:
        user = db.query(User).filter(User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.username = username
        user.email = email

        if image:
            if not os.path.exists("uploads"):
                os.makedirs("uploads")

            file_name = f"{user.id}_{image.filename}"
            file_location = os.path.join("uploads", file_name)

            with open(file_location, "wb") as f:
                f.write(await image.read())

            user.image = file_name
            print(f"Image saved: {file_location}")

        db.commit()
        db.refresh(user)

        return {
            "message": "Profile updated successfully",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "image_url": f"uploads/{user.image}" if user.image else None,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
async def delete_reviewer_service(request: reviwerdelete, db: Session):
    user = db.query(User).filter(User.id == request.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    if user.role != request.role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User role mismatch. Expected '{request.role}', found '{user.role}'."
        )

    # Delete related reviewer answers
    db.query(ReviewerAnswerVersion).filter(
        ReviewerAnswerVersion.user_id == request.user_id
    ).delete(synchronize_session=False)

    db.query(Reviewer).filter(
        Reviewer.user_id == request.user_id
    ).delete(synchronize_session=False)

    # Finally delete the user
    db.delete(user)
    db.commit()

    return {
        "message": f"User (id={request.user_id}, role={user.role}) "
                   f"and all related reviewer data deleted successfully"
    }

async def regenerate_answer_with_chat_service(request, db: Session):
    user_id = request.user_id
    ques_id = request.ques_id
    chat_message = request.chat_message

    reviewer = db.query(Reviewer).filter_by(user_id=user_id, ques_id=ques_id).first()
    if not reviewer:
        raise HTTPException(status_code=404, detail="Reviewer not assigned to this question")

    question = db.query(RFPQuestion).filter_by(id=ques_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    base_answer = reviewer.ans or ""

    context = get_similar_context(question.question_text,question.rfp_id, top_k=5)

    system_prompt = (
        "You are a senior proposal writer. "
        "Your task is to refine and regenerate proposal answers based on the user’s feedback, "
        "while also grounding the response in the provided knowledge base context. "

        "Rewrite Mode (Highest Priority): "
        "If the reviewer feedback includes instructions such as 'rewrite', 'shorten', "
        "'summarize', 'reduce word count', 'make concise', or 'rephrase', you MUST follow "
        "those rewrite instructions exactly. Ignore persuasion, structure preservation, and "
        "other styling rules unless the user explicitly requests them. If shortening is "
        "requested, reduce the word count by the requested amount. Do not add content. "
        "Do not expand the text. Preserve the meaning only. "

        "Preserve the original structure and intent, but improve clarity, flow, and professionalism "
        "when the user is NOT asking for a rewrite or reduction. "
        "Incorporate all requested changes accurately and consistently. "
        "Ensure the writing style is formal, persuasive, and suitable for RFP submissions "
        "unless in rewrite mode. "
        "Do not include or repeat the original question text. "
        "Do not use markdown symbols, headings, or special formatting; produce plain text only. "
        "Avoid redundancy and ensure the final output reads as a polished, client-ready response. "
        "If relevant context is provided, always integrate it faithfully into the final answer."
    )

    user_prompt = f"""
    Question: {question.question_text}
    Previous Answer: {base_answer}
    Reviewer Feedback: {chat_message}
    Relevant Context (from KB): {context}

    Please regenerate a refined answer using the context above.
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
        "message": "Answer generated and stored in versions",
        "new_answer_version": {
            "id": new_version.id,
            "ques_id": ques_id,
            "user_id": user_id,
            "answer": refined_answer,
            "generated_at": new_version.generated_at,
        }
    }

async def reassign_reviewer_service(request: ReassignReviewerRequest, db: Session, current_user: User):
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

def upload_documents(files, project_name, category, current_user, db: Session):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    uploaded_docs = []

    for file in files:
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in [".pdf", ".docx", ".pptx",".xlsx",".xls"]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format: {file.filename}"
            )

        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        saved_filename = f"{timestamp}_{file.filename}"
        file_path = os.path.join(UPLOAD_FOLDER, saved_filename)

        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        with open(file_path, "rb") as f:
            file_bytes = f.read()
            file_hash = hashlib.sha256(file_bytes).hexdigest()

        new_doc = RFPDocument(
            filename=file.filename,
            file_path=file_path,
            category=category,
            project_name=project_name,
            admin_id=current_user.id,
            uploaded_at=datetime.utcnow(),
            file_hash=file_hash
        )
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)

        text = extract_text_from_file(file_path)
        if not text:
            continue

        summary = generate_summary(text)
        summary_vector = get_embedding(summary)
        index.upsert(
            vectors=[(
                f"summary_{new_doc.id}",
                summary_vector,
                {
                    "document_id": str(new_doc.id),
                    "filename": new_doc.filename,
                    "category": new_doc.category,
                    "project_name": new_doc.project_name,
                    "type": "summary",
                    "text": summary
                }
            )],
            namespace="summaries"
        )

        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = splitter.split_text(text)
        vectors = []
        for i, chunk in enumerate(chunks):
            vector = get_embedding(chunk)
            vectors.append((
                f"{new_doc.id}_{i}",
                vector,
                {
                    "document_id": str(new_doc.id),
                    "filename": new_doc.filename,
                    "category": new_doc.category,
                    "project_name": new_doc.project_name,
                    "type": "chunk",
                    "chunk_id": i,
                    "text": chunk
                }
            ))

        if vectors:
            index.upsert(vectors=vectors, namespace=f"rfp_{new_doc.id}")

        uploaded_docs.append({
            "document_id": new_doc.id,
            "filename": new_doc.filename,
            "category": new_doc.category,
            "project_name": new_doc.project_name
        })

    return uploaded_docs

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

def restore_rfp_doc(rfp_id: int, db: Session, current_user: User):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can restore docs."
            )

        rfp = (
            db.query(RFPDocument)
            .filter(RFPDocument.id == rfp_id, RFPDocument.is_deleted == True)
            .first()
        )

        if not rfp:
            raise HTTPException(
                status_code=404,
                detail="RFP not found in Trash."
            )

        rfp.is_deleted = False
        rfp.deleted_at = None
        db.commit()

        return {"message": "RFP restored successfully."}

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restore RFP document: {str(e)}"
        )
    
def permanent_delete_rfp(rfp_id: int, db: Session, current_user: User):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can permanently delete docs."
            )

        rfp = (
            db.query(RFPDocument)
            .filter(RFPDocument.id == rfp_id, RFPDocument.is_deleted == True)
            .first()
        )

        if not rfp:
            raise HTTPException(
                status_code=404,
                detail="RFP not found in Trash."
            )

        if rfp.file_path and os.path.exists(rfp.file_path):
            os.remove(rfp.file_path)

        delete_rfp_embeddings(rfp_id)

        db.delete(rfp)
        db.commit()

        return {"message": "RFP permanently deleted."}

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to permanently delete RFP document: {str(e)}"
        )

def get_trash_documents(db: Session, current_user: User):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=401,
                detail="Only admins can view Trash."
            )

        deleted_docs = (
            db.query(RFPDocument)
            .filter(RFPDocument.is_deleted == True)
            .order_by(RFPDocument.deleted_at.desc())
            .all()
        )

        return [
            {
                "id": doc.id,
                "filename": doc.filename,
                "project_name": doc.project_name,
                "category": doc.category,
                "uploaded_at": doc.uploaded_at,
                "deleted_at": doc.deleted_at,
                "days_left": (
                    7 - (datetime.utcnow() - doc.deleted_at).days
                    if doc.deleted_at else None
                )
            }
            for doc in deleted_docs
        ]

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch trash list: {str(e)}"
        )

