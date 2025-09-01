from fastapi import UploadFile,File,Depends,HTTPException,APIRouter,File
from sqlalchemy.orm import Session
from typing import List
from fastapi import status
from fastapi_mail import FastMail, MessageSchema, MessageType
from app.config import mail_config
from datetime import datetime
from collections import defaultdict
from app.db.database import get_db
from sqlalchemy.orm import joinedload
from app.schemas.schema import FileDetails,AssignReviewer,ReviewerOut,AdminEditRequest,RFPDocumentGroupedQuestionsOut,UserOut,NotificationRequest,GroupedRFPQuestionOut,QuestionOut,reviwerdelete,ChatInputRequest,ReassignReviewerRequest
from app.models.rfp_models import User,Reviewer,RFPDocument,RFPQuestion,CompanySummary,ReviewerAnswerVersion
from app.services.llm_service import extract_text_from_pdf,extract_company_background_from_rfp,extract_questions_with_llm,summarize_results_with_llm,generate_search_queries,search_with_serpapi,analyze_answer_score_only ,query_vector_db,client,parse_rfp_summary,build_company_background_prompt,build_proposal_prompt
from app.api.routes.utils import get_current_user
from docx import Document
import os
from fastapi import status,Form
import hashlib
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import re

from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH


router = APIRouter()

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

router.mount("/uploads", StaticFiles(directory=UPLOAD_FOLDER), name="uploads")

@router.post("/search-related-summary/")
async def search_related_summary(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only admins can access summary docs."
        )
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
        category="history" 
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

    return {
        "status": "new",
        "rfp_id": new_rfp.id,
        "saved_file": file_path,
        "category": new_rfp.category,
        "summary": structured_summary,
        "total_questions": questions_grouped
    }


@router.get("/filedetails", response_model=List[FileDetails])
def get_file_details(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can access File details."
            )
        
        documents = (
            db.query(RFPDocument)
            .filter(RFPDocument.category.isnot(None))
            .filter(RFPDocument.category != "")
            .all()
        )
        return documents

    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


@router.post("/upload-library")
def upload_library(
    files: List[UploadFile] = File(...),
    category: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can upload library documents."
            )

        uploaded_docs = []
        for file in files:
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in [".pdf", ".doc", ".docx", ".ppt", ".pptx"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file format: {file.filename}"
                )

            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            saved_filename = f"{timestamp}_{file.filename}"
            file_path = os.path.join(UPLOAD_FOLDER, saved_filename)

            with open(file_path, "wb") as f:
                f.write(file.file.read())

            new_doc = RFPDocument(
                filename=file.filename,
                file_path=file_path,
                category=category,
                admin_id=current_user.id,
                uploaded_at=datetime.utcnow()
            )
            db.add(new_doc)
            db.commit()
            db.refresh(new_doc)

            uploaded_docs.append({
                "document_id": new_doc.id,
                "filename": new_doc.filename,
                "category": new_doc.category
            })

        return {
            "message": f"{len(uploaded_docs)} file(s) uploaded successfully",
            "documents": uploaded_docs
        }

    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


