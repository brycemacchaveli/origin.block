"""
Loan Origination API endpoints for blockchain financial platform.

This module provides REST API endpoints for loan application management,
including creation, retrieval, status updates, approval/rejection, and history tracking.
"""

import json
import secrets
import hashlib
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form
from pydantic import BaseModel, Field, validator
import structlog

from shared.auth import (
    get_current_user, 
    require_permissions, 
    Actor, 
    Permission
)
from shared.database import db_utils, LoanApplicationModel, CustomerModel, LoanDocumentModel
from shared.fabric_gateway import get_fabric_gateway, ChaincodeClient, ChaincodeType

logger = structlog.get_logger(__name__)

router = APIRouter()


class LoanType(str, Enum):
    """Supported loan types."""
    PERSONAL = "PERSONAL"
    MORTGAGE = "MORTGAGE"
    BUSINESS = "BUSINESS"
    AUTO = "AUTO"
    EDUCATION = "EDUCATION"


class ApplicationStatus(str, Enum):
    """Loan application status values."""
    SUBMITTED = "SUBMITTED"
    UNDERWRITING = "UNDERWRITING"
    CREDIT_APPROVAL = "CREDIT_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DISBURSED = "DISBURSED"
    CANCELLED = "CANCELLED"


class LoanApplicationCreate(BaseModel):
    """Schema for creating a new loan application."""
    customer_id: str = Field(..., description="Customer ID for the loan application")
    requested_amount: float = Field(..., gt=0, description="Requested loan amount")
    loan_type: LoanType = Field(..., description="Type of loan")
    introducer_id: Optional[str] = Field(None, description="External partner/introducer ID")
    additional_info: Optional[Dict[str, Any]] = Field(None, description="Additional application information")
    
    @validator('requested_amount')
    def validate_amount(cls, v):
        """Validate loan amount is reasonable."""
        if v <= 0:
            raise ValueError('Requested amount must be greater than 0')
        if v > 10_000_000:  # 10M limit for demo
            raise ValueError('Requested amount exceeds maximum limit')
        return v


class LoanApplicationUpdate(BaseModel):
    """Schema for updating loan application details."""
    requested_amount: Optional[float] = Field(None, gt=0, description="Updated requested amount")
    loan_type: Optional[LoanType] = Field(None, description="Updated loan type")
    additional_info: Optional[Dict[str, Any]] = Field(None, description="Updated additional information")


class LoanStatusUpdate(BaseModel):
    """Schema for updating loan application status."""
    new_status: ApplicationStatus = Field(..., description="New status for the loan application")
    notes: Optional[str] = Field(None, description="Notes about the status change")
    
    @validator('new_status')
    def validate_status_transition(cls, v):
        """Basic status validation - more complex logic would be in business layer."""
        if v not in ApplicationStatus:
            raise ValueError(f'Invalid status: {v}')
        return v


class LoanApprovalRequest(BaseModel):
    """Schema for loan approval."""
    approval_amount: float = Field(..., gt=0, description="Approved loan amount")
    notes: Optional[str] = Field(None, description="Approval notes")
    conditions: Optional[List[str]] = Field(None, description="Approval conditions")
    
    @validator('approval_amount')
    def validate_approval_amount(cls, v):
        """Validate approval amount."""
        if v <= 0:
            raise ValueError('Approval amount must be greater than 0')
        if v > 10_000_000:  # 10M limit for demo
            raise ValueError('Approval amount exceeds maximum limit')
        return v


class LoanRejectionRequest(BaseModel):
    """Schema for loan rejection."""
    rejection_reason: str = Field(..., description="Reason for rejection")
    notes: Optional[str] = Field(None, description="Additional rejection notes")


class LoanApplicationResponse(BaseModel):
    """Schema for loan application response."""
    loan_application_id: str
    customer_id: str
    application_date: datetime
    requested_amount: float
    loan_type: str
    application_status: str
    introducer_id: Optional[str]
    current_owner_actor_id: int
    approval_amount: Optional[float]
    rejection_reason: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class LoanHistoryResponse(BaseModel):
    """Schema for loan application history response."""
    id: int
    change_type: str
    previous_status: Optional[str]
    new_status: Optional[str]
    field_name: Optional[str]
    old_value: Optional[str]
    new_value: Optional[str]
    changed_by_actor_id: int
    blockchain_transaction_id: Optional[str]
    timestamp: datetime
    notes: Optional[str]
    
    class Config:
        from_attributes = True


def _generate_loan_application_id() -> str:
    """Generate a unique loan application ID."""
    return f"LOAN_{secrets.token_hex(6).upper()}"


def _validate_customer_exists(customer_id: str) -> CustomerModel:
    """Validate that customer exists and return customer model."""
    customer = db_utils.get_customer_by_customer_id(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer {customer_id} not found"
        )
    return customer


def _validate_loan_exists(loan_application_id: str) -> LoanApplicationModel:
    """Validate that loan application exists and return loan model."""
    loan = db_utils.get_loan_by_loan_id(loan_application_id)
    if not loan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Loan application {loan_application_id} not found"
        )
    return loan


def _check_loan_access_permissions(loan: LoanApplicationModel, current_user: Actor) -> None:
    """Check if current user has access to the loan application."""
    # For now, allow access if user has READ_LOAN_APPLICATION permission
    # In a real system, you might check ownership, role-based access, etc.
    if Permission.READ_LOAN_APPLICATION not in current_user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to access this loan application"
        )


def _calculate_file_hash(file_content: bytes) -> str:
    """Calculate SHA256 hash of file content."""
    return hashlib.sha256(file_content).hexdigest()


def _generate_document_id() -> str:
    """Generate a unique document ID."""
    return f"DOC_{secrets.token_hex(8).upper()}"


