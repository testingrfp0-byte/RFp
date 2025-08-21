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




