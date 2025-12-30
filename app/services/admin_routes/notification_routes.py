from fastapi import Depends, HTTPException, APIRouter
from fastapi_mail import FastMail, MessageSchema, MessageType
from sqlalchemy.orm import Session

from app.config import mail_config, LOGIN_URL
from app.db.database import get_db
from app.schemas.schema import NotificationRequest
from app.models.rfp_models import User, Reviewer, RFPQuestion

router = APIRouter()

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