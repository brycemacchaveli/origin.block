"""
Unit tests for Base Transformer.

Tests the base transformer functionality including SCD Type 2 logic,
batch tracking, validation, and common utility methods.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
from dataclasses import dataclass
from typing import List, Dict, Any

import pandas as pd

from etl.transformers.base_transformer import BaseTransformer
from etl.models import ETLBatch, SCDType


@dataclass
class TestDimension:
    """Test dimension class for SCD testing."""
    key: int
    business_key: str
    name: str
    value: str
    effective_date: datetime
    expiration_date: datetime = None
    is_current: bool = True
    version: int = 1


class ConcreteTransformer(BaseTransformer[TestDimension]):
    """Concrete implementation of BaseTransformer for testing."""
    
    def __init__(self, batch_id: str = None):
        super().__init__(batch_id)
        self.extracted_data = []
        self.should_fail_extract = False
        self.should_fail_transform = False
        self.should_fail_load = False
    
    def extract(self, **kwargs) -> List[Dict[str, Any]]:
        """Mock extract method."""
        if self.should_fail_extract:
            raise Exception("Extract failed")
        return self.extracted_data
    
    def transform(self, source_data: List[Dict[str, Any]]) -> List[TestDimension]:
        """Mock transform method."""
        if self.should_fail_transform:
            raise Exception("Transform failed")
        
        transformed = []
        for i, record in enumerate(source_data):
            dim = TestDimension(
                key=i + 1,
                business_key=record['business_key'],
                name=record['name'],
                value=record['value'],
                effective_date=datetime.now(timezone.utc),
                is_current=True,
                version=1
            )
            transformed.append(dim)
        return transformed
    
    def load(self, transformed_data: List[TestDimension]) -> bool:
        """Mock load method."""
        if self.should_fail_load:
            return False
        self.records_inserted = len(transformed_data)
        return True
    
    def _create_new_scd_record(
        self, 
        data_row: pd.Series, 
        effective_date: datetime,
        version: int = 1
    ) -> TestDimension:
        """Create new SCD Type 2 record."""
        return TestDimension(
            key=self.generate_surrogate_key(data_row['business_key'], 'test_table'),
            business_key=data_row['business_key'],
            name=data_row['name'],
            value=data_row['value'],
            effective_date=effective_date,
            is_current=True,
            version=version
        )
    
    def _expire_scd_record(
        self, 
        existing_row: pd.Series, 
        expiration_date: datetime
    ) -> TestDimension:
        """Expire existing SCD Type 2 record."""
        return TestDimension(
            key=existing_row['key'],
            business_key=existing_row['business_key'],
            name=existing_row['name'],
            value=existing_row['value'],
            effective_date=existing_row['effective_date'],
            expiration_date=expiration_date,
            is_current=False,
            version=existing_row['version']
        )


class TestBaseTransformer:
    """Test cases for BaseTransformer."""
    
    @pytest.fixture
    def transformer(self):
        """Create ConcreteTransformer instance."""
        return ConcreteTransformer(batch_id="test_batch_123")
    
    @pytest.fixture
    def sample_data(self):
        """Sample data for testing."""
        return [
            {'business_key': 'KEY_001', 'name': 'Record 1', 'value': 'Value 1'},
            {'business_key': 'KEY_002', 'name': 'Record 2', 'value': 'Value 2'},
            {'business_key': 'KEY_003', 'name': 'Record 3', 'value': 'Value 3'}
        ]
    
    def test_init_with_batch_id(self):
        """Test initialization with provided batch ID."""
        transformer = ConcreteTransformer(batch_id="custom_batch")
        
        assert transformer.batch_id == "custom_batch"
        assert transformer.records_processed == 0
        assert transformer.records_inserted == 0
        assert transformer.records_updated == 0
        assert transformer.records_failed == 0
        assert transformer.errors == []
    
    def test_init_without_batch_id(self):
        """Test initialization with auto-generated batch ID."""
        transformer = ConcreteTransformer()
        
        assert transformer.batch_id is not None
        assert "ConcreteTransformer" in transformer.batch_id
        assert len(transformer.batch_id) > 20  # Should include timestamp and UUID
    
    def test_generate_batch_id(self, transformer):
        """Test batch ID generation."""
        batch_id = transformer._generate_batch_id()
        
        assert "ConcreteTransformer" in batch_id
        assert len(batch_id.split('_')) == 3  # class_timestamp_uuid
    
    def test_process_success(self, transformer, sample_data):
        """Test successful ETL process."""
        transformer.extracted_data = sample_data
        
        batch_result = transformer.process()
        
        assert isinstance(batch_result, ETLBatch)
        assert batch_result.status == "SUCCESS"
        assert batch_result.records_processed == 3
        assert batch_result.records_inserted == 3
        assert batch_result.records_failed == 0
        assert batch_result.batch_id == "test_batch_123"
        assert batch_result.error_message is None
    
    def test_process_no_data(self, transformer):
        """Test process with no data."""
        transformer.extracted_data = []
        
        batch_result = transformer.process()
        
        assert batch_result.status == "SUCCESS"
        assert batch_result.records_processed == 0
        assert batch_result.records_inserted == 0
    
    def test_process_extract_failure(self, transformer):
        """Test process with extraction failure."""
        transformer.should_fail_extract = True
        
        batch_result = transformer.process()
        
        assert batch_result.status == "FAILED"
        assert len(transformer.errors) > 0
        assert "Extract failed" in transformer.errors[0]
    
    def test_process_transform_failure(self, transformer, sample_data):
        """Test process with transformation failure."""
        transformer.extracted_data = sample_data
        transformer.should_fail_transform = True
        
        batch_result = transformer.process()
        
        assert batch_result.status == "FAILED"
        assert len(transformer.errors) > 0
        assert "Transform failed" in transformer.errors[0]
    
    def test_process_load_failure(self, transformer, sample_data):
        """Test process with load failure."""
        transformer.extracted_data = sample_data
        transformer.should_fail_load = True
        
        batch_result = transformer.process()
        
        assert batch_result.status == "FAILED"
    
    def test_create_batch_summary(self, transformer):
        """Test batch summary creation."""
        transformer.records_processed = 10
        transformer.records_inserted = 8
        transformer.records_updated = 2
        transformer.records_failed = 0
        
        summary = transformer._create_batch_summary("SUCCESS")
        
        assert isinstance(summary, ETLBatch)
        assert summary.status == "SUCCESS"
        assert summary.records_processed == 10
        assert summary.records_inserted == 8
        assert summary.records_updated == 2
        assert summary.records_failed == 0
        assert summary.batch_id == "test_batch_123"
    
    def test_create_batch_summary_with_errors(self, transformer):
        """Test batch summary creation with errors."""
        transformer.errors = ["Error 1", "Error 2"]
        
        summary = transformer._create_batch_summary("FAILED")
        
        assert summary.status == "FAILED"
        assert summary.error_message == "Error 1; Error 2"
    
    def test_validate_data_all_valid(self, transformer, sample_data):
        """Test data validation with all valid records."""
        valid_records = transformer.validate_data(sample_data)
        
        assert len(valid_records) == 3
        assert transformer.records_failed == 0
    
    def test_validate_data_with_invalid_records(self, transformer):
        """Test data validation with invalid records."""
        # Override validation to reject records with 'invalid' in name
        def mock_validate_record(record):
            return 'invalid' not in record.get('name', '').lower()
        
        transformer._validate_record = mock_validate_record
        
        data = [
            {'business_key': 'KEY_001', 'name': 'Valid Record', 'value': 'Value 1'},
            {'business_key': 'KEY_002', 'name': 'Invalid Record', 'value': 'Value 2'},
            {'business_key': 'KEY_003', 'name': 'Another Valid', 'value': 'Value 3'}
        ]
        
        valid_records = transformer.validate_data(data)
        
        assert len(valid_records) == 2
        assert transformer.records_failed == 1
        assert len(transformer.errors) == 1
    
    def test_validate_record_default(self, transformer):
        """Test default record validation (always returns True)."""
        record = {'any': 'data'}
        result = transformer._validate_record(record)
        assert result is True
    
    def test_generate_surrogate_key(self, transformer):
        """Test surrogate key generation."""
        key1 = transformer.generate_surrogate_key('BUSINESS_001', 'table1')
        key2 = transformer.generate_surrogate_key('BUSINESS_002', 'table1')
        key3 = transformer.generate_surrogate_key('BUSINESS_001', 'table1')
        key4 = transformer.generate_surrogate_key('BUSINESS_001', 'table2')
        
        # Keys should be integers
        assert isinstance(key1, int)
        assert isinstance(key2, int)
        
        # Same business key and table should generate same key
        assert key1 == key3
        
        # Different business keys should generate different keys
        assert key1 != key2
        
        # Same business key but different table should generate different keys
        assert key1 != key4
        
        # Keys should be within reasonable range
        assert 0 < key1 < 10**9
    
    def test_convert_to_date_key(self, transformer):
        """Test date key conversion."""
        # Test with datetime
        test_date = datetime(2024, 3, 15, 14, 30, 0)
        date_key = transformer.convert_to_date_key(test_date)
        assert date_key == 20240315
        
        # Test with None
        date_key = transformer.convert_to_date_key(None)
        assert date_key == 19000101  # Default date key
    
    def test_safe_get(self, transformer):
        """Test safe dictionary access."""
        data = {'key1': 'value1', 'key2': None}
        
        # Test existing key
        assert transformer.safe_get(data, 'key1') == 'value1'
        
        # Test existing key with None value
        assert transformer.safe_get(data, 'key2') is None
        
        # Test missing key with default
        assert transformer.safe_get(data, 'missing', 'default') == 'default'
        
        # Test missing key without default
        assert transformer.safe_get(data, 'missing') is None
    
    def test_convert_datetime_valid_inputs(self, transformer):
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
        
        result = transformer.convert_datetime("2024-01-01T12:00:00")
        assert result == datetime(2024, 1, 1, 12, 0, 0)
    
    def test_convert_datetime_invalid_inputs(self, transformer):
        """Test datetime conversion with invalid inputs."""
        assert transformer.convert_datetime(None) is None
        assert transformer.convert_datetime("invalid_date") is None
        assert transformer.convert_datetime(123) is None
        assert transformer.convert_datetime("") is None
    
    def test_implement_scd_type2_new_records(self, transformer):
        """Test SCD Type 2 with new records only."""
        existing_records = []
        new_records = [
            TestDimension(1, 'KEY_001', 'Record 1', 'Value 1', datetime.now(timezone.utc)),
            TestDimension(2, 'KEY_002', 'Record 2', 'Value 2', datetime.now(timezone.utc))
        ]
        
        result = transformer.implement_scd_type2(
            existing_records=existing_records,
            new_records=new_records,
            business_key_field='business_key',
            compare_fields=['name', 'value']
        )
        
        assert len(result) == 2
        assert transformer.records_inserted == 2
        assert transformer.records_updated == 0
    
    def test_implement_scd_type2_changed_records(self, transformer):
        """Test SCD Type 2 with changed records."""
        base_time = datetime.now(timezone.utc)
        
        existing_records = [
            TestDimension(1, 'KEY_001', 'Record 1', 'Old Value', base_time - timedelta(days=1), 
                         is_current=True, version=1)
        ]
        
        new_records = [
            TestDimension(1, 'KEY_001', 'Record 1', 'New Value', base_time, 
                         is_current=True, version=1)
        ]
        
        result = transformer.implement_scd_type2(
            existing_records=existing_records,
            new_records=new_records,
            business_key_field='business_key',
            compare_fields=['name', 'value']
        )
        
        # Should have 2 records: expired old + new current
        assert len(result) == 2
        assert transformer.records_updated == 1
        
        # Find expired and new records
        expired_record = next(r for r in result if not r.is_current)
        new_record = next(r for r in result if r.is_current)
        
        assert expired_record.expiration_date is not None
        assert new_record.version == 2
    
    def test_implement_scd_type2_unchanged_records(self, transformer):
        """Test SCD Type 2 with unchanged records."""
        base_time = datetime.now(timezone.utc)
        
        existing_records = [
            TestDimension(1, 'KEY_001', 'Record 1', 'Same Value', base_time - timedelta(days=1), 
                         is_current=True, version=1)
        ]
        
        new_records = [
            TestDimension(1, 'KEY_001', 'Record 1', 'Same Value', base_time, 
                         is_current=True, version=1)
        ]
        
        result = transformer.implement_scd_type2(
            existing_records=existing_records,
            new_records=new_records,
            business_key_field='business_key',
            compare_fields=['name', 'value']
        )
        
        # No changes, so no new records
        assert len(result) == 0
        assert transformer.records_updated == 0
    
    def test_has_data_changed(self, transformer):
        """Test data change detection."""
        existing_row = pd.Series({
            'name': 'Record 1',
            'value': 'Old Value',
            'other': 'Same'
        })
        
        # Test with changes
        new_row_changed = pd.Series({
            'name': 'Record 1',
            'value': 'New Value',
            'other': 'Same'
        })
        
        result = transformer._has_data_changed(
            existing_row, new_row_changed, ['name', 'value']
        )
        assert result is True
        
        # Test without changes
        new_row_same = pd.Series({
            'name': 'Record 1',
            'value': 'Old Value',
            'other': 'Different'  # This field is not compared
        })
        
        result = transformer._has_data_changed(
            existing_row, new_row_same, ['name', 'value']
        )
        assert result is False
    
    @patch('etl.transformers.base_transformer.logger')
    def test_logging_on_process(self, mock_logger, transformer, sample_data):
        """Test that logging occurs during process execution."""
        transformer.extracted_data = sample_data
        
        transformer.process()
        
        # Verify logging was called
        mock_logger.info.assert_called()
    
    def test_batch_timing(self, transformer, sample_data):
        """Test that batch timing is recorded correctly."""
        transformer.extracted_data = sample_data
        
        start_time = datetime.now(timezone.utc)
        batch_result = transformer.process()
        end_time = datetime.now(timezone.utc)
        
        assert batch_result.start_time >= start_time
        assert batch_result.end_time <= end_time
        assert batch_result.end_time >= batch_result.start_time
    
    def test_error_accumulation(self, transformer):
        """Test that errors are properly accumulated."""
        transformer.errors.append("Error 1")
        transformer.errors.append("Error 2")
        transformer.records_failed = 2
        
        summary = transformer._create_batch_summary("FAILED")
        
        assert summary.records_failed == 2
        assert "Error 1; Error 2" in summary.error_message