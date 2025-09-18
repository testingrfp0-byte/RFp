import os
from datetime import datetime
from typing import List
from fastapi import (
    UploadFile, File, Form, Depends, HTTPException, APIRouter, status)
from fastapi.staticfiles import StaticFiles
from fastapi_mail import FastMail, MessageSchema, MessageType
from sqlalchemy.orm import Session
from docx import Document
from collections import defaultdict
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from app.config import mail_config
from app.db.database import get_db, Base, engine
from app.schemas.schema import (
    FileDetails, AssignReviewer, ReviewerOut, AdminEditRequest,
    RFPDocumentGroupedQuestionsOut, NotificationRequest,
    reviwerdelete, ChatInputRequest, ReassignReviewerRequest, GroupedRFPQuestionOut,QuestionOut)
from app.models.rfp_models import User, Reviewer, RFPDocument, RFPQuestion
from app.services.llm_service import (
    query_vector_db, client,
    build_company_background_prompt, build_proposal_prompt)
from app.api.routes.utils import get_current_user
from app.utils.admin_function import (
    process_rfp_file, fetch_file_details, process_library_upload,
    get_all_users, get_assigned_users,
    assign_multiple_review, get_reviewers_by_file_service,
    get_user_by_id_service, check_submissions_service,
    get_assign_user_status_service, delete_rfp_document_service,
    remove_user_service, filter_question_service,
    admin_filter_questions_by_status_service, analyze_overall_score_service,
    view_rfp_document_service, edit_question_by_admin_service,
    update_profile_service, delete_reviewer_service,
    regenerate_answer_with_chat_service, reassign_reviewer_service
)

router = APIRouter()
Base.metadata.create_all(engine)


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
    
    return await process_rfp_file(file, db, current_user)

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

@router.post("/upload-library")
def upload_library(
    files: List[UploadFile] = File(...),
    category: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only admins can upload library documents."
        )
    
    return process_library_upload(files, category, db, current_user)

@router.get("/userdetails")
def get_user(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_all_users(db, current_user)

@router.get("/get_assign_users")
def get_assigned_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_assigned_users(db, current_user)

@router.get("/userdetails/{user_id}")
def get_user_by_id_route(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_user_by_id_service(user_id, db)

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
def assign_multiple_reviewers(
    request: AssignReviewer,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return assign_multiple_review(request, db, current_user)

@router.get("/assigned-reviewers/{file_id}", response_model=list[ReviewerOut])
def get_reviewers_by_file(file_id: int, db: Session = Depends(get_db)):
    return get_reviewers_by_file_service(file_id, db)

LOGIN_URL = "https://inspiring-sunburst-3954ce.netlify.app"

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

@router.get("/check_submit")
def check(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return check_submissions_service(db, current_user)


@router.get("/assign_user_status")
def assign_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_assign_user_status_service(db, current_user)

    
@router.delete("/rfp/{rfp_id}")
def delete_rfp_document(
    rfp_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return delete_rfp_document_service(rfp_id, db, current_user)

@router.delete("/reviewer-remove")
async def remove_user(
    ques_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await remove_user_service(ques_id, user_id, db, current_user)

@router.get("/filter/{rfp_id}")
def filter_question(
    rfp_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return filter_question_service(rfp_id, db, current_user)

@router.get("/admin/filter-questions-by-user/{status}")
def admin_filter_questions_by_status(
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return admin_filter_questions_by_status_service(status, db, current_user)
 
@router.post("/admin/analyze-answers")
def analyze_overall_score_only_if_complete(
    rfp_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role.lower() != "admin":
        raise HTTPException(status_code=403, detail="Only admins can access this endpoint.")
    
    return analyze_overall_score_service(rfp_id, db)

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

    rfp_text = getattr(rfp_doc, "full_text", executive_summary)
    case_studies = [cs.text for cs in getattr(rfp_doc, "case_studies", [])]

    proposal_prompt = build_proposal_prompt(rfp_text, company_background, case_studies)

    proposal_resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": proposal_prompt}],
        temperature=0.4
    )
    full_proposal_text = proposal_resp.choices[0].message.content.strip()

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

@router.patch("/admin/edit-answer")
def edit_question_by_admin(
    request: AdminEditRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only admins can edit submitted questions."
        )

    try:
        return edit_question_by_admin_service(request, db)
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
    current_user: User = Depends(get_current_user),
):
    try:
        return await update_profile_service(db, current_user, username, email, image)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
            detail="Admin cannot be deleted"
        )

    return await delete_reviewer_service(request, db)

@router.post("/questions/chat_input")
async def regenerate_answer_with_chat(
    request: ChatInputRequest,
    db: Session = Depends(get_db),
):
    try:
        return await regenerate_answer_with_chat_service(request, db)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reassign")
async def reassign_reviewer(
    request: ReassignReviewerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only admins can reassign reviewers."
        )

    try:
        return await reassign_reviewer_service(request, db, current_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))









# ------------------------------------------
# for test the endpoint 
from pinecone import Pinecone, ServerlessSpec
from langchain.text_splitter import RecursiveCharacterTextSplitter

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENV")   # e.g. aws-us-east-1
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "kb-index")
pc = Pinecone(api_key=PINECONE_API_KEY)





if PINECONE_INDEX not in pc.list_indexes().names():
    pc.create_index(
        name=PINECONE_INDEX,
        dimension=1536, 
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1" 
        )
    )

index = pc.Index(PINECONE_INDEX)










def extract_text_from_file(file_path: str) -> str:
    """Extract text from PDF/DOCX/PPTX. 
       Replace with your actual implementation."""
    if file_path.endswith(".pdf"):
        from PyPDF2 import PdfReader
        reader = PdfReader(file_path)
        return " ".join([page.extract_text() for page in reader.pages if page.extract_text()])
    # TODO: Add docx, pptx extraction
    return ""


def get_embedding(text: str) -> list:
    """Generate embeddings for a text string."""
    resp = client.embeddings.create(model="text-embedding-3-small", input=[text])
    return resp.data[0].embedding


def generate_summary(text: str) -> str:
    """Generate summary of an RFP using LLM."""
    prompt = f"Summarize the following RFP in 3–5 paragraphs:\n\n{text[:8000]}"
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an RFP summarizer."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()


# ----------- API Route -----------

@router.post("/upload-library-new")
def upload_library(
    files: List[UploadFile] = File(...),
    category: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only admins can upload library documents."
        )

    try:
        uploaded_docs = []

        for file in files:
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in [".pdf", ".docx", ".pptx"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file format: {file.filename}"
                )

            # Save file locally
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            saved_filename = f"{timestamp}_{file.filename}"
            file_path = os.path.join(UPLOAD_FOLDER, saved_filename)

            with open(file_path, "wb") as f:
                f.write(file.file.read())

            # Save metadata in DB
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

            # Extract text
            text = extract_text_from_file(file_path)
            if not text:
                continue

            # ---- (A) Store Summary in Pinecone ----
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
                        "type": "summary",
                        "text": summary
                    }
                )],
                namespace="summaries"
            )

            # ---- (B) Store Chunks in Pinecone ----
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
                        "type": "chunk",
                        "chunk_id": i,
                        "text": chunk
                    }
                ))

            if vectors:
                index.upsert(vectors, namespace=f"rfp_{new_doc.id}")

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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


