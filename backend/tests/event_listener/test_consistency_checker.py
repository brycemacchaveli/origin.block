"""
Unit tests for data consistency checker functionality.

Tests cover:
- Data reconciliation between blockchain and database
- Inconsistency detection and classification
- Manual resync capabilities
- Performance monitoring and alerting
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

from event_listener.consistency_checker import (
    DataConsistencyChecker,
    BlockchainDataFetcher,
    DataInconsistency,
    InconsistencyType,
    SeverityLevel,
    ReconciliationReport
)
from event_listener.consistency_monitoring import (
    ConsistencyMonitor,
    Alert,
    AlertType
)
from shared.database import (
    CustomerModel,
    LoanApplicationModel,
    ComplianceEventModel,
    LoanDocumentModel,
    ActorModel
)


class TestBlockchainDataFetcher:
    """Test blockchain data fetcher functionality."""
    
    @pytest.fixture
    def mock_gateway(self):
        """Mock Fabric gateway."""
        gateway = AsyncMock()
        return gateway
    
    @pytest.fixture
    def fetcher(self, mock_gateway):
        """Create blockchain data fetcher with mocked gateway."""
        fetcher = BlockchainDataFetcher()
        fetcher.gateway = mock_gateway
        return fetcher
    
    @pytest.mark.asyncio
    async def test_get_customer_data_success(self, fetcher, mock_gateway):
        """Test successful customer data retrieval."""
        # Arrange
        customer_data = {
            'customerID': 'CUST001',
            'firstName': 'John',
            'lastName': 'Doe',
            'contactEmail': 'john.doe@example.com',
            'kycStatus': 'VERIFIED',
            'amlStatus': 'CLEAR'
        }
        mock_gateway.evaluate_transaction.return_value = bytes(
            json.dumps(customer_data), 'utf-8'
        )
        
        # Act
        result = await fetcher.get_customer_data('CUST001')
        
        # Assert
        assert result == customer_data
        mock_gateway.evaluate_transaction.assert_called_once_with(
            'customer', 'GetCustomer', 'CUST001'
        )
    
    @pytest.mark.asyncio
    async def test_get_customer_data_not_found(self, fetcher, mock_gateway):
        """Test customer data retrieval when customer not found."""
        # Arrange
        mock_gateway.evaluate_transaction.return_value = None
        
        # Act
        result = await fetcher.get_customer_data('NONEXISTENT')
        
        # Assert
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_loan_application_data_success(self, fetcher, mock_gateway):
        """Test successful loan application data retrieval."""
        # Arrange
        loan_data = {
            'loanApplicationID': 'LOAN001',
            'customerID': 'CUST001',
            'requestedAmount': 50000.0,
            'loanType': 'PERSONAL',
            'applicationStatus': 'APPROVED'
        }
        mock_gateway.evaluate_transaction.return_value = bytes(
            json.dumps(loan_data), 'utf-8'
        )
        
        # Act
        result = await fetcher.get_loan_application_data('LOAN001')
        
        # Assert
        assert result == loan_data
        mock_gateway.evaluate_transaction.assert_called_once_with(
            'loan', 'GetLoanApplication', 'LOAN001'
        )
    
    @pytest.mark.asyncio
    async def test_get_compliance_events_success(self, fetcher, mock_gateway):
        """Test successful compliance events retrieval."""
        # Arrange
        events_data = [
            {
                'eventID': 'EVENT001',
                'eventType': 'AML_CHECK',
                'affectedEntityType': 'CUSTOMER',
                'affectedEntityID': 'CUST001'
            }
        ]
        mock_gateway.evaluate_transaction.return_value = bytes(
            json.dumps(events_data), 'utf-8'
        )
        
        # Act
        result = await fetcher.get_compliance_events('CUSTOMER', 'CUST001')
        
        # Assert
        assert result == events_data
        mock_gateway.evaluate_transaction.assert_called_once_with(
            'compliance', 'GetComplianceEventsByEntity', 'CUSTOMER', 'CUST001'
        )


class TestDataConsistencyChecker:
    """Test data consistency checker functionality."""
    
    @pytest.fixture
    def mock_blockchain_fetcher(self):
        """Mock blockchain data fetcher."""
        fetcher = AsyncMock(spec=BlockchainDataFetcher)
        return fetcher
    
    @pytest.fixture
    def consistency_checker(self, mock_blockchain_fetcher):
        """Create consistency checker with mocked dependencies."""
        checker = DataConsistencyChecker()
        checker.blockchain_fetcher = mock_blockchain_fetcher
        return checker
    
    @pytest.fixture
    def sample_customer(self):
        """Create sample customer model."""
        return CustomerModel(
            id=1,
            customer_id='CUST001',
            first_name='John',
            last_name='Doe',
            contact_email='john.doe@example.com',
            kyc_status='VERIFIED',
            aml_status='CLEAR',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            created_by_actor_id=1
        )
    
    @pytest.fixture
    def sample_loan(self):
        """Create sample loan application model."""
        return LoanApplicationModel(
            id=1,
            loan_application_id='LOAN001',
            customer_id=1,
            requested_amount=50000.0,
            loan_type='PERSONAL',
            application_status='APPROVED',
            application_date=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            created_by_actor_id=1,
            current_owner_actor_id=1
        )
    
    @pytest.mark.asyncio
    async def test_compare_customer_data_no_differences(self, consistency_checker, sample_customer):
        """Test customer data comparison with no differences."""
        # Arrange
        blockchain_data = {
            'customerID': 'CUST001',
            'firstName': 'John',
            'lastName': 'Doe',
            'contactEmail': 'john.doe@example.com',
            'kycStatus': 'VERIFIED',
            'amlStatus': 'CLEAR'
        }
        
        # Act
        inconsistencies = await consistency_checker._compare_customer_data(
            sample_customer, blockchain_data
        )
        
        # Assert
        assert len(inconsistencies) == 0
    
    @pytest.mark.asyncio
    async def test_compare_customer_data_with_differences(self, consistency_checker, sample_customer):
        """Test customer data comparison with differences."""
        # Arrange
        blockchain_data = {
            'customerID': 'CUST001',
            'firstName': 'Jane',  # Different first name
            'lastName': 'Doe',
            'contactEmail': 'jane.doe@example.com',  # Different email
            'kycStatus': 'PENDING',  # Different KYC status
            'amlStatus': 'CLEAR'
        }
        
        # Act
        inconsistencies = await consistency_checker._compare_customer_data(
            sample_customer, blockchain_data
        )
        
        # Assert
        assert len(inconsistencies) == 1
        inconsistency = inconsistencies[0]
        assert inconsistency.inconsistency_type == InconsistencyType.DATA_MISMATCH
        assert inconsistency.severity == SeverityLevel.HIGH  # KYC status is critical
        assert inconsistency.entity_type == 'customer'
        assert inconsistency.entity_id == 'CUST001'
        assert 'first_name' in inconsistency.field_differences
        assert 'contact_email' in inconsistency.field_differences
        assert 'kyc_status' in inconsistency.field_differences
    
    @pytest.mark.asyncio
    async def test_compare_customer_data_missing_in_blockchain(self, consistency_checker, sample_customer):
        """Test customer data comparison when customer missing in blockchain."""
        # Act
        inconsistencies = await consistency_checker._compare_customer_data(
            sample_customer, None
        )
        
        # Assert
        assert len(inconsistencies) == 1
        inconsistency = inconsistencies[0]
        assert inconsistency.inconsistency_type == InconsistencyType.MISSING_IN_BLOCKCHAIN
        assert inconsistency.severity == SeverityLevel.HIGH
        assert inconsistency.entity_type == 'customer'
        assert inconsistency.entity_id == 'CUST001'
        assert inconsistency.blockchain_data is None
    
    @pytest.mark.asyncio
    async def test_compare_loan_data_with_status_mismatch(self, consistency_checker, sample_loan):
        """Test loan data comparison with status mismatch."""
        # Arrange
        blockchain_data = {
            'loanApplicationID': 'LOAN001',
            'customerID': 'CUST001',
            'requestedAmount': 50000.0,
            'loanType': 'PERSONAL',
            'applicationStatus': 'REJECTED'  # Different status
        }
        
        # Act
        inconsistencies = await consistency_checker._compare_loan_application_data(
            sample_loan, blockchain_data
        )
        
        # Assert
        assert len(inconsistencies) == 1
        inconsistency = inconsistencies[0]
        assert inconsistency.inconsistency_type == InconsistencyType.DATA_MISMATCH
        assert inconsistency.severity == SeverityLevel.CRITICAL  # Status mismatch is critical
        assert 'application_status' in inconsistency.field_differences
    
    @pytest.mark.asyncio
    async def test_compare_document_data_hash_mismatch(self, consistency_checker):
        """Test document data comparison with hash mismatch."""
        # Arrange
        document = LoanDocumentModel(
            id=1,
            loan_application_id=1,
            document_type='IDENTITY',
            document_name='passport.pdf',
            document_hash='abc123',
            verification_status='VERIFIED',
            uploaded_by_actor_id=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        blockchain_data = {
            'documentType': 'IDENTITY',
            'documentName': 'passport.pdf',
            'documentHash': 'def456'  # Different hash
        }
        
        # Act
        inconsistencies = await consistency_checker._compare_document_data(
            document, blockchain_data
        )
        
        # Assert
        assert len(inconsistencies) == 1
        inconsistency = inconsistencies[0]
        assert inconsistency.inconsistency_type == InconsistencyType.HASH_MISMATCH
        assert inconsistency.severity == SeverityLevel.CRITICAL
        assert 'document_hash' in inconsistency.field_differences
    
    @pytest.mark.asyncio
    @patch('event_listener.consistency_checker.db_manager')
    @patch('event_listener.consistency_checker.db_utils')
    async def test_manual_resync_customer_create_new(self, mock_db_utils, mock_db_manager, consistency_checker):
        """Test manual resync creating new customer."""
        # Arrange
        blockchain_data = {
            'customerID': 'CUST002',
            'firstName': 'Alice',
            'lastName': 'Smith',
            'contactEmail': 'alice.smith@example.com',
            'kycStatus': 'VERIFIED',
            'amlStatus': 'CLEAR'
        }
        
        consistency_checker.blockchain_fetcher.get_customer_data.return_value = blockchain_data
        mock_db_utils.get_customer_by_customer_id.return_value = None  # Customer doesn't exist
        
        # Mock actor creation
        mock_actor = ActorModel(id=1, actor_id='CONSISTENCY_CHECKER')
        consistency_checker._get_or_create_system_actor = AsyncMock(return_value=mock_actor)
        
        # Mock customer creation
        mock_customer = CustomerModel(id=2, customer_id='CUST002')
        mock_db_utils.create_customer.return_value = mock_customer
        
        # Act
        result = await consistency_checker.manual_resync_entity('customer', 'CUST002')
        
        # Assert
        assert result['success'] is True
        assert 'created_customer' in result['changes_made']
        mock_db_utils.create_customer.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_manual_resync_customer_not_found_in_blockchain(self, consistency_checker):
        """Test manual resync when customer not found in blockchain."""
        # Arrange
        consistency_checker.blockchain_fetcher.get_customer_data.return_value = None
        
        # Act
        result = await consistency_checker.manual_resync_entity('customer', 'NONEXISTENT')
        
        # Assert
        assert result['success'] is False
        assert 'not found in blockchain' in result['error']
    
    @pytest.mark.asyncio
    @patch('event_listener.consistency_checker.db_manager')
    async def test_perform_full_reconciliation_success(self, mock_db_manager, consistency_checker):
        """Test successful full reconciliation."""
        # Mock database queries to return empty results for simplicity
        mock_session = Mock()
        mock_session.query.return_value.offset.return_value.limit.return_value.all.return_value = []
        mock_db_manager.session_scope.return_value.__enter__.return_value = mock_session
        mock_db_manager.session_scope.return_value.__exit__.return_value = None
        
        # Act
        report = await consistency_checker.perform_full_reconciliation(['customers'])
        
        # Assert
        assert report.success is True
        assert 'customers' in report.entities_checked
        assert report.total_inconsistencies == 0
        assert isinstance(report.start_time, datetime)
        assert isinstance(report.end_time, datetime)
    
    def test_get_inconsistency_summary_empty(self, consistency_checker):
        """Test inconsistency summary when no inconsistencies exist."""
        # Act
        summary = consistency_checker.get_inconsistency_summary()
        
        # Assert
        assert summary['total_inconsistencies'] == 0
        assert summary['by_entity_type'] == {}
        assert summary['by_severity'] == {}
        assert summary['by_inconsistency_type'] == {}
    
    def test_get_inconsistency_summary_with_data(self, consistency_checker):
        """Test inconsistency summary with inconsistencies."""
        # Arrange
        inconsistencies = [
            DataInconsistency(
                inconsistency_type=InconsistencyType.DATA_MISMATCH,
                severity=SeverityLevel.HIGH,
                entity_type='customer',
                entity_id='CUST001',
                blockchain_data={},
                database_data={},
                description='Test inconsistency',
                detected_at=datetime.utcnow()
            ),
            DataInconsistency(
                inconsistency_type=InconsistencyType.MISSING_IN_BLOCKCHAIN,
                severity=SeverityLevel.CRITICAL,
                entity_type='loan_application',
                entity_id='LOAN001',
                blockchain_data=None,
                database_data={},
                description='Test inconsistency 2',
                detected_at=datetime.utcnow()
            )
        ]
        consistency_checker.inconsistencies = inconsistencies
        
        # Act
        summary = consistency_checker.get_inconsistency_summary()
        
        # Assert
        assert summary['total_inconsistencies'] == 2
        assert summary['by_entity_type']['customer'] == 1
        assert summary['by_entity_type']['loan_application'] == 1
        assert summary['by_severity']['high'] == 1
        assert summary['by_severity']['critical'] == 1
        assert summary['by_inconsistency_type']['data_mismatch'] == 1
        assert summary['by_inconsistency_type']['missing_in_blockchain'] == 1


class TestConsistencyMonitor:
    """Test consistency monitoring functionality."""
    
    @pytest.fixture
    def mock_consistency_checker(self):
        """Mock consistency checker."""
        checker = Mock(spec=DataConsistencyChecker)
        return checker
    
    @pytest.fixture
    def monitor(self, mock_consistency_checker):
        """Create consistency monitor with mocked checker."""
        return ConsistencyMonitor(mock_consistency_checker)
    
    @pytest.mark.asyncio
    async def test_check_critical_inconsistencies_generates_alert(self, monitor, mock_consistency_checker):
        """Test that critical inconsistencies generate alerts."""
        # Arrange
        critical_inconsistency = DataInconsistency(
            inconsistency_type=InconsistencyType.HASH_MISMATCH,
            severity=SeverityLevel.CRITICAL,
            entity_type='loan_document',
            entity_id='DOC001',
            blockchain_data={'documentHash': 'abc123'},
            database_data={'document_hash': 'def456'},
            description='Document hash mismatch',
            detected_at=datetime.utcnow()
        )
        
        mock_consistency_checker.get_inconsistencies.return_value = [critical_inconsistency]
        
        # Act
        await monitor._check_critical_inconsistencies()
        
        # Assert
        assert len(monitor.alerts) == 1
        alert = monitor.alerts[0]
        assert alert.alert_type == AlertType.CRITICAL_INCONSISTENCY
        assert alert.severity == SeverityLevel.CRITICAL
        assert 'DOC001' in alert.description
    
    @pytest.mark.asyncio
    async def test_check_inconsistency_trends_high_count(self, monitor, mock_consistency_checker):
        """Test that high inconsistency count generates alert."""
        # Arrange
        summary = {
            'total_inconsistencies': 150,  # Above threshold
            'by_severity': {'high': 100, 'medium': 50},
            'by_entity_type': {'customer': 75, 'loan_application': 75}
        }
        mock_consistency_checker.get_inconsistency_summary.return_value = summary
        
        # Act
        await monitor._check_inconsistency_trends()
        
        # Assert
        assert len(monitor.alerts) == 1
        alert = monitor.alerts[0]
        assert alert.alert_type == AlertType.HIGH_INCONSISTENCY_COUNT
        assert alert.severity == SeverityLevel.HIGH
        assert '150' in alert.description
    
    @pytest.mark.asyncio
    async def test_check_reconciliation_health_no_history(self, monitor, mock_consistency_checker):
        """Test reconciliation health check with no history."""
        # Arrange
        mock_consistency_checker.get_reconciliation_history.return_value = []
        
        # Act
        await monitor._check_reconciliation_health()
        
        # Assert
        assert len(monitor.alerts) == 1
        alert = monitor.alerts[0]
        assert alert.alert_type == AlertType.RECONCILIATION_FAILURE
        assert alert.severity == SeverityLevel.MEDIUM
        assert 'No reconciliation' in alert.title
    
    @pytest.mark.asyncio
    async def test_check_reconciliation_health_recent_failure(self, monitor, mock_consistency_checker):
        """Test reconciliation health check with recent failure."""
        # Arrange
        failed_report = {
            'success': False,
            'error_message': 'Database connection failed',
            'end_time': datetime.utcnow().isoformat()
        }
        mock_consistency_checker.get_reconciliation_history.return_value = [failed_report]
        
        # Act
        await monitor._check_reconciliation_health()
        
        # Assert
        assert len(monitor.alerts) == 1
        alert = monitor.alerts[0]
        assert alert.alert_type == AlertType.RECONCILIATION_FAILURE
        assert alert.severity == SeverityLevel.HIGH
        assert 'failed' in alert.description
    
    def test_acknowledge_alert_success(self, monitor):
        """Test successful alert acknowledgment."""
        # Arrange
        alert = Alert(
            alert_type=AlertType.CRITICAL_INCONSISTENCY,
            severity=SeverityLevel.CRITICAL,
            title='Test Alert',
            description='Test Description',
            details={},
            created_at=datetime.utcnow()
        )
        monitor.alerts.append(alert)
        
        # Act
        result = monitor.acknowledge_alert(0, 'test_user')
        
        # Assert
        assert result is True
        assert alert.acknowledged is True
        assert alert.acknowledged_by == 'test_user'
        assert alert.acknowledged_at is not None
    
    def test_acknowledge_alert_invalid_id(self, monitor):
        """Test alert acknowledgment with invalid ID."""
        # Act
        result = monitor.acknowledge_alert(999, 'test_user')
        
        # Assert
        assert result is False
    
    def test_get_active_alerts_filters_acknowledged(self, monitor):
        """Test that get_active_alerts filters out acknowledged alerts."""
        # Arrange
        alert1 = Alert(
            alert_type=AlertType.CRITICAL_INCONSISTENCY,
            severity=SeverityLevel.CRITICAL,
            title='Active Alert',
            description='Active',
            details={},
            created_at=datetime.utcnow()
        )
        
        alert2 = Alert(
            alert_type=AlertType.HIGH_INCONSISTENCY_COUNT,
            severity=SeverityLevel.HIGH,
            title='Acknowledged Alert',
            description='Acknowledged',
            details={},
            created_at=datetime.utcnow(),
            acknowledged=True
        )
        
        monitor.alerts.extend([alert1, alert2])
        
        # Act
        active_alerts = monitor.get_active_alerts()
        
        # Assert
        assert len(active_alerts) == 1
        assert active_alerts[0].title == 'Active Alert'
    
    def test_get_alert_summary(self, monitor):
        """Test alert summary generation."""
        # Arrange
        alerts = [
            Alert(
                alert_type=AlertType.CRITICAL_INCONSISTENCY,
                severity=SeverityLevel.CRITICAL,
                title='Critical Alert',
                description='Critical',
                details={},
                created_at=datetime.utcnow()
            ),
            Alert(
                alert_type=AlertType.HIGH_INCONSISTENCY_COUNT,
                severity=SeverityLevel.HIGH,
                title='High Alert',
                description='High',
                details={},
                created_at=datetime.utcnow()
            ),
            Alert(
                alert_type=AlertType.RECONCILIATION_FAILURE,
                severity=SeverityLevel.MEDIUM,
                title='Acknowledged Alert',
                description='Acknowledged',
                details={},
                created_at=datetime.utcnow(),
                acknowledged=True
            )
        ]
        monitor.alerts.extend(alerts)
        
        # Act
        summary = monitor.get_alert_summary()
        
        # Assert
        assert summary['total_active_alerts'] == 2  # Only unacknowledged
        assert summary['total_alerts'] == 3
        assert summary['by_severity']['critical'] == 1
        assert summary['by_severity']['high'] == 1
        assert summary['by_type']['critical_inconsistency'] == 1
        assert summary['by_type']['high_inconsistency_count'] == 1


# Integration tests
class TestConsistencyIntegration:
    """Integration tests for consistency checking components."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_consistency_check_workflow(self):
        """Test complete consistency check workflow."""
        # This would be an integration test that:
        # 1. Sets up test data in database
        # 2. Mocks blockchain responses
        # 3. Runs full reconciliation
        # 4. Verifies inconsistencies are detected
        # 5. Tests manual resync
        # 6. Verifies alerts are generated
        
        # For now, this is a placeholder for the integration test structure
        pass
    
    @pytest.mark.asyncio
    async def test_performance_under_load(self):
        """Test consistency checker performance under load."""
        # This would test:
        # 1. Large datasets (thousands of records)
        # 2. Concurrent reconciliation requests
        # 3. Memory usage patterns
        # 4. Response time metrics
        
        # For now, this is a placeholder for performance testing
        pass


if __name__ == '__main__':
    pytest.main([__file__])