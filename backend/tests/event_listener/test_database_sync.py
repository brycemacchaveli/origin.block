"""
Unit tests for database synchronization logic in event listener service.

Tests cover customer, loan, and compliance event handlers with error handling
and retry logic.
"""
import pytest
import asyncio
import json
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.exc import IntegrityError, OperationalError

from event_listener.service import (
    EventProcessor, EventListenerService, BlockchainEvent, EventType,
    DatabaseSyncError, RetryableError, NonRetryableError
)
from shared.database import (
    CustomerModel, LoanApplicationModel, ComplianceEventModel,
    CustomerHistoryModel, LoanApplicationHistoryModel, ActorModel
)


class TestEventProcessor:
    """Test cases for EventProcessor database synchronization."""
    
    @pytest.fixture
    def event_processor(self):
        """Create EventProcessor instance for testing."""
        return EventProcessor()
    
    @pytest.fixture
    def sample_blockchain_event(self):
        """Create sample blockchain event for testing."""
        return BlockchainEvent(
            event_type=EventType.CUSTOMER_CREATED,
            chaincode_name='customer',
            transaction_id='tx123',
            block_number=100,
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            payload={
                'customerID': 'CUST001',
                'firstName': 'John',
                'lastName': 'Doe',
                'contactEmail': 'john.doe@example.com',
                'actorID': 'ACTOR001'
            },
            raw_event={}
        )
    
    @pytest.mark.asyncio
    async def test_process_event_success(self, event_processor, sample_blockchain_event, mock_db_manager):
        """Test successful event processing."""
        with patch('event_listener.service.db_manager', mock_db_manager), \
             patch('event_listener.service.db_utils') as mock_db_utils:
            
            # Mock actor and customer creation
            mock_actor = Mock(spec=ActorModel)
            mock_actor.id = 1
            mock_db_utils.get_actor_by_actor_id.return_value = None
            mock_db_utils.create_actor.return_value = mock_actor
            mock_db_utils.get_customer_by_customer_id.return_value = None
            mock_db_utils.create_customer.return_value = Mock(id=1, customer_id='CUST001')
            
            # Process event
            result = await event_processor.process_event(sample_blockchain_event)
            
            assert result is True
            mock_db_utils.create_customer.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_event_missing_handler(self, event_processor):
        """Test processing event with no handler."""
        unknown_event = BlockchainEvent(
            event_type=Mock(),  # Unknown event type
            chaincode_name='test',
            transaction_id='tx123',
            block_number=100,
            timestamp=datetime.utcnow(),
            payload={},
            raw_event={}
        )
        unknown_event.event_type.value = 'UNKNOWN_EVENT'
        
        result = await event_processor.process_event(unknown_event)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_process_event_retryable_error(self, event_processor, sample_blockchain_event):
        """Test event processing with retryable error."""
        with patch.object(event_processor, '_process_event_with_error_handling') as mock_handler:
            mock_handler.side_effect = OperationalError("Connection lost", None, None)
            
            # The retry mechanism will exhaust retries and return False
            result = await event_processor.process_event(sample_blockchain_event)
            assert result is False
            # Should have made 3 attempts (initial + 2 retries)
            assert mock_handler.call_count == 3
    
    @pytest.mark.asyncio
    async def test_process_event_non_retryable_error(self, event_processor, sample_blockchain_event):
        """Test event processing with non-retryable error."""
        with patch.object(event_processor, '_process_event_with_error_handling') as mock_handler:
            mock_handler.side_effect = NonRetryableError("Invalid data")
            
            result = await event_processor.process_event(sample_blockchain_event)
            assert result is False
            # Should have made only 1 attempt
            assert mock_handler.call_count == 1


