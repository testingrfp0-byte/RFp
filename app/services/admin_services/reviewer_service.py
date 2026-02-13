import re
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from fastapi_mail import FastMail, MessageSchema, MessageType
from app.models.rfp_models import KeystoneFile, User, Reviewer, RFPQuestion, ReviewerAnswerVersion
from app.services.llm_services.llm_service import _sanitize_short_name, get_short_name, get_similar_context, client,get_active_keystone_text
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

# async def regenerate_answer_with_chat_service(request, db: Session):
#     user_id = request.user_id
#     ques_id = request.ques_id
#     chat_message = request.chat_message

#     reviewer = db.query(Reviewer).filter_by(
#         user_id=user_id,
#         ques_id=ques_id
#     ).first()

#     if not reviewer:
#         raise HTTPException(
#             status_code=404,
#             detail="Reviewer not assigned to this question"
#         )

#     question = db.query(RFPQuestion).filter_by(id=ques_id).first()
#     if not question:
#         raise HTTPException(
#             status_code=404,
#             detail="Question not found"
#         )

#     base_answer = reviewer.ans or ""

#     keystone_text = get_active_keystone_text(
#         db=db,
#         admin_id=question.admin_id
#     )

#     rfp_context = get_similar_context(
#         question.question_text,
#         question.rfp_id,
#         top_k=5
#     )

#     system_prompt = (
#         "You are a senior proposal writer refining an RFP response.\n\n"

#         "### KEYSTONE DATA (PRIMARY SOURCE — DO NOT VIOLATE):\n"
#         f"{keystone_text}\n\n"

#         "### NON-NEGOTIABLE RULES:\n"
#         "- Keystone Data is the single source of truth for company facts\n"
#         "- Do NOT modify, remove, or invent company details\n"
#         "- Do NOT add new services, certifications, locations, or metrics\n"
#         "- If reviewer feedback conflicts with Keystone Data, Keystone wins\n\n"

#         "### Rewrite Mode (Highest Priority):\n"
#         "- If feedback includes rewrite / shorten / summarize / rephrase,\n"
#         "  follow those instructions exactly\n"
#         "- Do NOT add new content when shortening\n"
#         "- Preserve meaning only\n\n"

#         "### General Rules:\n"
#         "- Improve clarity and flow when not in rewrite mode\n"
#         "- Produce plain text only (no markdown)\n"
#         "- Do NOT repeat the question text\n"
#         "- Output must be client-ready and professional\n"
#         "- Use 'we' or 'our' to refer to the company\n"
#         "- Never use 'I'\n"
#         "- Refer to the issuer by their short name from RFP context\n"
#         "- Anchor responses to RFP specifics from context\n"
#         "- If feedback asks to add details, only use Keystone Data or RFP context — state 'No additional information available' if missing\n"
#         "- For examples or case studies, only use anonymized or generalized ones from Keystone if available\n"
#         "- Ensure response is concise yet comprehensive\n"
#         "- Handle common feedback types:\n"
#         "  - Clarify: Rephrase ambiguous parts without adding info\n"
#         "  - Expand: Add depth only from sources\n"
#         "  - Remove: Eliminate specified elements exactly\n"
#         "  - Align: Ensure matches RFP requirements verbatim\n"
#     )

#     user_prompt = f"""
# Question:
# {question.question_text}

# Existing Answer:
# {base_answer}

# Reviewer Feedback:
# {chat_message}

# RFP Context:
# {rfp_context}

# Regenerate the answer while strictly respecting Keystone Data.
# """

#     response = client.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_prompt},
#         ],
#         temperature=0.3,
#     )

#     refined_answer = response.choices[0].message.content.strip()
#     refined_answer = re.sub(r"(\*\*|##+)", "", refined_answer)

#     new_version = ReviewerAnswerVersion(
#         user_id=user_id,
#         ques_id=ques_id,
#         answer=refined_answer,
#         generated_at=datetime.utcnow()
#     )
#     db.add(new_version)

