"""
Customer Mastery API endpoints

This module implements the Customer Mastery API service with CRUD operations
for customer data management, including consent management and identity verification.
"""

import asyncio
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


@router.post("/{customer_id}/consent", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED)
async def record_customer_consent(
    customer_id: str,
    consent_data: ConsentPreferences,
    current_user: Actor = Depends(require_permissions(Permission.MANAGE_CUSTOMER_CONSENT))
):
    """
    Record customer consent preferences.
    
    Records consent preferences on both blockchain and operational database,
    ensuring immutable consent tracking for compliance purposes.
    
    Requirements: 2.6, 4.2
    """
    try:
        logger.info("Recording customer consent", 
                   customer_id=customer_id, 
                   actor_id=current_user.actor_id)
        
        # Verify customer exists
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
        
        # Update consent preferences in database
        consent_dict = consent_data.dict()
        
        with db_utils.db_manager.session_scope() as session:
            db_customer = session.query(CustomerModel).filter(
                CustomerModel.customer_id == customer_id
            ).first()
            
            if not db_customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer {customer_id} not found"
                )
            
            old_consent = db_customer.consent_preferences or {}
            db_customer.consent_preferences = consent_dict
            db_customer.updated_at = datetime.utcnow()
            
            # Record consent on blockchain
            blockchain_transaction_id = None
            try:
                gateway = await get_fabric_gateway()
                chaincode_client = ChaincodeClient(gateway, ChaincodeType.CUSTOMER)
                blockchain_result = await chaincode_client.invoke_chaincode(
                    "customer",
                    "RecordConsent",
                    [customer_id, json.dumps(consent_dict)]
                )
                
                blockchain_transaction_id = blockchain_result.get("transaction_id")
                
                logger.info("Consent recorded on blockchain", 
                           customer_id=customer_id,
                           transaction_id=blockchain_transaction_id)
                
            except FabricError as e:
                logger.error("Failed to record consent on blockchain", 
                            customer_id=customer_id, 
                            error=str(e))
                # Continue with database update even if blockchain fails
            
            # Create history record
            history_data = {
                "customer_id": db_customer.id,
                "change_type": "CONSENT_UPDATE",
                "field_name": "consent_preferences",
                "old_value": json.dumps(old_consent),
                "new_value": json.dumps(consent_dict),
                "changed_by_actor_id": actor.id,
                "blockchain_transaction_id": blockchain_transaction_id
            }
            history = CustomerHistoryModel(**history_data)
            session.add(history)
            
            session.refresh(db_customer)
        
        logger.info("Customer consent recorded successfully", customer_id=customer_id)
        
        return ConsentResponse(
            customer_id=customer_id,
            consent_preferences=consent_data,
            last_updated=datetime.utcnow(),
            recorded_by=current_user.actor_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to record customer consent", 
                    customer_id=customer_id, 
                    error=str(e), 
                    actor_id=current_user.actor_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record customer consent: {str(e)}"
        )


@router.get("/{customer_id}/consent", response_model=ConsentResponse)
async def get_customer_consent(
    customer_id: str,
    current_user: Actor = Depends(require_permissions(Permission.MANAGE_CUSTOMER_CONSENT))
):
    """
    Retrieve customer consent preferences.
    
    Returns current consent preferences from the operational database
    with proper access control validation.
    
    Requirements: 2.6, 4.2
    """
    try:
        logger.info("Retrieving customer consent", 
                   customer_id=customer_id, 
                   actor_id=current_user.actor_id)
        
        # Get customer from database
        customer = db_utils.get_customer_by_customer_id(customer_id)
        
        if not customer:
            logger.warning("Customer not found", customer_id=customer_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer {customer_id} not found"
            )
        
        # Get consent preferences
        consent_preferences = customer.consent_preferences or {}
        
        # Find the most recent consent update from history
        history_records = db_utils.get_customer_history(customer_id)
        last_consent_update = None
        recorded_by = "system"
        
        for record in history_records:
            if record.change_type == "CONSENT_UPDATE":
                last_consent_update = record.timestamp
                # Get the actor who made the change
                with db_utils.db_manager.session_scope() as session:
                    actor = session.query(ActorModel).filter(
                        ActorModel.id == record.changed_by_actor_id
                    ).first()
                    if actor:
                        recorded_by = actor.actor_id
                break
        
        logger.info("Customer consent retrieved successfully", customer_id=customer_id)
        
        return ConsentResponse(
            customer_id=customer_id,
            consent_preferences=ConsentPreferences(**consent_preferences),
            last_updated=last_consent_update or customer.updated_at,
            recorded_by=recorded_by
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve customer consent", 
                    customer_id=customer_id, 
                    error=str(e), 
                    actor_id=current_user.actor_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve customer consent: {str(e)}"
        )


