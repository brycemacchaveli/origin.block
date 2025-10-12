"""
Unit tests for database models and connection management.
"""

import pytest
import tempfile
import os
from datetime import datetime
from unittest.mock import patch, MagicMock

from sqlalchemy import text
from shared.database import (
    DatabaseManager,
    DatabaseUtilities,
    ActorModel,
    CustomerModel,
    CustomerHistoryModel,
    LoanApplicationModel,
    LoanApplicationHistoryModel,
    LoanDocumentModel,
    ComplianceEventModel,
    Base,
    init_database,
    cleanup_database,
    get_database,
    db_manager,
    db_utils
)


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
    """Create a test database manager."""
    manager = DatabaseManager(temp_db_path)
    manager.create_tables()
    yield manager
    manager.drop_tables()


@pytest.fixture
def test_db_utils(test_db_manager):
    """Create test database utilities."""
    return DatabaseUtilities(test_db_manager)


@pytest.fixture
def sample_actor_data():
    """Sample actor data for testing."""
    return {
        "actor_id": "test_actor_001",
        "actor_type": "Internal_User",
        "actor_name": "Test Actor",
        "role": "Underwriter",
        "permissions": ["read_customer", "read_loan_application"],
        "is_active": True
    }


@pytest.fixture
def sample_customer_data():
    """Sample customer data for testing."""
    return {
        "customer_id": "test_customer_001",
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": datetime(1990, 1, 1),
        "national_id_hash": "hashed_national_id",
        "address": "123 Test Street",
        "contact_email": "john.doe@example.com",
        "contact_phone": "+1234567890",
        "kyc_status": "VERIFIED",
        "aml_status": "CLEAR",
        "consent_preferences": {"marketing": True, "analytics": False}
    }


@pytest.fixture
def sample_loan_data():
    """Sample loan application data for testing."""
    return {
        "loan_application_id": "test_loan_001",
        "application_date": datetime.utcnow(),
        "requested_amount": 50000.0,
        "loan_type": "PERSONAL",
        "application_status": "SUBMITTED",
        "introducer_id": "partner_001"
    }


class TestDatabaseManager:
    """Test DatabaseManager class."""
    
    def test_database_manager_initialization(self, temp_db_path):
        """Test database manager initialization."""
        manager = DatabaseManager(temp_db_path)
        
        assert manager.database_url == temp_db_path
        assert manager.engine is not None
        assert manager.SessionLocal is not None
    
    def test_create_tables(self, test_db_manager):
        """Test table creation."""
        # Tables should already be created by fixture
        assert test_db_manager.engine is not None
        
        # Verify tables exist by checking metadata
        metadata = Base.metadata
        table_names = [table.name for table in metadata.tables.values()]
        
        expected_tables = [
            'actors', 'customers', 'customer_history',
            'loan_applications', 'loan_application_history',
            'loan_documents', 'compliance_events'
        ]
        
        for table_name in expected_tables:
            assert table_name in table_names
    
    def test_get_session(self, test_db_manager):
        """Test session creation."""
        session = test_db_manager.get_session()
        
        assert session is not None
        session.close()
    
    def test_session_scope(self, test_db_manager):
        """Test session scope context manager."""
        with test_db_manager.session_scope() as session:
            # Test that we can execute a query
            result = session.execute(text("SELECT 1")).scalar()
            assert result == 1
    
    def test_session_scope_rollback(self, test_db_manager):
        """Test session scope rollback on exception."""
        try:
            with test_db_manager.session_scope() as session:
                # Create an actor
                actor = ActorModel(
                    actor_id="test_rollback",
                    actor_type="Internal_User",
                    actor_name="Test Rollback",
                    role="Underwriter"
                )
                session.add(actor)
                session.flush()  # This should work
                
                # Force an exception
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # Verify the actor was not saved due to rollback
        with test_db_manager.session_scope() as session:
            actor = session.query(ActorModel).filter(
                ActorModel.actor_id == "test_rollback"
            ).first()
            assert actor is None
    
    def test_health_check(self, test_db_manager):
        """Test database health check."""
        assert test_db_manager.health_check() is True
    
    def test_health_check_failure(self, temp_db_path):
        """Test database health check failure."""
        manager = DatabaseManager("sqlite:///nonexistent/path/db.sqlite")
        assert manager.health_check() is False