def _validate_file_upload(file: UploadFile) -> None:
    """Validate uploaded file."""
    # Check file size (10MB limit)
    max_size = 10 * 1024 * 1024  # 10MB
    if file.size and file.size > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds 10MB limit"
        )
    
    # Check file type (basic validation)
    allowed_types = {
        'application/pdf',
        'image/jpeg',
        'image/png',
        'image/tiff',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    }
    
    if file.content_type and file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file.content_type} not allowed"
        )


@router.post("/", response_model=LoanApplicationResponse, status_code=status.HTTP_201_CREATED)
async def submit_loan_application(
    loan_data: LoanApplicationCreate,
    current_user: Actor = Depends(require_permissions(Permission.CREATE_LOAN_APPLICATION))
):
    """
    Submit a new loan application.
    
    Creates a new loan application record in both the database and blockchain.
    Validates customer existence and performs initial compliance checks.
    """
    try:
        logger.info("Submitting new loan application", 
                   customer_id=loan_data.customer_id,
                   amount=loan_data.requested_amount,
                   loan_type=loan_data.loan_type,
                   actor_id=current_user.actor_id)
        
        # Validate customer exists
        customer = _validate_customer_exists(loan_data.customer_id)
        
        # Get current user's database record
        db_actor = db_utils.get_actor_by_actor_id(current_user.actor_id)
        if not db_actor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Actor not found in database"
            )
        
        # Generate loan application ID
        loan_application_id = _generate_loan_application_id()
        
        # Prepare loan data for database
        loan_db_data = {
            "loan_application_id": loan_application_id,
            "customer_id": customer.id,  # Use database ID for foreign key
            "application_date": datetime.utcnow(),
            "requested_amount": loan_data.requested_amount,
            "loan_type": loan_data.loan_type.value,
            "application_status": ApplicationStatus.SUBMITTED.value,
            "introducer_id": loan_data.introducer_id,
            "current_owner_actor_id": db_actor.id,
            "created_by_actor_id": db_actor.id
        }
        
        # Create loan application in database
        db_loan = db_utils.create_loan_application(loan_db_data)
        
        # Prepare data for blockchain
        blockchain_data = {
            "loanApplicationID": loan_application_id,
            "customerID": loan_data.customer_id,  # Use customer_id string for blockchain
            "applicationDate": datetime.utcnow().isoformat(),
            "requestedAmount": loan_data.requested_amount,
            "loanType": loan_data.loan_type.value,
            "applicationStatus": ApplicationStatus.SUBMITTED.value,
            "introducerID": loan_data.introducer_id or "",
            "currentOwnerActor": current_user.actor_id,
            "additionalInfo": json.dumps(loan_data.additional_info or {})
        }
        
        # Submit to blockchain
        try:
            gateway = await get_fabric_gateway()
            chaincode_client = ChaincodeClient(gateway, ChaincodeType.LOAN)
            
            blockchain_result = await gateway.invoke_chaincode(
                "loan",
                "SubmitApplication",
                [json.dumps(blockchain_data)]
            )
            
            logger.info("Loan application submitted to blockchain",
                       loan_id=loan_application_id,
                       transaction_id=blockchain_result.get("transaction_id"))
            
        except Exception as e:
            logger.error("Failed to submit loan to blockchain",
                        loan_id=loan_application_id,
                        error=str(e))
            # In a real system, you might want to rollback the database transaction
            # For now, we'll continue with the database record
        
        # Convert database model to response
        response_data = LoanApplicationResponse(
            loan_application_id=db_loan.loan_application_id,
            customer_id=loan_data.customer_id,  # Use original customer_id string
            application_date=db_loan.application_date,
            requested_amount=db_loan.requested_amount,
            loan_type=db_loan.loan_type,
            application_status=db_loan.application_status,
            introducer_id=db_loan.introducer_id,
            current_owner_actor_id=db_loan.current_owner_actor_id,
            approval_amount=db_loan.approval_amount,
            rejection_reason=db_loan.rejection_reason,
            created_at=db_loan.created_at,
            updated_at=db_loan.updated_at
        )
        
        logger.info("Loan application submitted successfully",
                   loan_id=loan_application_id)
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to submit loan application", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit loan application"
        )


@router.get("/{loan_id}", response_model=LoanApplicationResponse)
async def get_loan_application(
    loan_id: str,
    current_user: Actor = Depends(require_permissions(Permission.READ_LOAN_APPLICATION))
):
    """
    Retrieve a loan application by ID.
    
    Returns loan application details with access control based on user permissions.
    """
    try:
        logger.info("Retrieving loan application", 
                   loan_id=loan_id,
                   actor_id=current_user.actor_id)
        
        # Validate loan exists
        loan = _validate_loan_exists(loan_id)
        
        # Check access permissions
        _check_loan_access_permissions(loan, current_user)
        
        # Get customer information by querying with the foreign key
        with db_utils.db_manager.session_scope() as session:
            customer = session.query(CustomerModel).filter(
                CustomerModel.id == loan.customer_id
            ).first()
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Customer data inconsistency"
                )
            customer_id = customer.customer_id
        
        # Convert to response format
        response_data = LoanApplicationResponse(
            loan_application_id=loan.loan_application_id,
            customer_id=customer_id,
            application_date=loan.application_date,
            requested_amount=loan.requested_amount,
            loan_type=loan.loan_type,
            application_status=loan.application_status,
            introducer_id=loan.introducer_id,
            current_owner_actor_id=loan.current_owner_actor_id,
            approval_amount=loan.approval_amount,
            rejection_reason=loan.rejection_reason,
            created_at=loan.created_at,
            updated_at=loan.updated_at
        )
        
        logger.info("Loan application retrieved successfully", loan_id=loan_id)
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve loan application", 
                    loan_id=loan_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve loan application"
        )