@router.put("/{customer_id}/consent", response_model=ConsentResponse)
async def update_customer_consent(
    customer_id: str,
    consent_data: ConsentPreferences,
    current_user: Actor = Depends(require_permissions(Permission.MANAGE_CUSTOMER_CONSENT))
):
    """
    Update customer consent preferences.
    
    Updates consent preferences in both blockchain and operational database,
    maintaining complete audit trail for compliance purposes.
    
    Requirements: 2.6, 4.2
    """
    try:
        logger.info("Updating customer consent", 
                   customer_id=customer_id, 
                   actor_id=current_user.actor_id)
        
        # Verify customer exists
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
        
        # Update consent preferences in database
        consent_dict = consent_data.dict()
        
        with db_utils.db_manager.session_scope() as session:
            db_customer = session.query(CustomerModel).filter(
                CustomerModel.customer_id == customer_id
            ).first()
            
            if not db_customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer {customer_id} not found"
                )
            
            old_consent = db_customer.consent_preferences or {}
            
            # Check if there are actual changes
            if old_consent == consent_dict:
                logger.info("No changes detected in consent preferences", customer_id=customer_id)
                return ConsentResponse(
                    customer_id=customer_id,
                    consent_preferences=consent_data,
                    last_updated=db_customer.updated_at,
                    recorded_by=current_user.actor_id
                )
            
            db_customer.consent_preferences = consent_dict
            db_customer.updated_at = datetime.utcnow()
            
            # Update consent on blockchain
            blockchain_transaction_id = None
            try:
                gateway = await get_fabric_gateway()
                chaincode_client = ChaincodeClient(gateway, ChaincodeType.CUSTOMER)
                blockchain_result = await chaincode_client.invoke_chaincode(
                    "customer",
                    "UpdateConsent",
                    [customer_id, json.dumps(consent_dict)]
                )
                
                blockchain_transaction_id = blockchain_result.get("transaction_id")
                
                logger.info("Consent updated on blockchain", 
                           customer_id=customer_id,
                           transaction_id=blockchain_transaction_id)
                
            except FabricError as e:
                logger.error("Failed to update consent on blockchain", 
                            customer_id=customer_id, 
                            error=str(e))
                # Continue with database update even if blockchain fails
            
            # Create history record
            history_data = {
                "customer_id": db_customer.id,
                "change_type": "CONSENT_UPDATE",
                "field_name": "consent_preferences",
                "old_value": json.dumps(old_consent),
                "new_value": json.dumps(consent_dict),
                "changed_by_actor_id": actor.id,
                "blockchain_transaction_id": blockchain_transaction_id
            }
            history = CustomerHistoryModel(**history_data)
            session.add(history)
            
            session.refresh(db_customer)
        
        logger.info("Customer consent updated successfully", customer_id=customer_id)
        
        return ConsentResponse(
            customer_id=customer_id,
            consent_preferences=consent_data,
            last_updated=datetime.utcnow(),
            recorded_by=current_user.actor_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update customer consent", 
                    customer_id=customer_id, 
                    error=str(e), 
                    actor_id=current_user.actor_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update customer consent: {str(e)}"
        )


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


def _generate_verification_id() -> str:
    """Generate a unique verification ID."""
    return f"VER_{uuid.uuid4().hex[:12].upper()}"