class TestCustomerEventHandlers:
    """Test cases for customer event handlers."""
    
    @pytest.fixture
    def event_processor(self):
        return EventProcessor()
    
    @pytest.mark.asyncio
    async def test_handle_customer_created_success(self, event_processor, mock_db_manager):
        """Test successful customer creation event handling."""
        event = BlockchainEvent(
            event_type=EventType.CUSTOMER_CREATED,
            chaincode_name='customer',
            transaction_id='tx123',
            block_number=100,
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            payload={
                'customerID': 'CUST001',
                'firstName': 'John',
                'lastName': 'Doe',
                'contactEmail': 'john.doe@example.com',
                'contactPhone': '+1234567890',
                'actorID': 'ACTOR001'
            },
            raw_event={}
        )
        
        with patch('event_listener.service.db_manager', mock_db_manager), \
             patch('event_listener.service.db_utils') as mock_db_utils:
            
            # Mock dependencies
            mock_actor = Mock(spec=ActorModel)
            mock_actor.id = 1
            mock_db_utils.get_actor_by_actor_id.return_value = None
            mock_db_utils.create_actor.return_value = mock_actor
            mock_db_utils.get_customer_by_customer_id.return_value = None
            mock_customer = Mock(id=1, customer_id='CUST001')
            mock_db_utils.create_customer.return_value = mock_customer
            
            # Execute handler
            await event_processor._handle_customer_created(event)
            
            # Verify calls
            mock_db_utils.create_customer.assert_called_once()
            customer_data = mock_db_utils.create_customer.call_args[0][0]
            assert customer_data['customer_id'] == 'CUST001'
            assert customer_data['first_name'] == 'John'
            assert customer_data['last_name'] == 'Doe'
    
    @pytest.mark.asyncio
    async def test_handle_customer_created_missing_required_field(self, event_processor):
        """Test customer creation with missing required field."""
        event = BlockchainEvent(
            event_type=EventType.CUSTOMER_CREATED,
            chaincode_name='customer',
            transaction_id='tx123',
            block_number=100,
            timestamp=datetime.utcnow(),
            payload={
                'customerID': 'CUST001',
                # Missing firstName
                'lastName': 'Doe',
                'actorID': 'ACTOR001'
            },
            raw_event={}
        )
        
        with pytest.raises(ValueError, match="Missing required field: firstName"):
            await event_processor._handle_customer_created(event)
    
    @pytest.mark.asyncio
    async def test_handle_customer_created_duplicate_customer(self, event_processor, mock_db_manager):
        """Test customer creation when customer already exists."""
        event = BlockchainEvent(
            event_type=EventType.CUSTOMER_CREATED,
            chaincode_name='customer',
            transaction_id='tx123',
            block_number=100,
            timestamp=datetime.utcnow(),
            payload={
                'customerID': 'CUST001',
                'firstName': 'John',
                'lastName': 'Doe',
                'actorID': 'ACTOR001'
            },
            raw_event={}
        )
        
        with patch('event_listener.service.db_manager', mock_db_manager), \
             patch('event_listener.service.db_utils') as mock_db_utils:
            
            # Mock existing customer
            existing_customer = Mock(spec=CustomerModel)
            mock_db_utils.get_customer_by_customer_id.return_value = existing_customer
            
            # Execute handler - should not raise error
            await event_processor._handle_customer_created(event)
            
            # Verify customer creation was not called
            mock_db_utils.create_customer.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_customer_updated_success(self, event_processor, mock_db_manager):
        """Test successful customer update event handling."""
        event = BlockchainEvent(
            event_type=EventType.CUSTOMER_UPDATED,
            chaincode_name='customer',
            transaction_id='tx123',
            block_number=100,
            timestamp=datetime.utcnow(),
            payload={
                'customerID': 'CUST001',
                'firstName': 'Jane',  # Updated name
                'contactEmail': 'jane.doe@example.com',  # Updated email
                'actorID': 'ACTOR001'
            },
            raw_event={}
        )
        
        with patch('event_listener.service.db_manager', mock_db_manager), \
             patch('event_listener.service.db_utils') as mock_db_utils:
            
            # Mock dependencies
            mock_actor = Mock(spec=ActorModel)
            mock_actor.id = 1
            mock_db_utils.get_actor_by_actor_id.return_value = mock_actor
            
            # Mock existing customer
            mock_customer = Mock(spec=CustomerModel)
            mock_customer.id = 1
            mock_customer.first_name = 'John'  # Old name
            mock_customer.contact_email = 'john.doe@example.com'  # Old email
            
            mock_session = mock_db_manager.session_scope.return_value.__enter__.return_value
            mock_session.query.return_value.filter.return_value.first.return_value = mock_customer
            
            # Execute handler
            await event_processor._handle_customer_updated(event)
            
            # Verify customer was updated
            assert mock_customer.first_name == 'Jane'
            assert mock_customer.contact_email == 'jane.doe@example.com'
    
    @pytest.mark.asyncio
    async def test_handle_customer_updated_not_found(self, event_processor, mock_db_manager):
        """Test customer update when customer doesn't exist."""
        event = BlockchainEvent(
            event_type=EventType.CUSTOMER_UPDATED,
            chaincode_name='customer',
            transaction_id='tx123',
            block_number=100,
            timestamp=datetime.utcnow(),
            payload={
                'customerID': 'CUST001',
                'firstName': 'Jane',
                'actorID': 'ACTOR001'
            },
            raw_event={}
        )
        
        with patch('event_listener.service.db_manager', mock_db_manager), \
             patch('event_listener.service.db_utils') as mock_db_utils, \
             patch.object(event_processor, '_handle_customer_created') as mock_create:
            
            # Mock dependencies
            mock_actor = Mock(spec=ActorModel)
            mock_actor.id = 1
            mock_db_utils.get_actor_by_actor_id.return_value = mock_actor
            
            # Mock customer not found
            mock_session = mock_db_manager.session_scope.return_value.__enter__.return_value
            mock_session.query.return_value.filter.return_value.first.return_value = None
            
            # Execute handler
            await event_processor._handle_customer_updated(event)
            
            # Verify customer creation was called
            mock_create.assert_called_once_with(event)


