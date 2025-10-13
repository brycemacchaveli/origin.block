"""
Unit tests for error handling and retry logic in event listener service.

Tests cover database connection failures, integrity errors, and retry mechanisms.
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from event_listener.service import (
    EventProcessor, EventListenerService, BlockchainEvent, EventType,
    DatabaseSyncError, RetryableError, NonRetryableError
)


class TestErrorHandling:
    """Test cases for error handling in database synchronization."""
    
    @pytest.fixture
    def event_processor(self):
        return EventProcessor()
    
    @pytest.fixture
    def sample_event(self):
        return BlockchainEvent(
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
    
    @pytest.mark.asyncio
    async def test_integrity_error_duplicate_key(self, event_processor, sample_event):
        """Test handling of duplicate key integrity errors."""
        with patch.object(event_processor, '_handle_customer_created') as mock_handler:
            # Simulate duplicate key error
            mock_handler.side_effect = IntegrityError(
                "duplicate key value violates unique constraint",
                None, None
            )
            
            # Should not raise exception for duplicate key
            await event_processor._process_event_with_error_handling(mock_handler, sample_event)
    
    @pytest.mark.asyncio
    async def test_integrity_error_other(self, event_processor, sample_event):
        """Test handling of non-duplicate integrity errors."""
        with patch.object(event_processor, '_handle_customer_created') as mock_handler:
            # Simulate other integrity error
            mock_handler.side_effect = IntegrityError(
                "foreign key constraint violation",
                None, None
            )
            
            with pytest.raises(RetryableError):
                await event_processor._process_event_with_error_handling(mock_handler, sample_event)
    
    @pytest.mark.asyncio
    async def test_operational_error_retry(self, event_processor, sample_event):
        """Test handling of operational errors that should be retried."""
        with patch.object(event_processor, '_handle_customer_created') as mock_handler:
            mock_handler.side_effect = OperationalError(
                "connection timeout",
                None, None
            )
            
            with pytest.raises(RetryableError):
                await event_processor._process_event_with_error_handling(mock_handler, sample_event)
    
    @pytest.mark.asyncio
    async def test_sqlalchemy_error_retry(self, event_processor, sample_event):
        """Test handling of SQLAlchemy errors that should be retried."""
        with patch.object(event_processor, '_handle_customer_created') as mock_handler:
            mock_handler.side_effect = SQLAlchemyError("database error")
            
            with pytest.raises(RetryableError):
                await event_processor._process_event_with_error_handling(mock_handler, sample_event)
    
    @pytest.mark.asyncio
    async def test_value_error_no_retry(self, event_processor, sample_event):
        """Test handling of value errors that should not be retried."""
        with patch.object(event_processor, '_handle_customer_created') as mock_handler:
            mock_handler.side_effect = ValueError("Invalid data format")
            
            with pytest.raises(NonRetryableError):
                await event_processor._process_event_with_error_handling(mock_handler, sample_event)
    
    @pytest.mark.asyncio
    async def test_key_error_no_retry(self, event_processor, sample_event):
        """Test handling of key errors that should not be retried."""
        with patch.object(event_processor, '_handle_customer_created') as mock_handler:
            mock_handler.side_effect = KeyError("missing_field")
            
            with pytest.raises(NonRetryableError):
                await event_processor._process_event_with_error_handling(mock_handler, sample_event)


class TestRetryMechanism:
    """Test cases for retry mechanism in event processing."""
    
    @pytest.fixture
    def event_processor(self):
        return EventProcessor()
    
    @pytest.fixture
    def sample_event(self):
        return BlockchainEvent(
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
    
    @pytest.mark.asyncio
    async def test_retry_success_after_failure(self, event_processor, sample_event):
        """Test successful retry after initial failure."""
        call_count = 0
        
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OperationalError("connection lost", None, None)
            # Success on second attempt
            return None
        
        with patch.object(event_processor, '_process_event_with_error_handling') as mock_handler:
            mock_handler.side_effect = side_effect
            
            result = await event_processor.process_event(sample_event)
            
            assert result is True
            assert call_count == 2  # Initial attempt + 1 retry
    
    @pytest.mark.asyncio
    async def test_retry_exhausted(self, event_processor, sample_event):
        """Test retry mechanism when all attempts are exhausted."""
        with patch.object(event_processor, '_process_event_with_error_handling') as mock_handler:
            # Always fail with retryable error
            mock_handler.side_effect = OperationalError("persistent error", None, None)
            
            result = await event_processor.process_event(sample_event)
            
            assert result is False
            # Should have made 3 attempts (initial + 2 retries)
            assert mock_handler.call_count == 3
    
    @pytest.mark.asyncio
    async def test_no_retry_for_non_retryable_error(self, event_processor, sample_event):
        """Test that non-retryable errors are not retried."""
        with patch.object(event_processor, '_process_event_with_error_handling') as mock_handler:
            mock_handler.side_effect = ValueError("invalid data")
            
            result = await event_processor.process_event(sample_event)
            
            assert result is False
            # Should have made only 1 attempt
            assert mock_handler.call_count == 1


class TestDatabaseConnectionHandling:
    """Test cases for database connection handling."""
    
    @pytest.fixture
    def event_listener_service(self):
        return EventListenerService()
    
    @pytest.mark.asyncio
    async def test_database_connection_recovery(self, event_listener_service):
        """Test database connection recovery after failure."""
        raw_event = {
            'eventName': 'CustomerCreated',
            'chaincodeId': 'customer',
            'txId': 'tx123',
            'blockNumber': 100,
            'timestamp': '2024-01-01T12:00:00Z',
            'payload': '{"customerID": "CUST001", "firstName": "John", "lastName": "Doe"}'
        }
        
        call_count = 0
        
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call fails with connection error
                raise OperationalError("connection lost", None, None)
            # Second call succeeds
            return True
        
        with patch.object(event_listener_service.event_processor, 'process_event') as mock_process:
            mock_process.side_effect = side_effect
            
            result = await event_listener_service.process_raw_event(raw_event)
            
            assert result is True
            assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_database_health_check_failure(self, event_listener_service):
        """Test health check when database is unhealthy."""
        with patch('event_listener.service.db_manager') as mock_db_manager:
            mock_db_manager.health_check.side_effect = Exception("Database connection failed")
            
            health_status = await event_listener_service.health_check()
            
            assert health_status['database_healthy'] is False
            assert health_status['overall_healthy'] is False
            assert 'error' in health_status


class TestEventValidation:
    """Test cases for event data validation."""
    
    @pytest.fixture
    def event_processor(self):
        return EventProcessor()
    
    @pytest.mark.asyncio
    async def test_customer_creation_missing_customer_id(self, event_processor):
        """Test customer creation with missing customer ID."""
        event = BlockchainEvent(
            event_type=EventType.CUSTOMER_CREATED,
            chaincode_name='customer',
            transaction_id='tx123',
            block_number=100,
            timestamp=datetime.utcnow(),
            payload={
                # Missing customerID
                'firstName': 'John',
                'lastName': 'Doe',
                'actorID': 'ACTOR001'
            },
            raw_event={}
        )
        
        with pytest.raises(ValueError, match="Missing required field: customerID"):
            await event_processor._handle_customer_created(event)
    
    @pytest.mark.asyncio
    async def test_loan_submission_invalid_amount_format(self, event_processor):
        """Test loan submission with invalid amount format."""
        event = BlockchainEvent(
            event_type=EventType.LOAN_APPLICATION_SUBMITTED,
            chaincode_name='loan',
            transaction_id='tx123',
            block_number=100,
            timestamp=datetime.utcnow(),
            payload={
                'loanApplicationID': 'LOAN001',
                'customerID': 'CUST001',
                'requestedAmount': 'not_a_number',
                'loanType': 'Personal',
                'actorID': 'ACTOR001'
            },
            raw_event={}
        )
        
        with pytest.raises(ValueError, match="Invalid requested amount"):
            await event_processor._handle_loan_application_submitted(event)
    
    @pytest.mark.asyncio
    async def test_loan_submission_negative_amount(self, event_processor, mock_db_manager):
        """Test loan submission with negative amount."""
        event = BlockchainEvent(
            event_type=EventType.LOAN_APPLICATION_SUBMITTED,
            chaincode_name='loan',
            transaction_id='tx123',
            block_number=100,
            timestamp=datetime.utcnow(),
            payload={
                'loanApplicationID': 'LOAN001',
                'customerID': 'CUST001',
                'requestedAmount': '-1000.00',
                'loanType': 'Personal',
                'actorID': 'ACTOR001'
            },
            raw_event={}
        )
        
        with patch('event_listener.service.db_manager', mock_db_manager), \
             patch('event_listener.service.db_utils') as mock_db_utils:
            
            # Mock dependencies
            mock_actor = Mock()
            mock_actor.id = 1
            mock_db_utils.get_actor_by_actor_id.return_value = mock_actor
            mock_db_utils.get_loan_by_loan_id.return_value = None
            
            with pytest.raises(ValueError, match="Requested amount must be positive"):
                await event_processor._handle_loan_application_submitted(event)


class TestConcurrencyHandling:
    """Test cases for handling concurrent event processing."""
    
    @pytest.fixture
    def event_listener_service(self):
        return EventListenerService()
    
    @pytest.mark.asyncio
    async def test_concurrent_event_processing(self, event_listener_service):
        """Test processing multiple events concurrently."""
        raw_events = []
        for i in range(5):
            raw_events.append({
                'eventName': 'CustomerCreated',
                'chaincodeId': 'customer',
                'txId': f'tx{i}',
                'blockNumber': 100 + i,
                'timestamp': '2024-01-01T12:00:00Z',
                'payload': f'{{"customerID": "CUST{i:03d}", "firstName": "John{i}", "lastName": "Doe"}}'
            })
        
        with patch.object(event_listener_service.event_processor, 'process_event') as mock_process:
            mock_process.return_value = True
            
            # Process events concurrently
            tasks = [event_listener_service.process_raw_event(event) for event in raw_events]
            results = await asyncio.gather(*tasks)
            
            assert all(results)
            assert event_listener_service.sync_stats['total_events'] == 5
            assert event_listener_service.sync_stats['successful_events'] == 5
    
    @pytest.mark.asyncio
    async def test_duplicate_event_detection_concurrent(self, event_listener_service):
        """Test duplicate event detection with concurrent processing."""
        # Same event processed multiple times
        raw_event = {
            'eventName': 'CustomerCreated',
            'chaincodeId': 'customer',
            'txId': 'tx123',
            'blockNumber': 100,
            'timestamp': '2024-01-01T12:00:00Z',
            'payload': '{"customerID": "CUST001", "firstName": "John", "lastName": "Doe"}'
        }
        
        with patch.object(event_listener_service.event_processor, 'process_event') as mock_process:
            mock_process.return_value = True
            
            # Process same event multiple times concurrently
            tasks = [event_listener_service.process_raw_event(raw_event) for _ in range(3)]
            results = await asyncio.gather(*tasks)
            
            # All should return True, but only one should be processed
            assert all(results)
            assert event_listener_service.sync_stats['total_events'] == 3
            assert event_listener_service.sync_stats['successful_events'] == 1
            assert event_listener_service.sync_stats['duplicate_events'] == 2