@router.post("/{customer_id}/verify", response_model=IdentityVerificationResponse, status_code=status.HTTP_201_CREATED)
async def initiate_identity_verification(
    customer_id: str,
    verification_request: IdentityVerificationRequest,
    current_user: Actor = Depends(require_permissions(Permission.CREATE_CUSTOMER))
):
    """
    Initiate identity verification for a customer.
    
    Triggers identity verification checks with external providers and
    records the verification request on the blockchain for audit purposes.
    
    Requirements: 2.5, 4.1
    """
    try:
        logger.info("Initiating identity verification", 
                   customer_id=customer_id, 
                   verification_type=verification_request.verification_type,
                   actor_id=current_user.actor_id)
        
        # Verify customer exists
        customer = db_utils.get_customer_by_customer_id(customer_id)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer {customer_id} not found"
            )
        
        # Generate verification ID
        verification_id = _generate_verification_id()
        
        # Get actor for foreign key
        actor = db_utils.get_actor_by_actor_id(current_user.actor_id)
        if not actor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Actor not found in database"
            )
        
        # Prepare verification data
        verification_data = {
            "verification_id": verification_id,
            "customer_id": customer_id,
            "verification_type": verification_request.verification_type,
            "provider": verification_request.provider,
            "status": "INITIATED",
            "initiated_by": current_user.actor_id,
            "additional_data": verification_request.additional_data
        }
        
        # Record verification initiation on blockchain
        blockchain_transaction_id = None
        try:
            gateway = await get_fabric_gateway()
            chaincode_client = ChaincodeClient(gateway, ChaincodeType.CUSTOMER)
            blockchain_result = await chaincode_client.invoke_chaincode(
                "customer",
                "InitiateIdentityVerification",
                [customer_id, json.dumps(verification_data)]
            )
            
            blockchain_transaction_id = blockchain_result.get("transaction_id")
            
            logger.info("Identity verification initiated on blockchain", 
                       customer_id=customer_id,
                       verification_id=verification_id,
                       transaction_id=blockchain_transaction_id)
            
        except FabricError as e:
            logger.error("Failed to record verification on blockchain", 
                        customer_id=customer_id, 
                        verification_id=verification_id,
                        error=str(e))
            # Continue with the process even if blockchain fails
        
        # Simulate external identity provider integration
        # In a real implementation, this would call actual identity verification services
        provider_response = await _simulate_identity_provider_call(
            customer_id, 
            verification_request.verification_type,
            verification_request.provider,
            verification_request.additional_data
        )
        
        # Update customer KYC/AML status based on verification type
        status_update = {}
        if verification_request.verification_type.upper() == "KYC":
            status_update["kyc_status"] = "IN_PROGRESS"
        elif verification_request.verification_type.upper() == "AML":
            status_update["aml_status"] = "IN_PROGRESS"
        
        if status_update:
            with db_utils.db_manager.session_scope() as session:
                db_customer = session.query(CustomerModel).filter(
                    CustomerModel.customer_id == customer_id
                ).first()
                
                if db_customer:
                    for field, value in status_update.items():
                        setattr(db_customer, field, value)
                    db_customer.updated_at = datetime.utcnow()
                    
                    # Create history record
                    history_data = {
                        "customer_id": db_customer.id,
                        "change_type": "VERIFICATION_INITIATED",
                        "field_name": f"{verification_request.verification_type.lower()}_status",
                        "new_value": status_update.get(f"{verification_request.verification_type.lower()}_status"),
                        "changed_by_actor_id": actor.id,
                        "blockchain_transaction_id": blockchain_transaction_id
                    }
                    history = CustomerHistoryModel(**history_data)
                    session.add(history)
        
        logger.info("Identity verification initiated successfully", 
                   customer_id=customer_id,
                   verification_id=verification_id)
        
        return IdentityVerificationResponse(
            customer_id=customer_id,
            verification_id=verification_id,
            verification_type=verification_request.verification_type,
            status="INITIATED",
            provider=verification_request.provider,
            initiated_by=current_user.actor_id,
            initiated_at=datetime.utcnow(),
            result_details=provider_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to initiate identity verification", 
                    customer_id=customer_id, 
                    error=str(e), 
                    actor_id=current_user.actor_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate identity verification: {str(e)}"
        )


