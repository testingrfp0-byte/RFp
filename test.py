# @router.get('/filter/status/{status}')
# def filter_question(
#     status: str, 
#     db: Session = Depends(get_db), 
#     current_user: User = Depends(get_current_user)
# ):
#     try:
#         if current_user.role != "admin":
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Only admins can FILTER."
#             )

#         valid_statuses = ["assigned", "unassigned", "total question"]
#         if status not in valid_statuses:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail=f"Invalid status. Allowed values: {valid_statuses}"
#             )

#         rfps = db.query(RFPDocument).options(joinedload(RFPDocument.questions)).all()

#         assigned_questions = []
#         unassigned_questions = []

#         for rfp in rfps:
#             for question in rfp.questions:
#                 reviewers = db.query(Reviewer).filter(Reviewer.ques_id == question.id).all()

#                 if reviewers:
#                     assigned_questions.append({
#                         "rfp_id": rfp.id,
#                         "pdf_filename": rfp.filename,
#                         "id": question.id,
#                         "text": question.question_text,
#                         "reviewers": [
#                             {
#                                 "user_id": r.user_id,
#                                 "username": db.query(User).filter(User.id == r.user_id).first().username,
#                                 "status": r.status,
#                                 "submitted_at": r.submitted_at
#                             } for r in reviewers
#                         ]
#                     })
#                 else:
#                     unassigned_questions.append({
#                         "rfp_id": rfp.id,
#                         "pdf_filename": rfp.filename,
#                         "id": question.id,
#                         "text": question.question_text
#                     })

#         if status == "assigned":
#             return {
#                 "status": "assigned",
#                 "count": len(assigned_questions),
#                 "questions": assigned_questions
#             }
#         elif status == "unassigned":
#             return {
#                 "status": "unassigned",
#                 "count": len(unassigned_questions),
#                 "questions": unassigned_questions
#             }
#         elif status == "total question":
#             return {
#                 "status": "total question",
#                 "total_questions": sum(len(rfp.questions) for rfp in rfps),
#                 "assigned_count": len(assigned_questions),
#                 "unassigned_count": len(unassigned_questions)
#             }

#     except HTTPException as http_exc:
#         raise http_exc
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/search-related-summary/")
# async def search_related_summary(
#     file: UploadFile = File(...),
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     print(current_user.role)
#     if current_user.role != "admin":
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Only admins can access summary docs."
#         )
#     file_bytes = await file.read()

#     timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
#     dummy_filename = f"rfp_{timestamp}.pdf"
#     file_path = os.path.join(UPLOAD_FOLDER, dummy_filename)

#     with open(file_path, "wb") as f:
#         f.write(file_bytes)

#     rfp_text = extract_text_from_pdf(file_bytes)

#     if not rfp_text.strip():
#         return {"error": "PDF text is empty or not readable."}

#     search_queries = generate_search_queries(rfp_text)
#     questions_grouped = extract_questions_with_llm(rfp_text)
#     company_rfp_text = extract_company_background_from_rfp(rfp_text)

#     all_snippets = []
#     for query in search_queries:
#         results = search_with_serpapi(query)
#         for item in results:
#             if snippet := item.get("snippet"):
#                 all_snippets.append(snippet)

#     summary_text = summarize_results_with_llm(
#         all_snippets,
#         rfp_company_text=company_rfp_text
#     )

#     new_rfp = RFPDocument(
#         filename=file.filename,      
#         file_path=file_path,         
#         extracted_text=rfp_text,
#         admin_id=current_user.id
#     )
#     db.add(new_rfp)
#     db.commit()
#     db.refresh(new_rfp)

#     new_summary = CompanySummary(
#         rfp_id=new_rfp.id,
#         summary_text=summary_text,
#         admin_id=current_user.id
#     )
#     db.add(new_summary)

#     for group_number, data in questions_grouped.items():
#         section_name = data.get("section", f"Section {group_number}")
#         for q in data.get("questions", []):
#             db.add(RFPQuestion(
#                 rfp_id=new_rfp.id,
#                 question_text=q,
#                 section=section_name,
#                 admin_id=current_user.id
#             ))

#     db.commit()

#     return {
#         "rfp_id": new_rfp.id,
#         "saved_file": file_path,
#         "summary": summary_text,
#         "total_questions": questions_grouped
#     }




# ====================================================
# def query_vector_db(question: str, top_k=8):
#     """
#     Query the vector database for relevant context.
#     """
#     emb = client.embeddings.create(
#         model="text-embedding-3-small",
#         input=question
#     ).data[0].embedding

#     results = index.query(
#         vector=emb,
#         top_k=top_k,
#         include_metadata=True
#     )
#     return [match['metadata']['text'] for match in results['matches']]



# def build_company_background_prompt(company_context: list[str]) -> str:
#     """
#     Build a prompt to summarize all available Ringer details.
#     """
#     return f"""
#     You are Ringer's Senior Proposal Assistant. 
#     Summarize ALL available details about Ringer clearly, concisely, and professionally. 

