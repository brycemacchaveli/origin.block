"""
Customer dimension transformer for ETL operations.

This module transforms customer data from the operational database
into the DimCustomer dimensional model with SCD Type 2 support.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import json

import pandas as pd
import structlog

from etl.models import DimCustomer
from etl.transformers.base_transformer import BaseTransformer
from shared.database import DatabaseManager, CustomerModel, ActorModel

logger = structlog.get_logger(__name__)


class CustomerTransformer(BaseTransformer[DimCustomer]):
    """
    Transformer for Customer dimension table.
    
    Implements SCD Type 2 for tracking historical changes to customer data.
    """
    
    def __init__(self, db_manager: DatabaseManager, batch_id: Optional[str] = None):
        """Initialize customer transformer."""
        super().__init__(batch_id)
        self.db_manager = db_manager
        self.table_name = "dim_customer"
    
    def extract(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Extract customer data from operational database.
        
        Args:
            **kwargs: Optional parameters for filtering
                - incremental: bool - If True, extract only recent changes
                - since_date: datetime - Extract changes since this date
                
        Returns:
            List of customer records
        """
        try:
            with self.db_manager.session_scope() as session:
                query = session.query(CustomerModel, ActorModel).join(
                    ActorModel, CustomerModel.created_by_actor_id == ActorModel.id
                )
                
                # Apply incremental filtering if specified
                if kwargs.get('incremental', False):
                    since_date = kwargs.get('since_date')
                    if since_date:
                        query = query.filter(CustomerModel.updated_at >= since_date)
                
                results = query.all()
                
                customers = []
                for customer, actor in results:
                    customer_data = {
                        'customer_id': customer.customer_id,
                        'first_name': customer.first_name,
                        'last_name': customer.last_name,
                        'date_of_birth': customer.date_of_birth,
                        'national_id_hash': customer.national_id_hash,
                        'address': customer.address,
                        'contact_email': customer.contact_email,
                        'contact_phone': customer.contact_phone,
                        'kyc_status': customer.kyc_status,
                        'aml_status': customer.aml_status,
                        'consent_preferences': customer.consent_preferences,
                        'created_by_actor_id': actor.actor_id,
                        'created_at': customer.created_at,
                        'updated_at': customer.updated_at
                    }
                    customers.append(customer_data)
                
                logger.info("Extracted customer data", 
                           count=len(customers), 
                           batch_id=self.batch_id)
                
                return customers
                
        except Exception as e:
            logger.error("Failed to extract customer data", 
                        error=str(e), 
                        batch_id=self.batch_id)
            raise
    
    def transform(self, source_data: List[Dict[str, Any]]) -> List[DimCustomer]:
        """
        Transform customer data to dimensional model.
        
        Args:
            source_data: Raw customer data from extraction
            
        Returns:
            List of DimCustomer records
        """
        try:
            # Validate data first
            valid_data = self.validate_data(source_data)
            
            transformed_records = []
            current_time = datetime.now(timezone.utc)
            
            for record in valid_data:
                try:
                    # Generate surrogate key
                    customer_key = self.generate_surrogate_key(
                        record['customer_id'], 
                        self.table_name
                    )
                    
                    # Parse consent preferences
                    consent_prefs = record.get('consent_preferences')
                    if isinstance(consent_prefs, str):
                        try:
                            consent_prefs = json.loads(consent_prefs)
                        except json.JSONDecodeError:
                            consent_prefs = None
                    
                    # Create dimension record
                    dim_customer = DimCustomer(
                        customer_key=customer_key,
                        customer_id=record['customer_id'],
                        first_name=record['first_name'],
                        last_name=record['last_name'],
                        date_of_birth=self.convert_datetime(record.get('date_of_birth')),
                        national_id_hash=record.get('national_id_hash'),
                        address=record.get('address'),
                        contact_email=record.get('contact_email'),
                        contact_phone=record.get('contact_phone'),
                        kyc_status=record['kyc_status'],
                        aml_status=record['aml_status'],
                        consent_preferences=consent_prefs,
                        created_by_actor_id=record['created_by_actor_id'],
                        
                        # SCD Type 2 fields
                        effective_date=current_time,
                        expiration_date=None,
                        is_current=True,
                        version=1,
                        
                        # Audit fields
                        created_at=self.convert_datetime(record['created_at']) or current_time,
                        updated_at=self.convert_datetime(record['updated_at']) or current_time,
                        etl_batch_id=self.batch_id
                    )
                    
                    transformed_records.append(dim_customer)
                    
                except Exception as e:
                    logger.error("Failed to transform customer record", 
                                customer_id=record.get('customer_id'),
                                error=str(e),
                                batch_id=self.batch_id)
                    self.records_failed += 1
                    self.errors.append(f"Transform error for customer {record.get('customer_id')}: {str(e)}")
            
            logger.info("Transformed customer data", 
                       count=len(transformed_records), 
                       batch_id=self.batch_id)
            
            return transformed_records
            
        except Exception as e:
            logger.error("Failed to transform customer data", 
                        error=str(e), 
                        batch_id=self.batch_id)
            raise
    
    def load(self, transformed_data: List[DimCustomer]) -> bool:
        """
        Load transformed data to BigQuery.
        
        Note: This is a placeholder implementation.
        In production, this would use BigQuery client to load data.
        
        Args:
            transformed_data: Transformed dimension records
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # TODO: Implement BigQuery loading
            # For now, just log the data that would be loaded
            
            logger.info("Loading customer dimension data", 
                       count=len(transformed_data), 
                       batch_id=self.batch_id)
            
            for record in transformed_data:
                logger.debug("Would load customer record", 
                           customer_id=record.customer_id,
                           customer_key=record.customer_key,
                           version=record.version,
                           is_current=record.is_current,
                           batch_id=self.batch_id)
            
            # Simulate successful load
            self.records_inserted = len(transformed_data)
            
            logger.info("Successfully loaded customer dimension data", 
                       records_inserted=self.records_inserted,
                       batch_id=self.batch_id)
            
            return True
            
        except Exception as e:
            logger.error("Failed to load customer dimension data", 
                        error=str(e), 
                        batch_id=self.batch_id)
            return False
    
    def process_scd_type2(self, existing_records: List[DimCustomer] = None) -> List[DimCustomer]:
        """
        Process SCD Type 2 logic for customer dimension.
        
        Args:
            existing_records: Current records in dimension table
            
        Returns:
            List of records to insert/update
        """
        # Extract new data
        source_data = self.extract(incremental=True)
        new_records = self.transform(source_data)
        
        if existing_records is None:
            existing_records = []
        
        # Define fields to compare for changes
        compare_fields = [
            'first_name', 'last_name', 'address', 'contact_email', 
            'contact_phone', 'kyc_status', 'aml_status', 'consent_preferences'
        ]
        
        # Implement SCD Type 2 logic
        scd_records = self.implement_scd_type2(
            existing_records=existing_records,
            new_records=new_records,
            business_key_field='customer_id',
            compare_fields=compare_fields
        )
        
        return scd_records
    
    def _create_new_scd_record(
        self, 
        data_row: pd.Series, 
        effective_date: datetime,
        version: int = 1
    ) -> DimCustomer:
        """Create new SCD Type 2 customer record."""
        customer_key = self.generate_surrogate_key(
            data_row['customer_id'], 
            self.table_name
        )
        
        return DimCustomer(
            customer_key=customer_key,
            customer_id=data_row['customer_id'],
            first_name=data_row['first_name'],
            last_name=data_row['last_name'],
            date_of_birth=self.convert_datetime(data_row.get('date_of_birth')),
            national_id_hash=data_row.get('national_id_hash'),
            address=data_row.get('address'),
            contact_email=data_row.get('contact_email'),
            contact_phone=data_row.get('contact_phone'),
            kyc_status=data_row['kyc_status'],
            aml_status=data_row['aml_status'],
            consent_preferences=data_row.get('consent_preferences'),
            created_by_actor_id=data_row['created_by_actor_id'],
            
            # SCD Type 2 fields
            effective_date=effective_date,
            expiration_date=None,
            is_current=True,
            version=version,
            
            # Audit fields
            created_at=self.convert_datetime(data_row['created_at']) or effective_date,
            updated_at=self.convert_datetime(data_row['updated_at']) or effective_date,
            etl_batch_id=self.batch_id
        )
    
    def _expire_scd_record(
        self, 
        existing_row: pd.Series, 
        expiration_date: datetime
    ) -> DimCustomer:
        """Expire existing SCD Type 2 customer record."""
        return DimCustomer(
            customer_key=existing_row['customer_key'],
            customer_id=existing_row['customer_id'],
            first_name=existing_row['first_name'],
            last_name=existing_row['last_name'],
            date_of_birth=self.convert_datetime(existing_row.get('date_of_birth')),
            national_id_hash=existing_row.get('national_id_hash'),
            address=existing_row.get('address'),
            contact_email=existing_row.get('contact_email'),
            contact_phone=existing_row.get('contact_phone'),
            kyc_status=existing_row['kyc_status'],
            aml_status=existing_row['aml_status'],
            consent_preferences=existing_row.get('consent_preferences'),
            created_by_actor_id=existing_row['created_by_actor_id'],
            
            # SCD Type 2 fields - expire the record
            effective_date=self.convert_datetime(existing_row['effective_date']),
            expiration_date=expiration_date,
            is_current=False,
            version=existing_row['version'],
            
            # Audit fields
            created_at=self.convert_datetime(existing_row['created_at']),
            updated_at=expiration_date,
            etl_batch_id=self.batch_id
        )
    
    def _validate_record(self, record: Dict[str, Any]) -> bool:
        """Validate customer record."""
        required_fields = ['customer_id', 'first_name', 'last_name', 'kyc_status', 'aml_status']
        
        for field in required_fields:
            if not record.get(field):
                logger.warning("Missing required field", 
                              field=field, 
                              customer_id=record.get('customer_id'),
                              batch_id=self.batch_id)
                return False
        
        # Validate status values
        valid_kyc_statuses = ['PENDING', 'VERIFIED', 'FAILED']
        valid_aml_statuses = ['PENDING', 'CLEAR', 'FLAGGED']
        
        if record['kyc_status'] not in valid_kyc_statuses:
            logger.warning("Invalid KYC status", 
                          kyc_status=record['kyc_status'],
                          customer_id=record.get('customer_id'),
                          batch_id=self.batch_id)
            return False
        
        if record['aml_status'] not in valid_aml_statuses:
            logger.warning("Invalid AML status", 
                          aml_status=record['aml_status'],
                          customer_id=record.get('customer_id'),
                          batch_id=self.batch_id)
            return False
        
        return True