class TestLoanEventHandlers:
    """Test cases for loan event handlers."""
    
    @pytest.fixture
    def event_processor(self):
        return EventProcessor()
    
    @pytest.mark.asyncio
    async def test_handle_loan_application_submitted_success(self, event_processor, mock_db_manager):
        """Test successful loan application submission event handling."""
        event = BlockchainEvent(
            event_type=EventType.LOAN_APPLICATION_SUBMITTED,
            chaincode_name='loan',
            transaction_id='tx123',
            block_number=100,
            timestamp=datetime.utcnow(),
            payload={
                'loanApplicationID': 'LOAN001',
                'customerID': 'CUST001',
                'requestedAmount': '50000.00',
                'loanType': 'Personal',
                'actorID': 'ACTOR001'
            },
            raw_event={}
        )
        
        with patch('event_listener.service.db_manager', mock_db_manager), \
             patch('event_listener.service.db_utils') as mock_db_utils:
            
            # Mock dependencies
            mock_actor = Mock(spec=ActorModel)
            mock_actor.id = 1
            mock_db_utils.get_actor_by_actor_id.return_value = mock_actor
            mock_db_utils.get_loan_by_loan_id.return_value = None
            
            mock_customer = Mock(spec=CustomerModel)
            mock_customer.id = 1
            mock_customer.customer_id = 'CUST001'
            mock_db_utils.get_customer_by_customer_id.return_value = mock_customer
            
            mock_loan = Mock(id=1, loan_application_id='LOAN001')
            mock_db_utils.create_loan_application.return_value = mock_loan
            
            # Execute handler
            await event_processor._handle_loan_application_submitted(event)
            
            # Verify calls
            mock_db_utils.create_loan_application.assert_called_once()
            loan_data = mock_db_utils.create_loan_application.call_args[0][0]
            assert loan_data['loan_application_id'] == 'LOAN001'
            assert loan_data['requested_amount'] == 50000.00
    
    @pytest.mark.asyncio
    async def test_handle_loan_application_submitted_invalid_amount(self, event_processor, mock_db_manager):
        """Test loan application submission with invalid amount."""
        event = BlockchainEvent(
            event_type=EventType.LOAN_APPLICATION_SUBMITTED,
            chaincode_name='loan',
            transaction_id='tx123',
            block_number=100,
            timestamp=datetime.utcnow(),
            payload={
                'loanApplicationID': 'LOAN001',
                'customerID': 'CUST001',
                'requestedAmount': 'invalid_amount',
                'loanType': 'Personal',
                'actorID': 'ACTOR001'
            },
            raw_event={}
        )
        
        with patch('event_listener.service.db_manager', mock_db_manager), \
             patch('event_listener.service.db_utils') as mock_db_utils:
            
            # Mock dependencies
            mock_actor = Mock(spec=ActorModel)
            mock_actor.id = 1
            mock_db_utils.get_actor_by_actor_id.return_value = None
            mock_db_utils.create_actor.return_value = mock_actor
            mock_db_utils.get_loan_by_loan_id.return_value = None
            
            mock_customer = Mock(spec=CustomerModel)
            mock_customer.id = 1
            mock_customer.customer_id = 'CUST001'
            mock_db_utils.get_customer_by_customer_id.return_value = mock_customer
            
            with pytest.raises(DatabaseSyncError, match="Invalid requested amount"):
                await event_processor._handle_loan_application_submitted(event)
    
    @pytest.mark.asyncio
    async def test_handle_loan_application_submitted_customer_not_found(self, event_processor, mock_db_manager):
        """Test loan application submission when customer doesn't exist."""
        event = BlockchainEvent(
            event_type=EventType.LOAN_APPLICATION_SUBMITTED,
            chaincode_name='loan',
            transaction_id='tx123',
            block_number=100,
            timestamp=datetime.utcnow(),
            payload={
                'loanApplicationID': 'LOAN001',
                'customerID': 'CUST001',
                'requestedAmount': '50000.00',
                'loanType': 'Personal',
                'actorID': 'ACTOR001'
            },
            raw_event={}
        )
        
        with patch('event_listener.service.db_manager', mock_db_manager), \
             patch('event_listener.service.db_utils') as mock_db_utils:
            
            # Mock dependencies
            mock_actor = Mock(spec=ActorModel)
            mock_actor.id = 1
            mock_db_utils.get_actor_by_actor_id.return_value = mock_actor
            mock_db_utils.get_loan_by_loan_id.return_value = None
            mock_db_utils.get_customer_by_customer_id.return_value = None
            
            with pytest.raises(ValueError, match="Customer not found"):
                await event_processor._handle_loan_application_submitted(event)
    
    @pytest.mark.asyncio
    async def test_handle_loan_application_status_updated_success(self, event_processor, mock_db_manager):
        """Test successful loan application status update event handling."""
        event = BlockchainEvent(
            event_type=EventType.LOAN_APPLICATION_STATUS_UPDATED,
            chaincode_name='loan',
            transaction_id='tx123',
            block_number=100,
            timestamp=datetime.utcnow(),
            payload={
                'loanApplicationID': 'LOAN001',
                'newStatus': 'APPROVED',
                'actorID': 'ACTOR001'
            },
            raw_event={}
        )
        
        with patch('event_listener.service.db_manager', mock_db_manager), \
             patch('event_listener.service.db_utils') as mock_db_utils:
            
            # Mock dependencies
            mock_actor = Mock(spec=ActorModel)
            mock_actor.id = 1
            mock_db_utils.get_actor_by_actor_id.return_value = mock_actor
            
            # Mock existing loan
            mock_loan = Mock(spec=LoanApplicationModel)
            mock_loan.id = 1
            mock_loan.application_status = 'SUBMITTED'
            
            mock_session = mock_db_manager.session_scope.return_value.__enter__.return_value
            mock_session.query.return_value.filter.return_value.first.return_value = mock_loan
            
            # Execute handler
            await event_processor._handle_loan_application_status_updated(event)
            
            # Verify loan status was updated
            assert mock_loan.application_status == 'APPROVED'