@router.put("/{loan_id}/status", response_model=LoanApplicationResponse)
async def update_loan_status(
    loan_id: str,
    status_update: LoanStatusUpdate,
    current_user: Actor = Depends(require_permissions(Permission.UPDATE_LOAN_APPLICATION))
):
    """
    Update loan application status.
    
    Updates the status of a loan application with proper validation and audit trail.
    """
    try:
        logger.info("Updating loan application status",
                   loan_id=loan_id,
                   new_status=status_update.new_status,
                   actor_id=current_user.actor_id)
        
        # Validate loan exists
        loan = _validate_loan_exists(loan_id)
        
        # Get current user's database record
        db_actor = db_utils.get_actor_by_actor_id(current_user.actor_id)
        if not db_actor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Actor not found in database"
            )
        
        # Validate status transition (basic validation)
        old_status = loan.application_status
        new_status = status_update.new_status.value
        
        if old_status == new_status:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Loan is already in {new_status} status"
            )
        
        # Update status in database with history tracking
        success = db_utils.update_loan_status(
            loan_id,
            new_status,
            db_actor.id,
            status_update.notes
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update loan status in database"
            )
        
        # Update blockchain record
        try:
            gateway = await get_fabric_gateway()
            chaincode_client = ChaincodeClient(gateway, ChaincodeType.LOAN)
            
            blockchain_data = {
                "loanApplicationID": loan_id,
                "newStatus": new_status,
                "updatedBy": current_user.actor_id,
                "notes": status_update.notes or "",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            blockchain_result = await gateway.invoke_chaincode(
                "loan",
                "UpdateStatus",
                [json.dumps(blockchain_data)]
            )
            
            logger.info("Loan status updated in blockchain",
                       loan_id=loan_id,
                       transaction_id=blockchain_result.get("transaction_id"))
            
        except Exception as e:
            logger.error("Failed to update loan status in blockchain",
                        loan_id=loan_id,
                        error=str(e))
            # Continue with database update even if blockchain fails
        
        # Retrieve updated loan
        updated_loan = _validate_loan_exists(loan_id)
        customer = db_utils.get_customer_by_customer_id(updated_loan.customer.customer_id)
        
        response_data = LoanApplicationResponse(
            loan_application_id=updated_loan.loan_application_id,
            customer_id=customer.customer_id,
            application_date=updated_loan.application_date,
            requested_amount=updated_loan.requested_amount,
            loan_type=updated_loan.loan_type,
            application_status=updated_loan.application_status,
            introducer_id=updated_loan.introducer_id,
            current_owner_actor_id=updated_loan.current_owner_actor_id,
            approval_amount=updated_loan.approval_amount,
            rejection_reason=updated_loan.rejection_reason,
            created_at=updated_loan.created_at,
            updated_at=updated_loan.updated_at
        )
        
        logger.info("Loan status updated successfully",
                   loan_id=loan_id,
                   old_status=old_status,
                   new_status=new_status)
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update loan status", 
                    loan_id=loan_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update loan status"
        )


@router.post("/{loan_id}/approve", response_model=LoanApplicationResponse)
async def approve_loan(
    loan_id: str,
    approval_request: LoanApprovalRequest,
    current_user: Actor = Depends(require_permissions(Permission.APPROVE_LOAN))
):
    """
    Approve a loan application.
    
    Approves a loan application with specified amount and conditions.
    """
    try:
        logger.info("Approving loan application",
                   loan_id=loan_id,
                   approval_amount=approval_request.approval_amount,
                   actor_id=current_user.actor_id)
        
        # Validate loan exists
        loan = _validate_loan_exists(loan_id)
        
        # Validate current status allows approval
        if loan.application_status in [ApplicationStatus.APPROVED.value, ApplicationStatus.DISBURSED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve loan in {loan.application_status} status"
            )
        
        if loan.application_status == ApplicationStatus.REJECTED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot approve a rejected loan"
            )
        
        # Get current user's database record
        db_actor = db_utils.get_actor_by_actor_id(current_user.actor_id)
        if not db_actor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Actor not found in database"
            )
        
        # Update loan in database
        with db_utils.db_manager.session_scope() as session:
            db_loan = session.query(LoanApplicationModel).filter(
                LoanApplicationModel.loan_application_id == loan_id
            ).first()
            
            if not db_loan:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Loan not found"
                )
            
            old_status = db_loan.application_status
            db_loan.application_status = ApplicationStatus.APPROVED.value
            db_loan.approval_amount = approval_request.approval_amount
            db_loan.updated_at = datetime.utcnow()
            
            # Create history record
            from shared.database import LoanApplicationHistoryModel
            history = LoanApplicationHistoryModel(
                loan_application_id=db_loan.id,
                change_type='APPROVAL',
                previous_status=old_status,
                new_status=ApplicationStatus.APPROVED.value,
                field_name='approval_amount',
                old_value=str(db_loan.approval_amount) if db_loan.approval_amount else None,
                new_value=str(approval_request.approval_amount),
                changed_by_actor_id=db_actor.id,
                notes=approval_request.notes
            )
            session.add(history)
        
        # Update blockchain record
        try:
            gateway = await get_fabric_gateway()
            chaincode_client = ChaincodeClient(gateway, ChaincodeType.LOAN)
            
            blockchain_data = {
                "loanApplicationID": loan_id,
                "approvalAmount": approval_request.approval_amount,
                "approvedBy": current_user.actor_id,
                "notes": approval_request.notes or "",
                "conditions": approval_request.conditions or [],
                "timestamp": datetime.utcnow().isoformat()
            }
            
            blockchain_result = await gateway.invoke_chaincode(
                "loan",
                "ApproveLoan",
                [json.dumps(blockchain_data)]
            )
            
            logger.info("Loan approval recorded in blockchain",
                       loan_id=loan_id,
                       transaction_id=blockchain_result.get("transaction_id"))
            
        except Exception as e:
            logger.error("Failed to record loan approval in blockchain",
                        loan_id=loan_id,
                        error=str(e))
        
        # Retrieve updated loan
        updated_loan = _validate_loan_exists(loan_id)
        customer = db_utils.get_customer_by_customer_id(updated_loan.customer.customer_id)
        
        response_data = LoanApplicationResponse(
            loan_application_id=updated_loan.loan_application_id,
            customer_id=customer.customer_id,
            application_date=updated_loan.application_date,
            requested_amount=updated_loan.requested_amount,
            loan_type=updated_loan.loan_type,
            application_status=updated_loan.application_status,
            introducer_id=updated_loan.introducer_id,
            current_owner_actor_id=updated_loan.current_owner_actor_id,
            approval_amount=updated_loan.approval_amount,
            rejection_reason=updated_loan.rejection_reason,
            created_at=updated_loan.created_at,
            updated_at=updated_loan.updated_at
        )
        
        logger.info("Loan approved successfully",
                   loan_id=loan_id,
                   approval_amount=approval_request.approval_amount)
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to approve loan", 
                    loan_id=loan_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve loan"
        )


