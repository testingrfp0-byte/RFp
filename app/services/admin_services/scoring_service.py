from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.rfp_models import RFPQuestion, Reviewer
from app.services.llm_services.llm_service import analyze_answer_score_only

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

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")