"""
Event Listener service-specific test configuration and fixtures.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import json


@pytest.fixture
def event_listener_mock_db_utils():
    """Mock database utilities specifically for event listener tests."""
    mock_db_utils = Mock()
    
    # Configure common event listener database operations
    mock_db_utils.create_customer_history.return_value = True
    mock_db_utils.create_loan_history.return_value = True
    mock_db_utils.create_compliance_event.return_value = Mock()
    
    return mock_db_utils


@pytest.fixture
def sample_blockchain_event():
    """Sample blockchain event data."""
    return {
        "event_type": "CUSTOMER_CREATED",
        "transaction_id": "tx_123456789",
        "block_number": 100,
        "timestamp": datetime.utcnow().isoformat(),
        "payload": {
            "customer_id": "CUST_123456789ABC",
            "actor_id": "customer_service_001",
            "action": "CREATE",
            "data": {
                "first_name": "John",
                "last_name": "Doe",
                "kyc_status": "PENDING"
            }
        }
    }


@pytest.fixture
def sample_loan_event():
    """Sample loan blockchain event data."""
    return {
        "event_type": "LOAN_STATUS_CHANGED",
        "transaction_id": "tx_987654321",
        "block_number": 101,
        "timestamp": datetime.utcnow().isoformat(),
        "payload": {
            "loan_application_id": "LOAN_123456",
            "actor_id": "underwriter_001",
            "action": "STATUS_CHANGE",
            "previous_status": "SUBMITTED",
            "new_status": "UNDERWRITING"
        }
    }


@pytest.fixture
def sample_compliance_event():
    """Sample compliance blockchain event data."""
    return {
        "event_type": "COMPLIANCE_CHECK",
        "transaction_id": "tx_555666777",
        "block_number": 102,
        "timestamp": datetime.utcnow().isoformat(),
        "payload": {
            "entity_type": "CUSTOMER",
            "entity_id": "CUST_123456789ABC",
            "check_type": "AML_SCREENING",
            "result": "CLEAR",
            "actor_id": "system"
        }
    }


@pytest.fixture
def mock_blockchain_listener():
    """Mock blockchain event listener."""
    listener = AsyncMock()
    listener.start_listening.return_value = None
    listener.stop_listening.return_value = None
    listener.is_listening = True
    return listener


@pytest.fixture
def mock_event_processor():
    """Mock event processor."""
    with patch('event_listener.service.EventProcessor') as mock_processor:
        processor_instance = AsyncMock()
        processor_instance.process_event.return_value = True
        mock_processor.return_value = processor_instance
        yield processor_instance


@pytest.fixture
def mock_fabric_event_stream():
    """Mock Fabric event stream."""
    with patch('event_listener.service.FabricEventStream') as mock_stream:
        stream_instance = AsyncMock()
        stream_instance.subscribe.return_value = None
        stream_instance.unsubscribe.return_value = None
        mock_stream.return_value = stream_instance
        yield stream_instance