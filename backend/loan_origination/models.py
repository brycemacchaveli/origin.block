"""
Loan Origination Pydantic models for request/response validation.

This module contains all Pydantic model classes used by the Loan Origination API
for data validation, serialization, and documentation.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, validator


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
    
    model_config = {"from_attributes": True}


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
    
    model_config = {"from_attributes": True}

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
    
    model_config = {"from_attributes": True}


class DocumentStatusUpdate(BaseModel):
    """Schema for updating document status."""
    verification_status: DocumentStatus = Field(..., description="New verification status")
    notes: Optional[str] = Field(None, description="Notes about the status change")