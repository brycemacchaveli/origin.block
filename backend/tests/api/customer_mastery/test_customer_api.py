"""
Unit tests for Customer Mastery API endpoints.

Tests cover CRUD operations, validation, error handling, and access control
for customer management functionality.
"""

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import status

from main import app
from shared.auth import Actor, ActorType, Role, Permission, jwt_manager
from shared.database import CustomerModel, ActorModel, CustomerHistoryModel
from customer_mastery.api import _generate_customer_id, _hash_national_id


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_actor():
    """Create test actor with customer permissions."""
    return Actor(
        actor_id="test_actor_001",
        actor_type=ActorType.INTERNAL_USER,
        actor_name="Test Actor",
        role=Role.CUSTOMER_SERVICE_REP,
        permissions={
            Permission.CREATE_CUSTOMER,
            Permission.READ_CUSTOMER,
            Permission.UPDATE_CUSTOMER,
            Permission.READ_CUSTOMER_HISTORY
        }
    )


@pytest.fixture
def auth_headers(test_actor):
    """Create authentication headers for test requests."""
    token = jwt_manager.create_access_token(test_actor)
    return {"Authorization": f"Bearer {token}"}


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
def mock_db_customer():
    """Mock database customer object."""
    customer = Mock(spec=CustomerModel)
    customer.id = 1
    customer.customer_id = "CUST_123456789ABC"
    customer.first_name = "John"
    customer.last_name = "Doe"
    customer.date_of_birth = datetime(1990, 1, 1)
    customer.national_id_hash = _hash_national_id("123456789")
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
    actor.role = "Customer_Service_Rep"
    actor.blockchain_identity = None
    actor.permissions = ["create_customer", "read_customer", "update_customer"]
    actor.is_active = True
    actor.created_at = datetime.utcnow()
    actor.updated_at = datetime.utcnow()
    return actor


