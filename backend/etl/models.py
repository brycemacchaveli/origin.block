"""
Data models for ETL transformations and dimensional modeling.

This module defines the structure of fact and dimension tables
for the BigQuery data warehouse.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class SCDType(Enum):
    """Slowly Changing Dimension types."""
    TYPE_1 = "TYPE_1"  # Overwrite
    TYPE_2 = "TYPE_2"  # Historical tracking


@dataclass
class DimCustomer:
    """Customer dimension table structure."""
    customer_key: int  # Surrogate key
    customer_id: str  # Business key
    first_name: str
    last_name: str
    date_of_birth: Optional[datetime]
    national_id_hash: Optional[str]
    address: Optional[str]
    contact_email: Optional[str]
    contact_phone: Optional[str]
    kyc_status: str
    aml_status: str
    consent_preferences: Optional[Dict[str, Any]]
    created_by_actor_id: str
    
    # SCD Type 2 fields
    effective_date: datetime
    expiration_date: Optional[datetime]
    is_current: bool
    version: int
    
    # Audit fields
    created_at: datetime
    updated_at: datetime
    etl_batch_id: str
    source_system: str = "blockchain_platform"


@dataclass
class DimActor:
    """Actor dimension table structure."""
    actor_key: int  # Surrogate key
    actor_id: str  # Business key
    actor_type: str
    actor_name: str
    role: str
    blockchain_identity: Optional[str]
    permissions: Optional[List[str]]
    is_active: bool
    
    # SCD Type 2 fields
    effective_date: datetime
    expiration_date: Optional[datetime]
    is_current: bool
    version: int
    
    # Audit fields
    created_at: datetime
    updated_at: datetime
    etl_batch_id: str
    source_system: str = "blockchain_platform"


@dataclass
class DimLoanApplication:
    """Loan Application dimension table structure."""
    loan_application_key: int  # Surrogate key
    loan_application_id: str  # Business key
    customer_key: int  # Foreign key to DimCustomer
    loan_type: str
    requested_amount: float
    approval_amount: Optional[float]
    introducer_id: Optional[str]
    rejection_reason: Optional[str]
    
    # SCD Type 2 fields
    effective_date: datetime
    expiration_date: Optional[datetime]
    is_current: bool
    version: int
    
    # Audit fields
    created_at: datetime
    updated_at: datetime
    etl_batch_id: str
    source_system: str = "blockchain_platform"


@dataclass
class DimDate:
    """Date dimension table structure."""
    date_key: int  # YYYYMMDD format
    full_date: datetime
    year: int
    quarter: int
    month: int
    month_name: str
    day: int
    day_of_week: int
    day_name: str
    week_of_year: int
    is_weekend: bool
    is_holiday: bool
    fiscal_year: int
    fiscal_quarter: int


@dataclass
class DimComplianceRule:
    """Compliance Rule dimension table structure."""
    compliance_rule_key: int  # Surrogate key
    rule_id: str  # Business key
    rule_name: str
    rule_description: str
    rule_logic: str
    applies_to_domain: str
    status: str
    last_modified_by: str
    
    # SCD Type 2 fields
    effective_date: datetime
    expiration_date: Optional[datetime]
    is_current: bool
    version: int
    
    # Audit fields
    created_at: datetime
    updated_at: datetime
    etl_batch_id: str
    source_system: str = "blockchain_platform"


@dataclass
class FactLoanApplicationEvents:
    """Loan Application Events fact table structure."""
    # Surrogate keys
    loan_application_key: int
    customer_key: int
    actor_key: int
    date_key: int
    
    # Business keys
    loan_application_id: str
    customer_id: str
    actor_id: str
    
    # Event details
    event_type: str  # STATUS_CHANGE, UPDATE, APPROVAL, REJECTION
    previous_status: Optional[str]
    new_status: Optional[str]
    change_type: str
    
    # Measures
    requested_amount: float
    approval_amount: Optional[float]
    processing_duration_hours: Optional[float]  # Time between status changes
    
    # Degenerate dimensions
    blockchain_transaction_id: Optional[str]
    notes: Optional[str]
    
    # Audit fields
    event_timestamp: datetime
    created_at: datetime
    etl_batch_id: str
    source_system: str = "blockchain_platform"


@dataclass
class FactComplianceEvents:
    """Compliance Events fact table structure."""
    # Surrogate keys
    compliance_rule_key: Optional[int]
    actor_key: int
    date_key: int
    
    # Business keys
    event_id: str
    rule_id: Optional[str]
    actor_id: str
    affected_entity_id: str
    
    # Event details
    event_type: str
    affected_entity_type: str
    severity: str
    resolution_status: str
    
    # Measures
    resolution_duration_hours: Optional[float]  # Time to resolve
    is_violation: bool  # 1 if violation, 0 if not
    alert_count: int  # Number of alerts generated
    
    # Degenerate dimensions
    description: str
    details: Optional[Dict[str, Any]]
    blockchain_transaction_id: Optional[str]
    
    # Audit fields
    event_timestamp: datetime
    acknowledged_at: Optional[datetime]
    created_at: datetime
    etl_batch_id: str
    source_system: str = "blockchain_platform"


@dataclass
class ETLBatch:
    """ETL batch tracking."""
    batch_id: str
    batch_type: str  # FULL, INCREMENTAL
    start_time: datetime
    end_time: Optional[datetime]
    status: str  # RUNNING, SUCCESS, FAILED
    records_processed: int
    records_inserted: int
    records_updated: int
    records_failed: int
    error_message: Optional[str]
    source_system: str = "blockchain_platform"