"""
Loan Application Events fact transformer for ETL operations.

This module transforms loan application history data from the operational database
into the FactLoanApplicationEvents fact table for analytical queries.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

import pandas as pd
import structlog

from etl.models import FactLoanApplicationEvents
from etl.transformers.base_transformer import BaseTransformer
from shared.database import (
    DatabaseManager, 
    LoanApplicationModel, 
    LoanApplicationHistoryModel,
    CustomerModel,
    ActorModel
)

logger = structlog.get_logger(__name__)


class LoanEventsTransformer(BaseTransformer[FactLoanApplicationEvents]):
    """
    Transformer for Loan Application Events fact table.
    
    Transforms loan application history into analytical fact records
    with measures for processing duration and status changes.
    """
    
    def __init__(self, db_manager: DatabaseManager, batch_id: Optional[str] = None):
        """Initialize loan events transformer."""
        super().__init__(batch_id)
        self.db_manager = db_manager
        self.table_name = "fact_loan_application_events"
    
    def extract(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Extract loan application history data from operational database.
        
        Args:
            **kwargs: Optional parameters for filtering
                - incremental: bool - If True, extract only recent changes
                - since_date: datetime - Extract changes since this date
                
        Returns:
            List of loan application history records with related data
        """
        try:
            with self.db_manager.session_scope() as session:
                # Build complex query joining all related tables
                query = session.query(
                    LoanApplicationHistoryModel,
                    LoanApplicationModel,
                    CustomerModel,
                    ActorModel
                ).join(
                    LoanApplicationModel, 
                    LoanApplicationHistoryModel.loan_application_id == LoanApplicationModel.id
                ).join(
                    CustomerModel,
                    LoanApplicationModel.customer_id == CustomerModel.id
                ).join(
                    ActorModel,
                    LoanApplicationHistoryModel.changed_by_actor_id == ActorModel.id
                )
                
                # Apply incremental filtering if specified
                if kwargs.get('incremental', False):
                    since_date = kwargs.get('since_date')
                    if since_date:
                        query = query.filter(LoanApplicationHistoryModel.timestamp >= since_date)
                
                results = query.order_by(
                    LoanApplicationHistoryModel.loan_application_id,
                    LoanApplicationHistoryModel.timestamp
                ).all()
                
                events = []
                for history, loan, customer, actor in results:
                    event_data = {
                        # History data
                        'history_id': history.id,
                        'loan_application_id': loan.loan_application_id,
                        'customer_id': customer.customer_id,
                        'actor_id': actor.actor_id,
                        'change_type': history.change_type,
                        'previous_status': history.previous_status,
                        'new_status': history.new_status,
                        'field_name': history.field_name,
                        'old_value': history.old_value,
                        'new_value': history.new_value,
                        'blockchain_transaction_id': history.blockchain_transaction_id,
                        'timestamp': history.timestamp,
                        'notes': history.notes,
                        
                        # Loan application data
                        'requested_amount': loan.requested_amount,
                        'approval_amount': loan.approval_amount,
                        'loan_type': loan.loan_type,
                        'application_date': loan.application_date,
                        'current_status': loan.application_status,
                        
                        # Customer data
                        'customer_name': f"{customer.first_name} {customer.last_name}",
                        
                        # Actor data
                        'actor_name': actor.actor_name,
                        'actor_role': actor.role
                    }
                    events.append(event_data)
                
                logger.info("Extracted loan events data", 
                           count=len(events), 
                           batch_id=self.batch_id)
                
                return events
                
        except Exception as e:
            logger.error("Failed to extract loan events data", 
                        error=str(e), 
                        batch_id=self.batch_id)
            raise
    
    def transform(self, source_data: List[Dict[str, Any]]) -> List[FactLoanApplicationEvents]:
        """
        Transform loan events data to fact table model.
        
        Args:
            source_data: Raw loan events data from extraction
            
        Returns:
            List of FactLoanApplicationEvents records
        """
        try:
            # Validate data first
            valid_data = self.validate_data(source_data)
            
            # Calculate processing durations
            enriched_data = self._calculate_processing_durations(valid_data)
            
            transformed_records = []
            current_time = datetime.now(timezone.utc)
            
            for record in enriched_data:
                try:
                    # Generate surrogate keys
                    loan_application_key = self.generate_surrogate_key(
                        record['loan_application_id'], 
                        'dim_loan_application'
                    )
                    
                    customer_key = self.generate_surrogate_key(
                        record['customer_id'], 
                        'dim_customer'
                    )
                    
                    actor_key = self.generate_surrogate_key(
                        record['actor_id'], 
                        'dim_actor'
                    )
                    
                    # Convert timestamp to date key
                    event_timestamp = self.convert_datetime(record['timestamp'])
                    date_key = self.convert_to_date_key(event_timestamp)
                    
                    # Determine event type
                    event_type = self._determine_event_type(record)
                    
                    # Create fact record
                    fact_record = FactLoanApplicationEvents(
                        # Surrogate keys
                        loan_application_key=loan_application_key,
                        customer_key=customer_key,
                        actor_key=actor_key,
                        date_key=date_key,
                        
                        # Business keys
                        loan_application_id=record['loan_application_id'],
                        customer_id=record['customer_id'],
                        actor_id=record['actor_id'],
                        
                        # Event details
                        event_type=event_type,
                        previous_status=record.get('previous_status'),
                        new_status=record.get('new_status'),
                        change_type=record['change_type'],
                        
                        # Measures
                        requested_amount=float(record['requested_amount']),
                        approval_amount=float(record['approval_amount']) if record.get('approval_amount') else None,
                        processing_duration_hours=record.get('processing_duration_hours'),
                        
                        # Degenerate dimensions
                        blockchain_transaction_id=record.get('blockchain_transaction_id'),
                        notes=record.get('notes'),
                        
                        # Audit fields
                        event_timestamp=event_timestamp,
                        created_at=current_time,
                        etl_batch_id=self.batch_id
                    )
                    
                    transformed_records.append(fact_record)
                    
                except Exception as e:
                    logger.error("Failed to transform loan event record", 
                                loan_id=record.get('loan_application_id'),
                                history_id=record.get('history_id'),
                                error=str(e),
                                batch_id=self.batch_id)
                    self.records_failed += 1
                    self.errors.append(f"Transform error for loan event {record.get('history_id')}: {str(e)}")
            
            logger.info("Transformed loan events data", 
                       count=len(transformed_records), 
                       batch_id=self.batch_id)
            
            return transformed_records
            
        except Exception as e:
            logger.error("Failed to transform loan events data", 
                        error=str(e), 
                        batch_id=self.batch_id)
            raise
    
    def load(self, transformed_data: List[FactLoanApplicationEvents]) -> bool:
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
            logger.info("Loading loan events fact data", 
                       count=len(transformed_data), 
                       batch_id=self.batch_id)
            
            for record in transformed_data:
                logger.debug("Would load loan event record", 
                           loan_application_id=record.loan_application_id,
                           event_type=record.event_type,
                           event_timestamp=record.event_timestamp,
                           processing_duration=record.processing_duration_hours,
                           batch_id=self.batch_id)
            
            # Simulate successful load
            self.records_inserted = len(transformed_data)
            
            logger.info("Successfully loaded loan events fact data", 
                       records_inserted=self.records_inserted,
                       batch_id=self.batch_id)
            
            return True
            
        except Exception as e:
            logger.error("Failed to load loan events fact data", 
                        error=str(e), 
                        batch_id=self.batch_id)
            return False
    
    def _calculate_processing_durations(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Calculate processing durations between status changes.
        
        Args:
            events: List of event records
            
        Returns:
            Events enriched with processing duration calculations
        """
        # Group events by loan application
        df = pd.DataFrame(events)
        if df.empty:
            return events
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values(['loan_application_id', 'timestamp'])
        
        enriched_events = []
        
        for loan_id, group in df.groupby('loan_application_id'):
            group = group.reset_index(drop=True)
            
            for i, row in group.iterrows():
                event_dict = row.to_dict()
                
                # Calculate duration from previous status change
                if i > 0 and row['change_type'] == 'STATUS_CHANGE':
                    prev_row = group.iloc[i-1]
                    if prev_row['change_type'] == 'STATUS_CHANGE':
                        duration = (row['timestamp'] - prev_row['timestamp']).total_seconds() / 3600
                        event_dict['processing_duration_hours'] = round(duration, 2)
                    else:
                        event_dict['processing_duration_hours'] = None
                else:
                    event_dict['processing_duration_hours'] = None
                
                enriched_events.append(event_dict)
        
        return enriched_events
    
    def _determine_event_type(self, record: Dict[str, Any]) -> str:
        """
        Determine standardized event type from change data.
        
        Args:
            record: Event record
            
        Returns:
            Standardized event type
        """
        change_type = record.get('change_type', '').upper()
        new_status = record.get('new_status', '').upper()
        
        # Map change types to standardized event types
        if change_type == 'STATUS_CHANGE':
            if new_status in ['APPROVED', 'DISBURSED']:
                return 'APPROVAL'
            elif new_status in ['REJECTED', 'DECLINED']:
                return 'REJECTION'
            elif new_status == 'UNDERWRITING':
                return 'UNDERWRITING_START'
            elif new_status == 'SUBMITTED':
                return 'APPLICATION_SUBMITTED'
            else:
                return 'STATUS_CHANGE'
        elif change_type == 'APPROVAL':
            return 'APPROVAL'
        elif change_type == 'REJECTION':
            return 'REJECTION'
        elif change_type == 'UPDATE':
            return 'DATA_UPDATE'
        else:
            return change_type or 'UNKNOWN'
    
    def _validate_record(self, record: Dict[str, Any]) -> bool:
        """Validate loan event record."""
        required_fields = [
            'loan_application_id', 'customer_id', 'actor_id', 
            'change_type', 'timestamp', 'requested_amount'
        ]
        
        for field in required_fields:
            if not record.get(field):
                logger.warning("Missing required field", 
                              field=field, 
                              loan_id=record.get('loan_application_id'),
                              history_id=record.get('history_id'),
                              batch_id=self.batch_id)
                return False
        
        # Validate timestamp
        try:
            timestamp = self.convert_datetime(record['timestamp'])
            if not timestamp:
                logger.warning("Invalid timestamp", 
                              timestamp=record['timestamp'],
                              loan_id=record.get('loan_application_id'),
                              batch_id=self.batch_id)
                return False
        except Exception:
            logger.warning("Failed to parse timestamp", 
                          timestamp=record['timestamp'],
                          loan_id=record.get('loan_application_id'),
                          batch_id=self.batch_id)
            return False
        
        # Validate amounts
        try:
            requested_amount = float(record['requested_amount'])
            if requested_amount <= 0:
                logger.warning("Invalid requested amount", 
                              amount=requested_amount,
                              loan_id=record.get('loan_application_id'),
                              batch_id=self.batch_id)
                return False
        except (ValueError, TypeError):
            logger.warning("Invalid requested amount format", 
                          amount=record['requested_amount'],
                          loan_id=record.get('loan_application_id'),
                          batch_id=self.batch_id)
            return False
        
        return True
    
    def get_processing_metrics(self, loan_application_id: str) -> Dict[str, Any]:
        """
        Get processing metrics for a specific loan application.
        
        Args:
            loan_application_id: Loan application ID
            
        Returns:
            Dictionary with processing metrics
        """
        try:
            # Extract events for specific loan
            events = self.extract()
            loan_events = [e for e in events if e['loan_application_id'] == loan_application_id]
            
            if not loan_events:
                return {}
            
            # Calculate metrics
            df = pd.DataFrame(loan_events)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            
            metrics = {
                'total_events': len(loan_events),
                'status_changes': len(df[df['change_type'] == 'STATUS_CHANGE']),
                'total_processing_time_hours': None,
                'average_stage_duration_hours': None,
                'current_stage_duration_hours': None,
                'stages': []
            }
            
            # Calculate total processing time
            if len(df) > 1:
                total_time = (df.iloc[-1]['timestamp'] - df.iloc[0]['timestamp']).total_seconds() / 3600
                metrics['total_processing_time_hours'] = round(total_time, 2)
            
            # Calculate stage durations
            status_changes = df[df['change_type'] == 'STATUS_CHANGE'].copy()
            if len(status_changes) > 1:
                durations = []
                for i in range(1, len(status_changes)):
                    duration = (status_changes.iloc[i]['timestamp'] - 
                              status_changes.iloc[i-1]['timestamp']).total_seconds() / 3600
                    durations.append(duration)
                    
                    stage_info = {
                        'from_status': status_changes.iloc[i-1]['new_status'],
                        'to_status': status_changes.iloc[i]['new_status'],
                        'duration_hours': round(duration, 2),
                        'start_time': status_changes.iloc[i-1]['timestamp'].isoformat(),
                        'end_time': status_changes.iloc[i]['timestamp'].isoformat()
                    }
                    metrics['stages'].append(stage_info)
                
                if durations:
                    metrics['average_stage_duration_hours'] = round(sum(durations) / len(durations), 2)
            
            # Calculate current stage duration
            if len(status_changes) > 0:
                last_status_change = status_changes.iloc[-1]['timestamp']
                current_time = datetime.now(timezone.utc)
                current_duration = (current_time - last_status_change).total_seconds() / 3600
                metrics['current_stage_duration_hours'] = round(current_duration, 2)
            
            return metrics
            
        except Exception as e:
            logger.error("Failed to calculate processing metrics", 
                        loan_id=loan_application_id,
                        error=str(e))
            return {}