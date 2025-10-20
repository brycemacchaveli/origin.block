"""
ETL Monitoring and Alerting system.

This module provides comprehensive monitoring capabilities for ETL processes
including metrics collection, alerting, and performance tracking.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import statistics
import json

import structlog

from etl.models import ETLBatch
from etl.orchestration.types import JobType, JobStatus
from etl.orchestration.data_quality import QualityCheckResult, QualitySeverity
from shared.database import DatabaseManager

logger = structlog.get_logger(__name__)


class AlertType(Enum):
    """Types of ETL alerts."""
    JOB_FAILURE = "job_failure"
    QUALITY_ISSUE = "quality_issue"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    DATA_FRESHNESS = "data_freshness"
    SYSTEM_ERROR = "system_error"


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """ETL alert."""
    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    timestamp: datetime
    job_id: Optional[str] = None
    batch_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None


@dataclass
class ETLMetrics:
    """ETL performance metrics."""
    job_id: str
    batch_id: str
    timestamp: datetime
    
    # Processing metrics
    records_processed: int
    records_inserted: int
    records_updated: int
    records_failed: int
    processing_time_seconds: float
    
    # Performance metrics
    records_per_second: float
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    
    # Quality metrics
    quality_score: float
    quality_issues: int
    
    # Business metrics
    job_type: JobType
    success: bool


class ETLMonitor:
    """
    Comprehensive ETL monitoring system.
    
    Provides metrics collection, alerting, and performance tracking
    for ETL processes.
    """
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize ETL monitor."""
        self.db_manager = db_manager
        self.alerts: List[Alert] = []
        self.metrics_history: List[ETLMetrics] = []
        self.alert_handlers: List[Callable[[Alert], None]] = []
        
        # Performance thresholds
        self.performance_thresholds = {
            'min_records_per_second': 100,
            'max_processing_time_minutes': 60,
            'min_quality_score': 0.95,
            'max_failure_rate': 0.05,
            'max_consecutive_failures': 3
        }
        
        # Alert configuration
        self.alert_config = {
            'enable_email_alerts': False,  # Would be configured in production
            'enable_slack_alerts': False,
            'enable_log_alerts': True,
            'alert_cooldown_minutes': 30  # Prevent alert spam
        }
    
    async def record_job_execution(
        self, 
        job, 
        batch_result: ETLBatch, 
        quality_result: QualityCheckResult
    ):
        """Record successful job execution metrics."""
        try:
            # Calculate performance metrics
            processing_time = 0.0
            records_per_second = 0.0
            
            if batch_result.start_time and batch_result.end_time:
                processing_time = (batch_result.end_time - batch_result.start_time).total_seconds()
                if processing_time > 0 and batch_result.records_processed > 0:
                    records_per_second = batch_result.records_processed / processing_time
            
            # Create metrics record
            metrics = ETLMetrics(
                job_id=job.job_id,
                batch_id=batch_result.batch_id,
                timestamp=datetime.now(timezone.utc),
                records_processed=batch_result.records_processed,
                records_inserted=batch_result.records_inserted,
                records_updated=batch_result.records_updated,
                records_failed=batch_result.records_failed,
                processing_time_seconds=processing_time,
                records_per_second=records_per_second,
                quality_score=quality_result.metrics.get('quality_score', 0.0),
                quality_issues=len(quality_result.issues),
                job_type=job.job_type,
                success=batch_result.status == "SUCCESS"
            )
            
            # Store metrics
            self.metrics_history.append(metrics)
            
            # Check for performance issues
            await self._check_performance_thresholds(job, metrics, quality_result)
            
            # Log success
            logger.info("Job execution recorded", 
                       job_id=job.job_id,
                       batch_id=batch_result.batch_id,
                       records_processed=batch_result.records_processed,
                       processing_time=processing_time,
                       quality_score=metrics.quality_score)
            
        except Exception as e:
            logger.error("Failed to record job execution", 
                        job_id=job.job_id,
                        error=str(e))
    
    async def record_job_failure(self, job, error_message: str):
        """Record job failure and generate alerts."""
        try:
            # Create failure alert
            alert = Alert(
                alert_id=f"job_failure_{job.job_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                alert_type=AlertType.JOB_FAILURE,
                severity=AlertSeverity.ERROR if job.retry_count < job.max_retries else AlertSeverity.CRITICAL,
                title=f"ETL Job Failed: {job.job_id}",
                message=f"Job {job.job_id} failed with error: {error_message}",
                timestamp=datetime.now(timezone.utc),
                job_id=job.job_id,
                details={
                    'error_message': error_message,
                    'retry_count': job.retry_count,
                    'max_retries': job.max_retries,
                    'job_type': job.job_type.value
                }
            )
            
            # Check for consecutive failures
            consecutive_failures = await self._count_consecutive_failures(job.job_id)
            if consecutive_failures >= self.performance_thresholds['max_consecutive_failures']:
                alert.severity = AlertSeverity.CRITICAL
                alert.title = f"Critical: Multiple ETL Job Failures: {job.job_id}"
                alert.message = f"Job {job.job_id} has failed {consecutive_failures} consecutive times"
                alert.details['consecutive_failures'] = consecutive_failures
            
            await self._send_alert(alert)
            
        except Exception as e:
            logger.error("Failed to record job failure", 
                        job_id=job.job_id,
                        error=str(e))
    
    async def _check_performance_thresholds(
        self, 
        job, 
        metrics: ETLMetrics, 
        quality_result: QualityCheckResult
    ):
        """Check performance metrics against thresholds and generate alerts."""
        
        # Check processing speed
        if metrics.records_per_second < self.performance_thresholds['min_records_per_second']:
            await self._send_alert(Alert(
                alert_id=f"perf_slow_{job.job_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                alert_type=AlertType.PERFORMANCE_DEGRADATION,
                severity=AlertSeverity.WARNING,
                title=f"Slow Processing: {job.job_id}",
                message=f"Job processing speed is {metrics.records_per_second:.1f} records/sec, below threshold of {self.performance_thresholds['min_records_per_second']}",
                timestamp=datetime.now(timezone.utc),
                job_id=job.job_id,
                batch_id=metrics.batch_id,
                details={
                    'records_per_second': metrics.records_per_second,
                    'threshold': self.performance_thresholds['min_records_per_second']
                }
            ))
        
        # Check processing time
        processing_minutes = metrics.processing_time_seconds / 60
        if processing_minutes > self.performance_thresholds['max_processing_time_minutes']:
            await self._send_alert(Alert(
                alert_id=f"perf_long_{job.job_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                alert_type=AlertType.PERFORMANCE_DEGRADATION,
                severity=AlertSeverity.WARNING,
                title=f"Long Processing Time: {job.job_id}",
                message=f"Job took {processing_minutes:.1f} minutes, exceeding threshold of {self.performance_thresholds['max_processing_time_minutes']} minutes",
                timestamp=datetime.now(timezone.utc),
                job_id=job.job_id,
                batch_id=metrics.batch_id,
                details={
                    'processing_minutes': processing_minutes,
                    'threshold': self.performance_thresholds['max_processing_time_minutes']
                }
            ))
        
        # Check quality score
        if metrics.quality_score < self.performance_thresholds['min_quality_score']:
            severity = AlertSeverity.CRITICAL if metrics.quality_score < 0.8 else AlertSeverity.ERROR
            
            await self._send_alert(Alert(
                alert_id=f"quality_low_{job.job_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                alert_type=AlertType.QUALITY_ISSUE,
                severity=severity,
                title=f"Low Data Quality: {job.job_id}",
                message=f"Data quality score is {metrics.quality_score:.2%}, below threshold of {self.performance_thresholds['min_quality_score']:.2%}",
                timestamp=datetime.now(timezone.utc),
                job_id=job.job_id,
                batch_id=metrics.batch_id,
                details={
                    'quality_score': metrics.quality_score,
                    'threshold': self.performance_thresholds['min_quality_score'],
                    'quality_issues': metrics.quality_issues
                }
            ))
        
        # Check for critical quality issues
        critical_issues = [
            issue for issue in quality_result.issues 
            if issue.severity == QualitySeverity.CRITICAL
        ]
        
        if critical_issues:
            await self._send_alert(Alert(
                alert_id=f"quality_critical_{job.job_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                alert_type=AlertType.QUALITY_ISSUE,
                severity=AlertSeverity.CRITICAL,
                title=f"Critical Data Quality Issues: {job.job_id}",
                message=f"Found {len(critical_issues)} critical data quality issues",
                timestamp=datetime.now(timezone.utc),
                job_id=job.job_id,
                batch_id=metrics.batch_id,
                details={
                    'critical_issues': [
                        {
                            'type': issue.check_type.value,
                            'message': issue.message,
                            'affected_records': issue.affected_records
                        }
                        for issue in critical_issues
                    ]
                }
            ))
    
    async def _count_consecutive_failures(self, job_id: str) -> int:
        """Count consecutive failures for a job."""
        # In a real implementation, this would query a persistent store
        # For now, check recent metrics
        recent_metrics = [
            m for m in self.metrics_history[-10:]  # Last 10 executions
            if m.job_id == job_id
        ]
        
        consecutive_failures = 0
        for metrics in reversed(recent_metrics):
            if not metrics.success:
                consecutive_failures += 1
            else:
                break
        
        return consecutive_failures
    
    async def _send_alert(self, alert: Alert):
        """Send alert through configured channels."""
        try:
            # Store alert
            self.alerts.append(alert)
            
            # Check alert cooldown to prevent spam
            if await self._is_alert_in_cooldown(alert):
                logger.debug("Alert in cooldown period", alert_id=alert.alert_id)
                return
            
            # Send through configured channels
            if self.alert_config['enable_log_alerts']:
                await self._send_log_alert(alert)
            
            if self.alert_config['enable_email_alerts']:
                await self._send_email_alert(alert)
            
            if self.alert_config['enable_slack_alerts']:
                await self._send_slack_alert(alert)
            
            # Call custom alert handlers
            for handler in self.alert_handlers:
                try:
                    handler(alert)
                except Exception as e:
                    logger.error("Alert handler failed", 
                               handler=handler.__name__,
                               error=str(e))
            
        except Exception as e:
            logger.error("Failed to send alert", 
                        alert_id=alert.alert_id,
                        error=str(e))
    
    async def _is_alert_in_cooldown(self, alert: Alert) -> bool:
        """Check if similar alert is in cooldown period."""
        cooldown_minutes = self.alert_config['alert_cooldown_minutes']
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)
        
        # Check for similar recent alerts
        similar_alerts = [
            a for a in self.alerts
            if (a.alert_type == alert.alert_type and
                a.job_id == alert.job_id and
                a.timestamp > cutoff_time)
        ]
        
        return len(similar_alerts) > 1  # Allow first alert, block subsequent ones
    
    async def _send_log_alert(self, alert: Alert):
        """Send alert to logs."""
        log_level = {
            AlertSeverity.INFO: logger.info,
            AlertSeverity.WARNING: logger.warning,
            AlertSeverity.ERROR: logger.error,
            AlertSeverity.CRITICAL: logger.critical
        }.get(alert.severity, logger.info)
        
        log_level("ETL Alert", 
                 alert_id=alert.alert_id,
                 alert_type=alert.alert_type.value,
                 severity=alert.severity.value,
                 title=alert.title,
                 message=alert.message,
                 job_id=alert.job_id,
                 batch_id=alert.batch_id,
                 details=alert.details)
    
    async def _send_email_alert(self, alert: Alert):
        """Send alert via email."""
        # In production, this would integrate with email service
        logger.info("Would send email alert", 
                   alert_id=alert.alert_id,
                   title=alert.title)
    
    async def _send_slack_alert(self, alert: Alert):
        """Send alert to Slack."""
        # In production, this would integrate with Slack API
        logger.info("Would send Slack alert", 
                   alert_id=alert.alert_id,
                   title=alert.title)
    
    def add_alert_handler(self, handler: Callable[[Alert], None]):
        """Add custom alert handler."""
        self.alert_handlers.append(handler)
        logger.info("Added alert handler", handler=handler.__name__)
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str):
        """Acknowledge an alert."""
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                alert.acknowledged_by = acknowledged_by
                alert.acknowledged_at = datetime.now(timezone.utc)
                
                logger.info("Alert acknowledged", 
                           alert_id=alert_id,
                           acknowledged_by=acknowledged_by)
                break
    
    def get_active_alerts(self, severity: Optional[AlertSeverity] = None) -> List[Alert]:
        """Get active (unacknowledged) alerts."""
        active_alerts = [alert for alert in self.alerts if not alert.acknowledged]
        
        if severity:
            active_alerts = [alert for alert in active_alerts if alert.severity == severity]
        
        return sorted(active_alerts, key=lambda a: a.timestamp, reverse=True)
    
    def get_job_metrics(
        self, 
        job_id: str, 
        hours: int = 24
    ) -> Dict[str, Any]:
        """Get performance metrics for a specific job."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        job_metrics = [
            m for m in self.metrics_history
            if m.job_id == job_id and m.timestamp > cutoff_time
        ]
        
        if not job_metrics:
            return {'job_id': job_id, 'no_data': True}
        
        # Calculate statistics
        processing_times = [m.processing_time_seconds for m in job_metrics]
        records_processed = [m.records_processed for m in job_metrics]
        quality_scores = [m.quality_score for m in job_metrics]
        success_rate = sum(1 for m in job_metrics if m.success) / len(job_metrics)
        
        return {
            'job_id': job_id,
            'period_hours': hours,
            'total_executions': len(job_metrics),
            'success_rate': success_rate,
            'avg_processing_time_seconds': statistics.mean(processing_times),
            'max_processing_time_seconds': max(processing_times),
            'min_processing_time_seconds': min(processing_times),
            'avg_records_processed': statistics.mean(records_processed),
            'total_records_processed': sum(records_processed),
            'avg_quality_score': statistics.mean(quality_scores),
            'min_quality_score': min(quality_scores),
            'recent_executions': [
                {
                    'timestamp': m.timestamp.isoformat(),
                    'batch_id': m.batch_id,
                    'records_processed': m.records_processed,
                    'processing_time_seconds': m.processing_time_seconds,
                    'quality_score': m.quality_score,
                    'success': m.success
                }
                for m in sorted(job_metrics, key=lambda x: x.timestamp, reverse=True)[:10]
            ]
        }
    
    def get_pipeline_dashboard(self) -> Dict[str, Any]:
        """Get comprehensive pipeline dashboard data."""
        current_time = datetime.now(timezone.utc)
        last_24h = current_time - timedelta(hours=24)
        
        # Get recent metrics
        recent_metrics = [m for m in self.metrics_history if m.timestamp > last_24h]
        
        # Calculate overall statistics
        total_executions = len(recent_metrics)
        successful_executions = len([m for m in recent_metrics if m.success])
        failed_executions = total_executions - successful_executions
        
        # Get active alerts by severity
        active_alerts = self.get_active_alerts()
        alerts_by_severity = {
            'critical': len([a for a in active_alerts if a.severity == AlertSeverity.CRITICAL]),
            'error': len([a for a in active_alerts if a.severity == AlertSeverity.ERROR]),
            'warning': len([a for a in active_alerts if a.severity == AlertSeverity.WARNING]),
            'info': len([a for a in active_alerts if a.severity == AlertSeverity.INFO])
        }
        
        # Job-specific metrics
        job_stats = {}
        for job_type in JobType:
            job_metrics = [m for m in recent_metrics if m.job_type == job_type]
            if job_metrics:
                job_stats[job_type.value] = {
                    'executions': len(job_metrics),
                    'success_rate': sum(1 for m in job_metrics if m.success) / len(job_metrics),
                    'avg_processing_time': statistics.mean([m.processing_time_seconds for m in job_metrics]),
                    'total_records': sum(m.records_processed for m in job_metrics),
                    'avg_quality_score': statistics.mean([m.quality_score for m in job_metrics])
                }
        
        return {
            'dashboard_timestamp': current_time.isoformat(),
            'period': '24 hours',
            'overall_stats': {
                'total_executions': total_executions,
                'successful_executions': successful_executions,
                'failed_executions': failed_executions,
                'success_rate': successful_executions / max(total_executions, 1),
                'total_records_processed': sum(m.records_processed for m in recent_metrics),
                'avg_quality_score': statistics.mean([m.quality_score for m in recent_metrics]) if recent_metrics else 0.0
            },
            'active_alerts': {
                'total': len(active_alerts),
                'by_severity': alerts_by_severity,
                'recent_alerts': [
                    {
                        'alert_id': alert.alert_id,
                        'type': alert.alert_type.value,
                        'severity': alert.severity.value,
                        'title': alert.title,
                        'timestamp': alert.timestamp.isoformat(),
                        'job_id': alert.job_id
                    }
                    for alert in active_alerts[:5]  # Most recent 5 alerts
                ]
            },
            'job_performance': job_stats,
            'system_health': {
                'pipeline_status': 'healthy' if alerts_by_severity['critical'] == 0 else 'degraded',
                'data_freshness': 'current',  # Would check actual data timestamps
                'processing_capacity': 'normal'  # Would check system resources
            }
        }
    
    def update_thresholds(self, new_thresholds: Dict[str, Any]):
        """Update performance monitoring thresholds."""
        self.performance_thresholds.update(new_thresholds)
        logger.info("Updated monitoring thresholds", thresholds=self.performance_thresholds)
    
    def update_alert_config(self, new_config: Dict[str, Any]):
        """Update alert configuration."""
        self.alert_config.update(new_config)
        logger.info("Updated alert configuration", config=self.alert_config)