"""
Unit tests for Customer Transformer.

Tests the customer dimension transformer functionality including
data extraction, transformation, SCD Type 2 logic, and validation.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock, patch
import json

from etl.transformers.customer_transformer import CustomerTransformer
from etl.models import DimCustomer, ETLBatch
from shared.database import DatabaseManager, CustomerModel, ActorModel


class TestCustomerTransformer:
    """Test cases for CustomerTransformer."""
    
    @pytest.fixture
    def mock_db_manager(self):
        """Create mock database manager."""
        db_manager = Mock(spec=DatabaseManager)
        db_manager.session_scope = MagicMock()
        return db_manager
    
    @pytest.fixture
    def transformer(self, mock_db_manager):
        """Create CustomerTransformer instance."""
        return CustomerTransformer(mock_db_manager, batch_id="test_batch_123")
    
    @pytest.fixture
    def sample_customer_data(self):
        """Sample customer data for testing."""
        return [
            {
                'customer_id': 'CUST_001',
                'first_name': 'John',
                'last_name': 'Doe',
                'date_of_birth': datetime(1990, 1, 15),
                'national_id_hash': 'hash123',
                'address': '123 Main St',
                'contact_email': 'john.doe@example.com',
                'contact_phone': '+1234567890',
                'kyc_status': 'VERIFIED',
                'aml_status': 'CLEAR',
                'consent_preferences': {'marketing': True, 'analytics': False},
                'created_by_actor_id': 'ACTOR_001',
                'created_at': datetime(2024, 1, 1, 10, 0, 0),
                'updated_at': datetime(2024, 1, 1, 10, 0, 0)
            },
            {
                'customer_id': 'CUST_002',
                'first_name': 'Jane',
                'last_name': 'Smith',
                'date_of_birth': datetime(1985, 5, 20),
                'national_id_hash': 'hash456',
                'address': '456 Oak Ave',
                'contact_email': 'jane.smith@example.com',
                'contact_phone': '+1987654321',
                'kyc_status': 'PENDING',
                'aml_status': 'PENDING',
                'consent_preferences': None,
                'created_by_actor_id': 'ACTOR_002',
                'created_at': datetime(2024, 1, 2, 14, 30, 0),
                'updated_at': datetime(2024, 1, 2, 14, 30, 0)
            }
        ]
    
    def test_init(self, mock_db_manager):
        """Test transformer initialization."""
        transformer = CustomerTransformer(mock_db_manager, batch_id="test_batch")
        
        assert transformer.db_manager == mock_db_manager
        assert transformer.batch_id == "test_batch"
        assert transformer.table_name == "dim_customer"
        assert transformer.records_processed == 0
    
    def test_extract_success(self, transformer, mock_db_manager):
        """Test successful data extraction."""
        # Mock database session and query results
        mock_session = MagicMock()
        mock_db_manager.session_scope.return_value.__enter__.return_value = mock_session
        
        # Create mock customer and actor objects
        mock_customer = Mock(spec=CustomerModel)
        mock_customer.customer_id = 'CUST_001'
        mock_customer.first_name = 'John'
        mock_customer.last_name = 'Doe'
        mock_customer.date_of_birth = datetime(1990, 1, 15)
        mock_customer.national_id_hash = 'hash123'
        mock_customer.address = '123 Main St'
        mock_customer.contact_email = 'john.doe@example.com'
        mock_customer.contact_phone = '+1234567890'
        mock_customer.kyc_status = 'VERIFIED'
        mock_customer.aml_status = 'CLEAR'
        mock_customer.consent_preferences = {'marketing': True}
        mock_customer.created_at = datetime(2024, 1, 1, 10, 0, 0)
        mock_customer.updated_at = datetime(2024, 1, 1, 10, 0, 0)
        
        mock_actor = Mock(spec=ActorModel)
        mock_actor.actor_id = 'ACTOR_001'
        
        # Mock query chain
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [(mock_customer, mock_actor)]
        
        # Execute extraction
        result = transformer.extract()
        
        # Verify results
        assert len(result) == 1
        assert result[0]['customer_id'] == 'CUST_001'
        assert result[0]['first_name'] == 'John'
        assert result[0]['kyc_status'] == 'VERIFIED'
        assert result[0]['created_by_actor_id'] == 'ACTOR_001'
    
    def test_extract_incremental(self, transformer, mock_db_manager):
        """Test incremental data extraction."""
        mock_session = MagicMock()
        mock_db_manager.session_scope.return_value.__enter__.return_value = mock_session
        
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        
        since_date = datetime.now(timezone.utc) - timedelta(days=1)
        
        # Execute incremental extraction
        result = transformer.extract(incremental=True, since_date=since_date)
        
        # Verify filter was applied
        mock_query.filter.assert_called()
        assert result == []
    
    def test_transform_success(self, transformer, sample_customer_data):
        """Test successful data transformation."""
        result = transformer.transform(sample_customer_data)
        
        assert len(result) == 2
        
        # Check first record
        first_record = result[0]
        assert isinstance(first_record, DimCustomer)
        assert first_record.customer_id == 'CUST_001'
        assert first_record.first_name == 'John'
        assert first_record.last_name == 'Doe'
        assert first_record.kyc_status == 'VERIFIED'
        assert first_record.aml_status == 'CLEAR'
        assert first_record.is_current is True
        assert first_record.version == 1
        assert first_record.etl_batch_id == "test_batch_123"
        
        # Check second record
        second_record = result[1]
        assert second_record.customer_id == 'CUST_002'
        assert second_record.kyc_status == 'PENDING'
        assert second_record.consent_preferences is None
    
    def test_transform_with_json_consent(self, transformer):
        """Test transformation with JSON string consent preferences."""
        data = [{
            'customer_id': 'CUST_001',
            'first_name': 'John',
            'last_name': 'Doe',
            'kyc_status': 'VERIFIED',
            'aml_status': 'CLEAR',
            'consent_preferences': '{"marketing": true, "analytics": false}',
            'created_by_actor_id': 'ACTOR_001',
            'created_at': datetime(2024, 1, 1),
            'updated_at': datetime(2024, 1, 1)
        }]
        
        result = transformer.transform(data)
        
        assert len(result) == 1
        assert result[0].consent_preferences == {'marketing': True, 'analytics': False}
    
    def test_transform_invalid_json_consent(self, transformer):
        """Test transformation with invalid JSON consent preferences."""
        data = [{
            'customer_id': 'CUST_001',
            'first_name': 'John',
            'last_name': 'Doe',
            'kyc_status': 'VERIFIED',
            'aml_status': 'CLEAR',
            'consent_preferences': 'invalid_json',
            'created_by_actor_id': 'ACTOR_001',
            'created_at': datetime(2024, 1, 1),
            'updated_at': datetime(2024, 1, 1)
        }]
        
        result = transformer.transform(data)
        
        assert len(result) == 1
        assert result[0].consent_preferences is None
    
    def test_load_success(self, transformer, sample_customer_data):
        """Test successful data loading."""
        transformed_data = transformer.transform(sample_customer_data)
        
        result = transformer.load(transformed_data)
        
        assert result is True
        assert transformer.records_inserted == 2
    
    def test_validate_record_valid(self, transformer):
        """Test validation of valid customer record."""
        valid_record = {
            'customer_id': 'CUST_001',
            'first_name': 'John',
            'last_name': 'Doe',
            'kyc_status': 'VERIFIED',
            'aml_status': 'CLEAR'
        }
        
        result = transformer._validate_record(valid_record)
        assert result is True
    
    def test_validate_record_missing_required_field(self, transformer):
        """Test validation with missing required field."""
        invalid_record = {
            'customer_id': 'CUST_001',
            'first_name': 'John',
            # Missing last_name
            'kyc_status': 'VERIFIED',
            'aml_status': 'CLEAR'
        }
        
        result = transformer._validate_record(invalid_record)
        assert result is False
    
    def test_validate_record_invalid_kyc_status(self, transformer):
        """Test validation with invalid KYC status."""
        invalid_record = {
            'customer_id': 'CUST_001',
            'first_name': 'John',
            'last_name': 'Doe',
            'kyc_status': 'INVALID_STATUS',
            'aml_status': 'CLEAR'
        }
        
        result = transformer._validate_record(invalid_record)
        assert result is False
    
    def test_validate_record_invalid_aml_status(self, transformer):
        """Test validation with invalid AML status."""
        invalid_record = {
            'customer_id': 'CUST_001',
            'first_name': 'John',
            'last_name': 'Doe',
            'kyc_status': 'VERIFIED',
            'aml_status': 'INVALID_STATUS'
        }
        
        result = transformer._validate_record(invalid_record)
        assert result is False
    
    def test_generate_surrogate_key(self, transformer):
        """Test surrogate key generation."""
        key1 = transformer.generate_surrogate_key('CUST_001', 'dim_customer')
        key2 = transformer.generate_surrogate_key('CUST_002', 'dim_customer')
        key3 = transformer.generate_surrogate_key('CUST_001', 'dim_customer')
        
        # Keys should be integers
        assert isinstance(key1, int)
        assert isinstance(key2, int)
        
        # Same input should generate same key
        assert key1 == key3
        
        # Different inputs should generate different keys
        assert key1 != key2
    
    def test_convert_datetime_valid(self, transformer):
        """Test datetime conversion with valid inputs."""
        # Test datetime object
        dt = datetime(2024, 1, 1, 12, 0, 0)
        result = transformer.convert_datetime(dt)
        assert result == dt
        
        # Test string formats
        result = transformer.convert_datetime("2024-01-01 12:00:00")
        assert result == datetime(2024, 1, 1, 12, 0, 0)
        
        result = transformer.convert_datetime("2024-01-01")
        assert result == datetime(2024, 1, 1, 0, 0, 0)
    
    def test_convert_datetime_invalid(self, transformer):
        """Test datetime conversion with invalid inputs."""
        assert transformer.convert_datetime(None) is None
        assert transformer.convert_datetime("invalid_date") is None
        assert transformer.convert_datetime(123) is None
    
    def test_process_full_workflow(self, transformer, mock_db_manager, sample_customer_data):
        """Test complete ETL process workflow."""
        # Mock extraction
        mock_session = MagicMock()
        mock_db_manager.session_scope.return_value.__enter__.return_value = mock_session
        
        mock_customer = Mock(spec=CustomerModel)
        mock_customer.customer_id = 'CUST_001'
        mock_customer.first_name = 'John'
        mock_customer.last_name = 'Doe'
        mock_customer.date_of_birth = datetime(1990, 1, 15)
        mock_customer.national_id_hash = 'hash123'
        mock_customer.address = '123 Main St'
        mock_customer.contact_email = 'john.doe@example.com'
        mock_customer.contact_phone = '+1234567890'
        mock_customer.kyc_status = 'VERIFIED'
        mock_customer.aml_status = 'CLEAR'
        mock_customer.consent_preferences = {'marketing': True}
        mock_customer.created_at = datetime(2024, 1, 1, 10, 0, 0)
        mock_customer.updated_at = datetime(2024, 1, 1, 10, 0, 0)
        
        mock_actor = Mock(spec=ActorModel)
        mock_actor.actor_id = 'ACTOR_001'
        
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = [(mock_customer, mock_actor)]
        
        # Execute full process
        batch_result = transformer.process()
        
        # Verify batch result
        assert isinstance(batch_result, ETLBatch)
        assert batch_result.status == "SUCCESS"
        assert batch_result.records_processed == 1
        assert batch_result.records_inserted == 1
        assert batch_result.batch_id == "test_batch_123"
    
    def test_process_no_data(self, transformer, mock_db_manager):
        """Test process with no data to extract."""
        # Mock empty extraction
        mock_session = MagicMock()
        mock_db_manager.session_scope.return_value.__enter__.return_value = mock_session
        
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = []
        
        # Execute process
        batch_result = transformer.process()
        
        # Verify batch result
        assert batch_result.status == "SUCCESS"
        assert batch_result.records_processed == 0
        assert batch_result.records_inserted == 0
    
    def test_process_extraction_error(self, transformer, mock_db_manager):
        """Test process with extraction error."""
        # Mock extraction error
        mock_db_manager.session_scope.side_effect = Exception("Database error")
        
        # Execute process
        batch_result = transformer.process()
        
        # Verify batch result
        assert batch_result.status == "FAILED"
        assert len(transformer.errors) > 0
        assert "Database error" in transformer.errors[0]
    
    @patch('etl.transformers.customer_transformer.logger')
    def test_logging(self, mock_logger, transformer, sample_customer_data):
        """Test that appropriate logging occurs."""
        transformer.transform(sample_customer_data)
        
        # Verify info logging was called
        mock_logger.info.assert_called()
        
        # Test error logging with invalid data
        invalid_data = [{'invalid': 'data'}]
        transformer.transform(invalid_data)
        
        # Verify error logging was called
        mock_logger.error.assert_called()
    
    def test_scd_type2_new_record(self, transformer):
        """Test SCD Type 2 logic with new record."""
        existing_records = []
        new_records = transformer.transform([{
            'customer_id': 'CUST_001',
            'first_name': 'John',
            'last_name': 'Doe',
            'kyc_status': 'VERIFIED',
            'aml_status': 'CLEAR',
            'created_by_actor_id': 'ACTOR_001',
            'created_at': datetime(2024, 1, 1),
            'updated_at': datetime(2024, 1, 1)
        }])
        
        compare_fields = ['first_name', 'last_name', 'kyc_status', 'aml_status']
        
        result = transformer.implement_scd_type2(
            existing_records=existing_records,
            new_records=new_records,
            business_key_field='customer_id',
            compare_fields=compare_fields
        )
        
        assert len(result) == 1
        assert result[0].is_current is True
        assert result[0].version == 1
        assert transformer.records_inserted == 1
    
    def test_batch_id_generation(self, mock_db_manager):
        """Test automatic batch ID generation."""
        transformer = CustomerTransformer(mock_db_manager)
        
        assert transformer.batch_id is not None
        assert "CustomerTransformer" in transformer.batch_id
        assert len(transformer.batch_id) > 20  # Should include timestamp and UUID