@router.post("/{loan_id}/reject", response_model=LoanApplicationResponse)
async def reject_loan(
    loan_id: str,
    rejection_request: LoanRejectionRequest,
    current_user: Actor = Depends(require_permissions(Permission.REJECT_LOAN))
):
    """
    Reject a loan application.
    
    Rejects a loan application with specified reason.
    """
    try:
        logger.info("Rejecting loan application",
                   loan_id=loan_id,
                   reason=rejection_request.rejection_reason,
                   actor_id=current_user.actor_id)
        
        # Validate loan exists
        loan = _validate_loan_exists(loan_id)
        
        # Validate current status allows rejection
        if loan.application_status in [ApplicationStatus.APPROVED.value, ApplicationStatus.DISBURSED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reject loan in {loan.application_status} status"
            )
        
        if loan.application_status == ApplicationStatus.REJECTED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Loan is already rejected"
            )
        
        # Get current user's database record
        db_actor = db_utils.get_actor_by_actor_id(current_user.actor_id)
        if not db_actor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Actor not found in database"
            )
        
        # Update loan in database
        with db_utils.db_manager.session_scope() as session:
            db_loan = session.query(LoanApplicationModel).filter(
                LoanApplicationModel.loan_application_id == loan_id
            ).first()
            
            if not db_loan:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Loan not found"
                )
            
            old_status = db_loan.application_status
            db_loan.application_status = ApplicationStatus.REJECTED.value
            db_loan.rejection_reason = rejection_request.rejection_reason
            db_loan.updated_at = datetime.utcnow()
            
            # Create history record
            from shared.database import LoanApplicationHistoryModel
            history = LoanApplicationHistoryModel(
                loan_application_id=db_loan.id,
                change_type='REJECTION',
                previous_status=old_status,
                new_status=ApplicationStatus.REJECTED.value,
                field_name='rejection_reason',
                old_value=db_loan.rejection_reason,
                new_value=rejection_request.rejection_reason,
                changed_by_actor_id=db_actor.id,
                notes=rejection_request.notes
            )
            session.add(history)
        
        # Update blockchain record
        try:
            gateway = await get_fabric_gateway()
            chaincode_client = ChaincodeClient(gateway, ChaincodeType.LOAN)
            
            blockchain_data = {
                "loanApplicationID": loan_id,
                "rejectionReason": rejection_request.rejection_reason,
                "rejectedBy": current_user.actor_id,
                "notes": rejection_request.notes or "",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            blockchain_result = await gateway.invoke_chaincode(
                "loan",
                "RejectLoan",
                [json.dumps(blockchain_data)]
            )
            
            logger.info("Loan rejection recorded in blockchain",
                       loan_id=loan_id,
                       transaction_id=blockchain_result.get("transaction_id"))
            
        except Exception as e:
            logger.error("Failed to record loan rejection in blockchain",
                        loan_id=loan_id,
                        error=str(e))
        
        # Retrieve updated loan
        updated_loan = _validate_loan_exists(loan_id)
        customer = db_utils.get_customer_by_customer_id(updated_loan.customer.customer_id)
        
        response_data = LoanApplicationResponse(
            loan_application_id=updated_loan.loan_application_id,
            customer_id=customer.customer_id,
            application_date=updated_loan.application_date,
            requested_amount=updated_loan.requested_amount,
            loan_type=updated_loan.loan_type,
            application_status=updated_loan.application_status,
            introducer_id=updated_loan.introducer_id,
            current_owner_actor_id=updated_loan.current_owner_actor_id,
            approval_amount=updated_loan.approval_amount,
            rejection_reason=updated_loan.rejection_reason,
            created_at=updated_loan.created_at,
            updated_at=updated_loan.updated_at
        )
        
        logger.info("Loan rejected successfully",
                   loan_id=loan_id,
                   reason=rejection_request.rejection_reason)
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to reject loan", 
                    loan_id=loan_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject loan"
        )


class LoanHistoryFilter(BaseModel):
    """Schema for filtering loan history."""
    change_type: Optional[str] = Field(None, description="Filter by change type")
    actor_id: Optional[int] = Field(None, description="Filter by actor who made the change")
    from_date: Optional[datetime] = Field(None, description="Filter from this date")
    to_date: Optional[datetime] = Field(None, description="Filter to this date")
    status: Optional[str] = Field(None, description="Filter by status changes")