class TestComplianceEventHandlers:
    """Test cases for compliance event handlers."""
    
    @pytest.fixture
    def event_processor(self):
        return EventProcessor()
    
    @pytest.mark.asyncio
    async def test_create_compliance_event_record_success(self, event_processor, mock_db_manager):
        """Test successful compliance event record creation."""
        event = BlockchainEvent(
            event_type=EventType.COMPLIANCE_EVENT_RECORDED,
            chaincode_name='compliance',
            transaction_id='tx123',
            block_number=100,
            timestamp=datetime.utcnow(),
            payload={
                'eventID': 'COMP001',
                'ruleID': 'RULE001',
                'affectedEntityType': 'CUSTOMER',
                'affectedEntityID': 'CUST001',
                'severity': 'WARNING',
                'details': 'AML check failed',
                'actorID': 'ACTOR001'
            },
            raw_event={}
        )
        
        with patch('event_listener.service.db_manager', mock_db_manager), \
             patch('event_listener.service.db_utils') as mock_db_utils:
            
            # Mock dependencies
            mock_actor = Mock(spec=ActorModel)
            mock_actor.id = 1
            mock_db_utils.get_actor_by_actor_id.return_value = mock_actor
            
            # Mock no existing event
            mock_session = mock_db_manager.session_scope.return_value.__enter__.return_value
            mock_session.query.return_value.filter.return_value.first.return_value = None
            
            mock_compliance_event = Mock(event_id='COMP001')
            mock_db_utils.create_compliance_event.return_value = mock_compliance_event
            
            # Execute handler
            await event_processor._create_compliance_event_record(event, 'COMPLIANCE_CHECK')
            
            # Verify calls
            mock_db_utils.create_compliance_event.assert_called_once()
            event_data = mock_db_utils.create_compliance_event.call_args[0][0]
            assert event_data['event_id'] == 'COMP001'
            assert event_data['event_type'] == 'COMPLIANCE_CHECK'
            assert event_data['severity'] == 'WARNING'


