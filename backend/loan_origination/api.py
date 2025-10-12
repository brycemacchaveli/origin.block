"""
Loan Origination API endpoints for blockchain financial platform.

This module provides REST API endpoints for loan application management,
including creation, retrieval, status updates, approval/rejection, and history tracking.
"""

import json
import secrets
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field, validator
import structlog

from shared.auth import (
    get_current_user, 
    require_permissions, 
    Actor, 
    Permission
)
from shared.database import db_utils, LoanApplicationModel, CustomerModel
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


@router.get("/{loan_id}/history", response_model=List[LoanHistoryResponse])
async def get_loan_history(
    loan_id: str,
    current_user: Actor = Depends(require_permissions(Permission.READ_LOAN_HISTORY))
):
    """
    Get loan application history.
    
    Returns complete audit trail of all changes to the loan application.
    """
    try:
        logger.info("Retrieving loan application history",
                   loan_id=loan_id,
                   actor_id=current_user.actor_id)
        
        # Validate loan exists
        loan = _validate_loan_exists(loan_id)
        
        # Check access permissions
        _check_loan_access_permissions(loan, current_user)
        
        # Get history records
        history_records = db_utils.get_loan_history(loan_id)
        
        # Convert to response format
        response_data = [
            LoanHistoryResponse(
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
            for record in history_records
        ]
        
        logger.info("Loan history retrieved successfully",
                   loan_id=loan_id,
                   record_count=len(response_data))
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve loan history", 
                    loan_id=loan_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve loan history"
        )