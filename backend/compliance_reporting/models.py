"""
Compliance Reporting Pydantic models for request/response validation.

This module contains all Pydantic model classes used by the Compliance Reporting API
for data validation, serialization, and documentation.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import uuid4
from pydantic import BaseModel, Field


class ComplianceEventResponse(BaseModel):
    """Response model for compliance events."""
    id: int
    event_id: str
    event_type: str
    rule_id: Optional[str]
    affected_entity_type: str
    affected_entity_id: str
    severity: str
    description: str
    details: Optional[Dict[str, Any]]
    is_alerted: bool
    acknowledged_by_actor_id: Optional[int]
    acknowledged_at: Optional[datetime]
    resolution_status: str
    resolution_notes: Optional[str]
    actor_id: int
    blockchain_transaction_id: Optional[str]
    timestamp: datetime
    
    model_config = {"from_attributes": True}


class ComplianceEventSummary(BaseModel):
    """Summary statistics for compliance events."""
    total_events: int
    events_by_severity: Dict[str, int]
    events_by_type: Dict[str, int]
    events_by_status: Dict[str, int]
    recent_critical_events: int
    unresolved_events: int


class ComplianceEventFilter(BaseModel):
    """Filter criteria for compliance events."""
    event_type: Optional[str] = None
    severity: Optional[str] = None
    affected_entity_type: Optional[str] = None
    affected_entity_id: Optional[str] = None
    resolution_status: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    actor_id: Optional[int] = None
    is_alerted: Optional[bool] = None


class RegulatoryReportRequest(BaseModel):
    """Request model for generating regulatory reports."""
    report_type: str = Field(..., description="Type of report (AML_SUMMARY, KYC_COMPLIANCE, LOAN_MONITORING)")
    from_date: datetime = Field(..., description="Start date for report period")
    to_date: datetime = Field(..., description="End date for report period")
    entity_filters: Optional[Dict[str, Any]] = Field(None, description="Additional entity filters")
    format: str = Field("JSON", description="Report format (JSON, CSV, PDF)")


class RegulatoryReportResponse(BaseModel):
    """Response model for regulatory reports."""
    report_id: str
    report_type: str
    status: str
    created_at: datetime
    from_date: datetime
    to_date: datetime
    format: str
    download_url: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None


class ReportTemplate(BaseModel):
    """Template for predefined regulatory reports."""
    template_id: str
    name: str
    description: str
    required_parameters: List[str]
    default_format: str


class RegulatoryAccessLog(BaseModel):
    """Model for logging regulatory access."""
    access_id: str
    regulator_id: str
    access_type: str
    resource_accessed: str
    timestamp: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class RegulatoryViewResponse(BaseModel):
    """Response model for regulatory view data."""
    view_id: str
    timestamp: datetime
    data_snapshot: Dict[str, Any]
    access_permissions: List[str]
    data_freshness: str
    audit_trail_hash: str


class RegulatoryDataFilter(BaseModel):
    """Filter model for regulatory data access."""
    entity_types: Optional[List[str]] = None
    severity_levels: Optional[List[str]] = None
    date_range: Optional[Dict[str, datetime]] = None
    compliance_rules: Optional[List[str]] = None