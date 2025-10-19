"""
Base transformer class for ETL operations.

This module provides the abstract base class for all data transformers,
implementing common functionality for dimensional modeling and SCD operations.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, TypeVar, Generic
import uuid
import logging
from dataclasses import asdict

import pandas as pd
import structlog

from etl.models import SCDType, ETLBatch

logger = structlog.get_logger(__name__)

T = TypeVar('T')


class BaseTransformer(ABC, Generic[T]):
    """
    Abstract base class for all ETL transformers.
    
    Provides common functionality for:
    - SCD Type 2 processing
    - Data validation
    - Batch tracking
    - Error handling
    """
    
    def __init__(self, batch_id: Optional[str] = None):
        """Initialize transformer with batch tracking."""
        self.batch_id = batch_id or self._generate_batch_id()
        self.batch_start_time = datetime.now(timezone.utc)
        self.records_processed = 0
        self.records_inserted = 0
        self.records_updated = 0
        self.records_failed = 0
        self.errors: List[str] = []
    
    def _generate_batch_id(self) -> str:
        """Generate unique batch ID."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"{self.__class__.__name__}_{timestamp}_{unique_id}"
    
    @abstractmethod
    def extract(self, **kwargs) -> List[Dict[str, Any]]:
        """Extract data from source system."""
        pass
    
    @abstractmethod
    def transform(self, source_data: List[Dict[str, Any]]) -> List[T]:
        """Transform source data to dimensional model."""
        pass
    
    @abstractmethod
    def load(self, transformed_data: List[T]) -> bool:
        """Load transformed data to target system."""
        pass
    
    def process(self, **kwargs) -> ETLBatch:
        """
        Execute complete ETL process.
        
        Returns:
            ETLBatch: Batch execution summary
        """
        try:
            logger.info("Starting ETL process", 
                       transformer=self.__class__.__name__, 
                       batch_id=self.batch_id)
            
            # Extract
            source_data = self.extract(**kwargs)
            self.records_processed = len(source_data)
            
            if not source_data:
                logger.info("No data to process", batch_id=self.batch_id)
                return self._create_batch_summary("SUCCESS")
            
            # Transform
            transformed_data = self.transform(source_data)
            
            # Load
            success = self.load(transformed_data)
            
            status = "SUCCESS" if success else "FAILED"
            logger.info("ETL process completed", 
                       batch_id=self.batch_id, 
                       status=status,
                       records_processed=self.records_processed)
            
            return self._create_batch_summary(status)
            
        except Exception as e:
            logger.error("ETL process failed", 
                        batch_id=self.batch_id, 
                        error=str(e))
            self.errors.append(str(e))
            return self._create_batch_summary("FAILED")
    
    def _create_batch_summary(self, status: str) -> ETLBatch:
        """Create batch execution summary."""
        return ETLBatch(
            batch_id=self.batch_id,
            batch_type="INCREMENTAL",  # Default, can be overridden
            start_time=self.batch_start_time,
            end_time=datetime.now(timezone.utc),
            status=status,
            records_processed=self.records_processed,
            records_inserted=self.records_inserted,
            records_updated=self.records_updated,
            records_failed=self.records_failed,
            error_message="; ".join(self.errors) if self.errors else None
        )
    
    def implement_scd_type2(
        self, 
        existing_records: List[T], 
        new_records: List[T],
        business_key_field: str,
        compare_fields: List[str]
    ) -> List[T]:
        """
        Implement SCD Type 2 logic for dimensional data.
        
        Args:
            existing_records: Current records in dimension table
            new_records: New records from source
            business_key_field: Field name for business key comparison
            compare_fields: Fields to compare for changes
            
        Returns:
            List of records to insert/update
        """
        result_records = []
        current_time = datetime.now(timezone.utc)
        
        # Convert to DataFrames for easier processing
        if existing_records:
            existing_df = pd.DataFrame([asdict(record) for record in existing_records])
            existing_df = existing_df[existing_df['is_current'] == True]
        else:
            existing_df = pd.DataFrame()
        
        new_df = pd.DataFrame([asdict(record) for record in new_records])
        
        for _, new_row in new_df.iterrows():
            business_key = new_row[business_key_field]
            
            # Find existing current record
            if not existing_df.empty:
                existing_record = existing_df[
                    existing_df[business_key_field] == business_key
                ]
            else:
                existing_record = pd.DataFrame()
            
            if existing_record.empty:
                # New record - insert as current
                new_record = self._create_new_scd_record(new_row, current_time)
                result_records.append(new_record)
                self.records_inserted += 1
                
            else:
                # Check if data has changed
                existing_row = existing_record.iloc[0]
                has_changed = self._has_data_changed(
                    existing_row, new_row, compare_fields
                )
                
                if has_changed:
                    # Expire existing record
                    expired_record = self._expire_scd_record(
                        existing_row, current_time
                    )
                    result_records.append(expired_record)
                    
                    # Insert new version
                    new_version = existing_row.get('version', 1) + 1
                    new_record = self._create_new_scd_record(
                        new_row, current_time, new_version
                    )
                    result_records.append(new_record)
                    self.records_updated += 1
        
        return result_records
    
    def _has_data_changed(
        self, 
        existing_row: pd.Series, 
        new_row: pd.Series, 
        compare_fields: List[str]
    ) -> bool:
        """Check if data has changed in specified fields."""
        for field in compare_fields:
            if field in existing_row and field in new_row:
                if existing_row[field] != new_row[field]:
                    return True
        return False
    
    def _create_new_scd_record(
        self, 
        data_row: pd.Series, 
        effective_date: datetime,
        version: int = 1
    ) -> T:
        """Create new SCD Type 2 record."""
        # This method should be overridden by subclasses
        # to return the appropriate dimension type
        raise NotImplementedError("Subclasses must implement _create_new_scd_record")
    
    def _expire_scd_record(
        self, 
        existing_row: pd.Series, 
        expiration_date: datetime
    ) -> T:
        """Expire existing SCD Type 2 record."""
        # This method should be overridden by subclasses
        # to return the appropriate dimension type
        raise NotImplementedError("Subclasses must implement _expire_scd_record")
    
    def validate_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate source data before transformation.
        
        Args:
            data: Source data to validate
            
        Returns:
            List of valid records
        """
        valid_records = []
        
        for record in data:
            try:
                if self._validate_record(record):
                    valid_records.append(record)
                else:
                    self.records_failed += 1
                    self.errors.append(f"Validation failed for record: {record}")
            except Exception as e:
                self.records_failed += 1
                self.errors.append(f"Validation error: {str(e)}")
        
        return valid_records
    
    def _validate_record(self, record: Dict[str, Any]) -> bool:
        """
        Validate individual record.
        Override in subclasses for specific validation rules.
        """
        return True
    
    def generate_surrogate_key(self, business_key: str, table_name: str) -> int:
        """
        Generate surrogate key for dimension tables.
        
        Args:
            business_key: Business key value
            table_name: Name of the dimension table
            
        Returns:
            Integer surrogate key
        """
        # Simple hash-based surrogate key generation
        # In production, this should use a proper key management system
        combined_key = f"{table_name}_{business_key}"
        return abs(hash(combined_key)) % (10**9)  # Limit to 9 digits
    
    def convert_to_date_key(self, date_value: datetime) -> int:
        """
        Convert datetime to date key (YYYYMMDD format).
        
        Args:
            date_value: Datetime to convert
            
        Returns:
            Integer date key
        """
        if date_value is None:
            return 19000101  # Default date key for null dates
        
        return int(date_value.strftime("%Y%m%d"))
    
    def safe_get(self, data: Dict[str, Any], key: str, default: Any = None) -> Any:
        """Safely get value from dictionary with default."""
        return data.get(key, default)
    
    def convert_datetime(self, value: Any) -> Optional[datetime]:
        """Convert various datetime formats to datetime object."""
        if value is None:
            return None
        
        if isinstance(value, datetime):
            return value
        
        if isinstance(value, str):
            try:
                # Try common datetime formats
                for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"]:
                    try:
                        return datetime.strptime(value, fmt)
                    except ValueError:
                        continue
                
                # If no format matches, try pandas parsing
                return pd.to_datetime(value).to_pydatetime()
            except Exception:
                return None
        
        return None