class PaginatedLoanHistoryResponse(BaseModel):
    """Schema for paginated loan history response."""
    items: List[LoanHistoryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


class AuditReportRequest(BaseModel):
    """Schema for audit report generation request."""
    report_type: str = Field(..., description="Type of audit report")
    from_date: Optional[datetime] = Field(None, description="Report start date")
    to_date: Optional[datetime] = Field(None, description="Report end date")
    include_blockchain_verification: bool = Field(True, description="Include blockchain integrity verification")
    format: str = Field("json", description="Report format (json, csv)")


class AuditReportResponse(BaseModel):
    """Schema for audit report response."""
    report_id: str
    report_type: str
    generated_at: datetime
    total_records: int
    integrity_verified: bool
    blockchain_hash_matches: int
    data: Dict[str, Any]
    download_url: Optional[str] = None


class DocumentType(str, Enum):
    """Supported document types."""
    IDENTITY = "IDENTITY"
    INCOME_PROOF = "INCOME_PROOF"
    BANK_STATEMENT = "BANK_STATEMENT"
    COLLATERAL = "COLLATERAL"
    OTHER = "OTHER"


class DocumentStatus(str, Enum):
    """Document verification status values."""
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class DocumentUploadRequest(BaseModel):
    """Schema for document upload metadata."""
    document_type: DocumentType = Field(..., description="Type of document")
    document_name: str = Field(..., description="Name of the document")
    
    @validator('document_name')
    def validate_document_name(cls, v):
        """Validate document name."""
        if not v or len(v.strip()) == 0:
            raise ValueError('Document name cannot be empty')
        if len(v) > 255:
            raise ValueError('Document name too long')
        return v.strip()


class LoanDocumentResponse(BaseModel):
    """Schema for loan document response."""
    id: int
    loan_application_id: str
    document_type: str
    document_name: str
    document_hash: str
    file_size: Optional[int]
    mime_type: Optional[str]
    verification_status: str
    uploaded_by_actor_id: int
    blockchain_record_hash: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DocumentStatusUpdate(BaseModel):
    """Schema for updating document status."""
    verification_status: DocumentStatus = Field(..., description="New verification status")
    notes: Optional[str] = Field(None, description="Notes about the status change")


@router.get("/{loan_id}/history", response_model=PaginatedLoanHistoryResponse)
async def get_loan_history(
    loan_id: str,
    page: int = 1,
    page_size: int = 50,
    change_type: Optional[str] = None,
    actor_id: Optional[int] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    status: Optional[str] = None,
    verify_integrity: bool = False,
    current_user: Actor = Depends(require_permissions(Permission.READ_LOAN_HISTORY))
):
    """
    Get loan application history with filtering and pagination.
    
    Returns complete audit trail of all changes to the loan application
    with optional filtering, pagination, and integrity verification.
    """
    try:
        logger.info("Retrieving loan application history",
                   loan_id=loan_id,
                   page=page,
                   page_size=page_size,
                   actor_id=current_user.actor_id)
        
        # Validate pagination parameters
        if page < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Page must be greater than 0"
            )
        if page_size < 1 or page_size > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Page size must be between 1 and 1000"
            )
        
        # Validate loan exists
        loan = _validate_loan_exists(loan_id)
        
        # Check access permissions
        _check_loan_access_permissions(loan, current_user)
        
        # Build filter criteria
        filter_criteria = LoanHistoryFilter(
            change_type=change_type,
            actor_id=actor_id,
            from_date=from_date,
            to_date=to_date,
            status=status
        )
        
        # Get filtered and paginated history records
        try:
            result = db_utils.get_loan_history_paginated(
                loan_id, 
                page, 
                page_size, 
                filter_criteria
            )
            if isinstance(result, tuple) and len(result) == 2:
                history_records, total_count = result
            else:
                # Handle case where method doesn't return tuple
                raise AttributeError("Method doesn't return expected tuple")
        except (AttributeError, ValueError):
            # Fallback to old method for backward compatibility
            history_records = db_utils.get_loan_history(loan_id)
            total_count = len(history_records)
            
            # Apply manual pagination
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            history_records = history_records[start_idx:end_idx]
        
        # Convert to response format
        response_items = []
        for record in history_records:
            item = LoanHistoryResponse(
                id=record.id,
                change_type=record.change_type,
                previous_status=record.previous_status,
                new_status=record.new_status,
                field_name=record.field_name,
                old_value=record.old_value,
                new_value=record.new_value,
                changed_by_actor_id=record.changed_by_actor_id,
                blockchain_transaction_id=record.blockchain_transaction_id,
                timestamp=record.timestamp,
                notes=record.notes
            )
            
            # Perform integrity verification if requested
            if verify_integrity and record.blockchain_transaction_id:
                try:
                    is_verified = await _verify_history_integrity(record)
                    # Add verification status to notes or create a separate field
                    if item.notes:
                        item.notes += f" | Blockchain Verified: {is_verified}"
                    else:
                        item.notes = f"Blockchain Verified: {is_verified}"
                except Exception as e:
                    logger.warning("Failed to verify history integrity",
                                 record_id=record.id,
                                 error=str(e))
            
            response_items.append(item)
        
        # Calculate pagination metadata
        total_pages = (total_count + page_size - 1) // page_size
        has_next = page < total_pages
        has_previous = page > 1
        
        response_data = PaginatedLoanHistoryResponse(
            items=response_items,
            total=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous
        )
        
        logger.info("Loan history retrieved successfully",
                   loan_id=loan_id,
                   record_count=len(response_items),
                   total_count=total_count)
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve loan history", 
                    loan_id=loan_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve loan history"
        )