@router.get("/{customer_id}/verify/{verification_id}", response_model=IdentityVerificationResponse)
async def get_verification_status(
    customer_id: str,
    verification_id: str,
    current_user: Actor = Depends(require_permissions(Permission.READ_CUSTOMER))
):
    """
    Get identity verification status.
    
    Retrieves the current status of an identity verification request,
    including results from external identity providers.
    
    Requirements: 2.5, 4.1
    """
    try:
        logger.info("Retrieving verification status", 
                   customer_id=customer_id, 
                   verification_id=verification_id,
                   actor_id=current_user.actor_id)
        
        # Verify customer exists
        customer = db_utils.get_customer_by_customer_id(customer_id)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer {customer_id} not found"
            )
        
        # Query blockchain for verification status
        try:
            gateway = await get_fabric_gateway()
            chaincode_client = ChaincodeClient(gateway, ChaincodeType.CUSTOMER)
            blockchain_result = await chaincode_client.query_chaincode(
                "customer",
                "GetVerificationStatus",
                [customer_id, verification_id]
            )
            
            verification_data = blockchain_result.get("payload", {})
            
            if not verification_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Verification {verification_id} not found"
                )
            
            logger.info("Verification status retrieved successfully", 
                       customer_id=customer_id,
                       verification_id=verification_id)
            
            return IdentityVerificationResponse(
                customer_id=customer_id,
                verification_id=verification_id,
                verification_type=verification_data.get("verification_type", "UNKNOWN"),
                status=verification_data.get("status", "UNKNOWN"),
                provider=verification_data.get("provider", "unknown"),
                initiated_by=verification_data.get("initiated_by", "unknown"),
                initiated_at=datetime.fromisoformat(verification_data.get("initiated_at", datetime.utcnow().isoformat())),
                completed_at=datetime.fromisoformat(verification_data["completed_at"]) if verification_data.get("completed_at") else None,
                result_details=verification_data.get("result_details", {})
            )
            
        except FabricError as e:
            logger.error("Failed to retrieve verification status from blockchain", 
                        customer_id=customer_id, 
                        verification_id=verification_id,
                        error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve verification status"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve verification status", 
                    customer_id=customer_id, 
                    verification_id=verification_id,
                    error=str(e), 
                    actor_id=current_user.actor_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve verification status: {str(e)}"
        )