class TestActorModel:
    """Test ActorModel database model."""
    
    def test_create_actor(self, test_db_manager, sample_actor_data):
        """Test creating an actor."""
        with test_db_manager.session_scope() as session:
            actor = ActorModel(**sample_actor_data)
            session.add(actor)
            session.flush()
            
            assert actor.id is not None
            assert actor.actor_id == "test_actor_001"
            assert actor.actor_type == "Internal_User"
            assert actor.role == "Underwriter"
            assert actor.is_active is True
            assert actor.created_at is not None
    
    def test_actor_relationships(self, test_db_manager, sample_actor_data):
        """Test actor relationships."""
        with test_db_manager.session_scope() as session:
            actor = ActorModel(**sample_actor_data)
            session.add(actor)
            session.flush()
            
            # Test that relationships are accessible
            assert hasattr(actor, 'customers')
            assert hasattr(actor, 'loan_applications')
            assert hasattr(actor, 'compliance_events')
    
    def test_actor_repr(self, test_db_manager, sample_actor_data):
        """Test actor string representation."""
        actor = ActorModel(**sample_actor_data)
        repr_str = repr(actor)
        
        assert "test_actor_001" in repr_str
        assert "Underwriter" in repr_str


class TestCustomerModel:
    """Test CustomerModel database model."""
    
    def test_create_customer(self, test_db_manager, sample_actor_data, sample_customer_data):
        """Test creating a customer."""
        with test_db_manager.session_scope() as session:
            # Create actor first
            actor = ActorModel(**sample_actor_data)
            session.add(actor)
            session.flush()
            
            # Create customer
            customer_data = sample_customer_data.copy()
            customer_data['created_by_actor_id'] = actor.id
            
            customer = CustomerModel(**customer_data)
            session.add(customer)
            session.flush()
            
            assert customer.id is not None
            assert customer.customer_id == "test_customer_001"
            assert customer.first_name == "John"
            assert customer.last_name == "Doe"
            assert customer.kyc_status == "VERIFIED"
            assert customer.created_by_actor_id == actor.id
    
    def test_customer_relationships(self, test_db_manager, sample_actor_data, sample_customer_data):
        """Test customer relationships."""
        with test_db_manager.session_scope() as session:
            # Create actor first
            actor = ActorModel(**sample_actor_data)
            session.add(actor)
            session.flush()
            
            # Create customer
            customer_data = sample_customer_data.copy()
            customer_data['created_by_actor_id'] = actor.id
            
            customer = CustomerModel(**customer_data)
            session.add(customer)
            session.flush()
            
            # Test relationships
            assert customer.created_by_actor == actor
            assert hasattr(customer, 'loan_applications')
            assert hasattr(customer, 'customer_history')


class TestLoanApplicationModel:
    """Test LoanApplicationModel database model."""
    
    def test_create_loan_application(self, test_db_manager, sample_actor_data, sample_customer_data, sample_loan_data):
        """Test creating a loan application."""
        with test_db_manager.session_scope() as session:
            # Create actor first
            actor = ActorModel(**sample_actor_data)
            session.add(actor)
            session.flush()
            
            # Create customer
            customer_data = sample_customer_data.copy()
            customer_data['created_by_actor_id'] = actor.id
            customer = CustomerModel(**customer_data)
            session.add(customer)
            session.flush()
            
            # Create loan application
            loan_data = sample_loan_data.copy()
            loan_data['customer_id'] = customer.id
            loan_data['created_by_actor_id'] = actor.id
            loan_data['current_owner_actor_id'] = actor.id
            
            loan = LoanApplicationModel(**loan_data)
            session.add(loan)
            session.flush()
            
            assert loan.id is not None
            assert loan.loan_application_id == "test_loan_001"
            assert loan.requested_amount == 50000.0
            assert loan.loan_type == "PERSONAL"
            assert loan.application_status == "SUBMITTED"
            assert loan.customer_id == customer.id
    
    def test_loan_relationships(self, test_db_manager, sample_actor_data, sample_customer_data, sample_loan_data):
        """Test loan application relationships."""
        with test_db_manager.session_scope() as session:
            # Create actor first
            actor = ActorModel(**sample_actor_data)
            session.add(actor)
            session.flush()
            
            # Create customer
            customer_data = sample_customer_data.copy()
            customer_data['created_by_actor_id'] = actor.id
            customer = CustomerModel(**customer_data)
            session.add(customer)
            session.flush()
            
            # Create loan application
            loan_data = sample_loan_data.copy()
            loan_data['customer_id'] = customer.id
            loan_data['created_by_actor_id'] = actor.id
            loan_data['current_owner_actor_id'] = actor.id
            
            loan = LoanApplicationModel(**loan_data)
            session.add(loan)
            session.flush()
            
            # Test relationships
            assert loan.customer == customer
            assert loan.created_by_actor == actor
            assert loan.current_owner_actor == actor


