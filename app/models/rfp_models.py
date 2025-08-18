from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey,Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base
import enum

class RFPDocument(Base):
    __tablename__ = "rfp_documents"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=True) #new for local update
    category = Column(String, nullable=True)
    extracted_text = Column(Text)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    summary = relationship("CompanySummary", back_populates="rfp", uselist=False,cascade="all, delete-orphan")
    questions = relationship("RFPQuestion", back_populates="rfp",cascade="all, delete-orphan")
    admin_id = Column(Integer) 

    file_hash = Column(String, unique=True, nullable=False)


class CompanySummary(Base):
    __tablename__ = "company_summaries"
    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer) 
    rfp_id = Column(Integer, ForeignKey("rfp_documents.id"))
    summary_text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    rfp = relationship("RFPDocument", back_populates="summary")

class RFPQuestion(Base):
    __tablename__ = "rfp_questions"
    id = Column(Integer, primary_key=True, index=True)
    rfp_id = Column(Integer, ForeignKey("rfp_documents.id"))
    question_text = Column(Text)
    section = Column(String) 
    assigned_user_id = Column(Integer, nullable=True)         
    assigned_username = Column(String, nullable=True)         
    assignment_status = Column(String, nullable=True)         
    assigned_at = Column(DateTime, nullable=True)  
    rfp = relationship("RFPDocument", back_populates="questions")
    reviewers = relationship("Reviewer", back_populates="question_ref", foreign_keys="Reviewer.ques_id",cascade="all, delete-orphan")
    answer_versions = relationship(
        "ReviewerAnswerVersion",
        back_populates="question",
        cascade="all, delete-orphan"
    )
    admin_id = Column(Integer)     
    
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String, nullable=False) 
    email = Column(String,nullable=False)
    role =Column(String,nullable=False)
    reviews = relationship("Reviewer", back_populates="user")


class Reviewer(Base):
    __tablename__ = "reviewer"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    ques_id = Column(Integer, ForeignKey("rfp_questions.id"), primary_key=True)
    question = Column(Text)
    ans = Column(Text)
    status = Column(Text)
    submit_status=Column(Text)
    submitted_at = Column(DateTime, nullable=True) 
    time = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="reviews", foreign_keys=[user_id])
    question_ref = relationship("RFPQuestion", back_populates="reviewers", foreign_keys=[ques_id])
    file_id = Column(Integer)
    admin_id = Column(Integer)    
 
class ReviewerAnswerVersion(Base):
    __tablename__ = "reviewer_answer_versions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    ques_id = Column(Integer, ForeignKey("rfp_questions.id"))
    answer = Column(Text)
    generated_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    question = relationship("RFPQuestion", back_populates="answer_versions")



