"""
Customer Mastery API endpoints

This module implements the Customer Mastery API service with CRUD operations
for customer data management, including consent management and identity verification.
"""

import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from hashlib import sha256

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field, EmailStr, field_validator
import structlog

from shared.auth import (
    get_current_user, 
    require_permissions, 
    Actor, 
    Permission
)
from shared.database import (
    db_utils, 
    CustomerModel, 
    CustomerHistoryModel,
    ActorModel
)
from shared.fabric_gateway import (
    get_fabric_gateway, 
    ChaincodeClient, 
    ChaincodeType,
    FabricError
)

logger = structlog.get_logger(__name__)

router = APIRouter()


# Pydantic schemas for request/response validation
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
    
    class Config:
        from_attributes = True


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
    
    class Config:
        from_attributes = True


class ConsentPreferences(BaseModel):
    """Schema for customer consent preferences."""
    data_sharing: bool = Field(False, description="Consent for data sharing")
    marketing: bool = Field(False, description="Consent for marketing communications")
    analytics: bool = Field(False, description="Consent for analytics and profiling")
    third_party_sharing: bool = Field(False, description="Consent for third-party data sharing")
    retention_period: Optional[int] = Field(None, description="Data retention period in months")
    
    class Config:
        extra = "allow"  # Allow additional consent fields


class ConsentResponse(BaseModel):
    """Schema for consent response."""
    customer_id: str = Field(..., description="Customer ID")
    consent_preferences: ConsentPreferences = Field(..., description="Current consent preferences")
    last_updated: datetime = Field(..., description="Last consent update timestamp")
    recorded_by: str = Field(..., description="Actor who recorded the consent")


def _hash_national_id(national_id: str) -> str:
    """Hash national ID for secure storage."""
    return sha256(national_id.encode()).hexdigest()


def _generate_customer_id() -> str:
    """Generate a unique customer ID."""
    return f"CUST_{uuid.uuid4().hex[:12].upper()}"


