from fastapi import HTTPException,APIRouter,Depends
from sqlalchemy.orm import Session
from app.models.rfp_models import User,Reviewer,RFPQuestion,ReviewerAnswerVersion
from datetime import datetime
from app.utils.dependencies import get_db
from app.api.routes.utils import get_current_user
from app.services.llm_service import get_similar_context,generate_answer_with_context
from app.utils.user_function import answer_versions,assigned_questions,generate_answers_service,update_answer_service,submit_service,chech_service,filter_service

router = APIRouter()

# @router.get("/assigned-questions")
# def get_assigned_questions(
#     db: Session = Depends(get_db),current_user: User=Depends(get_current_user)):
    
#     assignments = db.query(RFPQuestion, Reviewer).join(
#         Reviewer, RFPQuestion.id == Reviewer.ques_id
#     ).filter(Reviewer.user_id == current_user.id).all()
    
#     results = []
#     for question, reviewer in assignments:
#         results.append({
#             "rfp_id": question.rfp_id,
#             "filename": question.rfp.filename ,
#             "question_id": question.id,
#             "question_text": question.question_text,
#             "section": question.section,
#             "status": reviewer.status,
#             "assigned_at": question.assigned_at
#         })

#     return results

@router.get("/assigned-questions")
def get_assigned_questions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return assigned_questions(db, current_user)


# @router.get("/generate-answers/{question_id}")
# def generate_answers(
#     question_id: int,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     try:
#         assignment = db.query(RFPQuestion, Reviewer).join(
#             Reviewer, RFPQuestion.id == Reviewer.ques_id
#         ).filter(
#             Reviewer.user_id == current_user.id,
#             Reviewer.ques_id == question_id
#         ).first()

#         if assignment is None:
#             raise HTTPException(status_code=403, detail="Question not assigned to current user")

#         question, reviewer = assignment

#         context = get_similar_context(question.question_text)
#         answer = generate_answer_with_context(question.question_text, context)

#         version = ReviewerAnswerVersion(
#             user_id=current_user.id,
#             ques_id=question_id,
#             answer=answer
#         )
#         db.add(version)
#         reviewer.ans = answer  
#         db.commit()

#         return {
#             "question_id": question.id,
#             "question_text": question.question_text,
#             "answer": answer
#         }

#     except HTTPException as http_exc:
#         raise http_exc
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

@router.get("/generate-answers/{question_id}")
def generate_answers(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return generate_answers_service(db, current_user, question_id)


# @router.get("/answers/{question_id}/versions")
# def get_answer_versions(
#     question_id: int,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     versions = db.query(ReviewerAnswerVersion).filter_by(
#         user_id=current_user.id,
#         ques_id=question_id
#     ).order_by(ReviewerAnswerVersion.generated_at.desc()).all()

#     return {
#         "question_id": question_id,
#         "versions": [
#             {
#                 "id": version.id,
#                 "answer": version.answer,
#                 "generated_at": version.generated_at
#             }
#             for version in versions
#         ]
#     }

@router.get("/answers/{question_id}/versions")
def get_answer_versions(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return answer_versions(db, current_user, question_id)



# @router.patch('/update-answer/{question_id}')
# def update_question( question_id: int,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)):
#     try:
#         assignment = db.query(RFPQuestion, Reviewer).join(
#             Reviewer, RFPQuestion.id == Reviewer.ques_id
#         ).filter(
#             Reviewer.user_id == current_user.id,
#             Reviewer.ques_id == question_id
#         ).first()
#         if assignment is None:
#                 raise HTTPException(status_code=403, detail="Question not assigned to current user")

#         question ,reviewer= assignment
#         context = get_similar_context(question.question_text)
#         answer = generate_answer_with_context(question.question_text, context)
#         reviewer.ans= answer

#         db.commit()  
#         return {
#             "message": "Answer has been updated successfully.",
#             "question_id": question.id,
#             "answer": answer
#         }
    
#     except HTTPException as http_exc:
#             raise http_exc 
#     except Exception as e:
#             raise HTTPException(status_code=500, detail=str(e))


@router.patch('/update-answer/{question_id}')
def update_answer_endpoint(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return update_answer_service(db, current_user, question_id)



# @router.patch('/submit')
# def submit(
#     question_id: int,
#     status: str,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     try:
#         if status.lower() not in ["not submitted", "submitted"]:
#             raise HTTPException(status_code=400, detail="Invalid submission status. Must be 'submitted' or 'not submitted'.")
#         reviewer = db.query(Reviewer).filter(
#             Reviewer.user_id == current_user.id,
#             Reviewer.ques_id == question_id
#         ).first()
#         print(status)

#         if reviewer is None:
#             raise HTTPException(status_code=403, detail="Question not assigned to current user")
#         if reviewer.submit_status == "process":
#             reviewer.submit_status = status
         
#         elif reviewer.submit_status is None:
#             raise HTTPException(status_code=403, detail="Question does not submit")
#         else:
       
#             reviewer.submit_status = status
#         reviewer.submitted_at = datetime.utcnow() 
#         db.commit()

#         return {
#             "message": "Submission successful",
#             "question_id": question_id,
#             "submit_status": status
#         }

#     except HTTPException as http_exc:
#         raise http_exc
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


@router.patch('/submit')
def submit(
    question_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return submit_service(db, current_user, question_id,status)


# @router.get('/get_user_status')
# def check(db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
#     try:
#         reviewers = db.query(Reviewer).filter(
#                 Reviewer.user_id == current_user.id
#             ).all()
        
#         data = []
#         for i in reviewers:
#             if i.submit_status is None:
#                 continue

#             data.append({
#                 "username": i.user.username,
#                 "question": i.question,
#                 "answer": i.ans,
#                 "status": i.submit_status,
#                 "submitted_at": i.submitted_at
#             })

#         return {
#             "message": "user Status fetched successfully",
#             "data": data
#         }

#     except HTTPException as http_exc:
#         raise http_exc
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

@router.get('/get_user_status')
def check(db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    return chech_service(db,current_user)



# @router.get('/filter-questions-by-user/{status}')
# def filter_questions_by_status(
#     status: str,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     try:
#         valid_statuses = ["submitted", "not submitted", "process"]
#         status = status.strip().lower()

#         if status not in valid_statuses:
#             raise HTTPException(status_code=400, detail="Invalid status. Must be one of: submitted, not submitted, process.")

#         reviewers = db.query(Reviewer).filter(
#             Reviewer.user_id == current_user.id
#         ).all()

#         if not reviewers:
#             raise HTTPException(status_code=404, detail="No questions assigned to this user.")

#         filtered_questions = []

#         for r in reviewers:
#             current_status = r.submit_status.strip().lower() if r.submit_status else "not submitted"
            
#             if current_status == status:
#                 filtered_questions.append({
#                     "question_id": r.ques_id,
#                     "question": r.question,
#                     "rfp_id": r.file_id
#                 })

#         return {
#             "user_id": current_user.id,
#             "status": status,
#             "count": len(filtered_questions),
#             "questions": filtered_questions
#         }

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


@router.get('/filter-questions-by-user/{status}')
def filter_questions_by_status(
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return filter_service(db, current_user,status)