@router.post("/{loan_id}/audit-report", response_model=AuditReportResponse)
async def generate_audit_report(
    loan_id: str,
    report_request: AuditReportRequest,
    current_user: Actor = Depends(require_permissions(Permission.READ_LOAN_HISTORY))
):
    """
    Generate comprehensive audit report for loan application.
    
    Creates a detailed audit report with optional blockchain integrity verification.
    """
    try:
        logger.info("Generating audit report",
                   loan_id=loan_id,
                   report_type=report_request.report_type,
                   actor_id=current_user.actor_id)
        
        # Validate loan exists
        loan = _validate_loan_exists(loan_id)
        
        # Check access permissions
        _check_loan_access_permissions(loan, current_user)
        
        # Generate unique report ID
        report_id = f"AUDIT_{loan_id}_{secrets.token_hex(4).upper()}"
        
        # Get complete history for the loan
        all_history = db_utils.get_loan_history(loan_id)
        
        # Filter history by date range if specified
        filtered_history = all_history
        if report_request.from_date or report_request.to_date:
            filtered_history = []
            for record in all_history:
                if report_request.from_date and record.timestamp < report_request.from_date:
                    continue
                if report_request.to_date and record.timestamp > report_request.to_date:
                    continue
                filtered_history.append(record)
        
        # Perform blockchain integrity verification if requested
        integrity_verified = True
        blockchain_hash_matches = 0
        verification_details = []
        
        if report_request.include_blockchain_verification:
            for record in filtered_history:
                if record.blockchain_transaction_id:
                    try:
                        is_verified = await _verify_history_integrity(record)
                        if is_verified:
                            blockchain_hash_matches += 1
                        verification_details.append({
                            "record_id": record.id,
                            "transaction_id": record.blockchain_transaction_id,
                            "verified": is_verified,
                            "timestamp": record.timestamp.isoformat()
                        })
                    except Exception as e:
                        logger.warning("Verification failed for record",
                                     record_id=record.id,
                                     error=str(e))
                        integrity_verified = False
                        verification_details.append({
                            "record_id": record.id,
                            "transaction_id": record.blockchain_transaction_id,
                            "verified": False,
                            "error": str(e),
                            "timestamp": record.timestamp.isoformat()
                        })
        
        # Build audit report data
        audit_data = {
            "loan_application": {
                "loan_id": loan.loan_application_id,
                "customer_id": loan.customer.customer_id if loan.customer else None,
                "current_status": loan.application_status,
                "requested_amount": loan.requested_amount,
                "approval_amount": loan.approval_amount,
                "created_at": loan.created_at.isoformat(),
                "updated_at": loan.updated_at.isoformat()
            },
            "history_summary": {
                "total_changes": len(filtered_history),
                "status_changes": len([r for r in filtered_history if r.change_type == 'STATUS_CHANGE']),
                "approvals": len([r for r in filtered_history if r.change_type == 'APPROVAL']),
                "rejections": len([r for r in filtered_history if r.change_type == 'REJECTION']),
                "updates": len([r for r in filtered_history if r.change_type == 'UPDATE'])
            },
            "timeline": [
                {
                    "id": record.id,
                    "timestamp": record.timestamp.isoformat(),
                    "change_type": record.change_type,
                    "previous_status": record.previous_status,
                    "new_status": record.new_status,
                    "field_name": record.field_name,
                    "old_value": record.old_value,
                    "new_value": record.new_value,
                    "changed_by_actor_id": record.changed_by_actor_id,
                    "blockchain_transaction_id": record.blockchain_transaction_id,
                    "notes": record.notes
                }
                for record in filtered_history
            ],
            "actors_involved": list(set([
                record.changed_by_actor_id for record in filtered_history
            ])),
            "blockchain_verification": {
                "enabled": report_request.include_blockchain_verification,
                "total_records_with_blockchain": len([r for r in filtered_history if r.blockchain_transaction_id]),
                "verified_records": blockchain_hash_matches,
                "verification_details": verification_details if report_request.include_blockchain_verification else []
            }
        }
        
        # Create response
        response_data = AuditReportResponse(
            report_id=report_id,
            report_type=report_request.report_type,
            generated_at=datetime.utcnow(),
            total_records=len(filtered_history),
            integrity_verified=integrity_verified,
            blockchain_hash_matches=blockchain_hash_matches,
            data=audit_data
        )
        
        logger.info("Audit report generated successfully",
                   loan_id=loan_id,
                   report_id=report_id,
                   total_records=len(filtered_history))
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate audit report", 
                    loan_id=loan_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to generate audit report"
        )


async def _verify_history_integrity(history_record: 'LoanApplicationHistoryModel') -> bool:
    """
    Verify the integrity of a history record against blockchain data.
    
    This function would typically query the blockchain to verify that the
    recorded transaction ID and data match what's stored on the ledger.
    """
    try:
        if not history_record.blockchain_transaction_id:
            return False
        
        # Get blockchain data for verification
        gateway = await get_fabric_gateway()
        
        # Query blockchain for the specific transaction
        blockchain_result = await gateway.query_chaincode(
            "loan",
            "GetLoanHistory",
            [history_record.loan_application.loan_application_id]
        )
        
        if not blockchain_result:
            return False
        
        # Parse blockchain history and find matching transaction
        blockchain_history = json.loads(blockchain_result)
        
        # Find the matching transaction in blockchain history
        for blockchain_record in blockchain_history:
            if blockchain_record.get("transactionID") == history_record.blockchain_transaction_id:
                # Verify key fields match
                if (blockchain_record.get("changeType") == history_record.change_type and
                    blockchain_record.get("timestamp") and
                    abs((datetime.fromisoformat(blockchain_record["timestamp"].replace('Z', '+00:00')) - 
                         history_record.timestamp).total_seconds()) < 60):  # Allow 1 minute tolerance
                    return True
        
        return False
        
    except Exception as e:
        logger.error("Failed to verify history integrity",
                    record_id=history_record.id,
                    error=str(e))
        return False


