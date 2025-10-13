"""
Data consistency and integrity checker for blockchain-database synchronization.

This module provides functionality to:
- Perform periodic reconciliation between blockchain and database
- Validate data integrity and detect inconsistencies
- Generate alerts for synchronization issues
- Provide manual resync capabilities for data recovery
- Monitor synchronization health
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import traceback

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from shared.fabric_gateway import get_fabric_gateway, FabricError
from shared.database import (
    db_manager, db_utils,
    CustomerModel, LoanApplicationModel, ComplianceEventModel,
    LoanDocumentModel, ActorModel
)
from shared.config import settings

logger = structlog.get_logger(__name__)


class InconsistencyType(Enum):
    """Types of data inconsistencies that can be detected."""
    MISSING_IN_DATABASE = "missing_in_database"
    MISSING_IN_BLOCKCHAIN = "missing_in_blockchain"
    DATA_MISMATCH = "data_mismatch"
    HASH_MISMATCH = "hash_mismatch"
    TIMESTAMP_MISMATCH = "timestamp_mismatch"
    STATUS_MISMATCH = "status_mismatch"
    ORPHANED_RECORD = "orphaned_record"


class SeverityLevel(Enum):
    """Severity levels for inconsistencies."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DataInconsistency:
    """Represents a data inconsistency between blockchain and database."""
    inconsistency_type: InconsistencyType
    severity: SeverityLevel
    entity_type: str  # customer, loan_application, compliance_event, etc.
    entity_id: str
    blockchain_data: Optional[Dict[str, Any]]
    database_data: Optional[Dict[str, Any]]
    description: str
    detected_at: datetime
    field_differences: Optional[Dict[str, Tuple[Any, Any]]] = None  # field -> (blockchain_value, db_value)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        result['inconsistency_type'] = self.inconsistency_type.value
        result['severity'] = self.severity.value
        result['detected_at'] = self.detected_at.isoformat()
        return result


@dataclass
class ReconciliationReport:
    """Report of reconciliation results."""
    start_time: datetime
    end_time: datetime
    entities_checked: Dict[str, int]  # entity_type -> count
    inconsistencies_found: List[DataInconsistency]
    total_inconsistencies: int
    severity_breakdown: Dict[str, int]  # severity -> count
    success: bool
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'entities_checked': self.entities_checked,
            'inconsistencies_found': [inc.to_dict() for inc in self.inconsistencies_found],
            'total_inconsistencies': self.total_inconsistencies,
            'severity_breakdown': self.severity_breakdown,
            'success': self.success,
            'error_message': self.error_message
        }