#     Context includes past proposals, service offerings, methodologies, playbooks, 
#     case studies, pricing estimates, and SEO/social media support. 
#     Extract and include everything relevant to demonstrate Ringer’s full capabilities.

#     Also:
#     - Extract the client name (and email/contact if available) from the RFP context. 
#     - Present Ringer’s capabilities in a polished background section. 
#     - Emphasize consulting services, media planning, playbook development, 
#       social media strategy, SEO, analytics, reporting, and training. 
#     - Integrate relevant past work examples (from the context).
#     - Avoid repetition — make it narrative and professional.

#     Context:
#     {chr(10).join(company_context)}

#     provide short and consice summary 

#     Provide the final output as a professional "Company Background & Capabilities" 
#     section suitable for an RFP proposal.
#     """


# def build_proposal_prompt(rfp_text: str, company_context: str, case_studies: list[str] = None) -> str:
#     """
#     Build a structured proposal prompt to generate a concise, persuasive proposal.
#     Includes Ringer’s service details and optional case studies.
#     """
#     case_study_text = "\n".join(case_studies) if case_studies else "No case studies provided."

#     return f"""
#     You are a senior proposal writer creating a complete, professional, and concise RFP response. 
#     Use the RFP extract, enriched company background, and case studies (if available).
#     Do NOT include an Executive Summary (it will be added separately).

#     --- RFP Extract ---
#     {rfp_text}

#     --- Enriched Company Background (from vector DB) ---
#     {company_context}

#     --- Case Studies (Optional) ---
#     {case_study_text}

#     Write a structured, **short and direct** proposal with the following sections:

#     1. Strategic Approach  
#        - Clear methodology to meet client goals.  
#        - Cover creative, media, SEO, compliance, performance tracking.  
#        - Show Ringer’s workshops, phased strategies, co-creation.  

#     2. Scope of Work  
#        - List service modules (media planning, content, playbooks, SEO, training).  
#        - For each: Tasks, Outcomes, Compliance notes.  
#        - Reference past successes where relevant.  

#     3. Timeline  
#        - Use phases (Discovery, Development, Launch, Optimization).  
#        - Give estimated weeks/months + milestones.  

#     4. Budget & Investment  
#        - Show ranges (not exact).  
#        - Link investments to services.  
#        - Explain ROI/value.  
#        - Emphasize flexibility.  

#     5. Why Us  
#        - Highlight Ringer’s strengths + differentiators.  
#        - Insert case studies where relevant.  
#        - Stress expertise in media, social, SEO, training, analytics.  

#     6. Next Steps  
#        - Suggest clear follow-up actions (e.g., discovery call).  
#        - Leave placeholders for contact info.  

#     Notes:  
#     - Tone: Professional, persuasive, client-focused.  
#     - Keep sentences concise and avoid redundancy.  
#     - Always deliver a complete proposal.  
#     - Align with client’s language where possible.  
#     """


# @router.post("/generate-rfp-doc/")
# async def generate_rfp_doc(
#     rfp_id: int,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     if current_user.role.lower() != "admin":
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
#     rfp_doc = db.query(RFPDocument).filter(RFPDocument.id == rfp_id).first()
#     if not rfp_doc:
#         raise HTTPException(status_code=404, detail="RFP not found")

#     #  Pre-check: Ensure all questions are analyzed
#     unanswered = []
#     for q in rfp_doc.questions:
#         has_reviewer_ans = any(rev.submit_status == "submitted" for rev in q.reviewers)
#         has_ai_ans = bool(q.answer_versions)
#         if not (has_reviewer_ans or has_ai_ans):
#             unanswered.append(q.question_text)

#     if unanswered:
#         raise HTTPException(
#             status_code=409,
#             detail={
#                 "message": f"Report cannot be generated. {len(unanswered)} question(s) are not analyzed yet.",
#                 "unanswered_questions": unanswered
#             }
#         )

#     # Continue with your existing logic
#     summary_obj = rfp_doc.summary
#     if not summary_obj:
#         raise HTTPException(status_code=404, detail="Executive summary not found")
#     executive_summary = summary_obj.summary_text

#     company_name = getattr(rfp_doc, "client_name", "Ringer's")

#     # 1. Company Background
#     company_context = query_vector_db(
#         f"All details about Ringer (services, past proposals, playbooks, SEO, social media, training, case studies, pricing, methodology)", 
#         top_k=8
#     )
#     bg_prompt = build_company_background_prompt(company_context)

#     bg_resp = client.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=[{"role": "user", "content": bg_prompt}],
#         temperature=0.3
#     )
#     company_background = bg_resp.choices[0].message.content.strip()

#     # 2. Structured Proposal Narrative
#     rfp_text = getattr(rfp_doc, "full_text", executive_summary)
#     case_studies = [cs.text for cs in getattr(rfp_doc, "case_studies", [])]

