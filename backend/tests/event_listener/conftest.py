"""
Test configuration for event listener tests.
"""
import pytest
import asyncio
import sys
import os
from unittest.mock import Mock, patch
from datetime import datetime

from shared.database import db_manager, ActorModel, CustomerModel, LoanApplicationModel


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db_session():
    """Mock database session for testing."""
    session = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    session.close = Mock()
    session.query = Mock()
    session.flush = Mock()
    session.refresh = Mock()
    session.expunge = Mock()
    session.expunge_all = Mock()
    return session


@pytest.fixture
def mock_db_manager(mock_db_session):
    """Mock database manager for testing."""
    manager = Mock()
    # Create a proper context manager mock
    context_manager = Mock()
    context_manager.__enter__ = Mock(return_value=mock_db_session)
    context_manager.__exit__ = Mock(return_value=None)
    manager.session_scope.return_value = context_manager
    manager.health_check.return_value = True
    return manager


@pytest.fixture
def sample_actor():
    """Sample actor for testing."""
    return ActorModel(
        id=1,
        actor_id='ACTOR001',
        actor_type='Internal_User',
        actor_name='Test Actor',
        role='Underwriter',
        blockchain_identity='cert123',
        permissions=['read', 'write'],
        is_active=True,
        created_at=datetime(2024, 1, 1, 9, 0, 0),
        updated_at=datetime(2024, 1, 1, 9, 0, 0)
    )


@pytest.fixture
def sample_customer():
    """Sample customer for testing."""
    return CustomerModel(
        id=1,
        customer_id='CUST001',
        first_name='John',
        last_name='Doe',
        date_of_birth=datetime(1990, 1, 1),
        national_id_hash='hashed_id',
        address='123 Main St',
        contact_email='john.doe@example.com',
        contact_phone='+1234567890',
        kyc_status='PENDING',
        aml_status='PENDING',
        consent_preferences={'dataSharing': True},
        created_by_actor_id=1,
        created_at=datetime(2024, 1, 1, 10, 0, 0),
        updated_at=datetime(2024, 1, 1, 10, 0, 0)
    )


@pytest.fixture
def sample_loan_application():
    """Sample loan application for testing."""
    return LoanApplicationModel(
        id=1,
        loan_application_id='LOAN001',
        customer_id=1,
        application_date=datetime(2024, 1, 1, 11, 0, 0),
        requested_amount=50000.0,
        loan_type='Personal',
        application_status='SUBMITTED',
        introducer_id='INTRO001',
        current_owner_actor_id=1,
        created_by_actor_id=1,
        created_at=datetime(2024, 1, 1, 11, 0, 0),
        updated_at=datetime(2024, 1, 1, 11, 0, 0)
    )


@pytest.fixture
def mock_fabric_gateway():
    """Mock Fabric Gateway for testing."""
    gateway = Mock()
    gateway.connect = Mock()
    gateway.disconnect = Mock()
    gateway.invoke_chaincode = Mock()
    gateway.query_chaincode = Mock()
    return gateway


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment with mocked dependencies."""
    with patch('event_listener.service.get_fabric_gateway') as mock_get_gateway:
        mock_gateway = Mock()
        mock_get_gateway.return_value = mock_gateway
        yield mock_gateway