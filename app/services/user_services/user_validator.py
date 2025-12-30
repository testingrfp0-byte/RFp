"""
Validation layer for user-related operations
Handles all business rule validations
"""
from fastapi import HTTPException, status


class UserValidator:
    """Validator for user-related operations"""
    
    VALID_STATUSES = ["submitted", "not submitted", "process"]
    
    @staticmethod
    def validate_assignment_exists(assignment):
        """Validate that a question assignment exists"""
        if assignment is None:
            raise HTTPException(
                status_code=403, 
                detail="Question not assigned to current user"
            )
    
    @staticmethod
    def validate_rfp_document_exists(rfp_document):
        """Validate that RFP document exists"""
        if not rfp_document:
            raise HTTPException(
                status_code=404, 
                detail="RFP Document not found"
            )
    
    @staticmethod
    def validate_reviewer_exists(reviewer):
        """Validate that reviewer exists"""
        if reviewer is None:
            raise HTTPException(
                status_code=403, 
                detail="Question not assigned to current user"
            )
    
    @staticmethod
    def validate_submission_status(status_value: str):
        """Validate submission status"""
        if status_value.lower() not in ["not submitted", "submitted"]:
            raise HTTPException(
                status_code=400, 
                detail="Invalid submission status. Must be 'submitted' or 'not submitted'."
            )
    
    @staticmethod
    def validate_submit_status_exists(reviewer):
        """Validate that submit status exists"""
        if reviewer.submit_status is None:
            raise HTTPException(
                status_code=403, 
                detail="Question does not submit"
            )
    
    @staticmethod
    def validate_filter_status(status_value: str) -> str:
        """Validate and normalize filter status"""
        status_value = status_value.strip().lower()
        
        if status_value not in UserValidator.VALID_STATUSES:
            raise HTTPException(
                status_code=400, 
                detail="Invalid status. Must be one of: submitted, not submitted, process."
            )
        
        return status_value
    
    @staticmethod
    def validate_question_exists(question):
        """Validate that question exists"""
        if not question:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Question not found for the provided RFP."
            )