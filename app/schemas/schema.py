from pydantic import BaseModel,Field
from datetime import datetime
from typing import List, Optional

class UpdateProfileRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    image_base64: Optional[str] = None
    image_name: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class user_register(BaseModel):
    username: str
    email: str
    password: str
    role:str
    mode: Optional[str] = None

class UserOut(BaseModel):
    user_id:int
    username: str
    email: str
    role: str
    is_verified: bool

    class Config:
        from_attributes = True

class FileDetails(BaseModel):
    id: int
    filename: str
    project_name: str | None = None
    category: str | None
    uploaded_at: datetime

    class Config:
        from_attributes = True

class CompanySummaryOut(BaseModel):
    summary_text: str
    class Config:
        from_attributes = True

class RFPQuestionOut(BaseModel):
    ques_id: int = Field(..., alias="id")
    question_text: str
    section: str

class Config:
        from_attributes = True
        validate_by_name = True

class RFPDocumentDetails(BaseModel):
    id: int
    filename: str
    uploaded_at: datetime
    summary: Optional[CompanySummaryOut]
    questions: List[RFPQuestionOut]

    class Config:
        from_attributes = True

class QuestionOut(BaseModel):
    id: int
    question_text: str

class GroupedRFPQuestionOut(BaseModel):
    section: Optional[str] = None
    questions: List[QuestionOut]

class RFPDocumentGroupedQuestionsOut(BaseModel):
    id: int
    filename: str
    uploaded_at: datetime
    summary: Optional[CompanySummaryOut]
    questions_by_section: List[GroupedRFPQuestionOut]

    class Config:
        from_attributes = True

class AssignReviewer(BaseModel):
    user_id: List[int]
    ques_ids: List[int]
    file_id: int
    status: str 

class NotificationRequest(BaseModel):
    user_id: List[int]    
    ques_ids: List[int]

class AssignedQuestionOut(BaseModel):
    question_id: int
    question_text: str
    section: Optional[str]

    class Config:
        from_attributes = True

class ReviewerOut(BaseModel):
    ques_id: int
    question: str
    user_id: int
    username: str

    class Config:
        from_attributes = True

class AdminEditRequest(BaseModel):
    question_id: int
    answer: str

class ForgotPasswordRequest(BaseModel):
    email: str  

class ResetPasswordRequest(BaseModel):
    email: str
    new_password: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)

class reviwerdelete(BaseModel):
    user_id: int
    role:str

class ChatInputRequest(BaseModel):
    user_id: int
    ques_id: int
    chat_message: str

class UpdateAnswerRequest(BaseModel):
    answer: str

class VerifyOtpRequest(BaseModel):
    email: str
    otp: str

class ReassignReviewerRequest(BaseModel):
    user_id: int
    ques_id: int
    file_id: int

class PasswordUpdateRequest(BaseModel):
    email: str
    old_password: str
    new_password: str

class QuestionInput(BaseModel):
    questions: Optional[List[str]] = None

class KeystoneCreateRequest(BaseModel):
    section: str
    field_group: Optional[str] = None
    field_detail: Optional[str] = None
    field_type: Optional[str] = None
    default_answer: Optional[str] = None

class KeystoneUpdateRequest(BaseModel):
    section: Optional[str] = None
    field_group: Optional[str] = None
    field_detail: Optional[str] = None
    field_type: Optional[str] = None
    default_answer: Optional[str] = None

class KeystoneDynamicFormRequest(BaseModel):
    section: Optional[str] = Field(None, alias="section")
    field_group: Optional[str] = Field(None, alias="field_group")
    field_detail: Optional[str] = Field(None, alias="field_detail")
    unnamed: Optional[str] = Field(None, alias="unnamed")
    ringer_answer: Optional[str] = Field(None, alias="ringer's_answer")

class KeystonePatchRequest(BaseModel):
    section: Optional[str] = None
    field_group: Optional[str] = None
    field_detail: Optional[str] = None
    unnamed: Optional[str] = None
    ringer_answer: Optional[str] = None