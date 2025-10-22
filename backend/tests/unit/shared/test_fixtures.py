"""
Shared test fixtures and utilities for all test domains.

This module provides common fixtures that can be used across different
domain test suites to ensure consistency and reduce duplication.
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock
from fastapi.testclient import TestClient

from main import app
from shared.auth import Actor, ActorType, Role, Permission, jwt_manager
from shared.database import (
    DatabaseManager, DatabaseUtilities, ActorModel, CustomerModel,
    LoanApplicationModel, ComplianceEventModel
)


@pytest.fixture(scope="session")
def test_client():
    """Create FastAPI test client for the entire test session."""
    return TestClient(app)


@pytest.fixture
def temp_db_path():
    """Create a temporary database file for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield f"sqlite:///{path}"
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def test_db_manager(temp_db_path):
    """Create a test database manager with temporary database."""
    manager = DatabaseManager(temp_db_path)
    manager.create_tables()
    yield manager
    manager.drop_tables()


@pytest.fixture
def test_db_utils(test_db_manager):
    """Create test database utilities."""
    return DatabaseUtilities(test_db_manager)


# Actor Fixtures
@pytest.fixture
def system_actor():
    """Create system actor for testing."""
    return Actor(
        actor_id="system",
        actor_type=ActorType.SYSTEM,
        actor_name="System",
        role=Role.SYSTEM_ADMINISTRATOR,
        permissions=set(Permission)  # All permissions
    )


@pytest.fixture
def underwriter_actor():
    """Create underwriter actor for testing."""
    return Actor(
        actor_id="underwriter_001",
        actor_type=ActorType.INTERNAL_USER,
        actor_name="Test Underwriter",
        role=Role.UNDERWRITER,
        permissions={
            Permission.READ_CUSTOMER,
            Permission.READ_LOAN_APPLICATION,
            Permission.UPDATE_LOAN_APPLICATION,
            Permission.READ_LOAN_HISTORY
        }
    )


@pytest.fixture
def credit_officer_actor():
    """Create credit officer actor for testing."""
    return Actor(
        actor_id="credit_officer_001",
        actor_type=ActorType.INTERNAL_USER,
        actor_name="Test Credit Officer",
        role=Role.CREDIT_OFFICER,
        permissions={
            Permission.READ_LOAN_APPLICATION,
            Permission.APPROVE_LOAN,
            Permission.REJECT_LOAN,
            Permission.READ_LOAN_HISTORY
        }
    )


@pytest.fixture
def customer_service_actor():
    """Create customer service actor for testing."""
    return Actor(
        actor_id="customer_service_001",
        actor_type=ActorType.INTERNAL_USER,
        actor_name="Test Customer Service Rep",
        role=Role.CUSTOMER_SERVICE_REP,
        permissions={
            Permission.CREATE_CUSTOMER,
            Permission.READ_CUSTOMER,
            Permission.UPDATE_CUSTOMER,
            Permission.READ_CUSTOMER_HISTORY,
            Permission.MANAGE_CUSTOMER_CONSENT
        }
    )


@pytest.fixture
def introducer_actor():
    """Create introducer actor for testing."""
    return Actor(
        actor_id="introducer_001",
        actor_type=ActorType.EXTERNAL_PARTNER,
        actor_name="Test Introducer",
        role=Role.INTRODUCER,
        permissions={
            Permission.CREATE_LOAN_APPLICATION,
            Permission.READ_LOAN_APPLICATION,
            Permission.MANAGE_LOAN_DOCUMENTS
        }
    )


@pytest.fixture
def compliance_officer_actor():
    """Create compliance officer actor for testing."""
    return Actor(
        actor_id="compliance_001",
        actor_type=ActorType.INTERNAL_USER,
        actor_name="Test Compliance Officer",
        role=Role.COMPLIANCE_OFFICER,
        permissions={
            Permission.READ_COMPLIANCE_EVENTS,
            Permission.CREATE_COMPLIANCE_EVENTS,
            Permission.ACCESS_REGULATORY_VIEW
        }
    )


