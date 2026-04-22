from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.rfp_models import RFPQuestion, Reviewer
from app.services.llm_services.llm_service import analyze_answer_score_only

async def analyze_overall_score_service(rfp_id: int, db: AsyncSession):
    try:
        questions_result = await db.execute(
            select(RFPQuestion).where(RFPQuestion.rfp_id == rfp_id)
        )
        questions = questions_result.scalars().all()
        if not questions:
            raise HTTPException(status_code=404, detail="No questions found for this RFP.")

        incomplete_questions = []
        for question in questions:
            reviewers_result = await db.execute(
                select(Reviewer).where(
                    Reviewer.ques_id == question.id,
                    Reviewer.ans.is_not(None),
                    Reviewer.ans != ""
                )
            )
            reviewers = reviewers_result.scalars().all()
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
            reviewers_result = await db.execute(
                select(Reviewer).where(
                    Reviewer.ques_id == question.id,
                    Reviewer.ans.is_not(None),
                    Reviewer.ans != ""
                )
            )
            reviewers = reviewers_result.scalars().all()

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
