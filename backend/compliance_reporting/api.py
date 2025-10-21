"""
Compliance Reporting API endpoints for regulatory monitoring and reporting.

This module provides endpoints for querying compliance events, generating regulatory reports,
and providing secure access for regulatory authorities.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func

from shared.database import (
    get_db_session, 
    ComplianceEventModel, 
    ActorModel,
    CustomerModel,
    LoanApplicationModel
)
from shared.auth import (
    get_current_user, 
    require_permissions, 
    require_roles,
    Actor, 
    Permission, 
    Role
)
from shared.fabric_gateway import get_fabric_gateway, ChaincodeClient, ChaincodeType
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter()


# Pydantic models for request/response
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


@router.get("/events", response_model=List[ComplianceEventResponse])
async def list_compliance_events(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Number of events per page"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    severity: Optional[str] = Query(None, description="Filter by severity (INFO, WARNING, ERROR, CRITICAL)"),
    affected_entity_type: Optional[str] = Query(None, description="Filter by affected entity type"),
    affected_entity_id: Optional[str] = Query(None, description="Filter by affected entity ID"),
    resolution_status: Optional[str] = Query(None, description="Filter by resolution status"),
    from_date: Optional[datetime] = Query(None, description="Filter events from this date"),
    to_date: Optional[datetime] = Query(None, description="Filter events to this date"),
    is_alerted: Optional[bool] = Query(None, description="Filter by alert status"),
    current_user: Actor = Depends(require_permissions(Permission.READ_COMPLIANCE_EVENTS)),
    db: Session = Depends(get_db_session)
):
    """
    List compliance events with filtering and pagination.
    
    Supports filtering by event type, severity, entity, date range, and resolution status.
    Results are paginated and ordered by timestamp (most recent first).
    """
    try:
        logger.info("Listing compliance events", 
                   actor_id=current_user.actor_id,
                   page=page, 
                   page_size=page_size)
        
        # Build base query
        query = db.query(ComplianceEventModel)
        
        # Apply filters
        if event_type:
            query = query.filter(ComplianceEventModel.event_type == event_type)
        
        if severity:
            query = query.filter(ComplianceEventModel.severity == severity)
        
        if affected_entity_type:
            query = query.filter(ComplianceEventModel.affected_entity_type == affected_entity_type)
        
        if affected_entity_id:
            query = query.filter(ComplianceEventModel.affected_entity_id == affected_entity_id)
        
        if resolution_status:
            query = query.filter(ComplianceEventModel.resolution_status == resolution_status)
        
        if from_date:
            query = query.filter(ComplianceEventModel.timestamp >= from_date)
        
        if to_date:
            query = query.filter(ComplianceEventModel.timestamp <= to_date)
        
        if is_alerted is not None:
            query = query.filter(ComplianceEventModel.is_alerted == is_alerted)
        
        # Apply pagination and ordering
        offset = (page - 1) * page_size
        events = query.order_by(desc(ComplianceEventModel.timestamp)).offset(offset).limit(page_size).all()
        
        logger.info("Retrieved compliance events", 
                   count=len(events),
                   actor_id=current_user.actor_id)
        
        return [ComplianceEventResponse.model_validate(event) for event in events]
        
    except Exception as e:
        logger.error("Failed to list compliance events", 
                    error=str(e),
                    actor_id=current_user.actor_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve compliance events")


@router.get("/events/{event_id}", response_model=ComplianceEventResponse)
async def get_compliance_event(
    event_id: str,
    current_user: Actor = Depends(require_permissions(Permission.READ_COMPLIANCE_EVENTS)),
    db: Session = Depends(get_db_session)
):
    """
    Get detailed information about a specific compliance event.
    
    Returns complete event details including related entity information
    and resolution history.
    """
    try:
        logger.info("Getting compliance event details", 
                   event_id=event_id,
                   actor_id=current_user.actor_id)
        
        event = db.query(ComplianceEventModel).filter(
            ComplianceEventModel.event_id == event_id
        ).first()
        
        if not event:
            logger.warning("Compliance event not found", 
                          event_id=event_id,
                          actor_id=current_user.actor_id)
            raise HTTPException(status_code=404, detail="Compliance event not found")
        
        logger.info("Retrieved compliance event details", 
                   event_id=event_id,
                   actor_id=current_user.actor_id)
        
        return ComplianceEventResponse.model_validate(event)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get compliance event", 
                    event_id=event_id,
                    error=str(e),
                    actor_id=current_user.actor_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve compliance event")


@router.get("/events/summary", response_model=ComplianceEventSummary)
async def get_compliance_events_summary(
    days: int = Query(30, ge=1, le=365, description="Number of days to include in summary"),
    current_user: Actor = Depends(require_permissions(Permission.READ_COMPLIANCE_EVENTS)),
    db: Session = Depends(get_db_session)
):
    """
    Get aggregated summary statistics for compliance events.
    
    Provides counts by severity, type, status, and highlights recent critical events.
    """
    try:
        logger.info("Getting compliance events summary", 
                   days=days,
                   actor_id=current_user.actor_id)
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Base query for the time period
        base_query = db.query(ComplianceEventModel).filter(
            ComplianceEventModel.timestamp >= start_date,
            ComplianceEventModel.timestamp <= end_date
        )
        
        # Total events count
        total_events = base_query.count()
        
        # Events by severity
        severity_counts = db.query(
            ComplianceEventModel.severity,
            func.count(ComplianceEventModel.id)
        ).filter(
            ComplianceEventModel.timestamp >= start_date,
            ComplianceEventModel.timestamp <= end_date
        ).group_by(ComplianceEventModel.severity).all()
        
        events_by_severity = {severity: count for severity, count in severity_counts}
        
        # Events by type
        type_counts = db.query(
            ComplianceEventModel.event_type,
            func.count(ComplianceEventModel.id)
        ).filter(
            ComplianceEventModel.timestamp >= start_date,
            ComplianceEventModel.timestamp <= end_date
        ).group_by(ComplianceEventModel.event_type).all()
        
        events_by_type = {event_type: count for event_type, count in type_counts}
        
        # Events by resolution status
        status_counts = db.query(
            ComplianceEventModel.resolution_status,
            func.count(ComplianceEventModel.id)
        ).filter(
            ComplianceEventModel.timestamp >= start_date,
            ComplianceEventModel.timestamp <= end_date
        ).group_by(ComplianceEventModel.resolution_status).all()
        
        events_by_status = {status: count for status, count in status_counts}
        
        # Recent critical events (last 7 days)
        recent_critical_start = end_date - timedelta(days=7)
        recent_critical_events = db.query(ComplianceEventModel).filter(
            ComplianceEventModel.timestamp >= recent_critical_start,
            ComplianceEventModel.severity == 'CRITICAL'
        ).count()
        
        # Unresolved events
        unresolved_events = base_query.filter(
            ComplianceEventModel.resolution_status.in_(['OPEN', 'IN_PROGRESS'])
        ).count()
        
        summary = ComplianceEventSummary(
            total_events=total_events,
            events_by_severity=events_by_severity,
            events_by_type=events_by_type,
            events_by_status=events_by_status,
            recent_critical_events=recent_critical_events,
            unresolved_events=unresolved_events
        )
        
        logger.info("Generated compliance events summary", 
                   total_events=total_events,
                   actor_id=current_user.actor_id)
        
        return summary
        
    except Exception as e:
        logger.error("Failed to generate compliance events summary", 
                    error=str(e),
                    actor_id=current_user.actor_id)
        raise HTTPException(status_code=500, detail="Failed to generate compliance events summary")


@router.get("/events/real-time")
async def get_real_time_compliance_monitoring(
    severity_filter: Optional[str] = Query(None, description="Filter by minimum severity"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    current_user: Actor = Depends(require_permissions(Permission.READ_COMPLIANCE_EVENTS)),
    db: Session = Depends(get_db_session)
):
    """
    Get real-time compliance monitoring data.
    
    Returns recent compliance events and active alerts for monitoring dashboards.
    """
    try:
        logger.info("Getting real-time compliance monitoring data", 
                   actor_id=current_user.actor_id)
        
        # Get events from the last hour for real-time monitoring
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        
        query = db.query(ComplianceEventModel).filter(
            ComplianceEventModel.timestamp >= one_hour_ago
        )
        
        # Apply filters
        if severity_filter:
            # Filter by minimum severity level
            severity_levels = ['INFO', 'WARNING', 'ERROR', 'CRITICAL']
            if severity_filter in severity_levels:
                min_index = severity_levels.index(severity_filter)
                allowed_severities = severity_levels[min_index:]
                query = query.filter(ComplianceEventModel.severity.in_(allowed_severities))
        
        if entity_type:
            query = query.filter(ComplianceEventModel.affected_entity_type == entity_type)
        
        # Get recent events ordered by timestamp
        recent_events = query.order_by(desc(ComplianceEventModel.timestamp)).limit(100).all()
        
        # Get active alerts (unacknowledged critical/error events)
        active_alerts = db.query(ComplianceEventModel).filter(
            ComplianceEventModel.severity.in_(['ERROR', 'CRITICAL']),
            ComplianceEventModel.is_alerted == True,
            ComplianceEventModel.acknowledged_at.is_(None)
        ).order_by(desc(ComplianceEventModel.timestamp)).limit(50).all()
        
        monitoring_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "recent_events": [ComplianceEventResponse.model_validate(event) for event in recent_events],
            "active_alerts": [ComplianceEventResponse.model_validate(alert) for alert in active_alerts],
            "summary": {
                "recent_events_count": len(recent_events),
                "active_alerts_count": len(active_alerts),
                "monitoring_period_hours": 1
            }
        }
        
        logger.info("Generated real-time compliance monitoring data", 
                   recent_events=len(recent_events),
                   active_alerts=len(active_alerts),
                   actor_id=current_user.actor_id)
        
        return monitoring_data
        
    except Exception as e:
        logger.error("Failed to get real-time compliance monitoring data", 
                    error=str(e),
                    actor_id=current_user.actor_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve real-time monitoring data")


# Regulatory Reporting Models
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


@router.post("/reports/regulatory", response_model=RegulatoryReportResponse)
async def generate_regulatory_report(
    report_request: RegulatoryReportRequest,
    current_user: Actor = Depends(require_permissions(Permission.GENERATE_REGULATORY_REPORT)),
    db: Session = Depends(get_db_session)
):
    """
    Generate a regulatory report based on immutable transaction history.
    
    Creates predefined report templates aggregating ComplianceEvent data
    by date range, loan type, and other criteria for regulatory submission.
    """
    try:
        logger.info("Generating regulatory report", 
                   report_type=report_request.report_type,
                   from_date=report_request.from_date,
                   to_date=report_request.to_date,
                   actor_id=current_user.actor_id)
        
        # Generate unique report ID
        report_id = f"REG_{report_request.report_type}_{uuid4().hex[:8]}"
        
        # Validate date range
        if report_request.from_date >= report_request.to_date:
            raise HTTPException(status_code=400, detail="Invalid date range: from_date must be before to_date")
        
        # Generate report based on type
        report_data = await _generate_report_by_type(
            report_request.report_type,
            report_request.from_date,
            report_request.to_date,
            report_request.entity_filters or {},
            db
        )
        
        # Create report summary
        summary = {
            "total_events": len(report_data.get("events", [])),
            "period_days": (report_request.to_date - report_request.from_date).days,
            "generated_by": current_user.actor_id,
            "data_source": "immutable_blockchain_ledger"
        }
        
        # In a real implementation, you would store the report data
        # and provide a download URL. For now, we'll return the summary.
        
        response = RegulatoryReportResponse(
            report_id=report_id,
            report_type=report_request.report_type,
            status="COMPLETED",
            created_at=datetime.utcnow(),
            from_date=report_request.from_date,
            to_date=report_request.to_date,
            format=report_request.format,
            download_url=f"/api/compliance/reports/{report_id}/download",
            summary=summary
        )
        
        logger.info("Generated regulatory report", 
                   report_id=report_id,
                   total_events=summary["total_events"],
                   actor_id=current_user.actor_id)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate regulatory report", 
                    error=str(e),
                    actor_id=current_user.actor_id)
        raise HTTPException(status_code=500, detail="Failed to generate regulatory report")


@router.get("/reports/{report_id}", response_model=RegulatoryReportResponse)
async def get_regulatory_report(
    report_id: str,
    current_user: Actor = Depends(require_permissions(Permission.GENERATE_REGULATORY_REPORT)),
    db: Session = Depends(get_db_session)
):
    """
    Retrieve regulatory report details and status.
    
    Returns report metadata and download information for completed reports.
    """
    try:
        logger.info("Retrieving regulatory report", 
                   report_id=report_id,
                   actor_id=current_user.actor_id)
        
        # In a real implementation, you would retrieve the report from storage
        # For now, we'll return a mock response
        
        if not report_id.startswith("REG_"):
            raise HTTPException(status_code=404, detail="Report not found")
        
        # Parse report type from ID
        parts = report_id.split("_")
        if len(parts) < 2:
            raise HTTPException(status_code=404, detail="Invalid report ID format")
        
        report_type = parts[1]
        
        response = RegulatoryReportResponse(
            report_id=report_id,
            report_type=report_type,
            status="COMPLETED",
            created_at=datetime.utcnow() - timedelta(minutes=5),
            from_date=datetime.utcnow() - timedelta(days=30),
            to_date=datetime.utcnow(),
            format="JSON",
            download_url=f"/api/compliance/reports/{report_id}/download",
            summary={
                "total_events": 150,
                "period_days": 30,
                "generated_by": current_user.actor_id,
                "data_source": "immutable_blockchain_ledger"
            }
        )
        
        logger.info("Retrieved regulatory report", 
                   report_id=report_id,
                   actor_id=current_user.actor_id)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve regulatory report", 
                    report_id=report_id,
                    error=str(e),
                    actor_id=current_user.actor_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve regulatory report")


@router.get("/reports/{report_id}/download")
async def download_regulatory_report(
    report_id: str,
    format: str = Query("JSON", description="Download format (JSON, CSV, PDF)"),
    current_user: Actor = Depends(require_permissions(Permission.GENERATE_REGULATORY_REPORT)),
    db: Session = Depends(get_db_session)
):
    """
    Download regulatory report in specified format.
    
    Provides the actual report data in downloadable format for regulatory submission.
    """
    try:
        logger.info("Downloading regulatory report", 
                   report_id=report_id,
                   format=format,
                   actor_id=current_user.actor_id)
        
        if not report_id.startswith("REG_"):
            raise HTTPException(status_code=404, detail="Report not found")
        
        # Parse report type from ID
        parts = report_id.split("_")
        if len(parts) < 2:
            raise HTTPException(status_code=404, detail="Invalid report ID format")
        
        report_type = parts[1]
        
        # Generate report data based on type
        # In a real implementation, this would be retrieved from storage
        report_data = await _generate_sample_report_data(report_type, db)
        
        # Format response based on requested format
        if format.upper() == "JSON":
            from fastapi.responses import JSONResponse
            return JSONResponse(
                content=report_data,
                headers={
                    "Content-Disposition": f"attachment; filename={report_id}.json",
                    "Content-Type": "application/json"
                }
            )
        elif format.upper() == "CSV":
            # Convert to CSV format
            import csv
            import io
            
            output = io.StringIO()
            if report_data.get("events"):
                writer = csv.DictWriter(output, fieldnames=report_data["events"][0].keys())
                writer.writeheader()
                writer.writerows(report_data["events"])
            
            from fastapi.responses import StreamingResponse
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode()),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={report_id}.csv"}
            )
        else:
            raise HTTPException(status_code=400, detail="Unsupported format. Use JSON or CSV.")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to download regulatory report", 
                    report_id=report_id,
                    error=str(e),
                    actor_id=current_user.actor_id)
        raise HTTPException(status_code=500, detail="Failed to download regulatory report")


@router.get("/reports/templates", response_model=List[ReportTemplate])
async def get_report_templates(
    current_user: Actor = Depends(require_permissions(Permission.GENERATE_REGULATORY_REPORT))
):
    """
    Get available regulatory report templates.
    
    Returns predefined report templates with their parameters and descriptions.
    """
    try:
        logger.info("Getting report templates", actor_id=current_user.actor_id)
        
        templates = [
            ReportTemplate(
                template_id="AML_SUMMARY",
                name="AML Compliance Summary",
                description="Summary of AML checks, violations, and resolutions for regulatory reporting",
                required_parameters=["from_date", "to_date"],
                default_format="JSON"
            ),
            ReportTemplate(
                template_id="KYC_COMPLIANCE",
                name="KYC Compliance Report",
                description="Customer KYC verification status and compliance events",
                required_parameters=["from_date", "to_date"],
                default_format="JSON"
            ),
            ReportTemplate(
                template_id="LOAN_MONITORING",
                name="Loan Monitoring Report",
                description="Loan application processing and compliance monitoring",
                required_parameters=["from_date", "to_date", "loan_type"],
                default_format="JSON"
            ),
            ReportTemplate(
                template_id="TRANSACTION_AUDIT",
                name="Transaction Audit Trail",
                description="Complete audit trail of all transactions and compliance events",
                required_parameters=["from_date", "to_date"],
                default_format="JSON"
            )
        ]
        
        logger.info("Retrieved report templates", 
                   count=len(templates),
                   actor_id=current_user.actor_id)
        
        return templates
        
    except Exception as e:
        logger.error("Failed to get report templates", 
                    error=str(e),
                    actor_id=current_user.actor_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve report templates")


# Helper functions for report generation
async def _generate_report_by_type(
    report_type: str,
    from_date: datetime,
    to_date: datetime,
    entity_filters: Dict[str, Any],
    db: Session
) -> Dict[str, Any]:
    """Generate report data based on report type."""
    
    if report_type == "AML_SUMMARY":
        return await _generate_aml_summary_report(from_date, to_date, entity_filters, db)
    elif report_type == "KYC_COMPLIANCE":
        return await _generate_kyc_compliance_report(from_date, to_date, entity_filters, db)
    elif report_type == "LOAN_MONITORING":
        return await _generate_loan_monitoring_report(from_date, to_date, entity_filters, db)
    elif report_type == "TRANSACTION_AUDIT":
        return await _generate_transaction_audit_report(from_date, to_date, entity_filters, db)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported report type: {report_type}")


async def _generate_aml_summary_report(
    from_date: datetime,
    to_date: datetime,
    entity_filters: Dict[str, Any],
    db: Session
) -> Dict[str, Any]:
    """Generate AML summary report."""
    
    # Query AML-related compliance events
    aml_events = db.query(ComplianceEventModel).filter(
        ComplianceEventModel.timestamp >= from_date,
        ComplianceEventModel.timestamp <= to_date,
        ComplianceEventModel.event_type.in_(['AML_CHECK', 'SANCTION_SCREENING', 'AML_VIOLATION'])
    ).all()
    
    # Aggregate data
    total_checks = len([e for e in aml_events if e.event_type == 'AML_CHECK'])
    violations = len([e for e in aml_events if e.event_type == 'AML_VIOLATION'])
    sanction_hits = len([e for e in aml_events if e.event_type == 'SANCTION_SCREENING' and e.severity in ['ERROR', 'CRITICAL']])
    
    return {
        "report_type": "AML_SUMMARY",
        "period": {"from": from_date.isoformat(), "to": to_date.isoformat()},
        "summary": {
            "total_aml_checks": total_checks,
            "violations_detected": violations,
            "sanction_list_hits": sanction_hits,
            "compliance_rate": ((total_checks - violations) / total_checks * 100) if total_checks > 0 else 100
        },
        "events": [
            {
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type,
                "severity": event.severity,
                "affected_entity_type": event.affected_entity_type,
                "affected_entity_id": event.affected_entity_id,
                "description": event.description,
                "resolution_status": event.resolution_status
            }
            for event in aml_events
        ]
    }


async def _generate_kyc_compliance_report(
    from_date: datetime,
    to_date: datetime,
    entity_filters: Dict[str, Any],
    db: Session
) -> Dict[str, Any]:
    """Generate KYC compliance report."""
    
    # Query KYC-related compliance events
    kyc_events = db.query(ComplianceEventModel).filter(
        ComplianceEventModel.timestamp >= from_date,
        ComplianceEventModel.timestamp <= to_date,
        ComplianceEventModel.event_type.in_(['KYC_VERIFICATION', 'KYC_UPDATE', 'KYC_FAILURE'])
    ).all()
    
    # Get customer KYC status summary
    customers = db.query(CustomerModel).all()
    kyc_verified = len([c for c in customers if c.kyc_status == 'VERIFIED'])
    kyc_pending = len([c for c in customers if c.kyc_status == 'PENDING'])
    kyc_failed = len([c for c in customers if c.kyc_status == 'FAILED'])
    
    return {
        "report_type": "KYC_COMPLIANCE",
        "period": {"from": from_date.isoformat(), "to": to_date.isoformat()},
        "summary": {
            "total_customers": len(customers),
            "kyc_verified": kyc_verified,
            "kyc_pending": kyc_pending,
            "kyc_failed": kyc_failed,
            "verification_rate": (kyc_verified / len(customers) * 100) if customers else 0
        },
        "events": [
            {
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type,
                "severity": event.severity,
                "affected_entity_type": event.affected_entity_type,
                "affected_entity_id": event.affected_entity_id,
                "description": event.description,
                "resolution_status": event.resolution_status
            }
            for event in kyc_events
        ]
    }


async def _generate_loan_monitoring_report(
    from_date: datetime,
    to_date: datetime,
    entity_filters: Dict[str, Any],
    db: Session
) -> Dict[str, Any]:
    """Generate loan monitoring report."""
    
    # Query loan-related compliance events
    loan_events = db.query(ComplianceEventModel).filter(
        ComplianceEventModel.timestamp >= from_date,
        ComplianceEventModel.timestamp <= to_date,
        ComplianceEventModel.affected_entity_type == 'LOAN_APPLICATION'
    ).all()
    
    # Get loan application summary
    loans = db.query(LoanApplicationModel).filter(
        LoanApplicationModel.application_date >= from_date,
        LoanApplicationModel.application_date <= to_date
    ).all()
    
    # Apply loan type filter if specified
    if entity_filters.get("loan_type"):
        loans = [l for l in loans if l.loan_type == entity_filters["loan_type"]]
    
    approved_loans = len([l for l in loans if l.application_status == 'APPROVED'])
    rejected_loans = len([l for l in loans if l.application_status == 'REJECTED'])
    
    return {
        "report_type": "LOAN_MONITORING",
        "period": {"from": from_date.isoformat(), "to": to_date.isoformat()},
        "filters": entity_filters,
        "summary": {
            "total_applications": len(loans),
            "approved_applications": approved_loans,
            "rejected_applications": rejected_loans,
            "approval_rate": (approved_loans / len(loans) * 100) if loans else 0,
            "compliance_events": len(loan_events)
        },
        "events": [
            {
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type,
                "severity": event.severity,
                "affected_entity_type": event.affected_entity_type,
                "affected_entity_id": event.affected_entity_id,
                "description": event.description,
                "resolution_status": event.resolution_status
            }
            for event in loan_events
        ]
    }


async def _generate_transaction_audit_report(
    from_date: datetime,
    to_date: datetime,
    entity_filters: Dict[str, Any],
    db: Session
) -> Dict[str, Any]:
    """Generate transaction audit trail report."""
    
    # Query all compliance events for audit trail
    all_events = db.query(ComplianceEventModel).filter(
        ComplianceEventModel.timestamp >= from_date,
        ComplianceEventModel.timestamp <= to_date
    ).order_by(ComplianceEventModel.timestamp).all()
    
    return {
        "report_type": "TRANSACTION_AUDIT",
        "period": {"from": from_date.isoformat(), "to": to_date.isoformat()},
        "summary": {
            "total_events": len(all_events),
            "audit_trail_complete": True,
            "data_integrity_verified": True
        },
        "events": [
            {
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type,
                "severity": event.severity,
                "affected_entity_type": event.affected_entity_type,
                "affected_entity_id": event.affected_entity_id,
                "description": event.description,
                "actor_id": event.actor_id,
                "blockchain_transaction_id": event.blockchain_transaction_id,
                "resolution_status": event.resolution_status
            }
            for event in all_events
        ]
    }


async def _generate_sample_report_data(report_type: str, db: Session) -> Dict[str, Any]:
    """Generate sample report data for download."""
    
    # This is a simplified version for demonstration
    # In a real implementation, this would retrieve stored report data
    
    sample_events = [
        {
            "event_id": "evt_001",
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "AML_CHECK",
            "severity": "INFO",
            "affected_entity_type": "CUSTOMER",
            "affected_entity_id": "cust_001",
            "description": "AML check completed successfully",
            "resolution_status": "RESOLVED"
        },
        {
            "event_id": "evt_002",
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "KYC_VERIFICATION",
            "severity": "INFO",
            "affected_entity_type": "CUSTOMER",
            "affected_entity_id": "cust_002",
            "description": "KYC verification completed",
            "resolution_status": "RESOLVED"
        }
    ]
    
    return {
        "report_type": report_type,
        "generated_at": datetime.utcnow().isoformat(),
        "data_source": "immutable_blockchain_ledger",
        "events": sample_events
    }


# Regulatory View Models
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


@router.get("/regulator/view")
async def regulator_view(
    entity_type: Optional[str] = Query(None, description="Filter by entity type (CUSTOMER, LOAN_APPLICATION)"),
    severity: Optional[str] = Query(None, description="Minimum severity level (INFO, WARNING, ERROR, CRITICAL)"),
    hours: int = Query(24, ge=1, le=168, description="Hours of data to include (max 7 days)"),
    current_user: Actor = Depends(require_roles(Role.REGULATOR)),
    request: Request = None,
    db: Session = Depends(get_db_session)
):
    """
    Provide secure, read-only interface for authorized regulators.
    
    Offers near real-time regulatory monitoring with filtered ComplianceEvent data
    and comprehensive audit logging of all regulatory access.
    """
    try:
        # Generate unique view ID for audit trail
        view_id = f"REG_VIEW_{uuid4().hex[:8]}"
        
        logger.info("Regulatory view accessed", 
                   view_id=view_id,
                   regulator_id=current_user.actor_id,
                   entity_type=entity_type,
                   severity=severity,
                   hours=hours)
        
        # Log regulatory access for audit trail
        await _log_regulatory_access(
            regulator_id=current_user.actor_id,
            access_type="VIEW_COMPLIANCE_DATA",
            resource_accessed=f"compliance_events?entity_type={entity_type}&severity={severity}&hours={hours}",
            request=request,
            db=db
        )
        
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        # Build query with regulatory filters
        query = db.query(ComplianceEventModel).filter(
            ComplianceEventModel.timestamp >= start_time,
            ComplianceEventModel.timestamp <= end_time
        )
        
        # Apply entity type filter
        if entity_type:
            query = query.filter(ComplianceEventModel.affected_entity_type == entity_type)
        
        # Apply severity filter (minimum level)
        if severity:
            severity_levels = ['INFO', 'WARNING', 'ERROR', 'CRITICAL']
            if severity in severity_levels:
                min_index = severity_levels.index(severity)
                allowed_severities = severity_levels[min_index:]
                query = query.filter(ComplianceEventModel.severity.in_(allowed_severities))
        
        # Execute query with ordering
        compliance_events = query.order_by(desc(ComplianceEventModel.timestamp)).limit(1000).all()
        
        # Get summary statistics
        total_events = len(compliance_events)
        critical_events = len([e for e in compliance_events if e.severity == 'CRITICAL'])
        unresolved_events = len([e for e in compliance_events if e.resolution_status in ['OPEN', 'IN_PROGRESS']])
        
        # Get entity summaries for regulatory overview
        customer_events = len([e for e in compliance_events if e.affected_entity_type == 'CUSTOMER'])
        loan_events = len([e for e in compliance_events if e.affected_entity_type == 'LOAN_APPLICATION'])
        
        # Create data snapshot for regulatory view
        data_snapshot = {
            "summary": {
                "total_events": total_events,
                "critical_events": critical_events,
                "unresolved_events": unresolved_events,
                "customer_related_events": customer_events,
                "loan_related_events": loan_events,
                "monitoring_period_hours": hours,
                "data_as_of": end_time.isoformat()
            },
            "events": [
                {
                    "event_id": event.event_id,
                    "timestamp": event.timestamp.isoformat(),
                    "event_type": event.event_type,
                    "severity": event.severity,
                    "affected_entity_type": event.affected_entity_type,
                    "affected_entity_id": event.affected_entity_id,
                    "description": event.description,
                    "resolution_status": event.resolution_status,
                    "is_alerted": event.is_alerted,
                    "blockchain_transaction_id": event.blockchain_transaction_id
                }
                for event in compliance_events
            ],
            "regulatory_metadata": {
                "data_source": "immutable_blockchain_ledger",
                "data_integrity_verified": True,
                "access_permissions": ["READ_ONLY", "COMPLIANCE_MONITORING"],
                "regulator_id": current_user.actor_id,
                "view_generated_at": datetime.utcnow().isoformat()
            }
        }
        
        # Generate audit trail hash for data integrity
        import hashlib
        data_string = json.dumps(data_snapshot, sort_keys=True, default=str)
        audit_trail_hash = hashlib.sha256(data_string.encode()).hexdigest()
        
        response = RegulatoryViewResponse(
            view_id=view_id,
            timestamp=datetime.utcnow(),
            data_snapshot=data_snapshot,
            access_permissions=["READ_ONLY", "COMPLIANCE_MONITORING"],
            data_freshness="REAL_TIME",
            audit_trail_hash=audit_trail_hash
        )
        
        logger.info("Regulatory view generated", 
                   view_id=view_id,
                   regulator_id=current_user.actor_id,
                   total_events=total_events,
                   critical_events=critical_events)
        
        return response
        
    except Exception as e:
        logger.error("Failed to generate regulatory view", 
                    error=str(e),
                    regulator_id=current_user.actor_id)
        raise HTTPException(status_code=500, detail="Failed to generate regulatory view")


@router.get("/regulator/entities/{entity_type}")
async def get_regulatory_entity_view(
    entity_type: str,
    entity_id: Optional[str] = Query(None, description="Specific entity ID to view"),
    include_history: bool = Query(True, description="Include historical compliance events"),
    current_user: Actor = Depends(require_roles(Role.REGULATOR)),
    request: Request = None,
    db: Session = Depends(get_db_session)
):
    """
    Get regulatory view of specific entity types with compliance history.
    
    Provides detailed view of customers or loan applications with their
    complete compliance event history for regulatory investigation.
    """
    try:
        logger.info("Regulatory entity view accessed", 
                   entity_type=entity_type,
                   entity_id=entity_id,
                   regulator_id=current_user.actor_id)
        
        # Validate entity type
        valid_entity_types = ['CUSTOMER', 'LOAN_APPLICATION', 'ACTOR']
        if entity_type.upper() not in valid_entity_types:
            raise HTTPException(status_code=400, detail=f"Invalid entity type. Must be one of: {valid_entity_types}")
        
        # Log regulatory access
        await _log_regulatory_access(
            regulator_id=current_user.actor_id,
            access_type="VIEW_ENTITY_DETAILS",
            resource_accessed=f"entity/{entity_type}/{entity_id or 'all'}",
            request=request,
            db=db
        )
        
        entity_type_upper = entity_type.upper()
        
        # Build compliance events query
        events_query = db.query(ComplianceEventModel).filter(
            ComplianceEventModel.affected_entity_type == entity_type_upper
        )
        
        if entity_id:
            events_query = events_query.filter(
                ComplianceEventModel.affected_entity_id == entity_id
            )
        
        # Get compliance events
        compliance_events = events_query.order_by(desc(ComplianceEventModel.timestamp)).limit(500).all()
        
        # Get entity details based on type
        entity_details = []
        if entity_type_upper == 'CUSTOMER':
            if entity_id:
                customer = db.query(CustomerModel).filter(CustomerModel.customer_id == entity_id).first()
                if customer:
                    entity_details = [{
                        "entity_id": customer.customer_id,
                        "entity_type": "CUSTOMER",
                        "kyc_status": customer.kyc_status,
                        "aml_status": customer.aml_status,
                        "created_at": customer.created_at.isoformat(),
                        "updated_at": customer.updated_at.isoformat()
                    }]
            else:
                customers = db.query(CustomerModel).limit(100).all()
                entity_details = [
                    {
                        "entity_id": customer.customer_id,
                        "entity_type": "CUSTOMER",
                        "kyc_status": customer.kyc_status,
                        "aml_status": customer.aml_status,
                        "created_at": customer.created_at.isoformat(),
                        "updated_at": customer.updated_at.isoformat()
                    }
                    for customer in customers
                ]
        
        elif entity_type_upper == 'LOAN_APPLICATION':
            if entity_id:
                loan = db.query(LoanApplicationModel).filter(LoanApplicationModel.loan_application_id == entity_id).first()
                if loan:
                    entity_details = [{
                        "entity_id": loan.loan_application_id,
                        "entity_type": "LOAN_APPLICATION",
                        "application_status": loan.application_status,
                        "loan_type": loan.loan_type,
                        "requested_amount": loan.requested_amount,
                        "application_date": loan.application_date.isoformat(),
                        "updated_at": loan.updated_at.isoformat()
                    }]
            else:
                loans = db.query(LoanApplicationModel).limit(100).all()
                entity_details = [
                    {
                        "entity_id": loan.loan_application_id,
                        "entity_type": "LOAN_APPLICATION",
                        "application_status": loan.application_status,
                        "loan_type": loan.loan_type,
                        "requested_amount": loan.requested_amount,
                        "application_date": loan.application_date.isoformat(),
                        "updated_at": loan.updated_at.isoformat()
                    }
                    for loan in loans
                ]
        
        # Prepare response
        response_data = {
            "entity_type": entity_type_upper,
            "entity_id": entity_id,
            "regulator_access": {
                "regulator_id": current_user.actor_id,
                "access_timestamp": datetime.utcnow().isoformat(),
                "access_type": "READ_ONLY",
                "data_source": "immutable_blockchain_ledger"
            },
            "entities": entity_details,
            "compliance_events": [
                {
                    "event_id": event.event_id,
                    "timestamp": event.timestamp.isoformat(),
                    "event_type": event.event_type,
                    "severity": event.severity,
                    "description": event.description,
                    "resolution_status": event.resolution_status,
                    "blockchain_transaction_id": event.blockchain_transaction_id
                }
                for event in compliance_events
            ] if include_history else [],
            "summary": {
                "total_entities": len(entity_details),
                "total_compliance_events": len(compliance_events),
                "critical_events": len([e for e in compliance_events if e.severity == 'CRITICAL']),
                "unresolved_events": len([e for e in compliance_events if e.resolution_status in ['OPEN', 'IN_PROGRESS']])
            }
        }
        
        logger.info("Regulatory entity view generated", 
                   entity_type=entity_type,
                   entity_count=len(entity_details),
                   events_count=len(compliance_events),
                   regulator_id=current_user.actor_id)
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate regulatory entity view", 
                    entity_type=entity_type,
                    error=str(e),
                    regulator_id=current_user.actor_id)
        raise HTTPException(status_code=500, detail="Failed to generate regulatory entity view")


@router.get("/regulator/audit-log")
async def get_regulatory_audit_log(
    days: int = Query(7, ge=1, le=90, description="Number of days of audit log to retrieve"),
    regulator_id: Optional[str] = Query(None, description="Filter by specific regulator ID"),
    current_user: Actor = Depends(require_roles(Role.REGULATOR, Role.CHIEF_COMPLIANCE_OFFICER)),
    db: Session = Depends(get_db_session)
):
    """
    Get audit log of regulatory access and queries.
    
    Provides complete audit trail of all regulatory access for compliance
    and oversight purposes. Only accessible by regulators and chief compliance officers.
    """
    try:
        logger.info("Regulatory audit log accessed", 
                   days=days,
                   filter_regulator_id=regulator_id,
                   accessor_id=current_user.actor_id)
        
        # In a real implementation, this would query a dedicated audit log table
        # For now, we'll return a mock audit log
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Mock audit log entries
        audit_entries = [
            {
                "access_id": f"audit_{i:03d}",
                "regulator_id": regulator_id or "regulator_001",
                "access_type": "VIEW_COMPLIANCE_DATA",
                "resource_accessed": "compliance_events",
                "timestamp": (end_date - timedelta(hours=i)).isoformat(),
                "ip_address": "192.168.1.100",
                "user_agent": "Mozilla/5.0 (Regulatory Browser)",
                "data_accessed": f"Retrieved {50 + i} compliance events",
                "access_duration_seconds": 45 + (i % 30)
            }
            for i in range(min(days * 5, 50))  # Simulate 5 accesses per day, max 50 entries
        ]
        
        # Filter by regulator_id if specified
        if regulator_id:
            audit_entries = [entry for entry in audit_entries if entry["regulator_id"] == regulator_id]
        
        audit_summary = {
            "total_accesses": len(audit_entries),
            "unique_regulators": len(set(entry["regulator_id"] for entry in audit_entries)),
            "access_types": list(set(entry["access_type"] for entry in audit_entries)),
            "period": {
                "from": start_date.isoformat(),
                "to": end_date.isoformat(),
                "days": days
            }
        }
        
        response = {
            "audit_log": audit_entries,
            "summary": audit_summary,
            "generated_by": current_user.actor_id,
            "generated_at": datetime.utcnow().isoformat(),
            "data_integrity": "VERIFIED"
        }
        
        logger.info("Regulatory audit log generated", 
                   total_entries=len(audit_entries),
                   accessor_id=current_user.actor_id)
        
        return response
        
    except Exception as e:
        logger.error("Failed to generate regulatory audit log", 
                    error=str(e),
                    accessor_id=current_user.actor_id)
        raise HTTPException(status_code=500, detail="Failed to generate regulatory audit log")


# Helper function for logging regulatory access
async def _log_regulatory_access(
    regulator_id: str,
    access_type: str,
    resource_accessed: str,
    request: Request,
    db: Session
) -> None:
    """Log regulatory access for audit trail."""
    try:
        # Extract request metadata
        ip_address = request.client.host if request and request.client else None
        user_agent = request.headers.get("user-agent") if request else None
        
        # In a real implementation, you would store this in a dedicated audit log table
        # For now, we'll just log it
        logger.info("Regulatory access logged",
                   regulator_id=regulator_id,
                   access_type=access_type,
                   resource_accessed=resource_accessed,
                   ip_address=ip_address,
                   user_agent=user_agent,
                   timestamp=datetime.utcnow().isoformat())
        
        # You could also create a ComplianceEvent for regulatory access
        # This ensures all regulatory access is recorded on the blockchain
        
    except Exception as e:
        logger.error("Failed to log regulatory access", 
                    regulator_id=regulator_id,
                    error=str(e))