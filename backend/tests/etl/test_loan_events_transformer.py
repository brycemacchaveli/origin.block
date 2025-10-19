"""
Unit tests for Loan Events Transformer.

Tests the loan application events fact transformer functionality including
data extraction, transformation, processing duration calculations, and validation.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock, patch

from etl.transformers.loan_events_transformer import LoanEventsTransformer
from etl.models import FactLoanApplicationEvents, ETLBatch
from shared.database import (
    DatabaseManager, 
    LoanApplicationModel, 
    LoanApplicationHistoryModel,
    CustomerModel,
    ActorModel
)


class TestLoanEventsTransformer:
    """Test cases for LoanEventsTransformer."""
    
    @pytest.fixture
    def mock_db_manager(self):
        """Create mock database manager."""
        db_manager = Mock(spec=DatabaseManager)
        db_manager.session_scope = MagicMock()
        return db_manager
    
    @pytest.fixture
    def transformer(self, mock_db_manager):
        """Create LoanEventsTransformer instance."""
        return LoanEventsTransformer(mock_db_manager, batch_id="test_batch_123")
    
    @pytest.fixture
    def sample_loan_events_data(self):
        """Sample loan events data for testing."""
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        return [
            {
                'history_id': 1,
                'loan_application_id': 'LOAN_001',
                'customer_id': 'CUST_001',
                'actor_id': 'ACTOR_001',
                'change_type': 'STATUS_CHANGE',
                'previous_status': None,
                'new_status': 'SUBMITTED',
                'field_name': 'application_status',
                'old_value': None,
                'new_value': 'SUBMITTED',
                'blockchain_transaction_id': 'TX_001',
                'timestamp': base_time,
                'notes': 'Initial submission',
                'requested_amount': 50000.0,
                'approval_amount': None,
                'loan_type': 'PERSONAL',
                'application_date': base_time,
                'current_status': 'SUBMITTED',
                'customer_name': 'John Doe',
                'actor_name': 'Loan Officer',
                'actor_role': 'UNDERWRITER'
            },
            {
                'history_id': 2,
                'loan_application_id': 'LOAN_001',
                'customer_id': 'CUST_001',
                'actor_id': 'ACTOR_002',
                'change_type': 'STATUS_CHANGE',
                'previous_status': 'SUBMITTED',
                'new_status': 'UNDERWRITING',
                'field_name': 'application_status',
                'old_value': 'SUBMITTED',
                'new_value': 'UNDERWRITING',
                'blockchain_transaction_id': 'TX_002',
                'timestamp': base_time + timedelta(hours=2),
                'notes': 'Moved to underwriting',
                'requested_amount': 50000.0,
                'approval_amount': None,
                'loan_type': 'PERSONAL',
                'application_date': base_time,
                'current_status': 'UNDERWRITING',
                'customer_name': 'John Doe',
                'actor_name': 'Senior Underwriter',
                'actor_role': 'SENIOR_UNDERWRITER'
            },
            {
                'history_id': 3,
                'loan_application_id': 'LOAN_001',
                'customer_id': 'CUST_001',
                'actor_id': 'ACTOR_003',
                'change_type': 'STATUS_CHANGE',
                'previous_status': 'UNDERWRITING',
                'new_status': 'APPROVED',
                'field_name': 'application_status',
                'old_value': 'UNDERWRITING',
                'new_value': 'APPROVED',
                'blockchain_transaction_id': 'TX_003',
                'timestamp': base_time + timedelta(hours=24),
                'notes': 'Approved for 45000',
                'requested_amount': 50000.0,
                'approval_amount': 45000.0,
                'loan_type': 'PERSONAL',
                'application_date': base_time,
                'current_status': 'APPROVED',
                'customer_name': 'John Doe',
                'actor_name': 'Credit Manager',
                'actor_role': 'CREDIT_MANAGER'
            }
        ]
    
    def test_init(self, mock_db_manager):
        """Test transformer initialization."""
        transformer = LoanEventsTransformer(mock_db_manager, batch_id="test_batch")
        
        assert transformer.db_manager == mock_db_manager
        assert transformer.batch_id == "test_batch"
        assert transformer.table_name == "fact_loan_application_events"
        assert transformer.records_processed == 0
    
    def test_extract_success(self, transformer, mock_db_manager):
        """Test successful data extraction."""
        # Mock database session and query results
        mock_session = MagicMock()
        mock_db_manager.session_scope.return_value.__enter__.return_value = mock_session
        
        # Create mock objects
        mock_history = Mock(spec=LoanApplicationHistoryModel)
        mock_history.id = 1
        mock_history.change_type = 'STATUS_CHANGE'
        mock_history.previous_status = None
        mock_history.new_status = 'SUBMITTED'
        mock_history.field_name = 'application_status'
        mock_history.old_value = None
        mock_history.new_value = 'SUBMITTED'
        mock_history.blockchain_transaction_id = 'TX_001'
        mock_history.timestamp = datetime(2024, 1, 1, 10, 0, 0)
        mock_history.notes = 'Initial submission'
        
        mock_loan = Mock(spec=LoanApplicationModel)
        mock_loan.loan_application_id = 'LOAN_001'
        mock_loan.requested_amount = 50000.0
        mock_loan.approval_amount = None
        mock_loan.loan_type = 'PERSONAL'
        mock_loan.application_date = datetime(2024, 1, 1, 10, 0, 0)
        mock_loan.application_status = 'SUBMITTED'
        
        mock_customer = Mock(spec=CustomerModel)
        mock_customer.customer_id = 'CUST_001'
        mock_customer.first_name = 'John'
        mock_customer.last_name = 'Doe'
        
        mock_actor = Mock(spec=ActorModel)
        mock_actor.actor_id = 'ACTOR_001'
        mock_actor.actor_name = 'Loan Officer'
        mock_actor.role = 'UNDERWRITER'
        
        # Mock query chain
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [(mock_history, mock_loan, mock_customer, mock_actor)]
        
        # Execute extraction
        result = transformer.extract()
        
        # Verify results
        assert len(result) == 1
        assert result[0]['loan_application_id'] == 'LOAN_001'
        assert result[0]['customer_id'] == 'CUST_001'
        assert result[0]['actor_id'] == 'ACTOR_001'
        assert result[0]['change_type'] == 'STATUS_CHANGE'
        assert result[0]['requested_amount'] == 50000.0
    
    def test_transform_success(self, transformer, sample_loan_events_data):
        """Test successful data transformation."""
        result = transformer.transform(sample_loan_events_data)
        
        assert len(result) == 3
        
        # Check first record (submission)
        first_record = result[0]
        assert isinstance(first_record, FactLoanApplicationEvents)
        assert first_record.loan_application_id == 'LOAN_001'
        assert first_record.customer_id == 'CUST_001'
        assert first_record.actor_id == 'ACTOR_001'
        assert first_record.event_type == 'APPLICATION_SUBMITTED'
        assert first_record.new_status == 'SUBMITTED'
        assert first_record.requested_amount == 50000.0
        assert first_record.processing_duration_hours is None  # First event has no duration
        assert first_record.etl_batch_id == "test_batch_123"
        
        # Check second record (underwriting)
        second_record = result[1]
        assert second_record.event_type == 'UNDERWRITING_START'
        assert second_record.previous_status == 'SUBMITTED'
        assert second_record.new_status == 'UNDERWRITING'
        assert second_record.processing_duration_hours == 2.0  # 2 hours from first event
        
        # Check third record (approval)
        third_record = result[2]
        assert third_record.event_type == 'APPROVAL'
        assert third_record.previous_status == 'UNDERWRITING'
        assert third_record.new_status == 'APPROVED'
        assert third_record.approval_amount == 45000.0
        assert third_record.processing_duration_hours == 22.0  # 22 hours from second event
    
    def test_calculate_processing_durations(self, transformer, sample_loan_events_data):
        """Test processing duration calculations."""
        enriched_data = transformer._calculate_processing_durations(sample_loan_events_data)
        
        assert len(enriched_data) == 3
        
        # First event should have no duration
        assert enriched_data[0]['processing_duration_hours'] is None
        
        # Second event should have 2 hours duration
        assert enriched_data[1]['processing_duration_hours'] == 2.0
        
        # Third event should have 22 hours duration
        assert enriched_data[2]['processing_duration_hours'] == 22.0
    
    def test_determine_event_type(self, transformer):
        """Test event type determination logic."""
        # Test status change to approved
        record = {'change_type': 'STATUS_CHANGE', 'new_status': 'APPROVED'}
        assert transformer._determine_event_type(record) == 'APPROVAL'
        
        # Test status change to rejected
        record = {'change_type': 'STATUS_CHANGE', 'new_status': 'REJECTED'}
        assert transformer._determine_event_type(record) == 'REJECTION'
        
        # Test status change to underwriting
        record = {'change_type': 'STATUS_CHANGE', 'new_status': 'UNDERWRITING'}
        assert transformer._determine_event_type(record) == 'UNDERWRITING_START'
        
        # Test status change to submitted
        record = {'change_type': 'STATUS_CHANGE', 'new_status': 'SUBMITTED'}
        assert transformer._determine_event_type(record) == 'APPLICATION_SUBMITTED'
        
        # Test direct approval
        record = {'change_type': 'APPROVAL', 'new_status': 'APPROVED'}
        assert transformer._determine_event_type(record) == 'APPROVAL'
        
        # Test data update
        record = {'change_type': 'UPDATE', 'new_status': 'SUBMITTED'}
        assert transformer._determine_event_type(record) == 'DATA_UPDATE'
        
        # Test unknown type
        record = {'change_type': 'UNKNOWN_TYPE', 'new_status': 'SOME_STATUS'}
        assert transformer._determine_event_type(record) == 'UNKNOWN_TYPE'
    
    def test_load_success(self, transformer, sample_loan_events_data):
        """Test successful data loading."""
        transformed_data = transformer.transform(sample_loan_events_data)
        
        result = transformer.load(transformed_data)
        
        assert result is True
        assert transformer.records_inserted == 3
    
    def test_validate_record_valid(self, transformer):
        """Test validation of valid loan event record."""
        valid_record = {
            'loan_application_id': 'LOAN_001',
            'customer_id': 'CUST_001',
            'actor_id': 'ACTOR_001',
            'change_type': 'STATUS_CHANGE',
            'timestamp': datetime(2024, 1, 1, 10, 0, 0),
            'requested_amount': 50000.0
        }
        
        result = transformer._validate_record(valid_record)
        assert result is True
    
    def test_validate_record_missing_required_field(self, transformer):
        """Test validation with missing required field."""
        invalid_record = {
            'loan_application_id': 'LOAN_001',
            'customer_id': 'CUST_001',
            # Missing actor_id
            'change_type': 'STATUS_CHANGE',
            'timestamp': datetime(2024, 1, 1, 10, 0, 0),
            'requested_amount': 50000.0
        }
        
        result = transformer._validate_record(invalid_record)
        assert result is False
    
    def test_validate_record_invalid_timestamp(self, transformer):
        """Test validation with invalid timestamp."""
        invalid_record = {
            'loan_application_id': 'LOAN_001',
            'customer_id': 'CUST_001',
            'actor_id': 'ACTOR_001',
            'change_type': 'STATUS_CHANGE',
            'timestamp': 'invalid_timestamp',
            'requested_amount': 50000.0
        }
        
        result = transformer._validate_record(invalid_record)
        assert result is False
    
    def test_validate_record_invalid_amount(self, transformer):
        """Test validation with invalid requested amount."""
        invalid_record = {
            'loan_application_id': 'LOAN_001',
            'customer_id': 'CUST_001',
            'actor_id': 'ACTOR_001',
            'change_type': 'STATUS_CHANGE',
            'timestamp': datetime(2024, 1, 1, 10, 0, 0),
            'requested_amount': -1000.0  # Negative amount
        }
        
        result = transformer._validate_record(invalid_record)
        assert result is False
        
        # Test non-numeric amount
        invalid_record['requested_amount'] = 'not_a_number'
        result = transformer._validate_record(invalid_record)
        assert result is False
    
    def test_get_processing_metrics(self, transformer, mock_db_manager, sample_loan_events_data):
        """Test processing metrics calculation."""
        # Mock extraction to return sample data
        with patch.object(transformer, 'extract', return_value=sample_loan_events_data):
            metrics = transformer.get_processing_metrics('LOAN_001')
        
        assert metrics['total_events'] == 3
        assert metrics['status_changes'] == 3
        assert metrics['total_processing_time_hours'] == 24.0  # 24 hours total
        assert metrics['average_stage_duration_hours'] == 12.0  # (2 + 22) / 2
        assert len(metrics['stages']) == 2
        
        # Check stage details
        first_stage = metrics['stages'][0]
        assert first_stage['from_status'] == 'SUBMITTED'
        assert first_stage['to_status'] == 'UNDERWRITING'
        assert first_stage['duration_hours'] == 2.0
        
        second_stage = metrics['stages'][1]
        assert second_stage['from_status'] == 'UNDERWRITING'
        assert second_stage['to_status'] == 'APPROVED'
        assert second_stage['duration_hours'] == 22.0
    
    def test_get_processing_metrics_no_data(self, transformer):
        """Test processing metrics with no data."""
        with patch.object(transformer, 'extract', return_value=[]):
            metrics = transformer.get_processing_metrics('NONEXISTENT_LOAN')
        
        assert metrics == {}
    
    def test_convert_to_date_key(self, transformer):
        """Test date key conversion."""
        test_date = datetime(2024, 1, 15, 14, 30, 0)
        date_key = transformer.convert_to_date_key(test_date)
        
        assert date_key == 20240115
        
        # Test with None
        date_key = transformer.convert_to_date_key(None)
        assert date_key == 19000101  # Default date key
    
    def test_generate_surrogate_key(self, transformer):
        """Test surrogate key generation."""
        key1 = transformer.generate_surrogate_key('LOAN_001', 'dim_loan_application')
        key2 = transformer.generate_surrogate_key('LOAN_002', 'dim_loan_application')
        key3 = transformer.generate_surrogate_key('LOAN_001', 'dim_loan_application')
        
        # Keys should be integers
        assert isinstance(key1, int)
        assert isinstance(key2, int)
        
        # Same input should generate same key
        assert key1 == key3
        
        # Different inputs should generate different keys
        assert key1 != key2
    
    def test_process_full_workflow(self, transformer, mock_db_manager, sample_loan_events_data):
        """Test complete ETL process workflow."""
        # Mock extraction
        mock_session = MagicMock()
        mock_db_manager.session_scope.return_value.__enter__.return_value = mock_session
        
        # Create minimal mock objects for one event
        mock_history = Mock(spec=LoanApplicationHistoryModel)
        mock_history.id = 1
        mock_history.change_type = 'STATUS_CHANGE'
        mock_history.previous_status = None
        mock_history.new_status = 'SUBMITTED'
        mock_history.field_name = 'application_status'
        mock_history.old_value = None
        mock_history.new_value = 'SUBMITTED'
        mock_history.blockchain_transaction_id = 'TX_001'
        mock_history.timestamp = datetime(2024, 1, 1, 10, 0, 0)
        mock_history.notes = 'Initial submission'
        
        mock_loan = Mock(spec=LoanApplicationModel)
        mock_loan.loan_application_id = 'LOAN_001'
        mock_loan.requested_amount = 50000.0
        mock_loan.approval_amount = None
        mock_loan.loan_type = 'PERSONAL'
        mock_loan.application_date = datetime(2024, 1, 1, 10, 0, 0)
        mock_loan.application_status = 'SUBMITTED'
        
        mock_customer = Mock(spec=CustomerModel)
        mock_customer.customer_id = 'CUST_001'
        mock_customer.first_name = 'John'
        mock_customer.last_name = 'Doe'
        
        mock_actor = Mock(spec=ActorModel)
        mock_actor.actor_id = 'ACTOR_001'
        mock_actor.actor_name = 'Loan Officer'
        mock_actor.role = 'UNDERWRITER'
        
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [(mock_history, mock_loan, mock_customer, mock_actor)]
        
        # Execute full process
        batch_result = transformer.process()
        
        # Verify batch result
        assert isinstance(batch_result, ETLBatch)
        assert batch_result.status == "SUCCESS"
        assert batch_result.records_processed == 1
        assert batch_result.records_inserted == 1
        assert batch_result.batch_id == "test_batch_123"
    
    @patch('etl.transformers.loan_events_transformer.logger')
    def test_logging(self, mock_logger, transformer, sample_loan_events_data):
        """Test that appropriate logging occurs."""
        transformer.transform(sample_loan_events_data)
        
        # Verify info logging was called
        mock_logger.info.assert_called()
        
        # Test error logging with invalid data
        invalid_data = [{'invalid': 'data'}]
        transformer.transform(invalid_data)
        
        # Verify error logging was called
        mock_logger.error.assert_called()
    
    def test_multiple_loans_processing_duration(self, transformer):
        """Test processing duration calculation with multiple loans."""
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        
        # Events for two different loans
        events = [
            {
                'loan_application_id': 'LOAN_001',
                'change_type': 'STATUS_CHANGE',
                'timestamp': base_time,
                'new_status': 'SUBMITTED'
            },
            {
                'loan_application_id': 'LOAN_002',
                'change_type': 'STATUS_CHANGE',
                'timestamp': base_time + timedelta(hours=1),
                'new_status': 'SUBMITTED'
            },
            {
                'loan_application_id': 'LOAN_001',
                'change_type': 'STATUS_CHANGE',
                'timestamp': base_time + timedelta(hours=3),
                'new_status': 'APPROVED'
            },
            {
                'loan_application_id': 'LOAN_002',
                'change_type': 'STATUS_CHANGE',
                'timestamp': base_time + timedelta(hours=5),
                'new_status': 'REJECTED'
            }
        ]
        
        enriched_data = transformer._calculate_processing_durations(events)
        
        # Check that durations are calculated correctly for each loan
        loan_001_events = [e for e in enriched_data if e['loan_application_id'] == 'LOAN_001']
        loan_002_events = [e for e in enriched_data if e['loan_application_id'] == 'LOAN_002']
        
        # First events should have no duration
        assert loan_001_events[0]['processing_duration_hours'] is None
        assert loan_002_events[0]['processing_duration_hours'] is None
        
        # Second events should have correct durations
        assert loan_001_events[1]['processing_duration_hours'] == 3.0  # 3 hours
        assert loan_002_events[1]['processing_duration_hours'] == 4.0  # 4 hours
    
    def test_batch_id_generation(self, mock_db_manager):
        """Test automatic batch ID generation."""
        transformer = LoanEventsTransformer(mock_db_manager)
        
        assert transformer.batch_id is not None
        assert "LoanEventsTransformer" in transformer.batch_id
        assert len(transformer.batch_id) > 20  # Should include timestamp and UUID