#     proposal_prompt = build_proposal_prompt(rfp_text, company_background, case_studies)

#     proposal_resp = client.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=[{"role": "user", "content": proposal_prompt}],
#         temperature=0.4
#     )
#     full_proposal_text = proposal_resp.choices[0].message.content.strip()

#     # 3. Q&A Based Narrative
#     qa_by_section = {}
#     for q in rfp_doc.questions:
#         reviewer_answer = next(
#             (rev for rev in q.reviewers if rev.submit_status == "submitted"), 
#             None
#         )

#         if reviewer_answer:
#             answer_text = reviewer_answer.ans
#         elif q.answer_versions:
#             latest_version = sorted(q.answer_versions, key=lambda v: v.generated_at)[-1]
#             answer_text = latest_version.answer
#         else:
#             answer_text = "No answer submitted."

#         if q.section not in qa_by_section:
#             qa_by_section[q.section] = []
#         qa_by_section[q.section].append({"question": q.question_text, "answer": answer_text})

#     proposal_sections_text = ""
#     for section, qas in qa_by_section.items():
#         qa_text = "\n".join([f"Q: {qa['question']}\nA: {qa['answer']}" for qa in qas])

#         section_prompt = f"""
#         You are a proposal writer at Ringer.
#         Convert the following Q&A into a professional proposal narrative for the section: {section}.
#         Write it as if Ringer is presenting the proposal to the client — no questions, only polished answers.

#         --- Input Q&A ---
#         {qa_text}

#         --- Instructions ---
#         - Do not show "Q:" or "A:" in the output.
#         - Rewrite answers into flowing paragraphs.
#         - Maintain a persuasive, professional proposal tone.
#         - Combine related answers into one coherent narrative.
#         - Give concise and detailed solutions to the client.
#         """

#         resp = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[{"role": "user", "content": section_prompt}],
#             temperature=0.4
#         )
#         section_text = resp.choices[0].message.content.strip()

#         proposal_sections_text += f"\n\n### {section}\n{section_text}"

#     # 4. Create DOCX
#     doc = Document()
#     doc.add_heading("RFP Proposal Response", level=0)
#     doc.add_paragraph(f"Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")

#     # Executive Summary (optional, uncomment if needed)
#     # doc.add_heading("Executive Summary", level=1)
#     # doc.add_paragraph(executive_summary)

#     # Company Background
#     doc.add_heading(f"{company_name} – Company Background & Capabilities", level=1)
#     doc.add_paragraph(company_background)

#     # Structured Proposal
#     doc.add_heading("Structured Proposal", level=1)
#     doc.add_paragraph(full_proposal_text)

#     # Proposal Response (Q&A-based)
#     # doc.add_heading("Proposal Response (Q&A)", level=1)
#     # doc.add_paragraph(proposal_sections_text)

#     # Save
#     os.makedirs(GENERATED_FOLDER, exist_ok=True)
#     file_name = f"rfp_response_{rfp_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.docx"
#     file_path = os.path.join(GENERATED_FOLDER, file_name)
#     doc.save(file_path)

#     return {
#         "message": "RFP proposal generated successfully",
#         "download_url": f"/download/{file_name}"
#     }






















# +++++++++++++++++++++++++++++++++++++++++++++++++



# def update_answer_service(db: Session, current_user: User, question_id: int):
#     try:
#         assignment = (
#             db.query(RFPQuestion, Reviewer)
#             .join(Reviewer, RFPQuestion.id == Reviewer.ques_id)
#             .filter(
#                 Reviewer.user_id == current_user.id,
#                 Reviewer.ques_id == question_id
#             )
#             .first()
#         )

#         if assignment is None:
#             raise HTTPException(status_code=403, detail="Question not assigned to current user")

#         question, reviewer = assignment

#         # ✅ Generate context + AI answer
#         context = get_similar_context(question.question_text)
#         answer = generate_answer_with_context(question.question_text, context)

#         # ✅ Save the *previous* answer as version if it exists
#         if reviewer.ans:
#             version = ReviewerAnswerVersion(
#                 user_id=current_user.id,
#                 ques_id=question.id,
#                 answer=reviewer.ans   # store old answer as version
#             )
#             db.add(version)

#         # ✅ Update latest answer
#         reviewer.ans = answer
#         reviewer.submitted_at = datetime.utcnow()

#         db.commit()
#         db.refresh(reviewer)

#         return {
#             "message": "Answer has been updated successfully.",
#             "question_id": question.id,
#             "current_answer": reviewer.ans,
#             "versions": db.query(ReviewerAnswerVersion)
#                           .filter_by(user_id=current_user.id, ques_id=question.id)
#                           .order_by(ReviewerAnswerVersion.generated_at.desc())
#                           .all()
#         }

#     except HTTPException as http_exc:
#         raise http_exc
#     except Exception as e:
#         db.rollback()
#         raise HTTPException(status_code=500, detail=str(e))
