"""
Customer Mastery Pydantic models for request/response validation.

This module contains all Pydantic model classes used by the Customer Mastery API
for data validation, serialization, and documentation.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, EmailStr, field_validator


class CustomerBase(BaseModel):
    """Base customer schema with common fields."""
    first_name: str = Field(..., min_length=1, max_length=255, description="Customer first name")
    last_name: str = Field(..., min_length=1, max_length=255, description="Customer last name")
    date_of_birth: Optional[datetime] = Field(None, description="Customer date of birth")
    national_id: Optional[str] = Field(None, min_length=5, max_length=50, description="National ID (will be hashed)")
    address: Optional[str] = Field(None, max_length=1000, description="Customer address")
    contact_email: Optional[EmailStr] = Field(None, description="Customer email address")
    contact_phone: Optional[str] = Field(None, max_length=50, description="Customer phone number")
    
    @field_validator('contact_phone')
    @classmethod
    def validate_phone(cls, v):
        if v and not v.replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '').isdigit():
            raise ValueError('Phone number must contain only digits and common separators')
        return v


class CustomerCreate(CustomerBase):
    """Schema for creating a new customer."""
    consent_preferences: Optional[Dict[str, Any]] = Field(
        default_factory=dict, 
        description="Customer consent preferences"
    )


class CustomerUpdate(BaseModel):
    """Schema for updating customer data."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=255)
    last_name: Optional[str] = Field(None, min_length=1, max_length=255)
    date_of_birth: Optional[datetime] = None
    address: Optional[str] = Field(None, max_length=1000)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, max_length=50)
    
    @field_validator('contact_phone')
    @classmethod
    def validate_phone(cls, v):
        if v and not v.replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '').isdigit():
            raise ValueError('Phone number must contain only digits and common separators')
        return v


class CustomerResponse(CustomerBase):
    """Schema for customer response data."""
    customer_id: str = Field(..., description="Unique customer identifier")
    kyc_status: str = Field(..., description="KYC verification status")
    aml_status: str = Field(..., description="AML screening status")
    consent_preferences: Dict[str, Any] = Field(default_factory=dict, description="Consent preferences")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    # Exclude sensitive fields
    national_id: Optional[str] = Field(None, exclude=True)
    
    model_config = {"from_attributes": True}


class CustomerHistoryResponse(BaseModel):
    """Schema for customer history records."""
    id: int = Field(..., description="History record ID")
    change_type: str = Field(..., description="Type of change")
    field_name: Optional[str] = Field(None, description="Field that was changed")
    old_value: Optional[str] = Field(None, description="Previous value")
    new_value: Optional[str] = Field(None, description="New value")
    changed_by_actor_id: int = Field(..., description="Actor who made the change")
    blockchain_transaction_id: Optional[str] = Field(None, description="Blockchain transaction ID")
    timestamp: datetime = Field(..., description="Change timestamp")
    
    model_config = {"from_attributes": True}


class ConsentPreferences(BaseModel):
    """Schema for customer consent preferences."""
    data_sharing: bool = Field(False, description="Consent for data sharing")
    marketing: bool = Field(False, description="Consent for marketing communications")
    analytics: bool = Field(False, description="Consent for analytics and profiling")
    third_party_sharing: bool = Field(False, description="Consent for third-party data sharing")
    retention_period: Optional[int] = Field(None, description="Data retention period in months")
    
    model_config = {"extra": "allow"}  # Allow additional consent fields


class ConsentResponse(BaseModel):
    """Schema for consent response."""
    customer_id: str = Field(..., description="Customer ID")
    consent_preferences: ConsentPreferences = Field(..., description="Current consent preferences")
    last_updated: datetime = Field(..., description="Last consent update timestamp")
    recorded_by: str = Field(..., description="Actor who recorded the consent")


class IdentityVerificationRequest(BaseModel):
    """Schema for identity verification request."""
    verification_type: str = Field(..., description="Type of verification (KYC, AML, DOCUMENT)")
    provider: Optional[str] = Field("default", description="Identity verification provider")
    additional_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional verification data")


class IdentityVerificationResponse(BaseModel):
    """Schema for identity verification response."""
    customer_id: str = Field(..., description="Customer ID")
    verification_id: str = Field(..., description="Verification request ID")
    verification_type: str = Field(..., description="Type of verification")
    status: str = Field(..., description="Verification status")
    provider: str = Field(..., description="Identity verification provider")
    initiated_by: str = Field(..., description="Actor who initiated verification")
    initiated_at: datetime = Field(..., description="Verification initiation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Verification completion timestamp")
    result_details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Verification result details")


class VerificationStatusUpdate(BaseModel):
    """Schema for updating verification status."""
    status: str = Field(..., description="New verification status")
    result_details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Verification result details")
    notes: Optional[str] = Field(None, description="Additional notes about the verification")