@router.post("/{loan_id}/documents", response_model=LoanDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    loan_id: str,
    file: UploadFile = File(...),
    document_type: DocumentType = Form(...),
    document_name: Optional[str] = Form(None),
    current_user: Actor = Depends(require_permissions(Permission.MANAGE_LOAN_DOCUMENTS))
):
    """
    Upload a document for a loan application.
    
    Uploads a document, calculates its hash for integrity verification,
    and records the hash on the blockchain.
    """
    try:
        logger.info("Uploading document for loan",
                   loan_id=loan_id,
                   document_type=document_type,
                   filename=file.filename,
                   actor_id=current_user.actor_id)
        
        # Validate loan exists
        loan = _validate_loan_exists(loan_id)
        
        # Check access permissions
        _check_loan_access_permissions(loan, current_user)
        
        # Validate file upload
        _validate_file_upload(file)
        
        # Get current user's database record
        db_actor = db_utils.get_actor_by_actor_id(current_user.actor_id)
        if not db_actor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Actor not found in database"
            )
        
        # Read file content and calculate hash
        file_content = await file.read()
        document_hash = _calculate_file_hash(file_content)
        
        # Use provided document name or file name
        final_document_name = document_name or file.filename or f"document_{document_type.value.lower()}"
        
        # Prepare document data for database
        document_data = {
            "loan_application_id": loan.id,  # Use database ID for foreign key
            "document_type": document_type.value,
            "document_name": final_document_name,
            "document_hash": document_hash,
            "file_size": len(file_content),
            "mime_type": file.content_type,
            "verification_status": DocumentStatus.PENDING.value,
            "uploaded_by_actor_id": db_actor.id
        }
        
        # Create document record in database
        db_document = db_utils.create_loan_document(document_data)
        
        # Record document hash on blockchain
        try:
            gateway = await get_fabric_gateway()
            
            # Get customer ID for blockchain record
            customer = db_utils.get_customer_by_customer_id(loan.customer.customer_id)
            
            blockchain_data = {
                "loanApplicationID": loan_id,
                "customerID": customer.customer_id,
                "documentType": document_type.value,
                "documentName": final_document_name,
                "documentHash": document_hash,
                "actorID": current_user.actor_id
            }
            
            blockchain_result = await gateway.invoke_chaincode(
                "loan",
                "RecordDocumentHash",
                [
                    loan_id,
                    customer.customer_id,
                    document_type.value,
                    final_document_name,
                    document_hash,
                    current_user.actor_id
                ]
            )
            
            # Update document with blockchain record hash
            if blockchain_result.get("transaction_id"):
                db_utils.update_document_verification_status(
                    db_document.id,
                    DocumentStatus.PENDING.value,
                    blockchain_result.get("transaction_id")
                )
            
            logger.info("Document hash recorded on blockchain",
                       loan_id=loan_id,
                       document_id=db_document.id,
                       transaction_id=blockchain_result.get("transaction_id"))
            
        except Exception as e:
            logger.error("Failed to record document hash on blockchain",
                        loan_id=loan_id,
                        document_id=db_document.id,
                        error=str(e))
            # Continue with database record even if blockchain fails
        
        # Convert to response format
        response_data = LoanDocumentResponse(
            id=db_document.id,
            loan_application_id=loan_id,
            document_type=db_document.document_type,
            document_name=db_document.document_name,
            document_hash=db_document.document_hash,
            file_size=db_document.file_size,
            mime_type=db_document.mime_type,
            verification_status=db_document.verification_status,
            uploaded_by_actor_id=db_document.uploaded_by_actor_id,
            blockchain_record_hash=db_document.blockchain_record_hash,
            created_at=db_document.created_at,
            updated_at=db_document.updated_at
        )
        
        logger.info("Document uploaded successfully",
                   loan_id=loan_id,
                   document_id=db_document.id,
                   document_hash=document_hash)
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to upload document", 
                    loan_id=loan_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document"
        )


@router.get("/{loan_id}/documents", response_model=List[LoanDocumentResponse])
async def get_loan_documents(
    loan_id: str,
    document_type: Optional[DocumentType] = None,
    verification_status: Optional[DocumentStatus] = None,
    current_user: Actor = Depends(require_permissions(Permission.READ_LOAN_APPLICATION))
):
    """
    Get all documents for a loan application.
    
    Returns a list of all documents associated with the loan application
    with optional filtering by document type and verification status.
    """
    try:
        logger.info("Retrieving documents for loan",
                   loan_id=loan_id,
                   document_type=document_type,
                   verification_status=verification_status,
                   actor_id=current_user.actor_id)
        
        # Validate loan exists
        loan = _validate_loan_exists(loan_id)
        
        # Check access permissions
        _check_loan_access_permissions(loan, current_user)
        
        # Get documents from database
        documents = db_utils.get_loan_documents(loan_id)
        
        # Apply filters if specified
        filtered_documents = documents
        if document_type:
            filtered_documents = [doc for doc in filtered_documents if doc.document_type == document_type.value]
        
        if verification_status:
            filtered_documents = [doc for doc in filtered_documents if doc.verification_status == verification_status.value]
        
        # Convert to response format
        response_data = []
        for doc in filtered_documents:
            response_data.append(LoanDocumentResponse(
                id=doc.id,
                loan_application_id=loan_id,
                document_type=doc.document_type,
                document_name=doc.document_name,
                document_hash=doc.document_hash,
                file_size=doc.file_size,
                mime_type=doc.mime_type,
                verification_status=doc.verification_status,
                uploaded_by_actor_id=doc.uploaded_by_actor_id,
                blockchain_record_hash=doc.blockchain_record_hash,
                created_at=doc.created_at,
                updated_at=doc.updated_at
            ))
        
        logger.info("Documents retrieved successfully",
                   loan_id=loan_id,
                   total_documents=len(response_data))
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve documents", 
                    loan_id=loan_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve documents"
        )