class TestCustomerCreation:
    """Test customer creation endpoint."""
    
    @patch('customer_mastery.api.db_utils')
    @patch('customer_mastery.api.get_fabric_gateway')
    def test_create_customer_success(self, mock_gateway, mock_db_utils, 
                                   client, auth_headers, sample_customer_data, 
                                   mock_db_actor, mock_db_customer):
        """Test successful customer creation."""
        # Setup mocks
        mock_db_utils.get_actor_by_actor_id.return_value = mock_db_actor
        mock_db_utils.create_customer.return_value = mock_db_customer
        
        # Mock blockchain interaction
        mock_gateway_instance = AsyncMock()
        mock_chaincode_client = AsyncMock()
        mock_chaincode_client.invoke_chaincode.return_value = {
            "transaction_id": "tx_123",
            "status": "SUCCESS"
        }
        mock_gateway.return_value = mock_gateway_instance
        
        with patch('customer_mastery.api.ChaincodeClient', return_value=mock_chaincode_client):
            response = client.post(
                "/api/v1/customers/",
                json=sample_customer_data,
                headers=auth_headers
            )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"
        assert data["kyc_status"] == "PENDING"
        assert data["aml_status"] == "PENDING"
        assert "customer_id" in data
        
        # Verify database calls
        mock_db_utils.create_customer.assert_called_once()
        
    def test_create_customer_invalid_data(self, client, auth_headers):
        """Test customer creation with invalid data."""
        invalid_data = {
            "first_name": "",  # Empty name should fail validation
            "contact_email": "invalid-email"  # Invalid email format
        }
        
        response = client.post(
            "/api/v1/customers/",
            json=invalid_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
    def test_create_customer_unauthorized(self, client, sample_customer_data):
        """Test customer creation without authentication."""
        response = client.post(
            "/api/v1/customers/",
            json=sample_customer_data
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
    @patch('customer_mastery.api.db_utils')
    def test_create_customer_insufficient_permissions(self, mock_db_utils, client, sample_customer_data):
        """Test customer creation with insufficient permissions."""
        # Create actor without CREATE_CUSTOMER permission
        limited_actor = Actor(
            actor_id="limited_actor",
            actor_type=ActorType.INTERNAL_USER,
            actor_name="Limited Actor",
            role=Role.UNDERWRITER,
            permissions={Permission.READ_CUSTOMER}  # Missing CREATE_CUSTOMER
        )
        
        token = jwt_manager.create_access_token(limited_actor)
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.post(
            "/api/v1/customers/",
            json=sample_customer_data,
            headers=headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Insufficient permissions" in response.json()["detail"]


class TestCustomerRetrieval:
    """Test customer retrieval endpoint."""
    
    @patch('customer_mastery.api.db_utils')
    def test_get_customer_success(self, mock_db_utils, client, auth_headers, mock_db_customer):
        """Test successful customer retrieval."""
        mock_db_utils.get_customer_by_customer_id.return_value = mock_db_customer
        
        response = client.get(
            "/api/v1/customers/CUST_123456789ABC",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["customer_id"] == "CUST_123456789ABC"
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"
        
        mock_db_utils.get_customer_by_customer_id.assert_called_once_with("CUST_123456789ABC")
        
    @patch('customer_mastery.api.db_utils')
    def test_get_customer_not_found(self, mock_db_utils, client, auth_headers):
        """Test customer retrieval when customer doesn't exist."""
        mock_db_utils.get_customer_by_customer_id.return_value = None
        
        response = client.get(
            "/api/v1/customers/NONEXISTENT",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]
        
    def test_get_customer_unauthorized(self, client):
        """Test customer retrieval without authentication."""
        response = client.get("/api/v1/customers/CUST_123456789ABC")
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestCustomerUpdate:
    """Test customer update endpoint."""
    
    @patch('customer_mastery.api.db_utils')
    @patch('customer_mastery.api.get_fabric_gateway')
    def test_update_customer_success(self, mock_gateway, mock_db_utils, 
                                   client, auth_headers, mock_db_customer, mock_db_actor):
        """Test successful customer update."""
        # Setup mocks
        mock_db_utils.get_customer_by_customer_id.return_value = mock_db_customer
        mock_db_utils.get_actor_by_actor_id.return_value = mock_db_actor
        
        # Mock database session
        mock_session = Mock()
        mock_db_customer_query = Mock()
        mock_db_customer_query.first.return_value = mock_db_customer
        mock_session.query.return_value.filter.return_value = mock_db_customer_query
        mock_db_utils.db_manager.session_scope.return_value.__enter__.return_value = mock_session
        mock_db_utils.db_manager.session_scope.return_value.__exit__.return_value = None
        
        # Mock blockchain interaction
        mock_gateway_instance = AsyncMock()
        mock_chaincode_client = AsyncMock()
        mock_chaincode_client.invoke_chaincode.return_value = {
            "transaction_id": "tx_update_123",
            "status": "SUCCESS"
        }
        mock_gateway.return_value = mock_gateway_instance
        
        update_data = {
            "first_name": "Jane",
            "contact_email": "jane.doe@example.com"
        }
        
        with patch('customer_mastery.api.ChaincodeClient', return_value=mock_chaincode_client):
            response = client.put(
                "/api/v1/customers/CUST_123456789ABC",
                json=update_data,
                headers=auth_headers
            )
        
        assert response.status_code == status.HTTP_200_OK
        
    @patch('customer_mastery.api.db_utils')
    def test_update_customer_not_found(self, mock_db_utils, client, auth_headers):
        """Test customer update when customer doesn't exist."""
        mock_db_utils.get_customer_by_customer_id.return_value = None
        
        update_data = {"first_name": "Jane"}
        
        response = client.put(
            "/api/v1/customers/NONEXISTENT",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
    def test_update_customer_invalid_data(self, client, auth_headers):
        """Test customer update with invalid data."""
        invalid_data = {
            "contact_email": "invalid-email-format"
        }
        
        response = client.put(
            "/api/v1/customers/CUST_123456789ABC",
            json=invalid_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestCustomerHistory:
    """Test customer history endpoint."""
    
    @patch('customer_mastery.api.db_utils')
    def test_get_customer_history_success(self, mock_db_utils, client, auth_headers, mock_db_customer):
        """Test successful customer history retrieval."""
        mock_db_utils.get_customer_by_customer_id.return_value = mock_db_customer
        
        # Mock history records
        mock_history = [
            Mock(
                id=1,
                change_type="CREATE",
                field_name=None,
                old_value=None,
                new_value='{"customer_id": "CUST_123", "first_name": "John"}',
                changed_by_actor_id=1,
                blockchain_transaction_id="tx_123",
                timestamp=datetime.utcnow()
            ),
            Mock(
                id=2,
                change_type="UPDATE",
                field_name="first_name",
                old_value="John",
                new_value="Jane",
                changed_by_actor_id=1,
                blockchain_transaction_id="tx_456",
                timestamp=datetime.utcnow()
            )
        ]
        mock_db_utils.get_customer_history.return_value = mock_history
        
        response = client.get(
            "/api/v1/customers/CUST_123456789ABC/history",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        assert data[0]["change_type"] == "CREATE"
        assert data[1]["change_type"] == "UPDATE"
        
    @patch('customer_mastery.api.db_utils')
    def test_get_customer_history_not_found(self, mock_db_utils, client, auth_headers):
        """Test customer history retrieval when customer doesn't exist."""
        mock_db_utils.get_customer_by_customer_id.return_value = None
        
        response = client.get(
            "/api/v1/customers/NONEXISTENT/history",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_generate_customer_id(self):
        """Test customer ID generation."""
        customer_id = _generate_customer_id()
        assert customer_id.startswith("CUST_")
        assert len(customer_id) == 17  # CUST_ + 12 hex chars
        
        # Test uniqueness
        customer_id2 = _generate_customer_id()
        assert customer_id != customer_id2
        
    def test_hash_national_id(self):
        """Test national ID hashing."""
        national_id = "123456789"
        hashed = _hash_national_id(national_id)
        
        assert len(hashed) == 64  # SHA256 hex length
        assert hashed != national_id
        
        # Test consistency
        hashed2 = _hash_national_id(national_id)
        assert hashed == hashed2
        
        # Test different inputs produce different hashes
        hashed3 = _hash_national_id("987654321")
        assert hashed != hashed3


class TestValidation:
    """Test input validation."""
    
    def test_phone_number_validation(self, client, auth_headers):
        """Test phone number validation."""
        # Valid phone numbers
        valid_phones = [
            "+1-555-123-4567",
            "555-123-4567",
            "(555) 123-4567",
            "5551234567",
            "+44 20 7946 0958"
        ]
        
        for phone in valid_phones:
            data = {
                "first_name": "John",
                "last_name": "Doe",
                "contact_phone": phone
            }
            # This would normally test the validation, but since we're mocking
            # the database, we'll just verify the schema accepts it
            from customer_mastery.api import CustomerCreate
            customer = CustomerCreate(**data)
            assert customer.contact_phone == phone
        
        # Invalid phone numbers
        invalid_phones = [
            "abc-def-ghij",
            "123-abc-4567",
            "not-a-phone"
        ]
        
        for phone in invalid_phones:
            data = {
                "first_name": "John",
                "last_name": "Doe",
                "contact_phone": phone
            }
            with pytest.raises(ValueError):
                CustomerCreate(**data)
    
    def test_email_validation(self):
        """Test email validation."""
        from customer_mastery.api import CustomerCreate
        
        # Valid email
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "contact_email": "john.doe@example.com"
        }
        customer = CustomerCreate(**data)
        assert customer.contact_email == "john.doe@example.com"
        
        # Invalid email
        data["contact_email"] = "invalid-email"
        with pytest.raises(ValueError):
            CustomerCreate(**data)
    
    def test_required_fields(self):
        """Test required field validation."""
        from customer_mastery.api import CustomerCreate
        
        # Missing required fields
        with pytest.raises(ValueError):
            CustomerCreate()
        
        with pytest.raises(ValueError):
            CustomerCreate(first_name="John")  # Missing last_name
        
        # Valid minimal data
        customer = CustomerCreate(first_name="John", last_name="Doe")
        assert customer.first_name == "John"
        assert customer.last_name == "Doe"


class TestConsentManagement:
    """Test consent management endpoints."""
    
    @pytest.fixture
    def consent_actor(self):
        """Create test actor with consent permissions."""
        from shared.auth import actor_manager
        
        actor = Actor(
            actor_id="consent_actor_001",
            actor_type=ActorType.INTERNAL_USER,
            actor_name="Consent Manager",
            role=Role.CUSTOMER_SERVICE_REP,
            permissions={Permission.MANAGE_CUSTOMER_CONSENT}
        )
        
        # Add actor to the actor manager
        actor_manager._actors[actor.actor_id] = actor
        
        return actor
    
    @pytest.fixture
    def consent_auth_headers(self, consent_actor):
        """Create authentication headers for consent requests."""
        token = jwt_manager.create_access_token(consent_actor)
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture
    def sample_consent_data(self):
        """Sample consent data for testing."""
        return {
            "data_sharing": True,
            "marketing": False,
            "analytics": True,
            "third_party_sharing": False,
            "retention_period": 24
        }
    
    @patch('customer_mastery.api.db_utils')
    @patch('customer_mastery.api.get_fabric_gateway')
    def test_record_customer_consent_success(self, mock_gateway, mock_db_utils, 
                                           client, consent_auth_headers, sample_consent_data, 
                                           mock_db_customer, mock_db_actor):
        """Test successful consent recording."""
        # Setup mocks
        mock_db_utils.get_customer_by_customer_id.return_value = mock_db_customer
        mock_db_utils.get_actor_by_actor_id.return_value = mock_db_actor
        
        # Mock database session
        mock_session = Mock()
        mock_db_customer_query = Mock()
        mock_db_customer_query.first.return_value = mock_db_customer
        mock_session.query.return_value.filter.return_value = mock_db_customer_query
        mock_db_utils.db_manager.session_scope.return_value.__enter__.return_value = mock_session
        mock_db_utils.db_manager.session_scope.return_value.__exit__.return_value = None
        
        # Mock blockchain interaction
        mock_gateway_instance = AsyncMock()
        mock_chaincode_client = AsyncMock()
        mock_chaincode_client.invoke_chaincode.return_value = {
            "transaction_id": "tx_consent_123",
            "status": "SUCCESS"
        }
        mock_gateway.return_value = mock_gateway_instance
        
        with patch('customer_mastery.api.ChaincodeClient', return_value=mock_chaincode_client):
            response = client.post(
                "/api/v1/customers/CUST_123456789ABC/consent",
                json=sample_consent_data,
                headers=consent_auth_headers
            )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["customer_id"] == "CUST_123456789ABC"
        assert data["consent_preferences"]["data_sharing"] == True
        assert data["consent_preferences"]["marketing"] == False
        assert "last_updated" in data
        assert "recorded_by" in data
    
    @patch('customer_mastery.api.db_utils')
    def test_record_consent_customer_not_found(self, mock_db_utils, client, consent_auth_headers, sample_consent_data):
        """Test consent recording when customer doesn't exist."""
        mock_db_utils.get_customer_by_customer_id.return_value = None
        
        response = client.post(
            "/api/v1/customers/NONEXISTENT/consent",
            json=sample_consent_data,
            headers=consent_auth_headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]
    
    @patch('customer_mastery.api.db_utils')
    def test_get_customer_consent_success(self, mock_db_utils, client, consent_auth_headers, mock_db_customer):
        """Test successful consent retrieval."""
        # Set up consent preferences
        mock_db_customer.consent_preferences = {
            "data_sharing": True,
            "marketing": False,
            "analytics": True
        }
        mock_db_utils.get_customer_by_customer_id.return_value = mock_db_customer
        mock_db_utils.get_customer_history.return_value = []
        
        response = client.get(
            "/api/v1/customers/CUST_123456789ABC/consent",
            headers=consent_auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["customer_id"] == "CUST_123456789ABC"
        assert data["consent_preferences"]["data_sharing"] == True
        assert data["consent_preferences"]["marketing"] == False
    
    @patch('customer_mastery.api.db_utils')
    def test_get_consent_customer_not_found(self, mock_db_utils, client, consent_auth_headers):
        """Test consent retrieval when customer doesn't exist."""
        mock_db_utils.get_customer_by_customer_id.return_value = None
        
        response = client.get(
            "/api/v1/customers/NONEXISTENT/consent",
            headers=consent_auth_headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]
    
    @patch('customer_mastery.api.db_utils')
    @patch('customer_mastery.api.get_fabric_gateway')
    def test_update_customer_consent_success(self, mock_gateway, mock_db_utils, 
                                           client, consent_auth_headers, sample_consent_data, 
                                           mock_db_customer, mock_db_actor):
        """Test successful consent update."""
        # Setup mocks
        mock_db_customer.consent_preferences = {"data_sharing": False, "marketing": True}
        mock_db_utils.get_customer_by_customer_id.return_value = mock_db_customer
        mock_db_utils.get_actor_by_actor_id.return_value = mock_db_actor
        
        # Mock database session
        mock_session = Mock()
        mock_db_customer_query = Mock()
        mock_db_customer_query.first.return_value = mock_db_customer
        mock_session.query.return_value.filter.return_value = mock_db_customer_query
        mock_db_utils.db_manager.session_scope.return_value.__enter__.return_value = mock_session
        mock_db_utils.db_manager.session_scope.return_value.__exit__.return_value = None
        
        # Mock blockchain interaction
        mock_gateway_instance = AsyncMock()
        mock_chaincode_client = AsyncMock()
        mock_chaincode_client.invoke_chaincode.return_value = {
            "transaction_id": "tx_consent_update_123",
            "status": "SUCCESS"
        }
        mock_gateway.return_value = mock_gateway_instance
        
        with patch('customer_mastery.api.ChaincodeClient', return_value=mock_chaincode_client):
            response = client.put(
                "/api/v1/customers/CUST_123456789ABC/consent",
                json=sample_consent_data,
                headers=consent_auth_headers
            )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["customer_id"] == "CUST_123456789ABC"
        assert data["consent_preferences"]["data_sharing"] == True
        assert data["consent_preferences"]["marketing"] == False
    
    def test_consent_unauthorized(self, client, sample_consent_data):
        """Test consent operations without authentication."""
        customer_id = "CUST_123456789ABC"
        
        # Test POST
        response = client.post(f"/api/v1/customers/{customer_id}/consent", json=sample_consent_data)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Test GET
        response = client.get(f"/api/v1/customers/{customer_id}/consent")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Test PUT
        response = client.put(f"/api/v1/customers/{customer_id}/consent", json=sample_consent_data)
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_consent_validation(self):
        """Test consent preferences validation."""
        from customer_mastery.api import ConsentPreferences
        
        # Valid consent data
        valid_consent = {
            "data_sharing": True,
            "marketing": False,
            "analytics": True,
            "third_party_sharing": False,
            "retention_period": 24
        }
        consent = ConsentPreferences(**valid_consent)
        assert consent.data_sharing == True
        assert consent.marketing == False
        assert consent.retention_period == 24
        
        # Test with additional fields (should be allowed due to extra="allow")
        extended_consent = {
            **valid_consent,
            "custom_field": "custom_value"
        }
        consent = ConsentPreferences(**extended_consent)
        assert hasattr(consent, 'custom_field')
        assert consent.custom_field == "custom_value"


class TestIdentityVerification:
    """Test identity verification endpoints."""
    
    @pytest.fixture
    def verification_actor(self):
        """Create test actor with verification permissions."""
        from shared.auth import actor_manager
        
        actor = Actor(
            actor_id="verification_actor_001",
            actor_type=ActorType.INTERNAL_USER,
            actor_name="Verification Manager",
            role=Role.CUSTOMER_SERVICE_REP,
            permissions={
                Permission.CREATE_CUSTOMER,
                Permission.READ_CUSTOMER,
                Permission.UPDATE_CUSTOMER
            }
        )
        
        # Add actor to the actor manager
        actor_manager._actors[actor.actor_id] = actor
        
        return actor
    
    @pytest.fixture
    def verification_auth_headers(self, verification_actor):
        """Create authentication headers for verification requests."""
        token = jwt_manager.create_access_token(verification_actor)
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture
    def sample_verification_request(self):
        """Sample verification request data for testing."""
        return {
            "verification_type": "KYC",
            "provider": "test_provider",
            "additional_data": {
                "document_type": "passport",
                "country": "US"
            }
        }
    
    @patch('customer_mastery.api.db_utils')
    @patch('customer_mastery.api.get_fabric_gateway')
    @patch('customer_mastery.api._simulate_identity_provider_call')
    def test_initiate_identity_verification_success(self, mock_provider_call, mock_gateway, mock_db_utils, 
                                                  client, verification_auth_headers, sample_verification_request, 
                                                  mock_db_customer, mock_db_actor):
        """Test successful identity verification initiation."""
        # Setup mocks
        mock_db_utils.get_customer_by_customer_id.return_value = mock_db_customer
        mock_db_utils.get_actor_by_actor_id.return_value = mock_db_actor
        
        # Mock database session
        mock_session = Mock()
        mock_db_customer_query = Mock()
        mock_db_customer_query.first.return_value = mock_db_customer
        mock_session.query.return_value.filter.return_value = mock_db_customer_query
        mock_db_utils.db_manager.session_scope.return_value.__enter__.return_value = mock_session
        mock_db_utils.db_manager.session_scope.return_value.__exit__.return_value = None
        
        # Mock blockchain interaction
        mock_gateway_instance = AsyncMock()
        mock_chaincode_client = AsyncMock()
        mock_chaincode_client.invoke_chaincode.return_value = {
            "transaction_id": "tx_verification_123",
            "status": "SUCCESS"
        }
        mock_gateway.return_value = mock_gateway_instance
        
        # Mock identity provider call
        mock_provider_call.return_value = {
            "provider_reference": "test_kyc_12345678",
            "confidence_score": 0.95,
            "checks_performed": ["document_verification", "liveness_check"],
            "estimated_completion": "2-5 minutes"
        }
        
        with patch('customer_mastery.api.ChaincodeClient', return_value=mock_chaincode_client):
            response = client.post(
                "/api/v1/customers/CUST_123456789ABC/verify",
                json=sample_verification_request,
                headers=verification_auth_headers
            )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["customer_id"] == "CUST_123456789ABC"
        assert data["verification_type"] == "KYC"
        assert data["status"] == "INITIATED"
        assert data["provider"] == "test_provider"
        assert "verification_id" in data
        assert data["verification_id"].startswith("VER_")
        
        # Verify provider call was made
        mock_provider_call.assert_called_once()
    
    @patch('customer_mastery.api.db_utils')
    def test_initiate_verification_customer_not_found(self, mock_db_utils, client, verification_auth_headers, sample_verification_request):
        """Test verification initiation when customer doesn't exist."""
        mock_db_utils.get_customer_by_customer_id.return_value = None
        
        response = client.post(
            "/api/v1/customers/NONEXISTENT/verify",
            json=sample_verification_request,
            headers=verification_auth_headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]
    
    @patch('customer_mastery.api.db_utils')
    @patch('customer_mastery.api.get_fabric_gateway')
    def test_get_verification_status_success(self, mock_gateway, mock_db_utils, 
                                           client, verification_auth_headers, mock_db_customer):
        """Test successful verification status retrieval."""
        mock_db_utils.get_customer_by_customer_id.return_value = mock_db_customer
        
        # Mock blockchain query
        mock_gateway_instance = AsyncMock()
        mock_chaincode_client = AsyncMock()
        mock_chaincode_client.query_chaincode.return_value = {
            "payload": {
                "verification_type": "KYC",
                "status": "COMPLETED",
                "provider": "test_provider",
                "initiated_by": "verification_actor_001",
                "initiated_at": "2024-01-01T00:00:00",
                "completed_at": "2024-01-01T00:05:00",
                "result_details": {
                    "confidence_score": 0.95,
                    "checks_passed": True
                }
            }
        }
        mock_gateway.return_value = mock_gateway_instance
        
        with patch('customer_mastery.api.ChaincodeClient', return_value=mock_chaincode_client):
            response = client.get(
                "/api/v1/customers/CUST_123456789ABC/verify/VER_123456789ABC",
                headers=verification_auth_headers
            )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["customer_id"] == "CUST_123456789ABC"
        assert data["verification_id"] == "VER_123456789ABC"
        assert data["verification_type"] == "KYC"
        assert data["status"] == "COMPLETED"
    
    @patch('customer_mastery.api.db_utils')
    def test_get_verification_status_customer_not_found(self, mock_db_utils, client, verification_auth_headers):
        """Test verification status retrieval when customer doesn't exist."""
        mock_db_utils.get_customer_by_customer_id.return_value = None
        
        response = client.get(
            "/api/v1/customers/NONEXISTENT/verify/VER_123456789ABC",
            headers=verification_auth_headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]
    
    @patch('customer_mastery.api.db_utils')
    @patch('customer_mastery.api.get_fabric_gateway')
    def test_update_verification_status_success(self, mock_gateway, mock_db_utils, 
                                              client, verification_auth_headers, 
                                              mock_db_customer, mock_db_actor):
        """Test successful verification status update."""
        # Setup mocks
        mock_db_utils.get_customer_by_customer_id.return_value = mock_db_customer
        mock_db_utils.get_actor_by_actor_id.return_value = mock_db_actor
        
        # Mock database session
        mock_session = Mock()
        mock_db_customer_query = Mock()
        mock_db_customer_query.first.return_value = mock_db_customer
        mock_session.query.return_value.filter.return_value = mock_db_customer_query
        mock_db_utils.db_manager.session_scope.return_value.__enter__.return_value = mock_session
        mock_db_utils.db_manager.session_scope.return_value.__exit__.return_value = None
        
        # Mock blockchain interaction
        mock_gateway_instance = AsyncMock()
        mock_chaincode_client = AsyncMock()
        mock_chaincode_client.invoke_chaincode.return_value = {
            "transaction_id": "tx_verification_update_123",
            "status": "SUCCESS"
        }
        mock_gateway.return_value = mock_gateway_instance
        
        status_update = {
            "status": "COMPLETED",
            "result_details": {
                "confidence_score": 0.95,
                "checks_passed": True
            },
            "notes": "Verification completed successfully"
        }
        
        with patch('customer_mastery.api.ChaincodeClient', return_value=mock_chaincode_client):
            response = client.put(
                "/api/v1/customers/CUST_123456789ABC/verify/VER_123456789ABC",
                json=status_update,
                headers=verification_auth_headers
            )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["customer_id"] == "CUST_123456789ABC"
        assert data["verification_id"] == "VER_123456789ABC"
        assert data["status"] == "COMPLETED"
    
    def test_verification_unauthorized(self, client, sample_verification_request):
        """Test verification operations without authentication."""
        customer_id = "CUST_123456789ABC"
        verification_id = "VER_123456789ABC"
        
        # Test POST
        response = client.post(f"/api/v1/customers/{customer_id}/verify", json=sample_verification_request)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Test GET
        response = client.get(f"/api/v1/customers/{customer_id}/verify/{verification_id}")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Test PUT
        status_update = {"status": "COMPLETED", "result_details": {}}
        response = client.put(f"/api/v1/customers/{customer_id}/verify/{verification_id}", json=status_update)
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_verification_request_validation(self):
        """Test verification request validation."""
        from customer_mastery.api import IdentityVerificationRequest
        
        # Valid verification request
        valid_request = {
            "verification_type": "KYC",
            "provider": "test_provider",
            "additional_data": {"document_type": "passport"}
        }
        request = IdentityVerificationRequest(**valid_request)
        assert request.verification_type == "KYC"
        assert request.provider == "test_provider"
        
        # Test with minimal data
        minimal_request = {"verification_type": "AML"}
        request = IdentityVerificationRequest(**minimal_request)
        assert request.verification_type == "AML"
        assert request.provider == "default"
        assert request.additional_data == {}
    
    def test_verification_id_generation(self):
        """Test verification ID generation."""
        from customer_mastery.api import _generate_verification_id
        
        verification_id = _generate_verification_id()
        assert verification_id.startswith("VER_")
        assert len(verification_id) == 16  # VER_ + 12 hex chars
        
        # Test uniqueness
        verification_id2 = _generate_verification_id()
        assert verification_id != verification_id2