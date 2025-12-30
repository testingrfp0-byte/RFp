"""
Data Transfer Objects for user-related operations
Defines the structure of data being transferred between layers
"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel


class AssignedQuestionDTO(BaseModel):
    """DTO for assigned question information"""
    user_id: int
    rfp_id: int
    filename: str
    project_name: str
    question_id: int
    question_text: str
    section: Optional[str]
    status: str
    assigned_at: Optional[datetime]
    submit_status: Optional[str]
    is_submitted: bool
    answer_id: Optional[int]
    answer: Optional[str]


class AnswerVersionDTO(BaseModel):
    """DTO for answer version information"""
    id: int
    answer: str
    generated_at: datetime


class GeneratedAnswerDTO(BaseModel):
    """DTO for generated answer response"""
    question_id: int
    question_text: str
    rfp_id: int
    answer: str
    sources: List


class UpdateAnswerDTO(BaseModel):
    """DTO for update answer response"""
    message: str
    question_id: int
    current_answer: str


class SubmitResponseDTO(BaseModel):
    """DTO for submission response"""
    message: str
    question_id: int
    answer: str
    submit_status: str


class UserStatusDataDTO(BaseModel):
    """DTO for user status data"""
    username: str
    question: object
    answer: Optional[str]
    status: str
    submitted_at: Optional[datetime]


class FilteredQuestionDTO(BaseModel):
    """DTO for filtered question"""
    question_id: int
    question: object
    rfp_id: int


class AnalyzeQuestionDTO(BaseModel):
    """DTO for analyzed question response"""
    rfp_id: int
    question_id: int
    question_text: str
    user_id: int
    answer: str
    score: float