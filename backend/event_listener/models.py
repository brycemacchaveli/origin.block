"""
Event Listener Pydantic models for request/response validation.

This module contains all Pydantic model classes used by the Event Listener API
for data validation, serialization, and documentation.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ReconciliationRequest(BaseModel):
    """Request model for reconciliation."""
    entity_types: Optional[List[str]] = Field(
        default=None,
        description="List of entity types to reconcile (customers, loan_applications, compliance_events, loan_documents)"
    )
    batch_size: int = Field(default=100, ge=1, le=1000, description="Batch size for processing")


class ManualResyncRequest(BaseModel):
    """Request model for manual resync."""
    entity_type: str = Field(description="Type of entity to resync")
    entity_id: str = Field(description="ID of entity to resync")
    force_overwrite: bool = Field(default=False, description="Force overwrite even if no inconsistencies")


class InconsistencyResponse(BaseModel):
    """Response model for inconsistency data."""
    inconsistency_type: str
    severity: str
    entity_type: str
    entity_id: str
    description: str
    detected_at: datetime
    field_differences: Optional[Dict[str, Any]] = None
    blockchain_data: Optional[Dict[str, Any]] = None
    database_data: Optional[Dict[str, Any]] = None


class ReconciliationResponse(BaseModel):
    """Response model for reconciliation results."""
    success: bool
    start_time: datetime
    end_time: datetime
    entities_checked: Dict[str, int]
    total_inconsistencies: int
    severity_breakdown: Dict[str, int]
    error_message: Optional[str] = None


class AlertResponse(BaseModel):
    """Response model for alerts."""
    alert_type: str
    severity: str
    title: str
    description: str
    details: Dict[str, Any]
    created_at: datetime
    acknowledged: bool
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None


class ConsistencySummaryResponse(BaseModel):
    """Response model for consistency summary."""
    total_inconsistencies: int
    by_entity_type: Dict[str, int]
    by_severity: Dict[str, int]
    by_inconsistency_type: Dict[str, int]
    last_reconciliation: Optional[datetime] = None


class IntegrityReportResponse(BaseModel):
    """Response model for integrity report."""
    generated_at: datetime
    reconciliation_report: ReconciliationResponse
    database_statistics: Dict[str, Any]
    blockchain_connectivity: Dict[str, Any]
    inconsistency_summary: ConsistencySummaryResponse
    recommendations: List[str]
    success: bool
    error: Optional[str] = None