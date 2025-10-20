"""
Real-time process tracking and analytics.

This module provides real-time tracking of loan application processes,
bottleneck identification, and performance monitoring.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import statistics

import structlog

from shared.database import DatabaseManager

logger = structlog.get_logger(__name__)


class ProcessStatus(Enum):
    """Process status categories."""
    ON_TRACK = "on_track"
    DELAYED = "delayed"
    STALLED = "stalled"
    ESCALATED = "escalated"


class BottleneckSeverity(Enum):
    """Bottleneck severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ProcessMetrics:
    """Process performance metrics."""
    process_id: str
    process_type: str
    current_stage: str
    stage_entry_time: datetime
    total_processing_time_hours: float
    expected_completion_time: Optional[datetime]
    status: ProcessStatus
    bottleneck_indicators: List[str]
    performance_score: float  # 0-100


@dataclass
class StageMetrics:
    """Stage-level performance metrics."""
    stage_name: str
    avg_duration_hours: float
    median_duration_hours: float
    p90_duration_hours: float
    current_volume: int
    throughput_per_hour: float
    bottleneck_severity: BottleneckSeverity


@dataclass
class BottleneckAlert:
    """Bottleneck alert information."""
    alert_id: str
    stage_name: str
    severity: BottleneckSeverity
    description: str
    affected_processes: int
    avg_delay_hours: float
    recommended_actions: List[str]
    created_at: datetime