class TestComplianceEventModel:
    """Test ComplianceEventModel database model."""
    
    def test_create_compliance_event(self, test_db_manager, sample_actor_data):
        """Test creating a compliance event."""
        with test_db_manager.session_scope() as session:
            # Create actor first
            actor = ActorModel(**sample_actor_data)
            session.add(actor)
            session.flush()
            
            # Create compliance event
            event = ComplianceEventModel(
                event_id="test_event_001",
                event_type="AML_CHECK",
                affected_entity_type="CUSTOMER",
                affected_entity_id="test_customer_001",
                severity="INFO",
                description="AML check performed",
                details={"check_result": "CLEAR"},
                actor_id=actor.id
            )
            session.add(event)
            session.flush()
            
            assert event.id is not None
            assert event.event_id == "test_event_001"
            assert event.event_type == "AML_CHECK"
            assert event.severity == "INFO"
            assert event.resolution_status == "OPEN"
            assert event.actor_id == actor.id


class TestDatabaseUtilities:
    """Test DatabaseUtilities class."""
    
    def test_get_actor_by_actor_id(self, test_db_utils, sample_actor_data):
        """Test getting actor by actor_id."""
        # Create actor
        actor = test_db_utils.create_actor(sample_actor_data)
        
        # Retrieve actor
        retrieved_actor = test_db_utils.get_actor_by_actor_id("test_actor_001")
        
        assert retrieved_actor is not None
        assert retrieved_actor.actor_id == "test_actor_001"
        assert retrieved_actor.role == "Underwriter"
    
    def test_get_nonexistent_actor(self, test_db_utils):
        """Test getting nonexistent actor."""
        actor = test_db_utils.get_actor_by_actor_id("nonexistent")
        assert actor is None
    
    def test_create_customer(self, test_db_utils, sample_actor_data, sample_customer_data):
        """Test creating customer through utilities."""
        # Create actor first
        actor = test_db_utils.create_actor(sample_actor_data)
        
        # Create customer
        customer_data = sample_customer_data.copy()
        customer_data['created_by_actor_id'] = actor.id
        
        customer = test_db_utils.create_customer(customer_data)
        
        assert customer.id is not None
        assert customer.customer_id == "test_customer_001"
        assert customer.created_by_actor_id == actor.id
    
    def test_create_loan_application(self, test_db_utils, sample_actor_data, sample_customer_data, sample_loan_data):
        """Test creating loan application through utilities."""
        # Create actor first
        actor = test_db_utils.create_actor(sample_actor_data)
        
        # Create customer
        customer_data = sample_customer_data.copy()
        customer_data['created_by_actor_id'] = actor.id
        customer = test_db_utils.create_customer(customer_data)
        
        # Create loan application
        loan_data = sample_loan_data.copy()
        loan_data['customer_id'] = customer.id
        loan_data['created_by_actor_id'] = actor.id
        loan_data['current_owner_actor_id'] = actor.id
        
        loan = test_db_utils.create_loan_application(loan_data)
        
        assert loan.id is not None
        assert loan.loan_application_id == "test_loan_001"
        assert loan.customer_id == customer.id
    
    def test_update_loan_status(self, test_db_utils, sample_actor_data, sample_customer_data, sample_loan_data):
        """Test updating loan status."""
        # Create actor first
        actor = test_db_utils.create_actor(sample_actor_data)
        
        # Create customer
        customer_data = sample_customer_data.copy()
        customer_data['created_by_actor_id'] = actor.id
        customer = test_db_utils.create_customer(customer_data)
        
        # Create loan application
        loan_data = sample_loan_data.copy()
        loan_data['customer_id'] = customer.id
        loan_data['created_by_actor_id'] = actor.id
        loan_data['current_owner_actor_id'] = actor.id
        
        loan = test_db_utils.create_loan_application(loan_data)
        
        # Update status
        success = test_db_utils.update_loan_status(
            "test_loan_001",
            "APPROVED",
            actor.id,
            "Loan approved after review"
        )
        
        assert success is True
        
        # Verify status was updated
        updated_loan = test_db_utils.get_loan_by_loan_id("test_loan_001")
        assert updated_loan.application_status == "APPROVED"
        
        # Verify history was created
        history = test_db_utils.get_loan_history("test_loan_001")
        assert len(history) == 1
        assert history[0].change_type == "STATUS_CHANGE"
        assert history[0].previous_status == "SUBMITTED"
        assert history[0].new_status == "APPROVED"
    
    def test_get_compliance_events_by_entity(self, test_db_utils, sample_actor_data):
        """Test getting compliance events by entity."""
        # Create actor first
        actor = test_db_utils.create_actor(sample_actor_data)
        
        # Create compliance events
        event_data_1 = {
            "event_id": "test_event_001",
            "event_type": "AML_CHECK",
            "affected_entity_type": "CUSTOMER",
            "affected_entity_id": "test_customer_001",
            "severity": "INFO",
            "description": "AML check performed",
            "actor_id": actor.id
        }
        
        event_data_2 = {
            "event_id": "test_event_002",
            "event_type": "KYC_VERIFICATION",
            "affected_entity_type": "CUSTOMER",
            "affected_entity_id": "test_customer_001",
            "severity": "INFO",
            "description": "KYC verification completed",
            "actor_id": actor.id
        }
        
        test_db_utils.create_compliance_event(event_data_1)
        test_db_utils.create_compliance_event(event_data_2)
        
        # Retrieve events
        events = test_db_utils.get_compliance_events_by_entity("CUSTOMER", "test_customer_001")
        
        assert len(events) == 2
        assert events[0].event_type in ["AML_CHECK", "KYC_VERIFICATION"]
        assert events[1].event_type in ["AML_CHECK", "KYC_VERIFICATION"]