#     reviewer.ans = refined_answer
#     db.commit()
#     db.refresh(new_version)

#     return {
#         "status": "success",
#         "message": "Answer regenerated using Keystone Data",
#         "new_answer_version": {
#             "id": new_version.id,
#             "ques_id": ques_id,
#             "user_id": user_id,
#             "answer": refined_answer,
#             "generated_at": new_version.generated_at,
#         }
#     }


async def regenerate_answer_with_chat_service(request, db: Session):
    user_id = request.user_id
    ques_id = request.ques_id
    chat_message = request.chat_message

    # ----------------------------------------------------------------
    # Fetch reviewer
    # ----------------------------------------------------------------
    reviewer = db.query(Reviewer).filter_by(
        user_id=user_id,
        ques_id=ques_id
    ).first()

    if not reviewer:
        raise HTTPException(
            status_code=404,
            detail="Reviewer not assigned to this question"
        )

    # ----------------------------------------------------------------
    # Fetch question
    # ----------------------------------------------------------------
    question = db.query(RFPQuestion).filter_by(id=ques_id).first()
    if not question:
        raise HTTPException(
            status_code=404,
            detail="Question not found"
        )

    base_answer = reviewer.ans or ""

    # ----------------------------------------------------------------
    # Fetch short_name from the parent RFP record.
    # Sanitize defensively to block UUID/hash values.
    # ----------------------------------------------------------------
    rfp_record = db.query(KeystoneFile).filter_by(
        id=question.rfp_id
    ).first()

    raw_filename = rfp_record.filename if rfp_record and rfp_record.filename else ""
    short_name = _sanitize_short_name(get_short_name(raw_filename)) if raw_filename else "the City"

    # ----------------------------------------------------------------
    # Fetch Keystone data
    # ----------------------------------------------------------------
    keystone_text = get_active_keystone_text(
        db=db,
        admin_id=question.admin_id
    )

    # ----------------------------------------------------------------
    # Fetch RFP context — unpack tuple correctly.
    # get_similar_context() returns (context_text: str, sources: list).
    # ----------------------------------------------------------------
    rfp_context, _ = get_similar_context(
        question.question_text,
        question.rfp_id,
        top_k=5
    )

    # ----------------------------------------------------------------
    # Classify the type of change being requested.
    # IMPORTANT: Classification only adds CONSTRAINTS around execution.
    # It does NOT gate whether the instruction gets followed.
    # The user's chat_message is ALWAYS executed literally, regardless
    # of whether it matches a known keyword pattern.
    # ----------------------------------------------------------------
    chat_lower = chat_message.lower()

    is_surgical_edit = any(keyword in chat_lower for keyword in [
        "add to", "add to the", "change", "replace", "update",
        "modify", "insert", "remove", "delete", "edit",
        "in the sentence", "in sentence", "at the end of",
        "at the beginning of", "after the", "before the",
        "in the first", "in the second", "in the last",
        "in the paragraph", "in the section", "start with",
        "begin with", "end with", "prefix", "append",
    ])

    is_rewrite = any(keyword in chat_lower for keyword in [
        "rewrite", "shorten", "summarize", "rephrase",
        "condense", "simplify", "restructure", "redo",
        "make it shorter", "make shorter", "make it longer",
        "make longer", "make it more", "make it less",
    ])

    # ----------------------------------------------------------------
    # Build the edit instruction block.
    #
    # THE CORE FIX:
    # Every branch now starts with:
    #   "STEP 1: Execute this instruction EXACTLY: {chat_message}"
    #
    # This means the user's literal instruction is always the FIRST
    # thing the LLM sees and must act on — before any constraints,
    # rules, or classification guidance.
    #
    # The classification only adds ADDITIONAL CONSTRAINTS about HOW
    # to apply the instruction (surgical precision, rewrite scope, etc).
    # It no longer controls WHETHER the instruction gets followed.
    # ----------------------------------------------------------------

    if is_surgical_edit and not is_rewrite:
        edit_instruction_block = f"""
### ⚠️ USER INSTRUCTION — EXECUTE THIS FIRST, EXACTLY AS STATED:
\"\"\"{chat_message}\"\"\"

The instruction above is your PRIMARY directive. Execute it literally.
Do not interpret it loosely. Do not substitute your own judgment about
what would "improve" the answer. Do exactly what the instruction says.

SURGICAL EDIT CONSTRAINTS (apply AFTER executing the instruction above):
- The existing answer is your base. Preserve it entirely except for the
  one element the instruction targets.
- Locate the EXACT sentence, phrase, word, or section the instruction refers to.
  Apply the change there and ONLY there.
- Copy every other sentence in the existing answer VERBATIM — word for word.
- Do NOT rewrite, reorganize, expand, shorten, or improve any part of the
  answer that was not explicitly mentioned in the instruction.
- Do NOT add new paragraphs or sentences unless the instruction explicitly asks.
- Do NOT change the tone, voice, or structure of sections not being edited.
- Return the COMPLETE updated answer — not just the changed portion.
- If the instruction is ambiguous, apply the smallest possible change.

WHAT YOU MUST NOT DO:
- Do NOT produce a fully rewritten version as a "cleaner" alternative.
- Do NOT silently improve other sentences while applying the edit.
- Do NOT change the client name ({short_name}) in sections not being edited.
"""

    elif is_rewrite:
        edit_instruction_block = f"""
### ⚠️ USER INSTRUCTION — EXECUTE THIS FIRST, EXACTLY AS STATED:
\"\"\"{chat_message}\"\"\"

The instruction above is your PRIMARY directive. Execute it literally.

REWRITE CONSTRAINTS (apply while executing the instruction above):
- If "shorten" or "summarize": reduce length, preserve all key facts, add nothing new.
- If "rephrase" or "rewrite": change wording, keep same meaning and facts.
- If "restructure": reorganize only — do not add or remove factual content.
- If "make it longer" or "expand": add depth only from Keystone Data or RFP context.
- In all cases: preserve all Keystone Data facts exactly.
- Do NOT invent new statistics or case studies while applying this instruction.
"""

    else:
        # Catch-all for ALL other instructions — including simple ones like
        # "start with OK", "add a sentence", "change the tone", "make it formal", etc.
        # These are not surgical edits or rewrites, but they are still LITERAL COMMANDS
        # that must be followed exactly.
        edit_instruction_block = f"""
###  USER INSTRUCTION — EXECUTE THIS FIRST, EXACTLY AS STATED:
\"\"\"{chat_message}\"\"\"

The instruction above is your PRIMARY directive. Execute it literally and completely.

Examples of how to interpret literal instructions:
- "add a closing sentence" → Add exactly one closing sentence at the end
- "make it more formal" → Adjust tone throughout to be more formal
- "remove the last paragraph" → Delete only the last paragraph
- "begin with a question" → The first sentence must be a question

EXECUTION RULES:
- Apply the instruction to the existing answer.
- After applying the instruction, check: did you actually do what was asked?
  If not, redo it until the output literally reflects the instruction.
- Preserve all content from the existing answer that the instruction
  does not explicitly target.
- Do NOT use this instruction as an excuse to rewrite or regenerate the
  entire answer from scratch.
- Do NOT invent statistics, metrics, or fictional case studies.
- Do NOT substitute "general improvements" for the specific instruction given.
"""

    # ----------------------------------------------------------------
    # System prompt
    # ----------------------------------------------------------------
    system_prompt = (
        "You are a senior proposal writer refining an RFP response.\n\n"

        "### ⚠️ INSTRUCTION COMPLIANCE RULE (ABSOLUTE PRIORITY):\n"
        "- The user's instruction in the USER INSTRUCTION block is a DIRECT COMMAND.\n"
        "- You MUST execute it LITERALLY and COMPLETELY before doing anything else.\n"
        "- 'start with OK' means the response begins with 'OK'.\n"
        "- 'add X' means X is present in the output.\n"
        "- 'remove X' means X is absent from the output.\n"
        "- After generating your response, verify: does it literally reflect\n"
        "  what the instruction asked? If not, fix it before outputting.\n"
        "- NEVER ignore, skip, or reinterpret a user instruction.\n\n"

        "### ⚠️ CLIENT NAMING RULE (MANDATORY):\n"
        f"- The client's name is: {short_name}\n"
        f"- Refer to the issuer EXCLUSIVELY as '{short_name}' throughout the response.\n"
        "- NEVER use a filename, document ID, UUID, or alphanumeric code as a client name.\n"
        "- NEVER use strings like '24Ad8E0C', '24AA07', or similar as a client name.\n"
        "- NEVER use 'the client' as a substitute.\n\n"

        "### KEYSTONE DATA (PRIMARY SOURCE OF TRUTH — DO NOT VIOLATE):\n"
        f"{keystone_text}\n\n"

        "### NON-NEGOTIABLE RULES:\n"
        "- Keystone Data is the single source of truth for company facts.\n"
        "- Do NOT modify, remove, or invent company details.\n"
        "- Do NOT add new services, certifications, locations, or metrics.\n"
        "- If reviewer feedback conflicts with Keystone Data, Keystone wins.\n\n"

        "### ⚠️ ANTI-HALLUCINATION RULES (MANDATORY — ZERO TOLERANCE):\n"
        "- NEVER invent statistics, percentages, or quantified results.\n"
        "- Do NOT write phrases like 'resulting in a 30% increase' or\n"
        "  'led to a 50% improvement' unless that exact figure is in Keystone Data.\n"
        "- NEVER fabricate fictional client engagements or case studies.\n"
        "- Do NOT use placeholder phrases like 'for a regional tourism board',\n"
        "  'for a coastal destination', 'for a national park', or similar.\n"
        "  These are fabrications — never acceptable under any circumstance.\n"
        "- Only reference client work explicitly described in Keystone Data.\n"
        "- If no real case study exists for a discipline, write:\n"
        "  'We bring direct expertise to this area — specific case study details\n"
        "  are available upon request.'\n"
        "- If no metrics are available, describe the approach qualitatively only.\n\n"

        "### VOICE & FORMATTING RULES:\n"
        "- Use 'we' or 'our' to refer to the agency. Never use 'I'.\n"
        "- Plain text only — no markdown, no bold, no headers, no asterisks.\n"
        "- Do NOT repeat the question text in the response.\n"
        "- Output must be client-ready and professional.\n"
        "- Anchor responses to specifics from the RFP context.\n"
        "- Do NOT default to numbered lists or bullet points.\n"
        "- If covering multiple disciplines or areas, write each as a prose\n"
        "  paragraph — not a numbered list.\n\n"

        "### EDIT MODE AUTHORITY:\n"
        "- The existing answer is the base. Preserve all content not targeted\n"
        "  by the user instruction.\n"
        "- Never use an instruction as an excuse to rewrite the whole answer.\n"
    )

    # ----------------------------------------------------------------
    # User prompt — instruction block appears BEFORE the existing answer
    # so the LLM reads the command before it reads the content to edit.
    # ----------------------------------------------------------------
    user_prompt = f"""
{edit_instruction_block}

Question:
{question.question_text}

Existing Answer:
{base_answer}

RFP Context:
{rfp_context}

Now apply the USER INSTRUCTION above to the Existing Answer.
Check your output: does it literally reflect what the instruction asked?
If not, revise until it does. Then output the final result.
"""

    # ----------------------------------------------------------------
    # LLM call
    # ----------------------------------------------------------------
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,  # Lower than before — instruction-following needs precision
    )

    refined_answer = response.choices[0].message.content.strip()
    refined_answer = re.sub(r"(\*\*|##+|\*)", "", refined_answer)

    # ----------------------------------------------------------------
    # Persist new version
    # ----------------------------------------------------------------
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
