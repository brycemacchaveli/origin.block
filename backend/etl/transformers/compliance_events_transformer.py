"""
Compliance Events fact transformer for ETL operations.

This module transforms compliance event data from the operational database
into the FactComplianceEvents fact table for regulatory reporting and analysis.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import json

import pandas as pd
import structlog

from etl.models import FactComplianceEvents
from etl.transformers.base_transformer import BaseTransformer
from shared.database import (
    DatabaseManager, 
    ComplianceEventModel,
    ActorModel
)

logger = structlog.get_logger(__name__)


class ComplianceEventsTransformer(BaseTransformer[FactComplianceEvents]):
    """
    Transformer for Compliance Events fact table.
    
    Transforms compliance events into analytical fact records
    with measures for resolution time and violation tracking.
    """
    
    def __init__(self, db_manager: DatabaseManager, batch_id: Optional[str] = None):
        """Initialize compliance events transformer."""
        super().__init__(batch_id)
        self.db_manager = db_manager
        self.table_name = "fact_compliance_events"
    
    def extract(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Extract compliance events data from operational database.
        
        Args:
            **kwargs: Optional parameters for filtering
                - incremental: bool - If True, extract only recent changes
                - since_date: datetime - Extract changes since this date
                - severity: str - Filter by severity level
                - event_type: str - Filter by event type
                
        Returns:
            List of compliance event records with related data
        """
        try:
            with self.db_manager.session_scope() as session:
                # Build query joining compliance events with actors
                query = session.query(
                    ComplianceEventModel,
                    ActorModel.alias('triggering_actor'),
                    ActorModel.alias('acknowledging_actor')
                ).join(
                    ActorModel.alias('triggering_actor'),
                    ComplianceEventModel.actor_id == ActorModel.id
                ).outerjoin(
                    ActorModel.alias('acknowledging_actor'),
                    ComplianceEventModel.acknowledged_by_actor_id == ActorModel.id
                )
                
                # Apply filters
                if kwargs.get('incremental', False):
                    since_date = kwargs.get('since_date')
                    if since_date:
                        query = query.filter(ComplianceEventModel.timestamp >= since_date)
                
                if kwargs.get('severity'):
                    query = query.filter(ComplianceEventModel.severity == kwargs['severity'])
                
                if kwargs.get('event_type'):
                    query = query.filter(ComplianceEventModel.event_type == kwargs['event_type'])
                
                results = query.order_by(ComplianceEventModel.timestamp.desc()).all()
                
                events = []
                for event, triggering_actor, acknowledging_actor in results:
                    # Parse details JSON if it exists
                    details = event.details
                    if isinstance(details, str):
                        try:
                            details = json.loads(details)
                        except json.JSONDecodeError:
                            details = {}
                    
                    event_data = {
                        # Event data
                        'event_id': event.event_id,
                        'event_type': event.event_type,
                        'rule_id': event.rule_id,
                        'affected_entity_type': event.affected_entity_type,
                        'affected_entity_id': event.affected_entity_id,
                        'severity': event.severity,
                        'description': event.description,
                        'details': details,
                        'is_alerted': event.is_alerted,
                        'resolution_status': event.resolution_status,
                        'resolution_notes': event.resolution_notes,
                        'blockchain_transaction_id': event.blockchain_transaction_id,
                        'timestamp': event.timestamp,
                        'acknowledged_at': event.acknowledged_at,
                        
                        # Actor data
                        'actor_id': triggering_actor.actor_id,
                        'actor_name': triggering_actor.actor_name,
                        'actor_role': triggering_actor.role,
                        'acknowledged_by_actor_id': acknowledging_actor.actor_id if acknowledging_actor else None,
                        'acknowledged_by_actor_name': acknowledging_actor.actor_name if acknowledging_actor else None,
                    }
                    events.append(event_data)
                
                logger.info("Extracted compliance events data", 
                           count=len(events), 
                           batch_id=self.batch_id)
                
                return events
                
        except Exception as e:
            logger.error("Failed to extract compliance events data", 
                        error=str(e), 
                        batch_id=self.batch_id)
            raise
    
    def transform(self, source_data: List[Dict[str, Any]]) -> List[FactComplianceEvents]:
        """
        Transform compliance events data to fact table model.
        
        Args:
            source_data: Raw compliance events data from extraction
            
        Returns:
            List of FactComplianceEvents records
        """
        try:
            # Validate data first
            valid_data = self.validate_data(source_data)
            
            transformed_records = []
            current_time = datetime.now(timezone.utc)
            
            for record in valid_data:
                try:
                    # Generate surrogate keys
                    compliance_rule_key = None
                    if record.get('rule_id'):
                        compliance_rule_key = self.generate_surrogate_key(
                            record['rule_id'], 
                            'dim_compliance_rule'
                        )
                    
                    actor_key = self.generate_surrogate_key(
                        record['actor_id'], 
                        'dim_actor'
                    )
                    
                    # Convert timestamp to date key
                    event_timestamp = self.convert_datetime(record['timestamp'])
                    date_key = self.convert_to_date_key(event_timestamp)
                    
                    # Calculate resolution duration
                    resolution_duration_hours = self._calculate_resolution_duration(record)
                    
                    # Determine if this is a violation
                    is_violation = self._is_violation_event(record)
                    
                    # Count alerts
                    alert_count = 1 if record.get('is_alerted', False) else 0
                    
                    # Create fact record
                    fact_record = FactComplianceEvents(
                        # Surrogate keys
                        compliance_rule_key=compliance_rule_key,
                        actor_key=actor_key,
                        date_key=date_key,
                        
                        # Business keys
                        event_id=record['event_id'],
                        rule_id=record.get('rule_id'),
                        actor_id=record['actor_id'],
                        affected_entity_id=record['affected_entity_id'],
                        
                        # Event details
                        event_type=record['event_type'],
                        affected_entity_type=record['affected_entity_type'],
                        severity=record['severity'],
                        resolution_status=record['resolution_status'],
                        
                        # Measures
                        resolution_duration_hours=resolution_duration_hours,
                        is_violation=is_violation,
                        alert_count=alert_count,
                        
                        # Degenerate dimensions
                        description=record['description'],
                        details=record.get('details'),
                        blockchain_transaction_id=record.get('blockchain_transaction_id'),
                        
                        # Audit fields
                        event_timestamp=event_timestamp,
                        acknowledged_at=self.convert_datetime(record.get('acknowledged_at')),
                        created_at=current_time,
                        etl_batch_id=self.batch_id
                    )
                    
                    transformed_records.append(fact_record)
                    
                except Exception as e:
                    logger.error("Failed to transform compliance event record", 
                                event_id=record.get('event_id'),
                                error=str(e),
                                batch_id=self.batch_id)
                    self.records_failed += 1
                    self.errors.append(f"Transform error for compliance event {record.get('event_id')}: {str(e)}")
            
            logger.info("Transformed compliance events data", 
                       count=len(transformed_records), 
                       batch_id=self.batch_id)
            
            return transformed_records
            
        except Exception as e:
            logger.error("Failed to transform compliance events data", 
                        error=str(e), 
                        batch_id=self.batch_id)
            raise
    
    def load(self, transformed_data: List[FactComplianceEvents]) -> bool:
        """
        Load transformed data to BigQuery.
        
        Note: This is a placeholder implementation.
        In production, this would use BigQuery client to load data.
        
        Args:
            transformed_data: Transformed fact records
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Loading compliance events fact data", 
                       count=len(transformed_data), 
                       batch_id=self.batch_id)
            
            for record in transformed_data:
                logger.debug("Would load compliance event record", 
                           event_id=record.event_id,
                           event_type=record.event_type,
                           severity=record.severity,
                           is_violation=record.is_violation,
                           resolution_duration=record.resolution_duration_hours,
                           batch_id=self.batch_id)
            
            # Simulate successful load
            self.records_inserted = len(transformed_data)
            
            logger.info("Successfully loaded compliance events fact data", 
                       records_inserted=self.records_inserted,
                       batch_id=self.batch_id)
            
            return True
            
        except Exception as e:
            logger.error("Failed to load compliance events fact data", 
                        error=str(e), 
                        batch_id=self.batch_id)
            return False
    
    def _calculate_resolution_duration(self, record: Dict[str, Any]) -> Optional[float]:
        """
        Calculate resolution duration in hours.
        
        Args:
            record: Compliance event record
            
        Returns:
            Duration in hours or None if not resolved
        """
        if not record.get('acknowledged_at'):
            return None
        
        try:
            event_time = self.convert_datetime(record['timestamp'])
            acknowledged_time = self.convert_datetime(record['acknowledged_at'])
            
            if event_time and acknowledged_time:
                duration = (acknowledged_time - event_time).total_seconds() / 3600
                return round(duration, 2)
        except Exception as e:
            logger.warning("Failed to calculate resolution duration", 
                          event_id=record.get('event_id'),
                          error=str(e),
                          batch_id=self.batch_id)
        
        return None
    
    def _is_violation_event(self, record: Dict[str, Any]) -> bool:
        """
        Determine if event represents a compliance violation.
        
        Args:
            record: Compliance event record
            
        Returns:
            True if violation, False otherwise
        """
        # Define violation event types
        violation_types = [
            'RULE_VIOLATION',
            'AML_VIOLATION',
            'KYC_FAILURE',
            'SANCTION_HIT',
            'TRANSACTION_LIMIT_EXCEEDED',
            'UNAUTHORIZED_ACCESS',
            'DATA_BREACH'
        ]
        
        event_type = record.get('event_type', '').upper()
        severity = record.get('severity', '').upper()
        
        # Check if event type indicates violation
        if event_type in violation_types:
            return True
        
        # Check if severity indicates violation
        if severity in ['ERROR', 'CRITICAL']:
            return True
        
        # Check description for violation keywords
        description = record.get('description', '').lower()
        violation_keywords = ['violation', 'breach', 'failed', 'rejected', 'blocked', 'flagged']
        
        for keyword in violation_keywords:
            if keyword in description:
                return True
        
        return False
    
    def _validate_record(self, record: Dict[str, Any]) -> bool:
        """Validate compliance event record."""
        required_fields = [
            'event_id', 'event_type', 'affected_entity_type', 
            'affected_entity_id', 'severity', 'description', 
            'actor_id', 'timestamp'
        ]
        
        for field in required_fields:
            if not record.get(field):
                logger.warning("Missing required field", 
                              field=field, 
                              event_id=record.get('event_id'),
                              batch_id=self.batch_id)
                return False
        
        # Validate severity levels
        valid_severities = ['INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if record['severity'].upper() not in valid_severities:
            logger.warning("Invalid severity level", 
                          severity=record['severity'],
                          event_id=record.get('event_id'),
                          batch_id=self.batch_id)
            return False
        
        # Validate entity types
        valid_entity_types = ['CUSTOMER', 'LOAN_APPLICATION', 'ACTOR', 'TRANSACTION']
        if record['affected_entity_type'].upper() not in valid_entity_types:
            logger.warning("Invalid entity type", 
                          entity_type=record['affected_entity_type'],
                          event_id=record.get('event_id'),
                          batch_id=self.batch_id)
            return False
        
        # Validate timestamp
        try:
            timestamp = self.convert_datetime(record['timestamp'])
            if not timestamp:
                logger.warning("Invalid timestamp", 
                              timestamp=record['timestamp'],
                              event_id=record.get('event_id'),
                              batch_id=self.batch_id)
                return False
        except Exception:
            logger.warning("Failed to parse timestamp", 
                          timestamp=record['timestamp'],
                          event_id=record.get('event_id'),
                          batch_id=self.batch_id)
            return False
        
        return True
    
    def get_compliance_metrics(
        self, 
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        date_range_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get compliance metrics for analysis.
        
        Args:
            entity_type: Filter by entity type
            entity_id: Filter by specific entity ID
            date_range_days: Number of days to analyze
            
        Returns:
            Dictionary with compliance metrics
        """
        try:
            # Calculate date range
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=date_range_days)
            
            # Extract events for date range
            kwargs = {'incremental': True, 'since_date': start_date}
            if entity_type:
                kwargs['entity_type'] = entity_type
            
            events = self.extract(**kwargs)
            
            # Filter by entity ID if specified
            if entity_id:
                events = [e for e in events if e['affected_entity_id'] == entity_id]
            
            if not events:
                return {
                    'total_events': 0,
                    'violations': 0,
                    'violation_rate': 0.0,
                    'avg_resolution_time_hours': 0.0,
                    'events_by_severity': {},
                    'events_by_type': {},
                    'unresolved_events': 0
                }
            
            df = pd.DataFrame(events)
            
            # Calculate basic metrics
            total_events = len(events)
            violations = len([e for e in events if self._is_violation_event(e)])
            violation_rate = (violations / total_events) * 100 if total_events > 0 else 0.0
            
            # Calculate resolution times
            resolved_events = df[df['acknowledged_at'].notna()]
            avg_resolution_time = 0.0
            
            if not resolved_events.empty:
                resolution_times = []
                for _, row in resolved_events.iterrows():
                    duration = self._calculate_resolution_duration(row.to_dict())
                    if duration is not None:
                        resolution_times.append(duration)
                
                if resolution_times:
                    avg_resolution_time = sum(resolution_times) / len(resolution_times)
            
            # Group by severity
            events_by_severity = df['severity'].value_counts().to_dict()
            
            # Group by event type
            events_by_type = df['event_type'].value_counts().to_dict()
            
            # Count unresolved events
            unresolved_events = len(df[df['resolution_status'].isin(['OPEN', 'IN_PROGRESS'])])
            
            metrics = {
                'total_events': total_events,
                'violations': violations,
                'violation_rate': round(violation_rate, 2),
                'avg_resolution_time_hours': round(avg_resolution_time, 2),
                'events_by_severity': events_by_severity,
                'events_by_type': events_by_type,
                'unresolved_events': unresolved_events,
                'date_range_days': date_range_days,
                'analysis_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            }
            
            return metrics
            
        except Exception as e:
            logger.error("Failed to calculate compliance metrics", 
                        entity_type=entity_type,
                        entity_id=entity_id,
                        error=str(e))
            return {}
    
    def get_violation_trends(self, days: int = 90) -> Dict[str, Any]:
        """
        Get violation trends over time.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with trend data
        """
        try:
            # Calculate date range
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days)
            
            # Extract events
            events = self.extract(incremental=True, since_date=start_date)
            
            if not events:
                return {'daily_violations': {}, 'trend_direction': 'stable'}
            
            # Filter violations only
            violations = [e for e in events if self._is_violation_event(e)]
            
            if not violations:
                return {'daily_violations': {}, 'trend_direction': 'stable'}
            
            # Group by date
            df = pd.DataFrame(violations)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['date'] = df['timestamp'].dt.date
            
            daily_violations = df.groupby('date').size().to_dict()
            
            # Convert dates to strings for JSON serialization
            daily_violations = {
                str(date): count for date, count in daily_violations.items()
            }
            
            # Calculate trend direction
            if len(daily_violations) >= 7:
                recent_avg = sum(list(daily_violations.values())[-7:]) / 7
                earlier_avg = sum(list(daily_violations.values())[:-7]) / max(1, len(daily_violations) - 7)
                
                if recent_avg > earlier_avg * 1.1:
                    trend_direction = 'increasing'
                elif recent_avg < earlier_avg * 0.9:
                    trend_direction = 'decreasing'
                else:
                    trend_direction = 'stable'
            else:
                trend_direction = 'insufficient_data'
            
            return {
                'daily_violations': daily_violations,
                'trend_direction': trend_direction,
                'total_violations': len(violations),
                'analysis_days': days
            }
            
        except Exception as e:
            logger.error("Failed to calculate violation trends", 
                        days=days,
                        error=str(e))
            return {}