class TestGlobalInstances:
    """Test global database instances."""
    
    def test_get_database(self):
        """Test getting global database manager."""
        manager = get_database()
        assert manager is not None
        assert manager == db_manager
    
    @patch('shared.database.db_manager')
    def test_init_database(self, mock_db_manager):
        """Test database initialization."""
        init_database()
        mock_db_manager.create_tables.assert_called_once()
    
    @patch('shared.database.db_manager')
    def test_cleanup_database(self, mock_db_manager):
        """Test database cleanup."""
        mock_engine = MagicMock()
        mock_db_manager.engine = mock_engine
        
        cleanup_database()
        mock_engine.dispose.assert_called_once()


class TestDatabaseIntegration:
    """Integration tests for database operations."""
    
    def test_full_workflow(self, test_db_utils, sample_actor_data, sample_customer_data, sample_loan_data):
        """Test a complete workflow from actor creation to loan processing."""
        # Create actor
        actor = test_db_utils.create_actor(sample_actor_data)
        assert actor.id is not None
        
        # Create customer
        customer_data = sample_customer_data.copy()
        customer_data['created_by_actor_id'] = actor.id
        customer = test_db_utils.create_customer(customer_data)
        assert customer.id is not None
        
        # Create loan application
        loan_data = sample_loan_data.copy()
        loan_data['customer_id'] = customer.id
        loan_data['created_by_actor_id'] = actor.id
        loan_data['current_owner_actor_id'] = actor.id
        loan = test_db_utils.create_loan_application(loan_data)
        assert loan.id is not None
        
        # Update loan status
        success = test_db_utils.update_loan_status(
            loan.loan_application_id,
            "UNDERWRITING",
            actor.id,
            "Moved to underwriting"
        )
        assert success is True
        
        # Create compliance event
        event_data = {
            "event_id": f"event_{loan.loan_application_id}",
            "event_type": "STATUS_CHANGE",
            "affected_entity_type": "LOAN_APPLICATION",
            "affected_entity_id": loan.loan_application_id,
            "severity": "INFO",
            "description": "Loan status changed to underwriting",
            "actor_id": actor.id
        }
        event = test_db_utils.create_compliance_event(event_data)
        assert event.id is not None
        
        # Verify all data is connected properly
        retrieved_loan = test_db_utils.get_loan_by_loan_id(loan.loan_application_id)
        assert retrieved_loan.application_status == "UNDERWRITING"
        assert retrieved_loan.customer.customer_id == customer.customer_id
        assert retrieved_loan.created_by_actor.actor_id == actor.actor_id
        
        # Verify history
        history = test_db_utils.get_loan_history(loan.loan_application_id)
        assert len(history) == 1
        assert history[0].new_status == "UNDERWRITING"
        
        # Verify compliance events
        events = test_db_utils.get_compliance_events_by_entity(
            "LOAN_APPLICATION", 
            loan.loan_application_id
        )
        assert len(events) == 1
        assert events[0].event_type == "STATUS_CHANGE"