@pytest.fixture
def regulator_actor():
    """Create regulator actor for testing."""
    return Actor(
        actor_id="regulator_001",
        actor_type=ActorType.REGULATOR,
        actor_name="Test Regulator",
        role=Role.REGULATOR,
        permissions={
            Permission.ACCESS_REGULATORY_VIEW,
            Permission.READ_COMPLIANCE_EVENTS,
            Permission.READ_CUSTOMER_HISTORY,
            Permission.READ_LOAN_HISTORY
        }
    )


# Authentication Fixtures
@pytest.fixture
def auth_headers_underwriter(underwriter_actor):
    """Create authentication headers for underwriter."""
    token = jwt_manager.create_access_token(underwriter_actor)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_credit_officer(credit_officer_actor):
    """Create authentication headers for credit officer."""
    token = jwt_manager.create_access_token(credit_officer_actor)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_customer_service(customer_service_actor):
    """Create authentication headers for customer service."""
    token = jwt_manager.create_access_token(customer_service_actor)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_introducer(introducer_actor):
    """Create authentication headers for introducer."""
    token = jwt_manager.create_access_token(introducer_actor)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_compliance(compliance_officer_actor):
    """Create authentication headers for compliance officer."""
    token = jwt_manager.create_access_token(compliance_officer_actor)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_regulator(regulator_actor):
    """Create authentication headers for regulator."""
    token = jwt_manager.create_access_token(regulator_actor)
    return {"Authorization": f"Bearer {token}"}


# Sample Data Fixtures
@pytest.fixture
def sample_customer_data():
    """Sample customer data for testing."""
    return {
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1990-01-01T00:00:00",
        "national_id": "123456789",
        "address": "123 Main St, City, State 12345",
        "contact_email": "john.doe@example.com",
        "contact_phone": "+1-555-123-4567",
        "consent_preferences": {
            "data_sharing": True,
            "marketing": False,
            "analytics": True
        }
    }


@pytest.fixture
def sample_loan_data():
    """Sample loan application data for testing."""
    return {
        "customer_id": "CUST_123456789ABC",
        "requested_amount": 50000.0,
        "loan_type": "PERSONAL",
        "introducer_id": "INTRO_001",
        "additional_info": {
            "purpose": "Home improvement",
            "employment_status": "Full-time"
        }
    }


@pytest.fixture
def sample_compliance_event_data():
    """Sample compliance event data for testing."""
    return {
        "event_type": "AML_CHECK",
        "affected_entity_type": "CUSTOMER",
        "affected_entity_id": "CUST_123456789ABC",
        "severity": "INFO",
        "description": "AML check performed",
        "details": {"check_result": "CLEAR"}
    }


# Mock Database Objects
@pytest.fixture
def mock_db_customer():
    """Mock database customer object."""
    customer = Mock(spec=CustomerModel)
    customer.id = 1
    customer.customer_id = "CUST_123456789ABC"
    customer.first_name = "John"
    customer.last_name = "Doe"
    customer.date_of_birth = datetime(1990, 1, 1)
    customer.national_id_hash = "hashed_national_id"
    customer.address = "123 Main St, City, State 12345"
    customer.contact_email = "john.doe@example.com"
    customer.contact_phone = "+1-555-123-4567"
    customer.kyc_status = "PENDING"
    customer.aml_status = "PENDING"
    customer.consent_preferences = {"data_sharing": True, "marketing": False}
    customer.created_at = datetime.utcnow()
    customer.updated_at = datetime.utcnow()
    customer.created_by_actor_id = 1
    return customer


