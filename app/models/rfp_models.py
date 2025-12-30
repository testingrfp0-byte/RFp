from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey,ForeignKeyConstraint,Boolean,LargeBinary
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy.sql import func
from app.db.database import Base

class RFPDocument(Base):
    __tablename__ = "rfp_documents"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=True)
    category = Column(String, nullable=True)
    extracted_text = Column(Text)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    admin_id = Column(Integer) 
    file_hash = Column(String, unique=True, nullable=False)
    project_name = Column(String, nullable=True)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)

    summary = relationship(
        "CompanySummary",
        back_populates="rfp",
        uselist=False,
        cascade="all, delete-orphan"
    )
    questions = relationship(
        "RFPQuestion",
        back_populates="rfp",
        cascade="all, delete-orphan"
    )

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
    admin_id = Column(Integer)     

    rfp = relationship("RFPDocument", back_populates="questions")
    reviewers = relationship(
        "Reviewer",
        back_populates="question_ref",
        foreign_keys="Reviewer.ques_id",
        cascade="all, delete-orphan"
    )
    answer_versions = relationship(
        "ReviewerAnswerVersion",
        back_populates="question",
        cascade="all, delete-orphan",
        overlaps="reviewer"
    )

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String, nullable=False) 
    email = Column(String, nullable=False)
    role = Column(String, nullable=False)
    reset_otp = Column(String, nullable=True) 
    otp_expiry = Column(DateTime, nullable=True)
    is_verified = Column(Boolean, default=False)
    image = Column(String, nullable=True)
    image_bytea = Column(LargeBinary, nullable=True)

    reviews = relationship(
        "Reviewer",
        back_populates="user",
        cascade="all, delete-orphan",  
        passive_deletes=True          
    )

class Reviewer(Base):
    __tablename__ = "reviewer"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    ques_id = Column(Integer, ForeignKey("rfp_questions.id"), primary_key=True)
    question = Column(Text)
    ans = Column(Text)
    status = Column(Text)
    submit_status = Column(Text)
    submitted_at = Column(DateTime, nullable=True) 
    time = Column(DateTime, default=datetime.utcnow)
    file_id = Column(Integer)
    admin_id = Column(Integer)    

    user = relationship(
        "User",
        back_populates="reviews",
        foreign_keys=[user_id]
    )
    question_ref = relationship(
        "RFPQuestion",
        back_populates="reviewers",
        foreign_keys=[ques_id]
    )
    answer_versions = relationship(
        "ReviewerAnswerVersion",
        back_populates="reviewer",
        cascade="all, delete-orphan",
        passive_deletes=True,
        overlaps="question,user"
    )

class ReviewerAnswerVersion(Base):
    __tablename__ = "reviewer_answer_versions"

    id = Column(Integer, primary_key=True, index=True )
    user_id = Column(Integer, ForeignKey("users.id"))
    ques_id = Column(Integer, ForeignKey("rfp_questions.id"))
    answer = Column(Text)
    generated_at = Column(DateTime, default=datetime.utcnow)

    user = relationship(
        "User",
        overlaps="reviews,answer_versions"
    )
    question = relationship(
        "RFPQuestion",
        back_populates="answer_versions",
        overlaps="reviewer"
    )
    reviewer = relationship(
        "Reviewer",
        back_populates="answer_versions",
        primaryjoin="and_(ReviewerAnswerVersion.user_id == Reviewer.user_id, ReviewerAnswerVersion.ques_id == Reviewer.ques_id)",
        overlaps="question,user"
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "ques_id"],
            ["reviewer.user_id", "reviewer.ques_id"],
            ondelete="CASCADE"
        ),
    )
   
class KeystoneData(Base):
    __tablename__ = "keystone_data"

    id = Column(Integer, primary_key=True, index=True)
    section = Column(String, nullable=False)         
    field_group = Column(String, nullable=True)  
    field_detail = Column(String, nullable=True)   
    field_type = Column(String, nullable=True)   
    default_answer = Column(Text, nullable=True)  
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