@router.get("/userdetails")
def get_user(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role !="admin":
        raise HTTPException (status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only admins can access User details.")
    users= db.query(User).all()

    if current_user.role == "admin":
        users = db.query(User).all()

    return [    
        UserOut(
            user_id=user.id,
            username=user.username,
            email=user.email,
            role=user.role
        )
        for user in users
    ]


@router.get("/get_assign_users")
def get_assigned_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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


@router.get("/userdetails/{user_id}")
def get_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    
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
            pass  # include all questions

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


@router.post("/assign-reviewer")
def assign_multiple_reviewers(request: AssignReviewer, db: Session = Depends(get_db) ,
                              current_user: User = Depends(get_current_user)):
    try:
        if current_user.role!="admin":
            raise HTTPException( status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only admins can access Assign Question.")
        assigned_questions = []

        for uid in request.user_id:
            user = db.query(User).filter(User.id == uid).first()
            print('ysss')
            if not user:
                continue 
            for ques_id in request.ques_ids:
                question = db.query(RFPQuestion).filter(
                    RFPQuestion.id == ques_id,
                    RFPQuestion.rfp_id == request.file_id
                ).first()
                print('passs')
                print(question)
                if not question:
                    continue

                existing = db.query(Reviewer).filter_by(
                    user_id=uid,
                    ques_id=ques_id
                ).first()
                if existing:
                    continue
                print('dhdghfh')

                reviewer_entry = Reviewer(
                    user_id=uid,
                    ques_id=ques_id,
                    question=question.question_text,
                    status=request.status,
                    file_id=request.file_id,
                    admin_id=current_user.id,
                    submit_status= "process"

                )
                print(reviewer_entry)
                db.add(reviewer_entry)

                # question.assigned_user_id = uid
                # question.assigned_username = user.username
                # question.assignment_status = request.status
                question.assigned_at = datetime.utcnow()

                assigned_questions.append({"user_id": uid, "question_id": ques_id,"submit_status":'process'})

        db.commit()

        return {
            "message": "Reviewer(s) assigned to multiple questions successfully",
            "assigned_questions": assigned_questions
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/assigned-reviewers/{file_id}", response_model=list[ReviewerOut])
def get_reviewers_by_file(file_id: int, db: Session = Depends(get_db)):
    try:
        results = (
            db.query(Reviewer)
            .join(RFPQuestion, Reviewer.ques_id == RFPQuestion.id)
            .join(User, Reviewer.user_id == User.id)
            .filter(RFPQuestion.rfp_id == file_id)
            .all()
        )
        output = []
        for r in results:
            output.append(ReviewerOut(
                ques_id=r.ques_id,
                question=r.question,
                user_id=r.user_id,
                username=r.user.username,
                status=r.status
            ))

        return output

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

LOGIN_URL = "https://rfp-files-generator.netlify.app/login"

@router.post("/send-assignment-notification")
async def send_assignment_notification_bulk(
    request: NotificationRequest, db: Session = Depends(get_db)
):
    try:
        fm = FastMail(mail_config)
        summary = []

        for uid in request.user_id:
            user = db.query(User).filter(User.id == uid).first()
            if not user or not user.email:
                continue

            questions = []
            for ques_id in request.ques_ids:
                assignment = db.query(Reviewer).filter(
                    Reviewer.ques_id == ques_id,
                    Reviewer.user_id == uid
                ).first()
                question = db.query(RFPQuestion).filter(RFPQuestion.id == ques_id).first()

                if assignment and question:
                    questions.append((question, assignment))

            if not questions:
                continue

            question_texts = "<br><br>".join([
                f"<b>QID:</b> {q.id}<br><b>Section:</b> {q.section or 'N/A'}<br><b>Question:</b> {q.question_text}"
                for q, _ in questions
            ])

            html_body = f"""
                <p>Hello {user.username},</p>

                <p>The following questions have been assigned to you:</p>

                {question_texts}

                <p>Please click the button below to log in and review:</p>

                <a href="{LOGIN_URL}" 
                   style="display:inline-block; padding:10px 20px; font-size:16px; 
                          color:#fff; background-color:#007BFF; text-decoration:none; 
                          border-radius:5px;">
                    Log In
                </a>

                <p>Best regards,<br>RFP Automation System</p>
            """

            message = MessageSchema(
                subject="Multiple RFP Questions Assigned",
                recipients=[user.email],
                body=html_body,
                subtype=MessageType.html
            )

            await fm.send_message(message)

            for _, assignment in questions:
                assignment.status = "notified"

            summary.append({
                "user_id": uid,
                "email": user.email,
                "notified_questions": [q.id for q, _ in questions]
            })

        db.commit()

        return {
            "message": "Notification emails sent successfully",
            "notifications": summary
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send emails: {str(e)}")

@router.get('/check_submit')
def check(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
    ):
    try:
        if current_user.role!= "admin":
            raise HTTPException(status_code=403, detail="Only admins can view submissions.")      
        reviewers = db.query(Reviewer).all()
        data = []
        for i in reviewers:
            if i.status is None:
                continue
            file_name = i.question_ref.rfp.filename if i.question_ref and i.question_ref.rfp else "Unknown"

            data.append({
                "username": i.user.username,
                "question_id": i.ques_id,
                "question": i.question,
                "answer": i.ans,
                "status": i.submit_status,
                "submitted_at": i.submitted_at,
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

@router.get('/assign_user_status')
def assign_status(db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    try:
        if current_user.role!="admin":
            raise HTTPException( status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only admins can access check user status")
        reviewers = db.query(Reviewer).all()
        
        if reviewers is None:
            return None
        print(reviewers)
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
            "message": "assign details fetched successfully",
            "data": data
        }
        

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/rfp/{rfp_id}")
def delete_rfp_document(
    rfp_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can access delete docs."
            )
        rfp = db.query(RFPDocument).filter(RFPDocument.id == rfp_id).first()
        if not rfp:
            raise HTTPException(status_code=404, detail="RFP document not found.")
        
        db.delete(rfp)
        db.commit()
        return {"message": "RFP document and all related data deleted successfully."}

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/reviewer-remove")
async def remove_user(
    ques_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can remove the user."
            )
        assign = db.query(Reviewer).filter(
            Reviewer.ques_id == ques_id,
            Reviewer.user_id == user_id
        ).first()

        if not assign:
            raise HTTPException(status_code=404, detail="Reviewer assignment not found.")

        user = db.query(User).filter(User.id == user_id).first()
        question = db.query(RFPQuestion).filter(RFPQuestion.id == ques_id).first()
        
        ans = db.query(ReviewerAnswerVersion).filter(
            ReviewerAnswerVersion.ques_id == ques_id,
            ReviewerAnswerVersion.user_id == user_id
        ).first()
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
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/filter/{rfp_id}')
def filter_question(rfp_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can FILTER."
            )    

        rfp = db.query(RFPDocument).options(joinedload(RFPDocument.questions)).filter(RFPDocument.id == rfp_id).first()
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
                            "username": db.query(User).filter(User.id == r.user_id).first().username,
                            "status": r.status,
                            "submitted_at": r.submitted_at
                        } for r in reviewers
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
            "total_questions": len(all_questions),
            "assigned_count": len(assigned_questions),
            "unassigned_count": len(unassigned_questions),
            # "assigned_questions": assigned_questions,
            # "unassigned_questions": unassigned_questions
        }

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/admin/filter-questions-by-user/{status}')
def admin_filter_questions_by_status(
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role.lower() != "admin":
        raise HTTPException(status_code=403, detail="Only admins can access this endpoint.")

    valid_statuses = ["submitted", "not submitted", "process"]
    status = status.strip().lower()

    if status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail="Invalid status. Must be one of: submitted, not submitted, process."
        )

    reviewers = db.query(Reviewer).join(User).all()

    if not reviewers:
        raise HTTPException(status_code=404, detail="No reviewer data found for this admin.")

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


@router.post("/admin/analyze-answers")
def analyze_overall_score_only_if_complete(rfp_id: int, db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    if current_user.role.lower() != "admin":
        raise HTTPException(status_code=403, detail="Only admins can access this endpoint.")
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
 

@router.get("/rfp-documents/{rfp_id}/view")
def view_rfp_document(rfp_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only admins can view documents."
        )

    rfp_doc = db.query(RFPDocument).filter(RFPDocument.id == rfp_id).first()
    if not rfp_doc:
        raise HTTPException(status_code=404, detail="RFP document not found")

    if not rfp_doc.file_path or not os.path.exists(rfp_doc.file_path):
        raise HTTPException(status_code=404, detail="File not found on server")

    return FileResponse(
        path=rfp_doc.file_path,
        filename=rfp_doc.filename, 
        media_type="application/pdf"
    )

GENERATED_FOLDER = "generated_docs"

@router.post("/generate-rfp-doc/")
async def generate_rfp_doc(
    rfp_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role.lower() != "admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    rfp_doc = db.query(RFPDocument).filter(RFPDocument.id == rfp_id).first()
    if not rfp_doc:
        raise HTTPException(status_code=404, detail="RFP not found")

    # --- Pre-check: Ensure all questions are analyzed ---
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

    # --- Executive Summary ---
    summary_obj = rfp_doc.summary
    if not summary_obj:
        raise HTTPException(status_code=404, detail="Executive summary not found")
    executive_summary = summary_obj.summary_text

    company_name = getattr(rfp_doc, "client_name", "Ringer")

    # --- 1. Company Background ---
    company_context = query_vector_db(
        f"All details about Ringer (services, past proposals, playbooks, SEO, social media, training, case studies, pricing, methodology)", 
        top_k=8
    )
    bg_prompt = build_company_background_prompt(company_context)

    bg_resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": bg_prompt}],
        temperature=0.3
    )
    company_background = bg_resp.choices[0].message.content.strip()

    # --- 2. Structured Proposal Narrative ---
    rfp_text = getattr(rfp_doc, "full_text", executive_summary)
    case_studies = [cs.text for cs in getattr(rfp_doc, "case_studies", [])]

    proposal_prompt = build_proposal_prompt(rfp_text, company_background, case_studies)

    proposal_resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": proposal_prompt}],
        temperature=0.4
    )
    full_proposal_text = proposal_resp.choices[0].message.content.strip()

    # --- 3. Q&A Based Narrative ---
    qa_by_section = {}
    for q in rfp_doc.questions:
        reviewer_answer = next(
            (rev for rev in q.reviewers if rev.submit_status == "submitted"), 
            None
        )

        if reviewer_answer:
            answer_text = reviewer_answer.ans
        elif q.answer_versions:
            latest_version = sorted(q.answer_versions, key=lambda v: v.generated_at)[-1]
            answer_text = latest_version.answer
        else:
            answer_text = "No answer submitted."

        if q.section not in qa_by_section:
            qa_by_section[q.section] = []
        qa_by_section[q.section].append({"question": q.question_text, "answer": answer_text})

    proposal_sections_text = ""
    for section, qas in qa_by_section.items():
        qa_text = "\n".join([f"Q: {qa['question']}\nA: {qa['answer']}" for qa in qas])

        section_prompt = f"""
        You are a proposal writer at Ringer.
        Convert the following Q&A into a professional proposal narrative for the section: {section}.
        Write it as if Ringer is presenting the proposal to the client — no questions, only polished answers.

        --- Input Q&A ---
        {qa_text}

        --- Instructions ---
        - Do not show "Q:" or "A:" in the output.
        - Rewrite answers into flowing paragraphs.
        - Maintain a persuasive, professional proposal tone.
        - Combine related answers into one coherent narrative.
        - Give concise and detailed solutions to the client.
        """

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": section_prompt}],
            temperature=0.4
        )
        section_text = resp.choices[0].message.content.strip()

        proposal_sections_text += f"\n\n### {section}\n{section_text}"

    # --- 4. Create DOCX with Logo + Headings ---
    doc = Document()

    # Cover Page
    try:
        logo_path = "image.png"  # Adjust path if needed
        doc.add_picture(logo_path, width=Inches(1.5))
        last_paragraph = doc.paragraphs[-1]
        last_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    except Exception as e:
        print("Logo could not be added:", e)

    doc.add_heading("RFP Proposal Response", level=0)
    doc.add_paragraph(f"Presented by Ringer")
    doc.add_paragraph(f"Client: {company_name}")
    doc.add_paragraph(f"Generated on {datetime.utcnow().strftime('%Y-%m-%d')}")

    # Executive Summary
    # doc.add_page_break()
    # doc.add_heading("Executive Summary", level=1)
    # doc.add_paragraph(executive_summary)

    # Company Background
    doc.add_page_break()
    doc.add_heading("Company Background & Capabilities", level=1)
    doc.add_paragraph(company_background)

    # Strategic Approach
    doc.add_page_break()
    doc.add_heading("Strategic Approach", level=1)
    doc.add_paragraph(
        "Our methodology is designed to align with client objectives through "
        "creative development, media strategy, SEO, compliance alignment, and "
        "performance tracking. This approach ensures a phased and collaborative "
        "plan where Ringer co-creates with stakeholders."
    )

    # Scope of Work
    # doc.add_page_break()
    # doc.add_heading("Scope of Work", level=1)
    # doc.add_paragraph(full_proposal_text)

    # Timeline
    doc.add_page_break()
    doc.add_heading("Timeline", level=1)
    doc.add_paragraph(
        "Based on Ringer’s proven frameworks, project delivery is divided into phases:\n\n"
        "1. Discovery & Planning – 2-4 weeks\n"
        "2. Development & Playbook Creation – 4-6 weeks\n"
        "3. Launch & Activation – 6-8 weeks\n"
        "4. Optimization & Reporting – ongoing monthly cycles\n\n"
        "Exact timelines may vary depending on scope and client collaboration."
    )

    # Budget & Investment
    doc.add_page_break()
    doc.add_heading("Budget & Investment", level=1)
    doc.add_paragraph(
        "Ringer provides flexible investment ranges aligned to each service:\n\n"
        "- Media Planning & Management: $10,000 – $15,000 (per 90-day cycle)\n"
        "- Playbook Development: $10,000 – $12,000 (4–6 weeks)\n"
        "- Social Media Consulting: $7,500 initial + ongoing hourly support\n"
        "- SEO Playbook Development: $5,000+ (2–4 weeks)\n\n"
        "Budgets are indicative and will be finalized upon discovery. "
        "Our focus is always on delivering measurable ROI."
    )

    # Why Us
    doc.add_page_break()
    doc.add_heading("Why Us", level=1)
    doc.add_paragraph(
        "Ringer combines expertise in media planning, social media strategy, "
        "SEO, training, and analytics. Our differentiators include:\n\n"
        "- Proven success with leading retail and regulated industries\n"
        "- Custom playbooks tailored to compliance needs\n"
        "- Strategic workshops and ongoing leadership support\n"
        "- Integrated reporting, analytics, and optimization frameworks\n\n"
        "This unique mix positions Ringer as a trusted partner for scalable growth."
    )

    # Detailed Proposal Response (Q&A sections)
    doc.add_page_break()
    doc.add_heading("Detailed Proposal Response", level=1)
    doc.add_paragraph(proposal_sections_text)

    # Next Steps
    doc.add_page_break()
    doc.add_heading("Next Steps", level=1)
    doc.add_paragraph(
        "We recommend scheduling a discovery session to align on priorities, "
        "finalize scope, and confirm timelines.\n\n"
        "Please contact us at info@ringer.com to arrange the next discussion."
    )

    # Save File
    os.makedirs(GENERATED_FOLDER, exist_ok=True)
    file_name = f"rfp_response_{rfp_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.docx"
    file_path = os.path.join(GENERATED_FOLDER, file_name)
    doc.save(file_path)

    return {
        "message": "RFP proposal generated successfully",
        "download_url": f"/download/{file_name}"
    }

@router.patch('/admin/edit-answer')
def edit_question_by_admin(
    request: AdminEditRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Only admins can edit submitted questions.")
        assignment = db.query(RFPQuestion, Reviewer).join(
            Reviewer, RFPQuestion.id == Reviewer.ques_id
        ).filter(RFPQuestion.id == request.question_id).first()

        if assignment is None:
            raise HTTPException(status_code=404, detail="Question not found.")

        question, reviewer = assignment
        reviewer.ans = request.answer
        db.commit()

        return {
            "message": "Answer updated successfully by admin.",
            "question_id": question.id,
            "updated_answer": reviewer.ans
        }

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.put("/update-profile")
async def update_profile(
    username: str = Form(...),
    email: str = Form(...),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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
            "image_url": f"uploads/{user.image}" if user.image else None
        }
    }

@router.delete("/delete-reviewer_user")
async def delete_reviewer(
    request: reviwerdelete,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only admins can remove reviewers."
        )
    if request.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin can not be deleted"
        )

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

    db.query(ReviewerAnswerVersion).filter(
        ReviewerAnswerVersion.user_id == request.user_id
    ).delete(synchronize_session=False)

    db.query(Reviewer).filter(
        Reviewer.user_id == request.user_id
    ).delete(synchronize_session=False)

    db.delete(user)
    db.commit()

    return {
        "message": f"User (id={request.user_id}, role={user.role}) "
                   f"and all related reviewer data deleted successfully"
    }

@router.post("/questions/chat_input")
def regenerate_answer_with_chat(
    request: ChatInputRequest,
    db: Session = Depends(get_db)
):
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

    system_prompt = (
        "You are a senior proposal writer. "
        "Refine and regenerate the proposal answer based on the user’s feedback. "
        "Preserve structure, make it professional, and incorporate requested changes. "
        "Do not use markdown symbols like ** or ## in the response."
        "Do not include or repeat the question text in your response. "
    )

    user_prompt = f"""
    Question: {question.question_text}
    Previous Answer: {base_answer}
    Reviewer Feedback: {chat_message}
    Please regenerate a refined answer.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )

    refined_answer = response.choices[0].message.content.strip()

    refined_answer = re.sub(r"(\*\*|##+)", "", refined_answer)

    if not reviewer.ans:  
        reviewer.ans = refined_answer
        db.commit()
        return {
            "status": "success",
            "message": "First answer generated and stored",
            "answer": refined_answer,
            "source": "Reviewer.ans"
        }
    else:
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
            "message": "Answer refined and stored as new version",
            "new_answer_version": {
                "id": new_version.id,
                "ques_id": ques_id,
                "user_id": user_id,
                "answer": refined_answer,
                "generated_at": new_version.generated_at,
            }
        }
    

@router.post("/reassign")
async def reassign_reviewer(
    request: ReassignReviewerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can reassign reviewers."
            )

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
            subtype=MessageType.plain
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

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