@pytest.fixture
def mock_db_actor():
    """Mock database actor object."""
    actor = Mock(spec=ActorModel)
    actor.id = 1
    actor.actor_id = "test_actor_001"
    actor.actor_type = "Internal_User"
    actor.actor_name = "Test Actor"
    actor.role = "Underwriter"
    actor.blockchain_identity = None
    actor.permissions = ["read_customer", "read_loan_application"]
    actor.is_active = True
    actor.created_at = datetime.utcnow()
    actor.updated_at = datetime.utcnow()
    return actor


@pytest.fixture
def mock_db_loan(mock_db_customer):
    """Mock database loan application object."""
    loan = Mock(spec=LoanApplicationModel)
    loan.id = 1
    loan.loan_application_id = "LOAN_123456"
    loan.customer_id = 1
    loan.application_date = datetime.utcnow()
    loan.requested_amount = 50000.0
    loan.loan_type = "PERSONAL"
    loan.application_status = "SUBMITTED"
    loan.introducer_id = "INTRO_001"
    loan.current_owner_actor_id = 1
    loan.approval_amount = None
    loan.rejection_reason = None
    loan.created_at = datetime.utcnow()
    loan.updated_at = datetime.utcnow()
    loan.customer = mock_db_customer
    return loan


@pytest.fixture
def mock_db_compliance_event():
    """Mock database compliance event object."""
    event = Mock(spec=ComplianceEventModel)
    event.id = 1
    event.event_id = "EVENT_123456"
    event.event_type = "AML_CHECK"
    event.affected_entity_type = "CUSTOMER"
    event.affected_entity_id = "CUST_123456789ABC"
    event.severity = "INFO"
    event.description = "AML check performed"
    event.details = {"check_result": "CLEAR"}
    event.resolution_status = "RESOLVED"
    event.created_at = datetime.utcnow()
    event.updated_at = datetime.utcnow()
    event.actor_id = 1
    return event


# Blockchain Mock Fixtures
@pytest.fixture
def mock_fabric_gateway():
    """Mock Fabric Gateway for testing."""
    gateway = AsyncMock()
    gateway.invoke_chaincode.return_value = {
        "transaction_id": "tx_123456",
        "status": "SUCCESS",
        "timestamp": datetime.utcnow().isoformat()
    }
    gateway.query_chaincode.return_value = {
        "status": "SUCCESS",
        "payload": '{"result": "test_data"}',
        "timestamp": datetime.utcnow().isoformat()
    }
    return gateway


@pytest.fixture
def mock_chaincode_client():
    """Mock Chaincode Client for testing."""
    client = AsyncMock()
    client.invoke_chaincode.return_value = {
        "transaction_id": "tx_123456",
        "status": "SUCCESS"
    }
    client.create_entity.return_value = {
        "transaction_id": "tx_create_123",
        "status": "SUCCESS"
    }
    client.update_entity.return_value = {
        "transaction_id": "tx_update_123",
        "status": "SUCCESS"
    }
    client.get_entity.return_value = {
        "status": "SUCCESS",
        "payload": '{"entity_id": "test_123"}'
    }
    return client


# File Content Fixtures
@pytest.fixture
def sample_file_content():
    """Sample file content for document testing."""
    return b"This is a test document content for testing purposes"


@pytest.fixture
def sample_pdf_content():
    """Sample PDF-like content for document testing."""
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"


# Utility Functions
def create_test_actor_in_db(db_utils, actor_data):
    """Helper function to create an actor in test database."""
    return db_utils.create_actor(actor_data)


def create_test_customer_in_db(db_utils, customer_data, actor_id):
    """Helper function to create a customer in test database."""
    customer_data = customer_data.copy()
    customer_data['created_by_actor_id'] = actor_id
    return db_utils.create_customer(customer_data)


def create_test_loan_in_db(db_utils, loan_data, customer_id, actor_id):
    """Helper function to create a loan application in test database."""
    loan_data = loan_data.copy()
    loan_data['customer_id'] = customer_id
    loan_data['created_by_actor_id'] = actor_id
    loan_data['current_owner_actor_id'] = actor_id
    return db_utils.create_loan_application(loan_data)