@router.put("/{loan_id}/documents/{document_id}/status", response_model=LoanDocumentResponse)
async def update_document_status(
    loan_id: str,
    document_id: int,
    status_update: DocumentStatusUpdate,
    current_user: Actor = Depends(require_permissions(Permission.MANAGE_LOAN_DOCUMENTS))
):
    """
    Update document verification status.
    
    Updates the verification status of a document and records the change
    on the blockchain for audit trail purposes.
    """
    try:
        logger.info("Updating document status",
                   loan_id=loan_id,
                   document_id=document_id,
                   new_status=status_update.verification_status,
                   actor_id=current_user.actor_id)
        
        # Validate loan exists
        loan = _validate_loan_exists(loan_id)
        
        # Check access permissions
        _check_loan_access_permissions(loan, current_user)
        
        # Validate document exists and belongs to the loan
        document = db_utils.get_loan_document_by_id(document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found"
            )
        
        if document.loan_application_id != loan.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document does not belong to this loan application"
            )
        
        # Validate status transition
        old_status = document.verification_status
        new_status = status_update.verification_status.value
        
        if old_status == new_status:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document is already in {new_status} status"
            )
        
        # Update status in database
        success = db_utils.update_document_verification_status(
            document_id,
            new_status
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update document status in database"
            )
        
        # Update blockchain record
        try:
            gateway = await get_fabric_gateway()
            
            # Generate a document ID for blockchain (using database ID)
            blockchain_document_id = f"DOC_{document_id}"
            
            blockchain_result = await gateway.invoke_chaincode(
                "loan",
                "UpdateDocumentStatus",
                [
                    blockchain_document_id,
                    new_status,
                    current_user.actor_id,
                    status_update.notes or ""
                ]
            )
            
            logger.info("Document status updated on blockchain",
                       loan_id=loan_id,
                       document_id=document_id,
                       transaction_id=blockchain_result.get("transaction_id"))
            
        except Exception as e:
            logger.error("Failed to update document status on blockchain",
                        loan_id=loan_id,
                        document_id=document_id,
                        error=str(e))
            # Continue with database update even if blockchain fails
        
        # Retrieve updated document
        updated_document = db_utils.get_loan_document_by_id(document_id)
        
        response_data = LoanDocumentResponse(
            id=updated_document.id,
            loan_application_id=loan_id,
            document_type=updated_document.document_type,
            document_name=updated_document.document_name,
            document_hash=updated_document.document_hash,
            file_size=updated_document.file_size,
            mime_type=updated_document.mime_type,
            verification_status=updated_document.verification_status,
            uploaded_by_actor_id=updated_document.uploaded_by_actor_id,
            blockchain_record_hash=updated_document.blockchain_record_hash,
            created_at=updated_document.created_at,
            updated_at=updated_document.updated_at
        )
        
        logger.info("Document status updated successfully",
                   loan_id=loan_id,
                   document_id=document_id,
                   old_status=old_status,
                   new_status=new_status)
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update document status", 
                    loan_id=loan_id, 
                    document_id=document_id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update document status"
        )


@router.post("/{loan_id}/documents/{document_id}/verify", response_model=Dict[str, Any])
async def verify_document_hash(
    loan_id: str,
    document_id: int,
    current_user: Actor = Depends(require_permissions(Permission.MANAGE_LOAN_DOCUMENTS))
):
    """
    Verify document hash against blockchain record.
    
    Verifies that the document hash stored in the database matches
    the hash recorded on the blockchain for integrity verification.
    """
    try:
        logger.info("Verifying document hash",
                   loan_id=loan_id,
                   document_id=document_id,
                   actor_id=current_user.actor_id)
        
        # Validate loan exists
        loan = _validate_loan_exists(loan_id)
        
        # Check access permissions
        _check_loan_access_permissions(loan, current_user)
        
        # Validate document exists and belongs to the loan
        document = db_utils.get_loan_document_by_id(document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found"
            )
        
        if document.loan_application_id != loan.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document does not belong to this loan application"
            )
        
        # Verify hash against blockchain
        verification_result = {
            "document_id": document_id,
            "loan_application_id": loan_id,
            "document_hash": document.document_hash,
            "verification_timestamp": datetime.utcnow().isoformat(),
            "verified_by": current_user.actor_id,
            "blockchain_verified": False,
            "verification_details": {}
        }
        
        try:
            gateway = await get_fabric_gateway()
            
            # Generate blockchain document ID
            blockchain_document_id = f"DOC_{document_id}"
            
            blockchain_result = await gateway.invoke_chaincode(
                "loan",
                "VerifyDocumentHash",
                [
                    blockchain_document_id,
                    document.document_hash,
                    current_user.actor_id
                ]
            )
            
            # Parse blockchain response
            if blockchain_result.get("success"):
                verification_result["blockchain_verified"] = True
                verification_result["verification_details"] = {
                    "blockchain_hash": blockchain_result.get("stored_hash"),
                    "provided_hash": document.document_hash,
                    "match": blockchain_result.get("hash_match", False),
                    "transaction_id": blockchain_result.get("transaction_id")
                }
                
                # Update document verification status if verified
                if blockchain_result.get("hash_match"):
                    db_utils.update_document_verification_status(
                        document_id,
                        DocumentStatus.VERIFIED.value
                    )
                else:
                    db_utils.update_document_verification_status(
                        document_id,
                        DocumentStatus.FAILED.value
                    )
            else:
                verification_result["verification_details"] = {
                    "error": blockchain_result.get("error", "Unknown blockchain error")
                }
            
            logger.info("Document hash verification completed",
                       loan_id=loan_id,
                       document_id=document_id,
                       verified=verification_result["blockchain_verified"])
            
        except Exception as e:
            logger.error("Failed to verify document hash on blockchain",
                        loan_id=loan_id,
                        document_id=document_id,
                        error=str(e))
            verification_result["verification_details"] = {
                "error": f"Blockchain verification failed: {str(e)}"
            }
        
        return verification_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to verify document hash", 
                    loan_id=loan_id, 
                    document_id=document_id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify document hash"
        )