@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer_data: CustomerCreate,
    current_user: Actor = Depends(require_permissions(Permission.CREATE_CUSTOMER))
):
    """
    Create a new customer record.
    
    Creates a customer in both the blockchain and operational database,
    with proper validation and consent recording.
    
    Requirements: 2.1, 2.2, 2.4, 2.7
    """
    try:
        logger.info("Creating new customer", actor_id=current_user.actor_id)
        
        # Generate unique customer ID
        customer_id = _generate_customer_id()
        
        # Hash national ID if provided
        national_id_hash = None
        if customer_data.national_id:
            national_id_hash = _hash_national_id(customer_data.national_id)
        
        # Get actor from database for foreign key
        actor = db_utils.get_actor_by_actor_id(current_user.actor_id)
        if not actor:
            # Create actor if it doesn't exist
            actor_data = {
                "actor_id": current_user.actor_id,
                "actor_type": current_user.actor_type.value,
                "actor_name": current_user.actor_name,
                "role": current_user.role.value,
                "blockchain_identity": current_user.blockchain_identity,
                "permissions": [perm.value for perm in current_user.permissions]
            }
            actor = db_utils.create_actor(actor_data)
        
        # Prepare customer data for database
        db_customer_data = {
            "customer_id": customer_id,
            "first_name": customer_data.first_name,
            "last_name": customer_data.last_name,
            "date_of_birth": customer_data.date_of_birth,
            "national_id_hash": national_id_hash,
            "address": customer_data.address,
            "contact_email": customer_data.contact_email,
            "contact_phone": customer_data.contact_phone,
            "kyc_status": "PENDING",
            "aml_status": "PENDING",
            "consent_preferences": customer_data.consent_preferences,
            "created_by_actor_id": actor.id
        }
        
        # Create customer in database
        customer = db_utils.create_customer(db_customer_data)
        
        # Prepare data for blockchain
        blockchain_data = {
            "customerID": customer_id,
            "firstName": customer_data.first_name,
            "lastName": customer_data.last_name,
            "dateOfBirth": customer_data.date_of_birth.isoformat() if customer_data.date_of_birth else None,
            "nationalID": national_id_hash,  # Store hashed version on blockchain
            "address": customer_data.address,
            "contactEmail": customer_data.contact_email,
            "contactPhone": customer_data.contact_phone,
            "kycStatus": "PENDING",
            "amlStatus": "PENDING",
            "consentPreferences": json.dumps(customer_data.consent_preferences),
            "createdByActor": current_user.actor_id
        }
        
        # Store on blockchain
        try:
            gateway = await get_fabric_gateway()
            chaincode_client = ChaincodeClient(gateway, ChaincodeType.CUSTOMER)
            blockchain_result = await chaincode_client.invoke_chaincode(
                "customer",
                "CreateCustomer",
                [json.dumps(blockchain_data)]
            )
            
            logger.info("Customer created on blockchain", 
                       customer_id=customer_id,
                       transaction_id=blockchain_result.get("transaction_id"))
            
        except FabricError as e:
            logger.error("Failed to create customer on blockchain", 
                        customer_id=customer_id, 
                        error=str(e))
            # Note: In production, you might want to implement compensation logic
            # to rollback the database transaction if blockchain fails
            
        # Create history record
        history_data = {
            "customer_id": customer.id,
            "change_type": "CREATE",
            "new_value": json.dumps({
                "customer_id": customer_id,
                "first_name": customer_data.first_name,
                "last_name": customer_data.last_name
            }),
            "changed_by_actor_id": actor.id,
            "blockchain_transaction_id": blockchain_result.get("transaction_id") if 'blockchain_result' in locals() else None
        }
        
        with db_utils.db_manager.session_scope() as session:
            history = CustomerHistoryModel(**history_data)
            session.add(history)
        
        logger.info("Customer created successfully", customer_id=customer_id)
        
        return CustomerResponse.from_orm(customer)
        
    except Exception as e:
        logger.error("Failed to create customer", error=str(e), actor_id=current_user.actor_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create customer: {str(e)}"
        )


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: str,
    current_user: Actor = Depends(require_permissions(Permission.READ_CUSTOMER))
):
    """
    Retrieve a customer by ID.
    
    Returns customer data from the operational database with proper
    access control validation.
    
    Requirements: 2.2, 2.3, 2.7
    """
    try:
        logger.info("Retrieving customer", customer_id=customer_id, actor_id=current_user.actor_id)
        
        # Get customer from database
        customer = db_utils.get_customer_by_customer_id(customer_id)
        
        if not customer:
            logger.warning("Customer not found", customer_id=customer_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer {customer_id} not found"
            )
        
        logger.info("Customer retrieved successfully", customer_id=customer_id)
        
        return CustomerResponse.from_orm(customer)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve customer", 
                    customer_id=customer_id, 
                    error=str(e), 
                    actor_id=current_user.actor_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve customer: {str(e)}"
        )


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: str,
    customer_update: CustomerUpdate,
    current_user: Actor = Depends(require_permissions(Permission.UPDATE_CUSTOMER))
):
    """
    Update customer information.
    
    Updates customer data in both blockchain and operational database,
    maintaining complete audit trail.
    
    Requirements: 2.2, 2.4, 2.7
    """
    try:
        logger.info("Updating customer", customer_id=customer_id, actor_id=current_user.actor_id)
        
        # Get existing customer
        customer = db_utils.get_customer_by_customer_id(customer_id)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer {customer_id} not found"
            )
        
        # Get actor for foreign key
        actor = db_utils.get_actor_by_actor_id(current_user.actor_id)
        if not actor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Actor not found in database"
            )
        
        # Prepare update data
        update_data = customer_update.dict(exclude_unset=True)
        
        # Track changes for history
        changes = []
        blockchain_updates = {}
        
        with db_utils.db_manager.session_scope() as session:
            db_customer = session.query(CustomerModel).filter(
                CustomerModel.customer_id == customer_id
            ).first()
            
            if not db_customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer {customer_id} not found"
                )
            
            # Update fields and track changes
            for field, new_value in update_data.items():
                old_value = getattr(db_customer, field)
                if old_value != new_value:
                    changes.append({
                        "field_name": field,
                        "old_value": str(old_value) if old_value is not None else None,
                        "new_value": str(new_value) if new_value is not None else None
                    })
                    setattr(db_customer, field, new_value)
                    
                    # Map to blockchain field names
                    blockchain_field_map = {
                        "first_name": "firstName",
                        "last_name": "lastName",
                        "date_of_birth": "dateOfBirth",
                        "address": "address",
                        "contact_email": "contactEmail",
                        "contact_phone": "contactPhone"
                    }
                    
                    if field in blockchain_field_map:
                        blockchain_updates[blockchain_field_map[field]] = new_value
            
            if not changes:
                logger.info("No changes detected for customer", customer_id=customer_id)
                return CustomerResponse.from_orm(db_customer)
            
            db_customer.updated_at = datetime.utcnow()
            session.flush()
            
            # Update on blockchain if there are changes
            blockchain_transaction_id = None
            if blockchain_updates:
                try:
                    # Convert datetime to ISO string for blockchain
                    if "dateOfBirth" in blockchain_updates and blockchain_updates["dateOfBirth"]:
                        blockchain_updates["dateOfBirth"] = blockchain_updates["dateOfBirth"].isoformat()
                    
                    gateway = await get_fabric_gateway()
                    chaincode_client = ChaincodeClient(gateway, ChaincodeType.CUSTOMER)
                    blockchain_result = await chaincode_client.invoke_chaincode(
                        "customer",
                        "UpdateCustomerDetails",
                        [customer_id, json.dumps(blockchain_updates)]
                    )
                    
                    blockchain_transaction_id = blockchain_result.get("transaction_id")
                    
                    logger.info("Customer updated on blockchain", 
                               customer_id=customer_id,
                               transaction_id=blockchain_transaction_id)
                    
                except FabricError as e:
                    logger.error("Failed to update customer on blockchain", 
                                customer_id=customer_id, 
                                error=str(e))
                    # Continue with database update even if blockchain fails
            
            # Create history records for each change
            for change in changes:
                history_data = {
                    "customer_id": db_customer.id,
                    "change_type": "UPDATE",
                    "field_name": change["field_name"],
                    "old_value": change["old_value"],
                    "new_value": change["new_value"],
                    "changed_by_actor_id": actor.id,
                    "blockchain_transaction_id": blockchain_transaction_id
                }
                history = CustomerHistoryModel(**history_data)
                session.add(history)
            
            session.refresh(db_customer)
        
        logger.info("Customer updated successfully", 
                   customer_id=customer_id, 
                   changes_count=len(changes))
        
        return CustomerResponse.from_orm(db_customer)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update customer", 
                    customer_id=customer_id, 
                    error=str(e), 
                    actor_id=current_user.actor_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update customer: {str(e)}"
        )


@router.get("/{customer_id}/history", response_model=List[CustomerHistoryResponse])
async def get_customer_history(
    customer_id: str,
    current_user: Actor = Depends(require_permissions(Permission.READ_CUSTOMER_HISTORY))
):
    """
    Retrieve customer change history.
    
    Returns complete audit trail of all changes made to the customer record,
    providing transparency and compliance support.
    
    Requirements: 2.4, 4.1
    """
    try:
        logger.info("Retrieving customer history", 
                   customer_id=customer_id, 
                   actor_id=current_user.actor_id)
        
        # Verify customer exists
        customer = db_utils.get_customer_by_customer_id(customer_id)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer {customer_id} not found"
            )
        
        # Get history records
        history_records = db_utils.get_customer_history(customer_id)
        
        logger.info("Customer history retrieved successfully", 
                   customer_id=customer_id, 
                   records_count=len(history_records))
        
        return [CustomerHistoryResponse.from_orm(record) for record in history_records]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve customer history", 
                    customer_id=customer_id, 
                    error=str(e), 
                    actor_id=current_user.actor_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve customer history: {str(e)}"
        )