@router.put("/{customer_id}/verify/{verification_id}", response_model=IdentityVerificationResponse)
async def update_verification_status(
    customer_id: str,
    verification_id: str,
    status_update: VerificationStatusUpdate,
    current_user: Actor = Depends(require_permissions(Permission.UPDATE_CUSTOMER))
):
    """
    Update identity verification status.
    
    Updates the status of an identity verification request, typically
    called when receiving results from external identity providers.
    
    Requirements: 2.5, 4.1
    """
    try:
        logger.info("Updating verification status", 
                   customer_id=customer_id, 
                   verification_id=verification_id,
                   new_status=status_update.status,
                   actor_id=current_user.actor_id)
        
        # Verify customer exists
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
        update_data = {
            "status": status_update.status,
            "result_details": status_update.result_details,
            "completed_at": datetime.utcnow().isoformat() if status_update.status in ["COMPLETED", "FAILED"] else None,
            "updated_by": current_user.actor_id,
            "notes": status_update.notes
        }
        
        # Update verification status on blockchain
        blockchain_transaction_id = None
        try:
            gateway = await get_fabric_gateway()
            chaincode_client = ChaincodeClient(gateway, ChaincodeType.CUSTOMER)
            blockchain_result = await chaincode_client.invoke_chaincode(
                "customer",
                "UpdateVerificationStatus",
                [customer_id, verification_id, json.dumps(update_data)]
            )
            
            blockchain_transaction_id = blockchain_result.get("transaction_id")
            
            logger.info("Verification status updated on blockchain", 
                       customer_id=customer_id,
                       verification_id=verification_id,
                       transaction_id=blockchain_transaction_id)
            
        except FabricError as e:
            logger.error("Failed to update verification status on blockchain", 
                        customer_id=customer_id, 
                        verification_id=verification_id,
                        error=str(e))
            # Continue with database update even if blockchain fails
        
        # Update customer KYC/AML status based on verification results
        customer_status_updates = {}
        
        # Get verification type from blockchain (simplified for this implementation)
        verification_type = "KYC"  # This would be retrieved from blockchain in real implementation
        
        if status_update.status == "COMPLETED":
            if verification_type.upper() == "KYC":
                customer_status_updates["kyc_status"] = "VERIFIED"
            elif verification_type.upper() == "AML":
                customer_status_updates["aml_status"] = "CLEAR"
        elif status_update.status == "FAILED":
            if verification_type.upper() == "KYC":
                customer_status_updates["kyc_status"] = "FAILED"
            elif verification_type.upper() == "AML":
                customer_status_updates["aml_status"] = "FLAGGED"
        
        if customer_status_updates:
            with db_utils.db_manager.session_scope() as session:
                db_customer = session.query(CustomerModel).filter(
                    CustomerModel.customer_id == customer_id
                ).first()
                
                if db_customer:
                    for field, value in customer_status_updates.items():
                        old_value = getattr(db_customer, field)
                        setattr(db_customer, field, value)
                        
                        # Create history record for status change
                        history_data = {
                            "customer_id": db_customer.id,
                            "change_type": "VERIFICATION_COMPLETED",
                            "field_name": field,
                            "old_value": old_value,
                            "new_value": value,
                            "changed_by_actor_id": actor.id,
                            "blockchain_transaction_id": blockchain_transaction_id
                        }
                        history = CustomerHistoryModel(**history_data)
                        session.add(history)
                    
                    db_customer.updated_at = datetime.utcnow()
        
        logger.info("Verification status updated successfully", 
                   customer_id=customer_id,
                   verification_id=verification_id)
        
        return IdentityVerificationResponse(
            customer_id=customer_id,
            verification_id=verification_id,
            verification_type=verification_type,
            status=status_update.status,
            provider="default",
            initiated_by="system",
            initiated_at=datetime.utcnow(),
            completed_at=datetime.utcnow() if status_update.status in ["COMPLETED", "FAILED"] else None,
            result_details=status_update.result_details
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update verification status", 
                    customer_id=customer_id, 
                    verification_id=verification_id,
                    error=str(e), 
                    actor_id=current_user.actor_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update verification status: {str(e)}"
        )


async def _simulate_identity_provider_call(
    customer_id: str, 
    verification_type: str, 
    provider: str,
    additional_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Simulate external identity provider integration.
    
    In a real implementation, this would make actual API calls to
    identity verification services like Jumio, Onfido, or similar providers.
    """
    logger.info("Simulating identity provider call", 
               customer_id=customer_id,
               verification_type=verification_type,
               provider=provider)
    
    # Simulate processing delay
    await asyncio.sleep(0.1)
    
    # Simulate provider response
    if verification_type.upper() == "KYC":
        return {
            "provider_reference": f"{provider}_kyc_{uuid.uuid4().hex[:8]}",
            "confidence_score": 0.95,
            "checks_performed": ["document_verification", "liveness_check", "address_verification"],
            "estimated_completion": "2-5 minutes"
        }
    elif verification_type.upper() == "AML":
        return {
            "provider_reference": f"{provider}_aml_{uuid.uuid4().hex[:8]}",
            "screening_lists": ["sanctions", "pep", "adverse_media"],
            "initial_result": "clear",
            "estimated_completion": "1-2 minutes"
        }
    else:
        return {
            "provider_reference": f"{provider}_doc_{uuid.uuid4().hex[:8]}",
            "document_types": ["passport", "drivers_license", "national_id"],
            "estimated_completion": "3-10 minutes"
        }