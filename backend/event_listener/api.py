"""
API endpoints for data consistency checking and monitoring.

Provides REST endpoints for:
- Triggering consistency checks
- Manual entity resync
- Viewing inconsistencies and alerts
- Generating integrity reports
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Path, BackgroundTasks
from pydantic import BaseModel, Field
import structlog

from .consistency_checker import consistency_checker, SeverityLevel, InconsistencyType
from .consistency_monitoring import consistency_monitor
from .service import event_listener
from .models import (
    ReconciliationRequest,
    ManualResyncRequest,
    InconsistencyResponse,
    ReconciliationResponse,
    AlertResponse,
    ConsistencySummaryResponse,
    IntegrityReportResponse
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/consistency", tags=["Data Consistency"])


# Request/Response Models are imported from models.py


# API Endpoints
@router.post("/reconcile", response_model=ReconciliationResponse)
async def perform_reconciliation(
    request: ReconciliationRequest,
    background_tasks: BackgroundTasks
):
    """
    Perform data reconciliation between blockchain and database.
    
    This endpoint triggers a comprehensive reconciliation process that compares
    data between the blockchain and database to identify inconsistencies.
    """
    try:
        logger.info("Starting reconciliation via API", 
                   entity_types=request.entity_types,
                   batch_size=request.batch_size)
        
        # Perform reconciliation
        report = await consistency_checker.perform_full_reconciliation(
            entity_types=request.entity_types,
            batch_size=request.batch_size
        )
        
        # Schedule monitoring check in background
        background_tasks.add_task(consistency_monitor._perform_monitoring_cycle)
        
        return ReconciliationResponse(
            success=report.success,
            start_time=report.start_time,
            end_time=report.end_time,
            entities_checked=report.entities_checked,
            total_inconsistencies=report.total_inconsistencies,
            severity_breakdown=report.severity_breakdown,
            error_message=report.error_message
        )
        
    except Exception as e:
        logger.error("Reconciliation failed via API", error=str(e))
        raise HTTPException(status_code=500, detail=f"Reconciliation failed: {str(e)}")


@router.post("/resync")
async def manual_resync(request: ManualResyncRequest):
    """
    Manually resync a specific entity from blockchain to database.
    
    This endpoint allows manual synchronization of individual entities
    when inconsistencies are detected or data needs to be refreshed.
    """
    try:
        logger.info("Starting manual resync via API",
                   entity_type=request.entity_type,
                   entity_id=request.entity_id,
                   force_overwrite=request.force_overwrite)
        
        result = await consistency_checker.manual_resync_entity(
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            force_overwrite=request.force_overwrite
        )
        
        return result
        
    except Exception as e:
        logger.error("Manual resync failed via API", error=str(e))
        raise HTTPException(status_code=500, detail=f"Manual resync failed: {str(e)}")


@router.get("/inconsistencies", response_model=List[InconsistencyResponse])
async def get_inconsistencies(
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    severity: Optional[str] = Query(None, description="Filter by severity (low, medium, high, critical)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of inconsistencies to return")
):
    """
    Get current data inconsistencies with optional filtering.
    
    Returns a list of detected inconsistencies between blockchain and database data.
    """
    try:
        # Convert severity string to enum if provided
        severity_filter = None
        if severity:
            try:
                severity_filter = SeverityLevel(severity.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")
        
        inconsistencies = consistency_checker.get_inconsistencies(
            entity_type=entity_type,
            severity=severity_filter,
            limit=limit
        )
        
        return [
            InconsistencyResponse(
                inconsistency_type=inc.inconsistency_type.value,
                severity=inc.severity.value,
                entity_type=inc.entity_type,
                entity_id=inc.entity_id,
                description=inc.description,
                detected_at=inc.detected_at,
                field_differences=inc.field_differences,
                blockchain_data=inc.blockchain_data,
                database_data=inc.database_data
            )
            for inc in inconsistencies
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get inconsistencies via API", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get inconsistencies: {str(e)}")


@router.get("/summary", response_model=ConsistencySummaryResponse)
async def get_consistency_summary():
    """
    Get summary of current data consistency status.
    
    Returns aggregated statistics about inconsistencies by type, severity, and entity.
    """
    try:
        summary = consistency_checker.get_inconsistency_summary()
        
        return ConsistencySummaryResponse(
            total_inconsistencies=summary['total_inconsistencies'],
            by_entity_type=summary['by_entity_type'],
            by_severity=summary['by_severity'],
            by_inconsistency_type=summary['by_inconsistency_type'],
            last_reconciliation=datetime.fromisoformat(summary['last_reconciliation']) 
                               if summary['last_reconciliation'] else None
        )
        
    except Exception as e:
        logger.error("Failed to get consistency summary via API", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get summary: {str(e)}")


@router.get("/alerts", response_model=List[AlertResponse])
async def get_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    acknowledged: bool = Query(False, description="Include acknowledged alerts")
):
    """
    Get consistency monitoring alerts.
    
    Returns alerts generated by the consistency monitoring system.
    """
    try:
        # Convert severity string to enum if provided
        severity_filter = None
        if severity:
            try:
                severity_filter = SeverityLevel(severity.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")
        
        if acknowledged:
            # Get all alerts
            alerts = consistency_monitor.alerts
        else:
            # Get only active (unacknowledged) alerts
            alerts = consistency_monitor.get_active_alerts(severity=severity_filter)
        
        # Apply severity filter if not already applied
        if severity_filter and acknowledged:
            alerts = [alert for alert in alerts if alert.severity == severity_filter]
        
        return [
            AlertResponse(
                alert_type=alert.alert_type.value,
                severity=alert.severity.value,
                title=alert.title,
                description=alert.description,
                details=alert.details,
                created_at=alert.created_at,
                acknowledged=alert.acknowledged,
                acknowledged_at=alert.acknowledged_at,
                acknowledged_by=alert.acknowledged_by
            )
            for alert in alerts
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get alerts via API", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get alerts: {str(e)}")


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int = Path(..., description="Alert ID to acknowledge"),
    acknowledged_by: str = Query(..., description="User acknowledging the alert")
):
    """
    Acknowledge a consistency alert.
    
    Marks an alert as acknowledged to indicate it has been reviewed.
    """
    try:
        success = consistency_monitor.acknowledge_alert(alert_id, acknowledged_by)
        
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found or already acknowledged")
        
        return {"success": True, "message": "Alert acknowledged successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to acknowledge alert via API", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to acknowledge alert: {str(e)}")


@router.get("/alerts/summary")
async def get_alert_summary():
    """
    Get summary of consistency alerts.
    
    Returns aggregated statistics about alerts by type and severity.
    """
    try:
        summary = consistency_monitor.get_alert_summary()
        return summary
        
    except Exception as e:
        logger.error("Failed to get alert summary via API", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get alert summary: {str(e)}")


@router.get("/report", response_model=IntegrityReportResponse)
async def generate_integrity_report():
    """
    Generate comprehensive data integrity report.
    
    Creates a detailed report including reconciliation results, database statistics,
    blockchain connectivity status, and recommendations.
    """
    try:
        logger.info("Generating integrity report via API")
        
        report_data = await consistency_checker.generate_integrity_report()
        
        if not report_data.get('success', True):
            return IntegrityReportResponse(
                generated_at=datetime.fromisoformat(report_data['generated_at']),
                reconciliation_report=ReconciliationResponse(
                    success=False,
                    start_time=datetime.utcnow(),
                    end_time=datetime.utcnow(),
                    entities_checked={},
                    total_inconsistencies=0,
                    severity_breakdown={},
                    error_message=report_data.get('error')
                ),
                database_statistics={},
                blockchain_connectivity={},
                inconsistency_summary=ConsistencySummaryResponse(
                    total_inconsistencies=0,
                    by_entity_type={},
                    by_severity={},
                    by_inconsistency_type={}
                ),
                recommendations=[],
                success=False,
                error=report_data.get('error')
            )
        
        # Parse reconciliation report
        recon_data = report_data['reconciliation_report']
        reconciliation_report = ReconciliationResponse(
            success=recon_data['success'],
            start_time=datetime.fromisoformat(recon_data['start_time']),
            end_time=datetime.fromisoformat(recon_data['end_time']),
            entities_checked=recon_data['entities_checked'],
            total_inconsistencies=recon_data['total_inconsistencies'],
            severity_breakdown=recon_data['severity_breakdown'],
            error_message=recon_data.get('error_message')
        )
        
        # Parse inconsistency summary
        summary_data = report_data['inconsistency_summary']
        inconsistency_summary = ConsistencySummaryResponse(
            total_inconsistencies=summary_data['total_inconsistencies'],
            by_entity_type=summary_data['by_entity_type'],
            by_severity=summary_data['by_severity'],
            by_inconsistency_type=summary_data['by_inconsistency_type'],
            last_reconciliation=datetime.fromisoformat(summary_data['last_reconciliation']) 
                               if summary_data['last_reconciliation'] else None
        )
        
        return IntegrityReportResponse(
            generated_at=datetime.fromisoformat(report_data['generated_at']),
            reconciliation_report=reconciliation_report,
            database_statistics=report_data['database_statistics'],
            blockchain_connectivity=report_data['blockchain_connectivity'],
            inconsistency_summary=inconsistency_summary,
            recommendations=report_data['recommendations'],
            success=True
        )
        
    except Exception as e:
        logger.error("Failed to generate integrity report via API", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.get("/health")
async def get_consistency_health():
    """
    Get health status of consistency checking components.
    
    Returns status information about the consistency checker, monitoring, and related services.
    """
    try:
        # Get event listener health
        event_health = await event_listener.health_check()
        
        # Get consistency checker status
        checker_status = {
            'last_reconciliation': consistency_checker.last_reconciliation.isoformat() 
                                 if consistency_checker.last_reconciliation else None,
            'total_inconsistencies': len(consistency_checker.inconsistencies),
            'reconciliation_history_count': len(consistency_checker.reconciliation_history)
        }
        
        # Get monitoring status
        monitor_status = consistency_monitor.get_alert_summary()
        
        # Get performance metrics
        performance_metrics = consistency_monitor.get_performance_metrics()
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'overall_healthy': event_health.get('overall_healthy', False),
            'event_listener': event_health,
            'consistency_checker': checker_status,
            'monitoring': monitor_status,
            'performance_metrics': performance_metrics
        }
        
    except Exception as e:
        logger.error("Failed to get consistency health via API", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get health status: {str(e)}")


@router.post("/monitoring/start")
async def start_monitoring():
    """
    Start consistency monitoring.
    
    Begins continuous monitoring of data consistency and alert generation.
    """
    try:
        if consistency_monitor.monitoring_active:
            return {"message": "Monitoring is already active"}
        
        # Start monitoring in background
        import asyncio
        asyncio.create_task(consistency_monitor.start_monitoring())
        
        return {"message": "Consistency monitoring started"}
        
    except Exception as e:
        logger.error("Failed to start monitoring via API", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to start monitoring: {str(e)}")


@router.post("/monitoring/stop")
async def stop_monitoring():
    """
    Stop consistency monitoring.
    
    Stops continuous monitoring of data consistency.
    """
    try:
        consistency_monitor.stop_monitoring()
        return {"message": "Consistency monitoring stopped"}
        
    except Exception as e:
        logger.error("Failed to stop monitoring via API", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to stop monitoring: {str(e)}")


# Include router in main application
def get_consistency_router():
    """Get the consistency checking router."""
    return router