class TestEventListenerService:
    """Test cases for EventListenerService database synchronization."""
    
    @pytest.fixture
    def event_listener_service(self):
        return EventListenerService()
    
    @pytest.mark.asyncio
    async def test_process_raw_event_success(self, event_listener_service):
        """Test successful raw event processing."""
        raw_event = {
            'eventName': 'CustomerCreated',
            'chaincodeId': 'customer',
            'txId': 'tx123',
            'blockNumber': 100,
            'timestamp': '2024-01-01T12:00:00Z',
            'payload': json.dumps({
                'customerID': 'CUST001',
                'firstName': 'John',
                'lastName': 'Doe',
                'actorID': 'ACTOR001'
            })
        }
        
        with patch.object(event_listener_service.event_processor, 'process_event') as mock_process:
            mock_process.return_value = True
            
            result = await event_listener_service.process_raw_event(raw_event)
            
            assert result is True
            assert event_listener_service.sync_stats['total_events'] == 1
            assert event_listener_service.sync_stats['successful_events'] == 1
    
    @pytest.mark.asyncio
    async def test_process_raw_event_duplicate(self, event_listener_service):
        """Test processing duplicate raw event."""
        raw_event = {
            'eventName': 'CustomerCreated',
            'chaincodeId': 'customer',
            'txId': 'tx123',
            'blockNumber': 100,
            'timestamp': '2024-01-01T12:00:00Z',
            'payload': json.dumps({
                'customerID': 'CUST001',
                'firstName': 'John',
                'lastName': 'Doe',
                'actorID': 'ACTOR001'
            })
        }
        
        # Add event to processed events
        event_key = "tx123_CustomerCreated"
        event_listener_service.processed_events.add(event_key)
        
        result = await event_listener_service.process_raw_event(raw_event)
        
        assert result is True
        assert event_listener_service.sync_stats['duplicate_events'] == 1
    
    @pytest.mark.asyncio
    async def test_process_raw_event_failure(self, event_listener_service):
        """Test raw event processing failure."""
        raw_event = {
            'eventName': 'CustomerCreated',
            'chaincodeId': 'customer',
            'txId': 'tx123',
            'blockNumber': 100,
            'timestamp': '2024-01-01T12:00:00Z',
            'payload': json.dumps({
                'customerID': 'CUST001',
                'firstName': 'John',
                'lastName': 'Doe',
                'actorID': 'ACTOR001'
            })
        }
        
        with patch.object(event_listener_service.event_processor, 'process_event') as mock_process:
            mock_process.return_value = False
            
            result = await event_listener_service.process_raw_event(raw_event)
            
            assert result is False
            assert event_listener_service.sync_stats['failed_events'] == 1
            assert len(event_listener_service.failed_events) == 1
    
    @pytest.mark.asyncio
    async def test_retry_failed_events_success(self, event_listener_service):
        """Test successful retry of failed events."""
        # Add a failed event
        failed_event = {
            'raw_event': {
                'eventName': 'CustomerCreated',
                'txId': 'tx123',
                'payload': json.dumps({'customerID': 'CUST001'})
            },
            'event_key': 'tx123_CustomerCreated',
            'failed_at': datetime.utcnow(),
            'retry_count': 0
        }
        event_listener_service.failed_events.append(failed_event)
        
        with patch.object(event_listener_service, 'process_raw_event') as mock_process:
            mock_process.return_value = True
            
            retry_stats = await event_listener_service.retry_failed_events()
            
            assert retry_stats['attempted'] == 1
            assert retry_stats['successful'] == 1
            assert retry_stats['failed'] == 0
            assert len(event_listener_service.failed_events) == 0
    
    @pytest.mark.asyncio
    async def test_retry_failed_events_max_retries_exceeded(self, event_listener_service):
        """Test retry of failed events with max retries exceeded."""
        # Add a failed event with max retries already reached
        failed_event = {
            'raw_event': {
                'eventName': 'CustomerCreated',
                'txId': 'tx123',
                'payload': json.dumps({'customerID': 'CUST001'})
            },
            'event_key': 'tx123_CustomerCreated',
            'failed_at': datetime.utcnow(),
            'retry_count': 3  # Already at max retries
        }
        event_listener_service.failed_events.append(failed_event)
        
        retry_stats = await event_listener_service.retry_failed_events(max_retries=3)
        
        assert retry_stats['attempted'] == 1
        assert retry_stats['skipped'] == 1
        assert retry_stats['successful'] == 0
    
    def test_get_sync_statistics(self, event_listener_service):
        """Test getting synchronization statistics."""
        # Set some test statistics
        event_listener_service.sync_stats['total_events'] = 100
        event_listener_service.sync_stats['successful_events'] = 95
        event_listener_service.sync_stats['failed_events'] = 5
        event_listener_service.failed_events = [{'test': 'event'}]
        
        stats = event_listener_service.get_sync_statistics()
        
        assert stats['total_events'] == 100
        assert stats['successful_events'] == 95
        assert stats['failed_events'] == 5
        assert stats['success_rate'] == 0.95
        assert stats['failed_events_pending'] == 1
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, event_listener_service):
        """Test health check when service is healthy."""
        event_listener_service.running = True
        event_listener_service.sync_stats['last_sync_time'] = datetime.utcnow()
        
        with patch('event_listener.service.db_manager') as mock_db_manager:
            mock_db_manager.health_check.return_value = True
            
            health_status = await event_listener_service.health_check()
            
            assert health_status['service_running'] is True
            assert health_status['database_healthy'] is True
            assert health_status['recent_sync_activity'] is True
            assert health_status['overall_healthy'] is True
    
    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, event_listener_service):
        """Test health check when service is unhealthy."""
        event_listener_service.running = False
        event_listener_service.failed_events = [{'test': 'event'}] * 150  # Too many failures
        
        with patch('event_listener.service.db_manager') as mock_db_manager:
            mock_db_manager.health_check.return_value = False
            
            health_status = await event_listener_service.health_check()
            
            assert health_status['service_running'] is False
            assert health_status['database_healthy'] is False
            assert health_status['failed_events_count'] == 150
            assert health_status['overall_healthy'] is False