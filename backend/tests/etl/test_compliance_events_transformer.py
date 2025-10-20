"""
Unit tests for Compliance Events Transformer.

Tests the compliance events fact transformer functionality including
data extraction, transformation, violation detection, and metrics calculation.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock, patch
import json

from etl.transformers.compliance_events_transformer import ComplianceEventsTransformer
from etl.models import FactComplianceEvents, ETLBatch
from shared.database import DatabaseManager, ComplianceEventModel, ActorModel


class TestComplianceEventsTransformer:
    """Test cases for ComplianceEventsTransformer."""
    
    @pytest.fixture
    def mock_db_manager(self):
        """Create mock database manager."""
        db_manager = Mock(spec=DatabaseManager)
        db_manager.session_scope = MagicMock()
        return db_manager
    
    @pytest.fixture
    def transformer(self, mock_db_manager):
        """Create ComplianceEventsTransformer instance."""
        return ComplianceEventsTransformer(mock_db_manager, batch_id="test_batch_123")
    
    @pytest.fixture
    def sample_compliance_events_data(self):
        """Sample compliance events data for testing."""
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        return [
            {
                'event_id': 'COMP_001',
                'event_type': 'AML_CHECK',
                'rule_id': 'RULE_001',
                'affected_entity_type': 'CUSTOMER',
                'affected_entity_id': 'CUST_001',
                'severity': 'INFO',
                'description': 'Routine AML check passed',
                'details': {'check_type': 'automated', 'score': 0.1},
                'is_alerted': False,
                'resolution_status': 'RESOLVED',
                'resolution_notes': 'Automatically resolved',
                'blockchain_transaction_id': 'TX_001',
                'timestamp': base_time,
                'acknowledged_at': base_time + timedelta(minutes=5),
                'actor_id': 'ACTOR_001',
                'actor_name': 'System',
                'actor_role': 'SYSTEM',
                'acknowledged_by_actor_id': None,
                'acknowledged_by_actor_name': None
            },
            {
                'event_id': 'COMP_002',
                'event_type': 'RULE_VIOLATION',
                'rule_id': 'RULE_002',
                'affected_entity_type': 'LOAN_APPLICATION',
                'affected_entity_id': 'LOAN_001',
                'severity': 'ERROR',
                'description': 'Transaction limit exceeded',
                'details': {'limit': 100000, 'requested': 150000},
                'is_alerted': True,
                'resolution_status': 'IN_PROGRESS',
                'resolution_notes': None,
                'blockchain_transaction_id': 'TX_002',
                'timestamp': base_time + timedelta(hours=1),
                'acknowledged_at': base_time + timedelta(hours=2),
                'actor_id': 'ACTOR_002',
                'actor_name': 'Loan Officer',
                'actor_role': 'UNDERWRITER',
                'acknowledged_by_actor_id': 'ACTOR_003',
                'acknowledged_by_actor_name': 'Compliance Officer'
            },
            {
                'event_id': 'COMP_003',
                'event_type': 'SANCTION_HIT',
                'rule_id': 'RULE_003',
                'affected_entity_type': 'CUSTOMER',
                'affected_entity_id': 'CUST_002',
                'severity': 'CRITICAL',
                'description': 'Customer found on sanction list',
                'details': {'list_name': 'OFAC', 'match_score': 0.95},
                'is_alerted': True,
                'resolution_status': 'OPEN',
                'resolution_notes': None,
                'blockchain_transaction_id': 'TX_003',
                'timestamp': base_time + timedelta(hours=2),
                'acknowledged_at': None,
                'actor_id': 'ACTOR_001',
                'actor_name': 'System',
                'actor_role': 'SYSTEM',
                'acknowledged_by_actor_id': None,
                'acknowledged_by_actor_name': None
            }
        ]
    
    def test_init(self, mock_db_manager):
        """Test transformer initialization."""
        transformer = ComplianceEventsTransformer(mock_db_manager, batch_id="test_batch")
        
        assert transformer.db_manager == mock_db_manager
        assert transformer.batch_id == "test_batch"
        assert transformer.table_name == "fact_compliance_events"
        assert transformer.records_processed == 0
    
    def test_extract_success(self, transformer, mock_db_manager):
        """Test successful data extraction."""
        # Mock database session and query results
        mock_session = MagicMock()
        mock_db_manager.session_scope.return_value.__enter__.return_value = mock_session
        
        # Create mock objects
        mock_event = Mock(spec=ComplianceEventModel)
        mock_event.event_id = 'COMP_001'
        mock_event.event_type = 'AML_CHECK'
        mock_event.rule_id = 'RULE_001'
        mock_event.affected_entity_type = 'CUSTOMER'
        mock_event.affected_entity_id = 'CUST_001'
        mock_event.severity = 'INFO'
        mock_event.description = 'Routine AML check passed'
        mock_event.details = {'check_type': 'automated'}
        mock_event.is_alerted = False
        mock_event.resolution_status = 'RESOLVED'
        mock_event.resolution_notes = 'Automatically resolved'
        mock_event.blockchain_transaction_id = 'TX_001'
        mock_event.timestamp = datetime(2024, 1, 1, 10, 0, 0)
        mock_event.acknowledged_at = datetime(2024, 1, 1, 10, 5, 0)
        
        mock_triggering_actor = Mock(spec=ActorModel)
        mock_triggering_actor.actor_id = 'ACTOR_001'
        mock_triggering_actor.actor_name = 'System'
        mock_triggering_actor.role = 'SYSTEM'
        
        mock_acknowledging_actor = None  # No acknowledging actor
        
        # Mock query chain
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.outerjoin.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [(mock_event, mock_triggering_actor, mock_acknowledging_actor)]
        
        # Execute extraction
        result = transformer.extract()
        
        # Verify results
        assert len(result) == 1
        assert result[0]['event_id'] == 'COMP_001'
        assert result[0]['event_type'] == 'AML_CHECK'
        assert result[0]['severity'] == 'INFO'
        assert result[0]['actor_id'] == 'ACTOR_001'
        assert result[0]['acknowledged_by_actor_id'] is None
    
    def test_extract_with_filters(self, transformer, mock_db_manager):
        """Test data extraction with filters."""
        mock_session = MagicMock()
        mock_db_manager.session_scope.return_value.__enter__.return_value = mock_session
        
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.outerjoin.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []
        
        # Test with severity filter
        transformer.extract(severity='ERROR')
        
        # Test with event type filter
        transformer.extract(event_type='RULE_VIOLATION')
        
        # Test with incremental filter
        since_date = datetime.now(timezone.utc) - timedelta(days=1)
        transformer.extract(incremental=True, since_date=since_date)
        
        # Verify filters were applied
        assert mock_query.filter.call_count >= 3
    
    def test_transform_success(self, transformer, sample_compliance_events_data):
        """Test successful data transformation."""
        result = transformer.transform(sample_compliance_events_data)
        
        assert len(result) == 3
        
        # Check first record (AML check)
        first_record = result[0]
        assert isinstance(first_record, FactComplianceEvents)
        assert first_record.event_id == 'COMP_001'
        assert first_record.event_type == 'AML_CHECK'
        assert first_record.severity == 'INFO'
        assert first_record.is_violation is False  # INFO severity, not a violation
        assert first_record.alert_count == 0  # Not alerted
        assert first_record.resolution_duration_hours == 0.08  # 5 minutes = 0.08 hours (rounded)
        assert first_record.etl_batch_id == "test_batch_123"
        
        # Check second record (rule violation)
        second_record = result[1]
        assert second_record.event_type == 'RULE_VIOLATION'
        assert second_record.severity == 'ERROR'
        assert second_record.is_violation is True  # ERROR severity indicates violation
        assert second_record.alert_count == 1  # Alerted
        assert second_record.resolution_duration_hours == 1.0  # 1 hour
        
        # Check third record (sanction hit)
        third_record = result[2]
        assert third_record.event_type == 'SANCTION_HIT'
        assert third_record.severity == 'CRITICAL'
        assert third_record.is_violation is True  # CRITICAL severity indicates violation
        assert third_record.alert_count == 1  # Alerted
        assert third_record.resolution_duration_hours is None  # Not acknowledged yet
    
    def test_calculate_resolution_duration(self, transformer):
        """Test resolution duration calculation."""
        # Test with acknowledged event
        record_with_ack = {
            'timestamp': datetime(2024, 1, 1, 10, 0, 0),
            'acknowledged_at': datetime(2024, 1, 1, 12, 30, 0)
        }
        duration = transformer._calculate_resolution_duration(record_with_ack)
        assert duration == 2.5  # 2.5 hours
        
        # Test without acknowledgment
        record_without_ack = {
            'timestamp': datetime(2024, 1, 1, 10, 0, 0),
            'acknowledged_at': None
        }
        duration = transformer._calculate_resolution_duration(record_without_ack)
        assert duration is None
        
        # Test with invalid timestamps
        record_invalid = {
            'timestamp': 'invalid',
            'acknowledged_at': datetime(2024, 1, 1, 12, 0, 0)
        }
        duration = transformer._calculate_resolution_duration(record_invalid)
        assert duration is None
    
    def test_is_violation_event(self, transformer):
        """Test violation event detection."""
        # Test violation event types
        violation_record = {'event_type': 'RULE_VIOLATION', 'severity': 'INFO', 'description': 'test'}
        assert transformer._is_violation_event(violation_record) is True
        
        sanction_record = {'event_type': 'SANCTION_HIT', 'severity': 'INFO', 'description': 'test'}
        assert transformer._is_violation_event(sanction_record) is True
        
        # Test violation by severity
        error_record = {'event_type': 'SOME_EVENT', 'severity': 'ERROR', 'description': 'test'}
        assert transformer._is_violation_event(error_record) is True
        
        critical_record = {'event_type': 'SOME_EVENT', 'severity': 'CRITICAL', 'description': 'test'}
        assert transformer._is_violation_event(critical_record) is True
        
        # Test violation by description keywords
        keyword_record = {'event_type': 'SOME_EVENT', 'severity': 'INFO', 'description': 'Transaction failed due to violation'}
        assert transformer._is_violation_event(keyword_record) is True
        
        # Test non-violation
        normal_record = {'event_type': 'ROUTINE_CHECK', 'severity': 'INFO', 'description': 'Normal operation'}
        assert transformer._is_violation_event(normal_record) is False
    
    def test_load_success(self, transformer, sample_compliance_events_data):
        """Test successful data loading."""
        transformed_data = transformer.transform(sample_compliance_events_data)
        
        result = transformer.load(transformed_data)
        
        assert result is True
        assert transformer.records_inserted == 3
    
    def test_validate_record_valid(self, transformer):
        """Test validation of valid compliance event record."""
        valid_record = {
            'event_id': 'COMP_001',
            'event_type': 'AML_CHECK',
            'affected_entity_type': 'CUSTOMER',
            'affected_entity_id': 'CUST_001',
            'severity': 'INFO',
            'description': 'Routine check',
            'actor_id': 'ACTOR_001',
            'timestamp': datetime(2024, 1, 1, 10, 0, 0)
        }
        
        result = transformer._validate_record(valid_record)
        assert result is True
    
    def test_validate_record_missing_required_field(self, transformer):
        """Test validation with missing required field."""
        invalid_record = {
            'event_id': 'COMP_001',
            'event_type': 'AML_CHECK',
            # Missing affected_entity_type
            'affected_entity_id': 'CUST_001',
            'severity': 'INFO',
            'description': 'Routine check',
            'actor_id': 'ACTOR_001',
            'timestamp': datetime(2024, 1, 1, 10, 0, 0)
        }
        
        result = transformer._validate_record(invalid_record)
        assert result is False
    
    def test_validate_record_invalid_severity(self, transformer):
        """Test validation with invalid severity."""
        invalid_record = {
            'event_id': 'COMP_001',
            'event_type': 'AML_CHECK',
            'affected_entity_type': 'CUSTOMER',
            'affected_entity_id': 'CUST_001',
            'severity': 'INVALID_SEVERITY',
            'description': 'Routine check',
            'actor_id': 'ACTOR_001',
            'timestamp': datetime(2024, 1, 1, 10, 0, 0)
        }
        
        result = transformer._validate_record(invalid_record)
        assert result is False
    
    def test_validate_record_invalid_entity_type(self, transformer):
        """Test validation with invalid entity type."""
        invalid_record = {
            'event_id': 'COMP_001',
            'event_type': 'AML_CHECK',
            'affected_entity_type': 'INVALID_ENTITY',
            'affected_entity_id': 'CUST_001',
            'severity': 'INFO',
            'description': 'Routine check',
            'actor_id': 'ACTOR_001',
            'timestamp': datetime(2024, 1, 1, 10, 0, 0)
        }
        
        result = transformer._validate_record(invalid_record)
        assert result is False
    
    def test_validate_record_invalid_timestamp(self, transformer):
        """Test validation with invalid timestamp."""
        invalid_record = {
            'event_id': 'COMP_001',
            'event_type': 'AML_CHECK',
            'affected_entity_type': 'CUSTOMER',
            'affected_entity_id': 'CUST_001',
            'severity': 'INFO',
            'description': 'Routine check',
            'actor_id': 'ACTOR_001',
            'timestamp': 'invalid_timestamp'
        }
        
        result = transformer._validate_record(invalid_record)
        assert result is False
    
    def test_get_compliance_metrics(self, transformer, sample_compliance_events_data):
        """Test compliance metrics calculation."""
        with patch.object(transformer, 'extract', return_value=sample_compliance_events_data):
            metrics = transformer.get_compliance_metrics()
        
        assert metrics['total_events'] == 3
        assert metrics['violations'] == 2  # RULE_VIOLATION and SANCTION_HIT
        assert metrics['violation_rate'] == 66.67  # 2/3 * 100, rounded
        assert metrics['avg_resolution_time_hours'] == 0.54  # (0.08 + 1.0) / 2, rounded
        assert metrics['unresolved_events'] == 2  # IN_PROGRESS and OPEN
        
        # Check events by severity
        assert 'INFO' in metrics['events_by_severity']
        assert 'ERROR' in metrics['events_by_severity']
        assert 'CRITICAL' in metrics['events_by_severity']
        
        # Check events by type
        assert 'AML_CHECK' in metrics['events_by_type']
        assert 'RULE_VIOLATION' in metrics['events_by_type']
        assert 'SANCTION_HIT' in metrics['events_by_type']
    
    def test_get_compliance_metrics_no_data(self, transformer):
        """Test compliance metrics with no data."""
        with patch.object(transformer, 'extract', return_value=[]):
            metrics = transformer.get_compliance_metrics()
        
        assert metrics['total_events'] == 0
        assert metrics['violations'] == 0
        assert metrics['violation_rate'] == 0.0
        assert metrics['avg_resolution_time_hours'] == 0.0
        assert metrics['unresolved_events'] == 0
    
    def test_get_violation_trends(self, transformer):
        """Test violation trends calculation."""
        # Create sample violation data over multiple days
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        violation_events = []
        
        # Create violations for 10 days
        for day in range(10):
            for i in range(day + 1):  # Increasing trend
                event = {
                    'event_id': f'COMP_{day}_{i}',
                    'event_type': 'RULE_VIOLATION',
                    'severity': 'ERROR',
                    'description': 'Test violation',
                    'timestamp': base_time + timedelta(days=day, hours=i)
                }
                violation_events.append(event)
        
        with patch.object(transformer, 'extract', return_value=violation_events):
            with patch.object(transformer, '_is_violation_event', return_value=True):
                trends = transformer.get_violation_trends(days=10)
        
        assert 'daily_violations' in trends
        assert 'trend_direction' in trends
        assert trends['total_violations'] == len(violation_events)
        assert trends['analysis_days'] == 10
        
        # Should detect increasing trend
        assert trends['trend_direction'] == 'increasing'
    
    def test_get_violation_trends_no_data(self, transformer):
        """Test violation trends with no data."""
        with patch.object(transformer, 'extract', return_value=[]):
            trends = transformer.get_violation_trends()
        
        assert trends['daily_violations'] == {}
        assert trends['trend_direction'] == 'stable'
    
    def test_process_full_workflow(self, transformer, mock_db_manager):
        """Test complete ETL process workflow."""
        # Mock extraction
        mock_session = MagicMock()
        mock_db_manager.session_scope.return_value.__enter__.return_value = mock_session
        
        # Create minimal mock objects for one event
        mock_event = Mock(spec=ComplianceEventModel)
        mock_event.event_id = 'COMP_001'
        mock_event.event_type = 'AML_CHECK'
        mock_event.rule_id = 'RULE_001'
        mock_event.affected_entity_type = 'CUSTOMER'
        mock_event.affected_entity_id = 'CUST_001'
        mock_event.severity = 'INFO'
        mock_event.description = 'Routine check'
        mock_event.details = {}
        mock_event.is_alerted = False
        mock_event.resolution_status = 'RESOLVED'
        mock_event.resolution_notes = None
        mock_event.blockchain_transaction_id = 'TX_001'
        mock_event.timestamp = datetime(2024, 1, 1, 10, 0, 0)
        mock_event.acknowledged_at = None
        
        mock_actor = Mock(spec=ActorModel)
        mock_actor.actor_id = 'ACTOR_001'
        mock_actor.actor_name = 'System'
        mock_actor.role = 'SYSTEM'
        
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.outerjoin.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [(mock_event, mock_actor, None)]
        
        # Execute full process
        batch_result = transformer.process()
        
        # Verify batch result
        assert isinstance(batch_result, ETLBatch)
        assert batch_result.status == "SUCCESS"
        assert batch_result.records_processed == 1
        assert batch_result.records_inserted == 1
        assert batch_result.batch_id == "test_batch_123"
    
    @patch('etl.transformers.compliance_events_transformer.logger')
    def test_logging(self, mock_logger, transformer, sample_compliance_events_data):
        """Test that appropriate logging occurs."""
        transformer.transform(sample_compliance_events_data)
        
        # Verify info logging was called
        mock_logger.info.assert_called()
        
        # Test error logging with invalid data
        invalid_data = [{'invalid': 'data'}]
        transformer.transform(invalid_data)
        
        # Verify error logging was called
        mock_logger.error.assert_called()
    
    def test_json_details_parsing(self, transformer):
        """Test JSON details parsing in extraction."""
        # Test with string JSON details
        data = [{
            'event_id': 'COMP_001',
            'event_type': 'AML_CHECK',
            'affected_entity_type': 'CUSTOMER',
            'affected_entity_id': 'CUST_001',
            'severity': 'INFO',
            'description': 'Test',
            'details': '{"key": "value"}',
            'actor_id': 'ACTOR_001',
            'timestamp': datetime(2024, 1, 1, 10, 0, 0),
            'is_alerted': False,
            'resolution_status': 'RESOLVED'
        }]
        
        result = transformer.transform(data)
        assert len(result) == 1
        assert result[0].details == {"key": "value"}
    
    def test_batch_id_generation(self, mock_db_manager):
        """Test automatic batch ID generation."""
        transformer = ComplianceEventsTransformer(mock_db_manager)
        
        assert transformer.batch_id is not None
        assert "ComplianceEventsTransformer" in transformer.batch_id
        assert len(transformer.batch_id) > 20  # Should include timestamp and UUID