class RealTimeProcessTracker:
    """
    Real-time process tracking and bottleneck identification.
    
    Monitors loan application processes in real-time and identifies
    bottlenecks for operational optimization.
    """
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize process tracker."""
        self.db_manager = db_manager
        
        # Performance thresholds
        self.thresholds = {
            'stage_sla_hours': {
                'SUBMITTED': 24,
                'UNDERWRITING': 72,
                'CREDIT_REVIEW': 48,
                'APPROVED': 24,
                'DISBURSEMENT': 12
            },
            'bottleneck_threshold_multiplier': 1.5,  # 1.5x average = bottleneck
            'stalled_threshold_hours': 168,  # 7 days = stalled
            'critical_volume_threshold': 50  # 50+ items in stage = critical
        }
    
    async def get_real_time_metrics(self) -> Dict[str, Any]:
        """Get real-time process metrics."""
        try:
            with self.db_manager.session_scope() as session:
                # Get current active processes
                active_processes = await self._get_active_processes(session)
                
                # Calculate stage metrics
                stage_metrics = await self._calculate_stage_metrics(session)
                
                # Identify bottlenecks
                bottlenecks = await self._identify_bottlenecks(stage_metrics)
                
                # Calculate overall performance
                overall_performance = self._calculate_overall_performance(
                    active_processes, stage_metrics
                )
                
                return {
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'active_processes': len(active_processes),
                    'stage_metrics': {
                        stage.stage_name: {
                            'avg_duration_hours': stage.avg_duration_hours,
                            'current_volume': stage.current_volume,
                            'throughput_per_hour': stage.throughput_per_hour,
                            'bottleneck_severity': stage.bottleneck_severity.value
                        }
                        for stage in stage_metrics
                    },
                    'bottlenecks': [
                        {
                            'stage': bottleneck.stage_name,
                            'severity': bottleneck.severity.value,
                            'affected_processes': bottleneck.affected_processes,
                            'avg_delay_hours': bottleneck.avg_delay_hours,
                            'description': bottleneck.description
                        }
                        for bottleneck in bottlenecks
                    ],
                    'overall_performance': overall_performance,
                    'alerts': await self._get_active_alerts()
                }
                
        except Exception as e:
            logger.error("Failed to get real-time metrics", error=str(e))
            raise
    
    async def _get_active_processes(self, session) -> List[ProcessMetrics]:
        """Get currently active processes."""
        # This would query the actual database
        # For now, return mock data structure
        
        active_processes = []
        
        # In production, this would be a complex query joining:
        # - loan_application_history for current status
        # - loan_applications for basic info
        # - calculated metrics for processing times
        
        # Mock implementation
        mock_processes = [
            {
                'loan_application_id': 'LOAN_001',
                'current_status': 'UNDERWRITING',
                'status_entry_time': datetime.now(timezone.utc) - timedelta(hours=25),
                'total_processing_hours': 48.5
            },
            {
                'loan_application_id': 'LOAN_002', 
                'current_status': 'SUBMITTED',
                'status_entry_time': datetime.now(timezone.utc) - timedelta(hours=30),
                'total_processing_hours': 30.0
            }
        ]
        
        for process_data in mock_processes:
            stage_entry_time = process_data['status_entry_time']
            hours_in_stage = (datetime.now(timezone.utc) - stage_entry_time).total_seconds() / 3600
            
            # Determine status
            sla_hours = self.thresholds['stage_sla_hours'].get(
                process_data['current_status'], 48
            )
            
            if hours_in_stage > self.thresholds['stalled_threshold_hours']:
                status = ProcessStatus.STALLED
            elif hours_in_stage > sla_hours * 1.5:
                status = ProcessStatus.DELAYED
            elif hours_in_stage > sla_hours:
                status = ProcessStatus.ESCALATED
            else:
                status = ProcessStatus.ON_TRACK
            
            # Calculate performance score
            performance_score = max(0, 100 - (hours_in_stage / sla_hours * 50))
            
            process_metrics = ProcessMetrics(
                process_id=process_data['loan_application_id'],
                process_type='LOAN_APPLICATION',
                current_stage=process_data['current_status'],
                stage_entry_time=stage_entry_time,
                total_processing_time_hours=process_data['total_processing_hours'],
                expected_completion_time=stage_entry_time + timedelta(hours=sla_hours),
                status=status,
                bottleneck_indicators=[],
                performance_score=performance_score
            )
            
            active_processes.append(process_metrics)
        
        return active_processes
    
    async def _calculate_stage_metrics(self, session) -> List[StageMetrics]:
        """Calculate metrics for each process stage."""
        # This would query historical data to calculate stage performance
        # For now, return mock data
        
        stage_metrics = []
        
        mock_stage_data = {
            'SUBMITTED': {'avg': 18, 'median': 16, 'p90': 24, 'volume': 15, 'throughput': 2.5},
            'UNDERWRITING': {'avg': 45, 'median': 42, 'p90': 72, 'volume': 25, 'throughput': 1.2},
            'CREDIT_REVIEW': {'avg': 32, 'median': 28, 'p90': 48, 'volume': 8, 'throughput': 1.8},
            'APPROVED': {'avg': 16, 'median': 12, 'p90': 24, 'volume': 5, 'throughput': 3.0},
            'DISBURSEMENT': {'avg': 8, 'median': 6, 'p90': 12, 'volume': 3, 'throughput': 4.0}
        }
        
        for stage_name, data in mock_stage_data.items():
            # Determine bottleneck severity
            sla_hours = self.thresholds['stage_sla_hours'].get(stage_name, 48)
            
            if data['avg'] > sla_hours * 2:
                severity = BottleneckSeverity.CRITICAL
            elif data['avg'] > sla_hours * self.thresholds['bottleneck_threshold_multiplier']:
                severity = BottleneckSeverity.HIGH
            elif data['volume'] > self.thresholds['critical_volume_threshold']:
                severity = BottleneckSeverity.MEDIUM
            else:
                severity = BottleneckSeverity.LOW
            
            stage_metrics.append(StageMetrics(
                stage_name=stage_name,
                avg_duration_hours=data['avg'],
                median_duration_hours=data['median'],
                p90_duration_hours=data['p90'],
                current_volume=data['volume'],
                throughput_per_hour=data['throughput'],
                bottleneck_severity=severity
            ))
        
        return stage_metrics
    
    async def _identify_bottlenecks(self, stage_metrics: List[StageMetrics]) -> List[BottleneckAlert]:
        """Identify current bottlenecks."""
        bottlenecks = []
        
        for stage in stage_metrics:
            if stage.bottleneck_severity in [BottleneckSeverity.HIGH, BottleneckSeverity.CRITICAL]:
                sla_hours = self.thresholds['stage_sla_hours'].get(stage.stage_name, 48)
                delay_hours = stage.avg_duration_hours - sla_hours
                
                # Generate recommendations
                recommendations = []
                if stage.current_volume > self.thresholds['critical_volume_threshold']:
                    recommendations.append("Increase staffing for this stage")
                if stage.avg_duration_hours > sla_hours * 2:
                    recommendations.append("Review and optimize process workflow")
                if stage.throughput_per_hour < 1.0:
                    recommendations.append("Implement automation or process improvements")
                
                bottleneck = BottleneckAlert(
                    alert_id=f"bottleneck_{stage.stage_name}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}",
                    stage_name=stage.stage_name,
                    severity=stage.bottleneck_severity,
                    description=f"Stage {stage.stage_name} showing {stage.bottleneck_severity.value} bottleneck with {stage.current_volume} items and {stage.avg_duration_hours:.1f}h average duration",
                    affected_processes=stage.current_volume,
                    avg_delay_hours=delay_hours,
                    recommended_actions=recommendations,
                    created_at=datetime.now(timezone.utc)
                )
                
                bottlenecks.append(bottleneck)
        
        return bottlenecks
    
    def _calculate_overall_performance(
        self, 
        active_processes: List[ProcessMetrics], 
        stage_metrics: List[StageMetrics]
    ) -> Dict[str, Any]:
        """Calculate overall system performance metrics."""
        if not active_processes:
            return {
                'overall_score': 100.0,
                'total_processes': 0,
                'on_track_percent': 100.0,
                'avg_processing_time': 0.0,
                'bottleneck_stages': 0
            }
        
        # Calculate status distribution
        status_counts = {}
        for process in active_processes:
            status_counts[process.status.value] = status_counts.get(process.status.value, 0) + 1
        
        on_track_count = status_counts.get(ProcessStatus.ON_TRACK.value, 0)
        on_track_percent = (on_track_count / len(active_processes)) * 100
        
        # Calculate average performance score
        avg_performance_score = statistics.mean([p.performance_score for p in active_processes])
        
        # Count bottleneck stages
        bottleneck_stages = len([
            s for s in stage_metrics 
            if s.bottleneck_severity in [BottleneckSeverity.HIGH, BottleneckSeverity.CRITICAL]
        ])
        
        # Calculate overall score
        overall_score = (
            avg_performance_score * 0.6 +  # Individual process performance
            on_track_percent * 0.3 +       # Percentage on track
            max(0, 100 - bottleneck_stages * 10) * 0.1  # Bottleneck penalty
        )
        
        return {
            'overall_score': round(overall_score, 1),
            'total_processes': len(active_processes),
            'status_distribution': status_counts,
            'on_track_percent': round(on_track_percent, 1),
            'avg_processing_time': round(statistics.mean([p.total_processing_time_hours for p in active_processes]), 1),
            'bottleneck_stages': bottleneck_stages,
            'avg_performance_score': round(avg_performance_score, 1)
        }
    
    async def _get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get active process alerts."""
        # In production, this would query an alerts table
        # For now, return mock alerts
        
        return [
            {
                'alert_id': 'ALERT_001',
                'type': 'BOTTLENECK',
                'severity': 'HIGH',
                'message': 'UNDERWRITING stage has 25 applications with average 45h processing time',
                'created_at': (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
                'acknowledged': False
            },
            {
                'alert_id': 'ALERT_002',
                'type': 'SLA_BREACH',
                'severity': 'MEDIUM',
                'message': '5 applications have exceeded SLA in SUBMITTED stage',
                'created_at': (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
                'acknowledged': False
            }
        ]
    
    async def get_stage_performance_analysis(self, stage_name: str, days: int = 30) -> Dict[str, Any]:
        """Get detailed performance analysis for a specific stage."""
        try:
            # In production, this would query historical data
            # For now, return mock analysis
            
            mock_data = {
                'stage_name': stage_name,
                'analysis_period_days': days,
                'total_processed': 150,
                'avg_duration_hours': 42.5,
                'median_duration_hours': 38.0,
                'p90_duration_hours': 68.0,
                'min_duration_hours': 12.0,
                'max_duration_hours': 120.0,
                'sla_compliance_rate': 78.5,
                'throughput_trend': 'DECLINING',
                'bottleneck_frequency': 'HIGH',
                'recommendations': [
                    'Consider adding additional underwriters during peak hours',
                    'Implement automated pre-screening to reduce manual review time',
                    'Review complex cases that exceed 72 hours for process optimization'
                ]
            }
            
            return mock_data
            
        except Exception as e:
            logger.error("Failed to get stage performance analysis", 
                        stage=stage_name, error=str(e))
            raise
    
    async def get_process_timeline(self, process_id: str) -> Dict[str, Any]:
        """Get detailed timeline for a specific process."""
        try:
            # In production, this would query the process history
            # For now, return mock timeline
            
            mock_timeline = {
                'process_id': process_id,
                'process_type': 'LOAN_APPLICATION',
                'current_status': 'UNDERWRITING',
                'total_duration_hours': 48.5,
                'stages': [
                    {
                        'stage': 'SUBMITTED',
                        'entry_time': '2024-01-15T09:00:00Z',
                        'exit_time': '2024-01-15T15:30:00Z',
                        'duration_hours': 6.5,
                        'actor': 'SYSTEM',
                        'notes': 'Application submitted and validated'
                    },
                    {
                        'stage': 'UNDERWRITING',
                        'entry_time': '2024-01-15T15:30:00Z',
                        'exit_time': None,
                        'duration_hours': 42.0,
                        'actor': 'UNDERWRITER_001',
                        'notes': 'Under review for credit assessment'
                    }
                ],
                'bottlenecks_identified': [
                    {
                        'stage': 'UNDERWRITING',
                        'issue': 'Exceeding average duration by 15 hours',
                        'severity': 'MEDIUM'
                    }
                ],
                'predicted_completion': '2024-01-17T12:00:00Z',
                'sla_status': 'AT_RISK'
            }
            
            return mock_timeline
            
        except Exception as e:
            logger.error("Failed to get process timeline", 
                        process_id=process_id, error=str(e))
            raise
    
    def update_thresholds(self, new_thresholds: Dict[str, Any]):
        """Update performance thresholds."""
        self.thresholds.update(new_thresholds)
        logger.info("Updated process tracking thresholds", thresholds=self.thresholds)