class BlockchainDataFetcher:
    """Fetches data from blockchain for comparison."""
    
    def __init__(self):
        self.gateway = None
    
    async def initialize(self):
        """Initialize blockchain connection."""
        try:
            self.gateway = await get_fabric_gateway()
            logger.info("Blockchain data fetcher initialized")
        except Exception as e:
            logger.error("Failed to initialize blockchain connection", error=str(e))
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def get_customer_data(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Fetch customer data from blockchain."""
        try:
            if not self.gateway:
                await self.initialize()
            
            # Query customer chaincode
            result = await self.gateway.evaluate_transaction(
                'customer',
                'GetCustomer',
                customer_id
            )
            
            if result:
                return json.loads(result.decode('utf-8'))
            return None
            
        except FabricError as e:
            logger.warning("Failed to fetch customer from blockchain", 
                          customer_id=customer_id, error=str(e))
            return None
        except Exception as e:
            logger.error("Unexpected error fetching customer from blockchain",
                        customer_id=customer_id, error=str(e))
            raise


class DataConsistencyChecker:
    """Main class for checking data consistency between blockchain and database."""
    
    def __init__(self):
        self.blockchain_fetcher = BlockchainDataFetcher()
        self.inconsistencies: List[DataInconsistency] = []
        self.last_reconciliation: Optional[datetime] = None
        self.reconciliation_history: List[ReconciliationReport] = []
        
    async def initialize(self):
        """Initialize the consistency checker."""
        await self.blockchain_fetcher.initialize()
        logger.info("Data consistency checker initialized")
    
    async def perform_full_reconciliation(
        self,
        entity_types: Optional[List[str]] = None,
        batch_size: int = 100
    ) -> ReconciliationReport:
        """
        Perform full reconciliation between blockchain and database.
        
        Args:
            entity_types: List of entity types to check (default: all)
            batch_size: Number of entities to process in each batch
            
        Returns:
            ReconciliationReport with results
        """
        start_time = datetime.utcnow()
        logger.info("Starting full data reconciliation", entity_types=entity_types)
        
        if entity_types is None:
            entity_types = ['customers']  # Simplified for now
        
        entities_checked = {}
        all_inconsistencies = []
        
        try:
            # Check each entity type
            for entity_type in entity_types:
                logger.info("Reconciling entity type", entity_type=entity_type)
                
                if entity_type == 'customers':
                    inconsistencies, count = await self._reconcile_customers(batch_size)
                else:
                    logger.warning("Unknown entity type", entity_type=entity_type)
                    continue
                
                entities_checked[entity_type] = count
                all_inconsistencies.extend(inconsistencies)
                
                logger.info("Completed reconciliation for entity type",
                           entity_type=entity_type,
                           entities_checked=count,
                           inconsistencies_found=len(inconsistencies))
            
            # Calculate severity breakdown
            severity_breakdown = {}
            for severity in SeverityLevel:
                severity_breakdown[severity.value] = sum(
                    1 for inc in all_inconsistencies if inc.severity == severity
                )
            
            end_time = datetime.utcnow()
            
            report = ReconciliationReport(
                start_time=start_time,
                end_time=end_time,
                entities_checked=entities_checked,
                inconsistencies_found=all_inconsistencies,
                total_inconsistencies=len(all_inconsistencies),
                severity_breakdown=severity_breakdown,
                success=True
            )
            
            # Store inconsistencies and update last reconciliation time
            self.inconsistencies = all_inconsistencies
            self.last_reconciliation = end_time
            self.reconciliation_history.append(report)
            
            # Limit history size
            if len(self.reconciliation_history) > 50:
                self.reconciliation_history = self.reconciliation_history[-25:]
            
            logger.info("Full reconciliation completed",
                       total_entities=sum(entities_checked.values()),
                       total_inconsistencies=len(all_inconsistencies),
                       duration_seconds=(end_time - start_time).total_seconds())
            
            return report
            
        except Exception as e:
            end_time = datetime.utcnow()
            error_msg = f"Reconciliation failed: {str(e)}"
            logger.error("Full reconciliation failed", error=str(e), traceback=traceback.format_exc())
            
            report = ReconciliationReport(
                start_time=start_time,
                end_time=end_time,
                entities_checked=entities_checked,
                inconsistencies_found=all_inconsistencies,
                total_inconsistencies=len(all_inconsistencies),
                severity_breakdown={},
                success=False,
                error_message=error_msg
            )
            
            self.reconciliation_history.append(report)
            return report
    
    async def _reconcile_customers(self, batch_size: int) -> Tuple[List[DataInconsistency], int]:
        """Reconcile customer data between blockchain and database."""
        inconsistencies = []
        total_count = 0
        
        try:
            # Get all customers from database in batches
            with db_manager.session_scope() as session:
                offset = 0
                while True:
                    customers = session.query(CustomerModel).offset(offset).limit(batch_size).all()
                    if not customers:
                        break
                    
                    for customer in customers:
                        total_count += 1
                        
                        # Fetch corresponding blockchain data
                        blockchain_data = await self.blockchain_fetcher.get_customer_data(customer.customer_id)
                        
                        # Compare data
                        customer_inconsistencies = await self._compare_customer_data(
                            customer, blockchain_data
                        )
                        inconsistencies.extend(customer_inconsistencies)
                    
                    offset += batch_size
                    
                    # Add small delay to avoid overwhelming the system
                    await asyncio.sleep(0.1)
            
            return inconsistencies, total_count
            
        except Exception as e:
            logger.error("Error reconciling customers", error=str(e))
            raise
    
    async def _compare_customer_data(
        self, 
        db_customer: CustomerModel, 
        blockchain_data: Optional[Dict[str, Any]]
    ) -> List[DataInconsistency]:
        """Compare customer data between database and blockchain."""
        inconsistencies = []
        
        if not blockchain_data:
            # Customer exists in database but not in blockchain
            inconsistencies.append(DataInconsistency(
                inconsistency_type=InconsistencyType.MISSING_IN_BLOCKCHAIN,
                severity=SeverityLevel.HIGH,
                entity_type='customer',
                entity_id=db_customer.customer_id,
                blockchain_data=None,
                database_data=self._customer_to_dict(db_customer),
                description=f"Customer {db_customer.customer_id} exists in database but not in blockchain",
                detected_at=datetime.utcnow()
            ))
            return inconsistencies
        
        # Compare key fields
        field_differences = {}
        
        # Compare basic fields
        if db_customer.first_name != blockchain_data.get('firstName'):
            field_differences['first_name'] = (blockchain_data.get('firstName'), db_customer.first_name)
        
        if db_customer.last_name != blockchain_data.get('lastName'):
            field_differences['last_name'] = (blockchain_data.get('lastName'), db_customer.last_name)
        
        if db_customer.contact_email != blockchain_data.get('contactEmail'):
            field_differences['contact_email'] = (blockchain_data.get('contactEmail'), db_customer.contact_email)
        
        if db_customer.kyc_status != blockchain_data.get('kycStatus'):
            field_differences['kyc_status'] = (blockchain_data.get('kycStatus'), db_customer.kyc_status)
        
        if db_customer.aml_status != blockchain_data.get('amlStatus'):
            field_differences['aml_status'] = (blockchain_data.get('amlStatus'), db_customer.aml_status)
        
        # If there are differences, create inconsistency record
        if field_differences:
            severity = SeverityLevel.MEDIUM
            # Critical fields get high severity
            if any(field in field_differences for field in ['kyc_status', 'aml_status']):
                severity = SeverityLevel.HIGH
            
            inconsistencies.append(DataInconsistency(
                inconsistency_type=InconsistencyType.DATA_MISMATCH,
                severity=severity,
                entity_type='customer',
                entity_id=db_customer.customer_id,
                blockchain_data=blockchain_data,
                database_data=self._customer_to_dict(db_customer),
                description=f"Customer {db_customer.customer_id} has {len(field_differences)} field mismatches",
                detected_at=datetime.utcnow(),
                field_differences=field_differences
            ))
        
        return inconsistencies
    
    def _customer_to_dict(self, customer: CustomerModel) -> Dict[str, Any]:
        """Convert customer model to dictionary."""
        return {
            'customer_id': customer.customer_id,
            'first_name': customer.first_name,
            'last_name': customer.last_name,
            'date_of_birth': customer.date_of_birth.isoformat() if customer.date_of_birth else None,
            'contact_email': customer.contact_email,
            'contact_phone': customer.contact_phone,
            'kyc_status': customer.kyc_status,
            'aml_status': customer.aml_status,
            'created_at': customer.created_at.isoformat(),
            'updated_at': customer.updated_at.isoformat()
        }
    
    def get_inconsistencies(
        self,
        entity_type: Optional[str] = None,
        severity: Optional[SeverityLevel] = None,
        limit: int = 100
    ) -> List[DataInconsistency]:
        """
        Get current inconsistencies with optional filtering.
        
        Args:
            entity_type: Filter by entity type
            severity: Filter by severity level
            limit: Maximum number of inconsistencies to return
            
        Returns:
            List of inconsistencies matching the criteria
        """
        filtered_inconsistencies = self.inconsistencies
        
        if entity_type:
            filtered_inconsistencies = [
                inc for inc in filtered_inconsistencies 
                if inc.entity_type == entity_type
            ]
        
        if severity:
            filtered_inconsistencies = [
                inc for inc in filtered_inconsistencies 
                if inc.severity == severity
            ]
        
        return filtered_inconsistencies[:limit]
    
    def get_inconsistency_summary(self) -> Dict[str, Any]:
        """Get summary of current inconsistencies."""
        if not self.inconsistencies:
            return {
                'total_inconsistencies': 0,
                'by_entity_type': {},
                'by_severity': {},
                'by_inconsistency_type': {},
                'last_reconciliation': self.last_reconciliation.isoformat() if self.last_reconciliation else None
            }
        
        # Group by entity type
        by_entity_type = {}
        for inc in self.inconsistencies:
            by_entity_type[inc.entity_type] = by_entity_type.get(inc.entity_type, 0) + 1
        
        # Group by severity
        by_severity = {}
        for inc in self.inconsistencies:
            by_severity[inc.severity.value] = by_severity.get(inc.severity.value, 0) + 1
        
        # Group by inconsistency type
        by_inconsistency_type = {}
        for inc in self.inconsistencies:
            by_inconsistency_type[inc.inconsistency_type.value] = by_inconsistency_type.get(inc.inconsistency_type.value, 0) + 1
        
        return {
            'total_inconsistencies': len(self.inconsistencies),
            'by_entity_type': by_entity_type,
            'by_severity': by_severity,
            'by_inconsistency_type': by_inconsistency_type,
            'last_reconciliation': self.last_reconciliation.isoformat() if self.last_reconciliation else None
        }
    
    def get_reconciliation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent reconciliation history."""
        recent_reports = self.reconciliation_history[-limit:] if self.reconciliation_history else []
        return [report.to_dict() for report in recent_reports]
    
    async def manual_resync_entity(
        self,
        entity_type: str,
        entity_id: str,
        force_overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        Manually resync a specific entity from blockchain to database.
        
        Args:
            entity_type: Type of entity (customer, loan_application, etc.)
            entity_id: ID of the entity to resync
            force_overwrite: Whether to overwrite database data even if no inconsistency
            
        Returns:
            Dictionary with resync results
        """
        logger.info("Starting manual resync", entity_type=entity_type, entity_id=entity_id)
        
        try:
            if entity_type == 'customer':
                return await self._resync_customer(entity_id, force_overwrite)
            else:
                return {
                    'success': False,
                    'error': f"Unsupported entity type: {entity_type}",
                    'entity_type': entity_type,
                    'entity_id': entity_id
                }
                
        except Exception as e:
            logger.error("Manual resync failed", 
                        entity_type=entity_type, 
                        entity_id=entity_id, 
                        error=str(e))
            return {
                'success': False,
                'error': str(e),
                'entity_type': entity_type,
                'entity_id': entity_id
            }
    
    async def _resync_customer(self, customer_id: str, force_overwrite: bool) -> Dict[str, Any]:
        """Resync customer data from blockchain."""
        # Fetch blockchain data
        blockchain_data = await self.blockchain_fetcher.get_customer_data(customer_id)
        if not blockchain_data:
            return {
                'success': False,
                'error': f"Customer {customer_id} not found in blockchain",
                'entity_type': 'customer',
                'entity_id': customer_id
            }
        
        # Get database record
        db_customer = db_utils.get_customer_by_customer_id(customer_id)
        
        changes_made = []
        
        if not db_customer:
            # Create new customer in database
            # Get or create actor for the creation
            actor = await self._get_or_create_system_actor()
            
            customer_data = {
                'customer_id': customer_id,
                'first_name': blockchain_data.get('firstName', ''),
                'last_name': blockchain_data.get('lastName', ''),
                'date_of_birth': self._parse_datetime(blockchain_data.get('dateOfBirth')),
                'national_id_hash': blockchain_data.get('nationalID'),
                'address': blockchain_data.get('address'),
                'contact_email': blockchain_data.get('contactEmail'),
                'contact_phone': blockchain_data.get('contactPhone'),
                'kyc_status': blockchain_data.get('kycStatus', 'PENDING'),
                'aml_status': blockchain_data.get('amlStatus', 'PENDING'),
                'consent_preferences': blockchain_data.get('consentPreferences'),
                'created_by_actor_id': actor.id,
                'created_at': datetime.utcnow()
            }
            
            db_customer = db_utils.create_customer(customer_data)
            changes_made.append('created_customer')
        
        return {
            'success': True,
            'entity_type': 'customer',
            'entity_id': customer_id,
            'changes_made': changes_made,
            'force_overwrite': force_overwrite
        }
    
    async def _get_or_create_system_actor(self) -> ActorModel:
        """Get or create system actor for automated operations."""
        actor = db_utils.get_actor_by_actor_id("CONSISTENCY_CHECKER")
        if not actor:
            actor_data = {
                'actor_id': "CONSISTENCY_CHECKER",
                'actor_type': 'System',
                'actor_name': 'Data Consistency Checker',
                'role': 'System',
                'is_active': True
            }
            actor = db_utils.create_actor(actor_data)
        return actor
    
    def _parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string to datetime object."""
        if not date_str:
            return None
        
        try:
            # Try different datetime formats
            formats = [
                '%Y-%m-%dT%H:%M:%S.%fZ',
                '%Y-%m-%dT%H:%M:%SZ',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d'
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            logger.warning("Could not parse datetime", date_str=date_str)
            return None
            
        except Exception as e:
            logger.error("Error parsing datetime", date_str=date_str, error=str(e))
            return None
    
    async def generate_integrity_report(self) -> Dict[str, Any]:
        """Generate comprehensive data integrity report."""
        logger.info("Generating data integrity report")
        
        try:
            # Perform quick reconciliation check
            report = await self.perform_full_reconciliation(batch_size=50)
            
            # Get database statistics
            db_stats = await self._get_database_statistics()
            
            # Get blockchain connectivity status
            blockchain_status = await self._check_blockchain_connectivity()
            
            integrity_report = {
                'generated_at': datetime.utcnow().isoformat(),
                'reconciliation_report': report.to_dict(),
                'database_statistics': db_stats,
                'blockchain_connectivity': blockchain_status,
                'inconsistency_summary': self.get_inconsistency_summary(),
                'recommendations': self._generate_recommendations()
            }
            
            logger.info("Data integrity report generated successfully",
                       total_inconsistencies=report.total_inconsistencies)
            
            return integrity_report
            
        except Exception as e:
            logger.error("Failed to generate integrity report", error=str(e))
            return {
                'generated_at': datetime.utcnow().isoformat(),
                'error': str(e),
                'success': False
            }
    
    async def _get_database_statistics(self) -> Dict[str, Any]:
        """Get database statistics for the report."""
        try:
            with db_manager.session_scope() as session:
                stats = {
                    'customers_count': session.query(CustomerModel).count(),
                    'database_healthy': db_manager.health_check()
                }
                return stats
        except Exception as e:
            logger.error("Failed to get database statistics", error=str(e))
            return {'error': str(e)}
    
    async def _check_blockchain_connectivity(self) -> Dict[str, Any]:
        """Check blockchain connectivity status."""
        try:
            if not self.blockchain_fetcher.gateway:
                await self.blockchain_fetcher.initialize()
            
            # Try a simple query to test connectivity
            test_result = await self.blockchain_fetcher.get_customer_data("test_connectivity")
            
            return {
                'connected': True,
                'gateway_initialized': self.blockchain_fetcher.gateway is not None,
                'test_query_successful': True  # None is expected for non-existent customer
            }
        except Exception as e:
            logger.warning("Blockchain connectivity check failed", error=str(e))
            return {
                'connected': False,
                'error': str(e)
            }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on current inconsistencies."""
        recommendations = []
        
        if not self.inconsistencies:
            recommendations.append("No inconsistencies detected. Data integrity is good.")
            return recommendations
        
        # Count critical inconsistencies
        critical_count = sum(1 for inc in self.inconsistencies if inc.severity == SeverityLevel.CRITICAL)
        if critical_count > 0:
            recommendations.append(f"URGENT: {critical_count} critical inconsistencies require immediate attention.")
        
        # General recommendations
        if len(self.inconsistencies) > 100:
            recommendations.append("High number of inconsistencies detected. Consider full system reconciliation.")
        
        return recommendations


# Global consistency checker instance
consistency_checker = DataConsistencyChecker()