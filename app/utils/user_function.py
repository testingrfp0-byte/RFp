from sqlalchemy.orm import Session
from app.models.rfp_models import RFPQuestion, Reviewer, User,ReviewerAnswerVersion
from fastapi import HTTPException
from app.services.llm_service import get_similar_context,generate_answer_with_context
from datetime import datetime
from app.api.routes.utils import clean_answer

def assigned_questions(db: Session, current_user: User):
    try:
        assignments = (
            db.query(RFPQuestion, Reviewer)
            .join(Reviewer, RFPQuestion.id == Reviewer.ques_id)
            .filter(Reviewer.user_id == current_user.id)
            .all()
        )

        results = []
        for question, reviewer in assignments:
            latest_answer = (
                db.query(ReviewerAnswerVersion)
                .filter_by(user_id=reviewer.user_id, ques_id=reviewer.ques_id)
                .order_by(ReviewerAnswerVersion.generated_at.desc())
                .first()
            )

            results.append({
                "user_id": reviewer.user_id, 
                "rfp_id": question.rfp_id,
                "filename": question.rfp.filename,
                "question_id": question.id,
                "question_text": question.question_text,
                "section": question.section,
                "status": reviewer.status,
                "assigned_at": question.assigned_at,
                "submit_status": reviewer.submit_status,
                "is_submitted": reviewer.submit_status == "submitted" or reviewer.submitted_at is not None,
                "answer_id": latest_answer.id if latest_answer else None,
                "answer": latest_answer.answer if latest_answer else None
            })

        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def generate_answers_service(db: Session, current_user: User, question_id: int):
    try:
        assignment = (
            db.query(RFPQuestion, Reviewer)
            .join(Reviewer, RFPQuestion.id == Reviewer.ques_id)
            .filter(
                Reviewer.user_id == current_user.id,
                Reviewer.ques_id == question_id
            )
            .first()
        )

        if assignment is None:
            raise HTTPException(status_code=403, detail="Question not assigned to current user")

        question, reviewer = assignment

        contexts, sources = get_similar_context(question.question_text)

        answer = generate_answer_with_context(question.question_text, contexts)
        answer = clean_answer(answer)

        version = ReviewerAnswerVersion(
            user_id=current_user.id,
            ques_id=question_id,
            answer=answer
        )
        db.add(version)
        reviewer.ans = answer
        db.commit()

        return {
            "question_id": question.id,
            "question_text": question.question_text,
            "answer": answer,
            "sources": sources 
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def answer_versions(db: Session, current_user: User, question_id: int):
    try:
        versions = (
            db.query(ReviewerAnswerVersion)
            .filter_by(user_id=current_user.id, ques_id=question_id)
            .order_by(ReviewerAnswerVersion.generated_at.desc())
            .all()
        )

        return {
            "question_id": question_id,
            "versions": [
                {
                    "id": version.id,
                    "answer": version.answer,
                    "generated_at": version.generated_at
                }
                for version in versions
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def update_answer_service(db: Session, current_user: User, question_id: int, new_answer: str):
    try:
        reviewer = (
            db.query(Reviewer)
            .filter(
                Reviewer.user_id == current_user.id,
                Reviewer.ques_id == question_id
            )
            .first()
        )

        if reviewer is None:
            raise HTTPException(status_code=403, detail="Question not assigned to current user")

        # print('before submit', reviewer.ans)

        if reviewer.ans:
            version = ReviewerAnswerVersion(
                user_id=current_user.id,
                ques_id=reviewer.ques_id,
                answer=new_answer,
            )
            
            db.add(version)

        # reviewer.ans = new_answer
        db.commit()     
        db.refresh(version)

        reviewer.ans = new_answer

        db.commit()
        db.refresh(reviewer)

        # print('after submit', reviewer.ans)

        return {
            "message": "Answer has been updated successfully.",
            "question_id": reviewer.ques_id,
            "current_answer": reviewer.ans
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

def submit_service(db: Session, current_user: User, question_id: int, status: str,):
    try:
        if status.lower() not in ["not submitted", "submitted"]:
            raise HTTPException(status_code=400, detail="Invalid submission status. Must be 'submitted' or 'not submitted'.")
        reviewer = db.query(Reviewer).filter(
            Reviewer.user_id == current_user.id,
            Reviewer.ques_id == question_id
        ).first()
        print(status)

        if reviewer is None:
            raise HTTPException(status_code=403, detail="Question not assigned to current user")
        if reviewer.submit_status == "process":
            reviewer.submit_status = status
         
        elif reviewer.submit_status is None:
            raise HTTPException(status_code=403, detail="Question does not submit")
        else:
       
            reviewer.submit_status = status
        reviewer.submitted_at = datetime.utcnow() 
        db.commit()

        return {
            "message": "Submission successful",
            "question_id": question_id,
            "answer": reviewer.ans ,
            "submit_status": status
        }

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
def chech_service(db: Session, current_user: User):
    try:
        reviewers = db.query(Reviewer).filter(
                Reviewer.user_id == current_user.id
            ).all()
        
        data = []
        for i in reviewers:
            if i.submit_status is None:
                continue

            data.append({
                "username": i.user.username,
                "question": i.question,
                "answer": i.ans,
                "status": i.submit_status,
                "submitted_at": i.submitted_at
            })

        return {
            "message": "user Status fetched successfully",
            "data": data
        }

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
def filter_service(db: Session, current_user: User,status: str):
    try:
        valid_statuses = ["submitted", "not submitted", "process"]
        status = status.strip().lower()

        if status not in valid_statuses:
            raise HTTPException(status_code=400, detail="Invalid status. Must be one of: submitted, not submitted, process.")
        
        reviewers = db.query(Reviewer).filter(
            Reviewer.user_id == current_user.id
        ).all()

        if not reviewers:
            raise HTTPException(status_code=404, detail="No questions assigned to this user.")

        filtered_questions = []

        for r in reviewers:
            current_status = r.submit_status.strip().lower() if r.submit_status else "not submitted"
            
            if current_status == status:
                filtered_questions.append({
                    "question_id": r.ques_id,
                    "question": r.question,
                    "rfp_id": r.file_id
                })

        return {
            "user_id": current_user.id,
            "status": status,
            "count": len(filtered_questions),
            "questions": filtered_questions
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




