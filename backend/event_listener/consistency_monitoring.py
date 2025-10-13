"""
Monitoring and alerting functionality for data consistency checker.

This module provides:
- Health monitoring for synchronization processes
- Alerting for critical inconsistencies
- Performance metrics and reporting
- Automated reconciliation scheduling
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import traceback

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from .consistency_checker import (
    DataConsistencyChecker, 
    DataInconsistency, 
    SeverityLevel,
    InconsistencyType,
    consistency_checker
)
from shared.config import settings

logger = structlog.get_logger(__name__)


class AlertType(Enum):
    """Types of alerts that can be generated."""
    CRITICAL_INCONSISTENCY = "critical_inconsistency"
    HIGH_INCONSISTENCY_COUNT = "high_inconsistency_count"
    RECONCILIATION_FAILURE = "reconciliation_failure"
    BLOCKCHAIN_CONNECTIVITY_ISSUE = "blockchain_connectivity_issue"
    DATABASE_SYNC_FAILURE = "database_sync_failure"
    PERFORMANCE_DEGRADATION = "performance_degradation"


@dataclass
class Alert:
    """Represents an alert for data consistency issues."""
    alert_type: AlertType
    severity: SeverityLevel
    title: str
    description: str
    details: Dict[str, Any]
    created_at: datetime
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            'alert_type': self.alert_type.value,
            'severity': self.severity.value,
            'title': self.title,
            'description': self.description,
            'details': self.details,
            'created_at': self.created_at.isoformat(),
            'acknowledged': self.acknowledged,
            'acknowledged_at': self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            'acknowledged_by': self.acknowledged_by
        }


class ConsistencyMonitor:
    """Monitors data consistency and generates alerts."""
    
    def __init__(self, consistency_checker: DataConsistencyChecker):
        self.consistency_checker = consistency_checker
        self.alerts: List[Alert] = []
        self.alert_handlers: List[Callable[[Alert], None]] = []
        self.monitoring_active = False
        self.monitoring_interval = 300  # 5 minutes
        self.last_health_check = None
        self.performance_metrics = {
            'reconciliation_times': [],
            'inconsistency_trends': [],
            'alert_counts': {}
        }
    
    def add_alert_handler(self, handler: Callable[[Alert], None]):
        """Add an alert handler function."""
        self.alert_handlers.append(handler)
        logger.info("Alert handler added", handler_count=len(self.alert_handlers))
    
    async def start_monitoring(self):
        """Start continuous monitoring."""
        self.monitoring_active = True
        logger.info("Starting consistency monitoring", interval=self.monitoring_interval)
        
        while self.monitoring_active:
            try:
                await self._perform_monitoring_cycle()
                await asyncio.sleep(self.monitoring_interval)
            except Exception as e:
                logger.error("Error in monitoring cycle", error=str(e))
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    def stop_monitoring(self):
        """Stop continuous monitoring."""
        self.monitoring_active = False
        logger.info("Consistency monitoring stopped")
    
    async def _perform_monitoring_cycle(self):
        """Perform one monitoring cycle."""
        logger.debug("Performing monitoring cycle")
        
        try:
            # Check for critical inconsistencies
            await self._check_critical_inconsistencies()
            
            # Check inconsistency count trends
            await self._check_inconsistency_trends()
            
            # Check reconciliation health
            await self._check_reconciliation_health()
            
            # Check blockchain connectivity
            await self._check_blockchain_connectivity()
            
            # Update performance metrics
            await self._update_performance_metrics()
            
            self.last_health_check = datetime.utcnow()
            
        except Exception as e:
            logger.error("Error in monitoring cycle", error=str(e), traceback=traceback.format_exc())
    
    async def _check_critical_inconsistencies(self):
        """Check for critical inconsistencies and generate alerts."""
        critical_inconsistencies = self.consistency_checker.get_inconsistencies(
            severity=SeverityLevel.CRITICAL
        )
        
        if critical_inconsistencies:
            for inconsistency in critical_inconsistencies:
                # Check if we already have an alert for this inconsistency
                existing_alert = self._find_existing_alert(
                    AlertType.CRITICAL_INCONSISTENCY,
                    inconsistency.entity_id
                )
                
                if not existing_alert:
                    alert = Alert(
                        alert_type=AlertType.CRITICAL_INCONSISTENCY,
                        severity=SeverityLevel.CRITICAL,
                        title=f"Critical Data Inconsistency Detected",
                        description=f"Critical inconsistency found in {inconsistency.entity_type} {inconsistency.entity_id}",
                        details={
                            'entity_type': inconsistency.entity_type,
                            'entity_id': inconsistency.entity_id,
                            'inconsistency_type': inconsistency.inconsistency_type.value,
                            'description': inconsistency.description,
                            'field_differences': inconsistency.field_differences
                        },
                        created_at=datetime.utcnow()
                    )
                    
                    await self._generate_alert(alert)
    
    async def _check_inconsistency_trends(self):
        """Check for concerning trends in inconsistency counts."""
        summary = self.consistency_checker.get_inconsistency_summary()
        total_inconsistencies = summary['total_inconsistencies']
        
        # Record current count for trend analysis
        self.performance_metrics['inconsistency_trends'].append({
            'timestamp': datetime.utcnow(),
            'total_count': total_inconsistencies,
            'by_severity': summary['by_severity']
        })
        
        # Keep only last 24 hours of data
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        self.performance_metrics['inconsistency_trends'] = [
            trend for trend in self.performance_metrics['inconsistency_trends']
            if trend['timestamp'] > cutoff_time
        ]
        
        # Check for high inconsistency count
        if total_inconsistencies > 100:  # Configurable threshold
            existing_alert = self._find_existing_alert(
                AlertType.HIGH_INCONSISTENCY_COUNT,
                "system"
            )
            
            if not existing_alert:
                alert = Alert(
                    alert_type=AlertType.HIGH_INCONSISTENCY_COUNT,
                    severity=SeverityLevel.HIGH,
                    title="High Number of Data Inconsistencies",
                    description=f"System has {total_inconsistencies} data inconsistencies",
                    details={
                        'total_inconsistencies': total_inconsistencies,
                        'by_severity': summary['by_severity'],
                        'by_entity_type': summary['by_entity_type']
                    },
                    created_at=datetime.utcnow()
                )
                
                await self._generate_alert(alert)
    
    async def _check_reconciliation_health(self):
        """Check the health of reconciliation processes."""
        history = self.consistency_checker.get_reconciliation_history(limit=5)
        
        if not history:
            # No reconciliation history - this might be concerning
            alert = Alert(
                alert_type=AlertType.RECONCILIATION_FAILURE,
                severity=SeverityLevel.MEDIUM,
                title="No Reconciliation History",
                description="No reconciliation processes have been recorded",
                details={'last_reconciliation': None},
                created_at=datetime.utcnow()
            )
            
            await self._generate_alert(alert)
            return
        
        # Check for recent failures
        recent_failures = [
            report for report in history
            if not report.get('success', True)
        ]
        
        if recent_failures:
            latest_failure = recent_failures[0]
            alert = Alert(
                alert_type=AlertType.RECONCILIATION_FAILURE,
                severity=SeverityLevel.HIGH,
                title="Reconciliation Process Failed",
                description=f"Recent reconciliation failed: {latest_failure.get('error_message', 'Unknown error')}",
                details={
                    'failure_count': len(recent_failures),
                    'latest_failure': latest_failure,
                    'failure_time': latest_failure.get('end_time')
                },
                created_at=datetime.utcnow()
            )
            
            await self._generate_alert(alert)
        
        # Check for stale reconciliation (no reconciliation in last 24 hours)
        latest_reconciliation = history[0] if history else None
        if latest_reconciliation:
            last_time_str = latest_reconciliation.get('end_time')
            if last_time_str:
                last_time = datetime.fromisoformat(last_time_str.replace('Z', '+00:00'))
                if (datetime.utcnow() - last_time).total_seconds() > 86400:  # 24 hours
                    alert = Alert(
                        alert_type=AlertType.RECONCILIATION_FAILURE,
                        severity=SeverityLevel.MEDIUM,
                        title="Stale Reconciliation Data",
                        description="No reconciliation performed in the last 24 hours",
                        details={
                            'last_reconciliation': last_time_str,
                            'hours_since_last': (datetime.utcnow() - last_time).total_seconds() / 3600
                        },
                        created_at=datetime.utcnow()
                    )
                    
                    await self._generate_alert(alert)
    
    async def _check_blockchain_connectivity(self):
        """Check blockchain connectivity status."""
        try:
            # Try to initialize blockchain connection
            await self.consistency_checker.blockchain_fetcher.initialize()
            
            # Try a simple query
            test_result = await self.consistency_checker.blockchain_fetcher.get_customer_data("connectivity_test")
            
            # If we get here, connectivity is working
            logger.debug("Blockchain connectivity check passed")
            
        except Exception as e:
            logger.warning("Blockchain connectivity issue detected", error=str(e))
            
            existing_alert = self._find_existing_alert(
                AlertType.BLOCKCHAIN_CONNECTIVITY_ISSUE,
                "blockchain"
            )
            
            if not existing_alert:
                alert = Alert(
                    alert_type=AlertType.BLOCKCHAIN_CONNECTIVITY_ISSUE,
                    severity=SeverityLevel.HIGH,
                    title="Blockchain Connectivity Issue",
                    description=f"Unable to connect to blockchain: {str(e)}",
                    details={
                        'error': str(e),
                        'error_type': type(e).__name__
                    },
                    created_at=datetime.utcnow()
                )
                
                await self._generate_alert(alert)
    
    async def _update_performance_metrics(self):
        """Update performance metrics."""
        # Record reconciliation performance if available
        history = self.consistency_checker.get_reconciliation_history(limit=1)
        if history:
            latest = history[0]
            if latest.get('success'):
                start_time = datetime.fromisoformat(latest['start_time'].replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(latest['end_time'].replace('Z', '+00:00'))
                duration = (end_time - start_time).total_seconds()
                
                self.performance_metrics['reconciliation_times'].append({
                    'timestamp': end_time,
                    'duration_seconds': duration,
                    'entities_checked': sum(latest.get('entities_checked', {}).values()),
                    'inconsistencies_found': latest.get('total_inconsistencies', 0)
                })
                
                # Keep only last 50 reconciliation times
                self.performance_metrics['reconciliation_times'] = \
                    self.performance_metrics['reconciliation_times'][-50:]
    
    def _find_existing_alert(self, alert_type: AlertType, entity_id: str) -> Optional[Alert]:
        """Find existing unacknowledged alert for the same issue."""
        for alert in self.alerts:
            if (alert.alert_type == alert_type and 
                not alert.acknowledged and
                alert.details.get('entity_id') == entity_id):
                return alert
        return None
    
    async def _generate_alert(self, alert: Alert):
        """Generate and process an alert."""
        self.alerts.append(alert)
        
        # Update alert count metrics
        alert_key = f"{alert.alert_type.value}_{alert.severity.value}"
        self.performance_metrics['alert_counts'][alert_key] = \
            self.performance_metrics['alert_counts'].get(alert_key, 0) + 1
        
        logger.warning("Alert generated",
                      alert_type=alert.alert_type.value,
                      severity=alert.severity.value,
                      title=alert.title)
        
        # Call alert handlers
        for handler in self.alert_handlers:
            try:
                await self._call_alert_handler(handler, alert)
            except Exception as e:
                logger.error("Error calling alert handler", error=str(e))
    
    async def _call_alert_handler(self, handler: Callable, alert: Alert):
        """Call an alert handler safely."""
        if asyncio.iscoroutinefunction(handler):
            await handler(alert)
        else:
            handler(alert)
    
    def acknowledge_alert(self, alert_id: int, acknowledged_by: str) -> bool:
        """Acknowledge an alert."""
        if 0 <= alert_id < len(self.alerts):
            alert = self.alerts[alert_id]
            if not alert.acknowledged:
                alert.acknowledged = True
                alert.acknowledged_at = datetime.utcnow()
                alert.acknowledged_by = acknowledged_by
                
                logger.info("Alert acknowledged",
                           alert_id=alert_id,
                           alert_type=alert.alert_type.value,
                           acknowledged_by=acknowledged_by)
                return True
        return False
    
    def get_active_alerts(self, severity: Optional[SeverityLevel] = None) -> List[Alert]:
        """Get active (unacknowledged) alerts."""
        active_alerts = [alert for alert in self.alerts if not alert.acknowledged]
        
        if severity:
            active_alerts = [alert for alert in active_alerts if alert.severity == severity]
        
        return active_alerts
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get summary of alerts."""
        active_alerts = self.get_active_alerts()
        
        by_severity = {}
        by_type = {}
        
        for alert in active_alerts:
            # Count by severity
            severity_key = alert.severity.value
            by_severity[severity_key] = by_severity.get(severity_key, 0) + 1
            
            # Count by type
            type_key = alert.alert_type.value
            by_type[type_key] = by_type.get(type_key, 0) + 1
        
        return {
            'total_active_alerts': len(active_alerts),
            'total_alerts': len(self.alerts),
            'by_severity': by_severity,
            'by_type': by_type,
            'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None,
            'monitoring_active': self.monitoring_active
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        metrics = self.performance_metrics.copy()
        
        # Calculate average reconciliation time
        if metrics['reconciliation_times']:
            avg_duration = sum(r['duration_seconds'] for r in metrics['reconciliation_times']) / len(metrics['reconciliation_times'])
            metrics['average_reconciliation_duration'] = avg_duration
        else:
            metrics['average_reconciliation_duration'] = None
        
        # Calculate inconsistency trend
        if len(metrics['inconsistency_trends']) >= 2:
            latest = metrics['inconsistency_trends'][-1]
            previous = metrics['inconsistency_trends'][-2]
            trend = latest['total_count'] - previous['total_count']
            metrics['inconsistency_trend'] = trend
        else:
            metrics['inconsistency_trend'] = 0
        
        return metrics


# Default alert handlers
async def log_alert_handler(alert: Alert):
    """Default alert handler that logs alerts."""
    logger.warning("ALERT",
                   type=alert.alert_type.value,
                   severity=alert.severity.value,
                   title=alert.title,
                   description=alert.description)


async def email_alert_handler(alert: Alert):
    """Alert handler that sends email notifications (placeholder)."""
    # This would integrate with an email service
    logger.info("Email alert would be sent",
               alert_type=alert.alert_type.value,
               severity=alert.severity.value,
               title=alert.title)


# Global monitor instance
consistency_monitor = ConsistencyMonitor(consistency_checker)

# Add default alert handlers
consistency_monitor.add_alert_handler(log_alert_handler)