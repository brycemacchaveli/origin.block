"""
Unit tests for Loan Origination API endpoints.

Tests cover CRUD operations, validation, error handling, and access control
for loan application management functionality.
"""

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import status

from main import app
from shared.auth import Actor, ActorType, Role, Permission, jwt_manager
from shared.database import LoanApplicationModel, CustomerModel, ActorModel, LoanApplicationHistoryModel
from loan_origination.api import _generate_loan_application_id, ApplicationStatus, LoanType


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_introducer():
    """Create test actor with loan creation permissions."""
    from shared.auth import actor_manager
    
    actor = Actor(
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
    
    # Add actor to the actor manager
    actor_manager._actors[actor.actor_id] = actor
    
    return actor


@pytest.fixture
def test_underwriter():
    """Create test actor with loan update permissions."""
    from shared.auth import actor_manager
    
    actor = Actor(
        actor_id="underwriter_001",
        actor_type=ActorType.INTERNAL_USER,
        actor_name="Test Underwriter",
        role=Role.UNDERWRITER,
        permissions={
            Permission.READ_LOAN_APPLICATION,
            Permission.UPDATE_LOAN_APPLICATION,
            Permission.READ_LOAN_HISTORY
        }
    )
    
    # Add actor to the actor manager
    actor_manager._actors[actor.actor_id] = actor
    
    return actor


@pytest.fixture
def test_credit_officer():
    """Create test actor with approval permissions."""
    from shared.auth import actor_manager
    
    actor = Actor(
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
    
    # Add actor to the actor manager
    actor_manager._actors[actor.actor_id] = actor
    
    return actor


@pytest.fixture
def introducer_auth_headers(test_introducer):
    """Create authentication headers for introducer requests."""
    token = jwt_manager.create_access_token(test_introducer)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def underwriter_auth_headers(test_underwriter):
    """Create authentication headers for underwriter requests."""
    token = jwt_manager.create_access_token(test_underwriter)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def credit_officer_auth_headers(test_credit_officer):
    """Create authentication headers for credit officer requests."""
    token = jwt_manager.create_access_token(test_credit_officer)
    return {"Authorization": f"Bearer {token}"}


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
def mock_db_customer():
    """Mock database customer object."""
    customer = Mock(spec=CustomerModel)
    customer.id = 1
    customer.customer_id = "CUST_123456789ABC"
    customer.first_name = "John"
    customer.last_name = "Doe"
    customer.kyc_status = "VERIFIED"
    customer.aml_status = "CLEAR"
    return customer


@pytest.fixture
def mock_db_actor():
    """Mock database actor object."""
    actor = Mock(spec=ActorModel)
    actor.id = 1
    actor.actor_id = "introducer_001"
    actor.actor_type = "External_Partner"
    actor.actor_name = "Test Introducer"
    actor.role = "Introducer"
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
    
    # Mock customer relationship
    loan.customer = mock_db_customer
    
    return loan


class TestLoanApplicationCreation:
    """Test loan application creation endpoint."""
    
    @patch('loan_origination.api.db_utils')
    @patch('loan_origination.api.get_fabric_gateway')
    def test_submit_loan_application_success(self, mock_gateway, mock_db_utils,
                                           client, introducer_auth_headers, sample_loan_data,
                                           mock_db_customer, mock_db_actor, mock_db_loan):
        """Test successful loan application submission."""
        # Setup mocks
        mock_db_utils.get_customer_by_customer_id.return_value = mock_db_customer
        mock_db_utils.get_actor_by_actor_id.return_value = mock_db_actor
        mock_db_utils.create_loan_application.return_value = mock_db_loan
        
        # Mock blockchain interaction
        mock_gateway_instance = AsyncMock()
        mock_chaincode_client = AsyncMock()
        mock_chaincode_client.invoke_chaincode.return_value = {
            "transaction_id": "tx_loan_123",
            "status": "SUCCESS"
        }
        mock_gateway.return_value = mock_gateway_instance
        
        with patch('loan_origination.api.ChaincodeClient', return_value=mock_chaincode_client):
            response = client.post(
                "/api/v1/loans/",
                json=sample_loan_data,
                headers=introducer_auth_headers
            )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["customer_id"] == "CUST_123456789ABC"
        assert data["requested_amount"] == 50000.0
        assert data["loan_type"] == "PERSONAL"
        assert data["application_status"] == "SUBMITTED"
        assert "loan_application_id" in data
        
        # Verify database calls
        mock_db_utils.get_customer_by_customer_id.assert_called_once_with("CUST_123456789ABC")
        mock_db_utils.create_loan_application.assert_called_once()
    
    def test_submit_loan_application_invalid_data(self, client, introducer_auth_headers):
        """Test loan application submission with invalid data."""
        invalid_data = {
            "customer_id": "CUST_123",
            "requested_amount": -1000.0,  # Negative amount should fail
            "loan_type": "INVALID_TYPE"
        }
        
        response = client.post(
            "/api/v1/loans/",
            json=invalid_data,
            headers=introducer_auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @patch('loan_origination.api.db_utils')
    def test_submit_loan_application_customer_not_found(self, mock_db_utils,
                                                       client, introducer_auth_headers, sample_loan_data):
        """Test loan application submission when customer doesn't exist."""
        mock_db_utils.get_customer_by_customer_id.return_value = None
        
        response = client.post(
            "/api/v1/loans/",
            json=sample_loan_data,
            headers=introducer_auth_headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]
    
    def test_submit_loan_application_unauthorized(self, client, sample_loan_data):
        """Test loan application submission without authentication."""
        response = client.post(
            "/api/v1/loans/",
            json=sample_loan_data
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_submit_loan_application_insufficient_permissions(self, client, sample_loan_data):
        """Test loan application submission with insufficient permissions."""
        from shared.auth import actor_manager
        
        # Create actor without CREATE_LOAN_APPLICATION permission
        limited_actor = Actor(
            actor_id="limited_actor",
            actor_type=ActorType.INTERNAL_USER,
            actor_name="Limited Actor",
            role=Role.UNDERWRITER,
            permissions={Permission.READ_LOAN_APPLICATION}  # Missing CREATE_LOAN_APPLICATION
        )
        
        # Add actor to the actor manager
        actor_manager._actors[limited_actor.actor_id] = limited_actor
        
        token = jwt_manager.create_access_token(limited_actor)
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.post(
            "/api/v1/loans/",
            json=sample_loan_data,
            headers=headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Insufficient permissions" in response.json()["detail"]


class TestLoanApplicationRetrieval:
    """Test loan application retrieval endpoint."""
    
    @patch('loan_origination.api.db_utils')
    def test_get_loan_application_success(self, mock_db_utils,
                                        client, underwriter_auth_headers, mock_db_loan, mock_db_customer):
        """Test successful loan application retrieval."""
        mock_db_utils.get_loan_by_loan_id.return_value = mock_db_loan
        
        # Mock the customer query in the session scope
        mock_session = Mock()
        mock_customer_query = Mock()
        mock_customer_query.first.return_value = mock_db_customer
        mock_session.query.return_value.filter.return_value = mock_customer_query
        mock_db_utils.db_manager.session_scope.return_value.__enter__.return_value = mock_session
        mock_db_utils.db_manager.session_scope.return_value.__exit__.return_value = None
        
        response = client.get(
            "/api/v1/loans/LOAN_123456",
            headers=underwriter_auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["loan_application_id"] == "LOAN_123456"
        assert data["customer_id"] == "CUST_123456789ABC"
        assert data["requested_amount"] == 50000.0
        assert data["application_status"] == "SUBMITTED"
        
        mock_db_utils.get_loan_by_loan_id.assert_called_once_with("LOAN_123456")
    
    @patch('loan_origination.api.db_utils')
    def test_get_loan_application_not_found(self, mock_db_utils, client, underwriter_auth_headers):
        """Test loan application retrieval when loan doesn't exist."""
        mock_db_utils.get_loan_by_loan_id.return_value = None
        
        response = client.get(
            "/api/v1/loans/NONEXISTENT",
            headers=underwriter_auth_headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]
    
    def test_get_loan_application_unauthorized(self, client):
        """Test loan application retrieval without authentication."""
        response = client.get("/api/v1/loans/LOAN_123456")
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestLoanStatusUpdate:
    """Test loan status update endpoint."""
    
    @patch('loan_origination.api.db_utils')
    @patch('loan_origination.api.get_fabric_gateway')
    def test_update_loan_status_success(self, mock_gateway, mock_db_utils,
                                      client, underwriter_auth_headers, mock_db_loan, mock_db_actor):
        """Test successful loan status update."""
        # Setup mocks
        mock_db_utils.get_loan_by_loan_id.return_value = mock_db_loan
        mock_db_utils.get_actor_by_actor_id.return_value = mock_db_actor
        mock_db_utils.update_loan_status.return_value = True
        
        # Mock blockchain interaction
        mock_gateway_instance = AsyncMock()
        mock_chaincode_client = AsyncMock()
        mock_chaincode_client.invoke_chaincode.return_value = {
            "transaction_id": "tx_status_123",
            "status": "SUCCESS"
        }
        mock_gateway.return_value = mock_gateway_instance
        
        # Update mock loan status for the second call
        updated_loan = Mock(spec=LoanApplicationModel)
        updated_loan.loan_application_id = "LOAN_123456"
        updated_loan.application_status = "UNDERWRITING"
        updated_loan.customer = mock_db_loan.customer
        updated_loan.application_date = mock_db_loan.application_date
        updated_loan.requested_amount = mock_db_loan.requested_amount
        updated_loan.loan_type = mock_db_loan.loan_type
        updated_loan.introducer_id = mock_db_loan.introducer_id
        updated_loan.current_owner_actor_id = mock_db_loan.current_owner_actor_id
        updated_loan.approval_amount = mock_db_loan.approval_amount
        updated_loan.rejection_reason = mock_db_loan.rejection_reason
        updated_loan.created_at = mock_db_loan.created_at
        updated_loan.updated_at = datetime.utcnow()
        
        # Mock the second call to return updated loan
        mock_db_utils.get_loan_by_loan_id.side_effect = [mock_db_loan, updated_loan]
        
        status_update = {
            "new_status": "UNDERWRITING",
            "notes": "Moving to underwriting review"
        }
        
        with patch('loan_origination.api.ChaincodeClient', return_value=mock_chaincode_client):
            response = client.put(
                "/api/v1/loans/LOAN_123456/status",
                json=status_update,
                headers=underwriter_auth_headers
            )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["application_status"] == "UNDERWRITING"
        
        # Verify database calls
        mock_db_utils.update_loan_status.assert_called_once_with(
            "LOAN_123456", "UNDERWRITING", mock_db_actor.id, "Moving to underwriting review"
        )
    
    @patch('loan_origination.api.db_utils')
    def test_update_loan_status_not_found(self, mock_db_utils, client, underwriter_auth_headers):
        """Test loan status update when loan doesn't exist."""
        mock_db_utils.get_loan_by_loan_id.return_value = None
        
        status_update = {"new_status": "UNDERWRITING"}
        
        response = client.put(
            "/api/v1/loans/NONEXISTENT/status",
            json=status_update,
            headers=underwriter_auth_headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    @patch('loan_origination.api.db_utils')
    def test_update_loan_status_same_status(self, mock_db_utils, client, underwriter_auth_headers, mock_db_loan):
        """Test loan status update with same status."""
        mock_db_utils.get_loan_by_loan_id.return_value = mock_db_loan
        
        status_update = {"new_status": "SUBMITTED"}  # Same as current status
        
        response = client.put(
            "/api/v1/loans/LOAN_123456/status",
            json=status_update,
            headers=underwriter_auth_headers
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already in" in response.json()["detail"]
    
    def test_update_loan_status_invalid_data(self, client, underwriter_auth_headers):
        """Test loan status update with invalid data."""
        invalid_update = {"new_status": "INVALID_STATUS"}
        
        response = client.put(
            "/api/v1/loans/LOAN_123456/status",
            json=invalid_update,
            headers=underwriter_auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestLoanApproval:
    """Test loan approval endpoint."""
    
    @patch('loan_origination.api.db_utils')
    @patch('loan_origination.api.get_fabric_gateway')
    def test_approve_loan_success(self, mock_gateway, mock_db_utils,
                                client, credit_officer_auth_headers, mock_db_loan, mock_db_actor):
        """Test successful loan approval."""
        # Setup mocks
        mock_db_utils.get_loan_by_loan_id.return_value = mock_db_loan
        mock_db_utils.get_actor_by_actor_id.return_value = mock_db_actor
        
        # Mock database session
        mock_session = Mock()
        mock_db_loan_query = Mock()
        mock_db_loan_query.first.return_value = mock_db_loan
        mock_session.query.return_value.filter.return_value = mock_db_loan_query
        mock_db_utils.db_manager.session_scope.return_value.__enter__.return_value = mock_session
        mock_db_utils.db_manager.session_scope.return_value.__exit__.return_value = None
        
        # Mock blockchain interaction
        mock_gateway_instance = AsyncMock()
        mock_chaincode_client = AsyncMock()
        mock_chaincode_client.invoke_chaincode.return_value = {
            "transaction_id": "tx_approval_123",
            "status": "SUCCESS"
        }
        mock_gateway.return_value = mock_gateway_instance
        
        # Update mock loan for the second call
        approved_loan = Mock(spec=LoanApplicationModel)
        approved_loan.loan_application_id = "LOAN_123456"
        approved_loan.application_status = "APPROVED"
        approved_loan.approval_amount = 45000.0
        approved_loan.customer = mock_db_loan.customer
        approved_loan.application_date = mock_db_loan.application_date
        approved_loan.requested_amount = mock_db_loan.requested_amount
        approved_loan.loan_type = mock_db_loan.loan_type
        approved_loan.introducer_id = mock_db_loan.introducer_id
        approved_loan.current_owner_actor_id = mock_db_loan.current_owner_actor_id
        approved_loan.rejection_reason = mock_db_loan.rejection_reason
        approved_loan.created_at = mock_db_loan.created_at
        approved_loan.updated_at = datetime.utcnow()
        
        mock_db_utils.get_loan_by_loan_id.side_effect = [mock_db_loan, approved_loan]
        
        approval_request = {
            "approval_amount": 45000.0,
            "notes": "Approved with conditions",
            "conditions": ["Provide additional income verification"]
        }
        
        with patch('loan_origination.api.ChaincodeClient', return_value=mock_chaincode_client):
            response = client.post(
                "/api/v1/loans/LOAN_123456/approve",
                json=approval_request,
                headers=credit_officer_auth_headers
            )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["application_status"] == "APPROVED"
        assert data["approval_amount"] == 45000.0
    
    @patch('loan_origination.api.db_utils')
    def test_approve_loan_already_approved(self, mock_db_utils, client, credit_officer_auth_headers):
        """Test loan approval when loan is already approved."""
        approved_loan = Mock(spec=LoanApplicationModel)
        approved_loan.application_status = "APPROVED"
        mock_db_utils.get_loan_by_loan_id.return_value = approved_loan
        
        approval_request = {"approval_amount": 45000.0}
        
        response = client.post(
            "/api/v1/loans/LOAN_123456/approve",
            json=approval_request,
            headers=credit_officer_auth_headers
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cannot approve loan" in response.json()["detail"]
    
    @patch('loan_origination.api.db_utils')
    def test_approve_loan_rejected_loan(self, mock_db_utils, client, credit_officer_auth_headers):
        """Test loan approval when loan is rejected."""
        rejected_loan = Mock(spec=LoanApplicationModel)
        rejected_loan.application_status = "REJECTED"
        mock_db_utils.get_loan_by_loan_id.return_value = rejected_loan
        
        approval_request = {"approval_amount": 45000.0}
        
        response = client.post(
            "/api/v1/loans/LOAN_123456/approve",
            json=approval_request,
            headers=credit_officer_auth_headers
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cannot approve a rejected loan" in response.json()["detail"]
    
    def test_approve_loan_invalid_amount(self, client, credit_officer_auth_headers):
        """Test loan approval with invalid amount."""
        invalid_approval = {"approval_amount": -1000.0}
        
        response = client.post(
            "/api/v1/loans/LOAN_123456/approve",
            json=invalid_approval,
            headers=credit_officer_auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_approve_loan_insufficient_permissions(self, client, underwriter_auth_headers):
        """Test loan approval with insufficient permissions."""
        approval_request = {"approval_amount": 45000.0}
        
        response = client.post(
            "/api/v1/loans/LOAN_123456/approve",
            json=approval_request,
            headers=underwriter_auth_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestLoanRejection:
    """Test loan rejection endpoint."""
    
    @patch('loan_origination.api.db_utils')
    @patch('loan_origination.api.get_fabric_gateway')
    def test_reject_loan_success(self, mock_gateway, mock_db_utils,
                               client, credit_officer_auth_headers, mock_db_loan, mock_db_actor):
        """Test successful loan rejection."""
        # Setup mocks
        mock_db_utils.get_loan_by_loan_id.return_value = mock_db_loan
        mock_db_utils.get_actor_by_actor_id.return_value = mock_db_actor
        
        # Mock database session
        mock_session = Mock()
        mock_db_loan_query = Mock()
        mock_db_loan_query.first.return_value = mock_db_loan
        mock_session.query.return_value.filter.return_value = mock_db_loan_query
        mock_db_utils.db_manager.session_scope.return_value.__enter__.return_value = mock_session
        mock_db_utils.db_manager.session_scope.return_value.__exit__.return_value = None
        
        # Mock blockchain interaction
        mock_gateway_instance = AsyncMock()
        mock_chaincode_client = AsyncMock()
        mock_chaincode_client.invoke_chaincode.return_value = {
            "transaction_id": "tx_rejection_123",
            "status": "SUCCESS"
        }
        mock_gateway.return_value = mock_gateway_instance
        
        # Update mock loan for the second call
        rejected_loan = Mock(spec=LoanApplicationModel)
        rejected_loan.loan_application_id = "LOAN_123456"
        rejected_loan.application_status = "REJECTED"
        rejected_loan.rejection_reason = "Insufficient income"
        rejected_loan.customer = mock_db_loan.customer
        rejected_loan.application_date = mock_db_loan.application_date
        rejected_loan.requested_amount = mock_db_loan.requested_amount
        rejected_loan.loan_type = mock_db_loan.loan_type
        rejected_loan.introducer_id = mock_db_loan.introducer_id
        rejected_loan.current_owner_actor_id = mock_db_loan.current_owner_actor_id
        rejected_loan.approval_amount = mock_db_loan.approval_amount
        rejected_loan.created_at = mock_db_loan.created_at
        rejected_loan.updated_at = datetime.utcnow()
        
        mock_db_utils.get_loan_by_loan_id.side_effect = [mock_db_loan, rejected_loan]
        
        rejection_request = {
            "rejection_reason": "Insufficient income",
            "notes": "Credit score below minimum threshold"
        }
        
        with patch('loan_origination.api.ChaincodeClient', return_value=mock_chaincode_client):
            response = client.post(
                "/api/v1/loans/LOAN_123456/reject",
                json=rejection_request,
                headers=credit_officer_auth_headers
            )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["application_status"] == "REJECTED"
        assert data["rejection_reason"] == "Insufficient income"
    
    @patch('loan_origination.api.db_utils')
    def test_reject_loan_already_rejected(self, mock_db_utils, client, credit_officer_auth_headers):
        """Test loan rejection when loan is already rejected."""
        rejected_loan = Mock(spec=LoanApplicationModel)
        rejected_loan.application_status = "REJECTED"
        mock_db_utils.get_loan_by_loan_id.return_value = rejected_loan
        
        rejection_request = {"rejection_reason": "Insufficient income"}
        
        response = client.post(
            "/api/v1/loans/LOAN_123456/reject",
            json=rejection_request,
            headers=credit_officer_auth_headers
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already rejected" in response.json()["detail"]
    
    @patch('loan_origination.api.db_utils')
    def test_reject_loan_approved_loan(self, mock_db_utils, client, credit_officer_auth_headers):
        """Test loan rejection when loan is approved."""
        approved_loan = Mock(spec=LoanApplicationModel)
        approved_loan.application_status = "APPROVED"
        mock_db_utils.get_loan_by_loan_id.return_value = approved_loan
        
        rejection_request = {"rejection_reason": "Changed decision"}
        
        response = client.post(
            "/api/v1/loans/LOAN_123456/reject",
            json=rejection_request,
            headers=credit_officer_auth_headers
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cannot reject loan" in response.json()["detail"]
    
    def test_reject_loan_missing_reason(self, client, credit_officer_auth_headers):
        """Test loan rejection without reason."""
        invalid_rejection = {}
        
        response = client.post(
            "/api/v1/loans/LOAN_123456/reject",
            json=invalid_rejection,
            headers=credit_officer_auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestLoanHistory:
    """Test loan history endpoint."""
    
    @patch('loan_origination.api.db_utils')
    def test_get_loan_history_success(self, mock_db_utils,
                                    client, underwriter_auth_headers, mock_db_loan):
        """Test successful loan history retrieval."""
        mock_db_utils.get_loan_by_loan_id.return_value = mock_db_loan
        
        # Mock history records
        mock_history = [
            Mock(
                id=1,
                change_type="STATUS_CHANGE",
                previous_status="SUBMITTED",
                new_status="UNDERWRITING",
                field_name="application_status",
                old_value="SUBMITTED",
                new_value="UNDERWRITING",
                changed_by_actor_id=1,
                blockchain_transaction_id="tx_123",
                timestamp=datetime.utcnow(),
                notes="Moving to underwriting"
            ),
            Mock(
                id=2,
                change_type="APPROVAL",
                previous_status="UNDERWRITING",
                new_status="APPROVED",
                field_name="approval_amount",
                old_value=None,
                new_value="45000.0",
                changed_by_actor_id=2,
                blockchain_transaction_id="tx_456",
                timestamp=datetime.utcnow(),
                notes="Approved with conditions"
            )
        ]
        mock_db_utils.get_loan_history.return_value = mock_history
        
        response = client.get(
            "/api/v1/loans/LOAN_123456/history",
            headers=underwriter_auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Check paginated response structure
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        
        # Check the actual history items
        assert len(data["items"]) == 2
        assert data["total"] == 2
        assert data["page"] == 1
        assert data["items"][0]["change_type"] == "STATUS_CHANGE"
        assert data["items"][1]["change_type"] == "APPROVAL"
        
        mock_db_utils.get_loan_history.assert_called_once_with("LOAN_123456")
    
    @patch('loan_origination.api.db_utils')
    def test_get_loan_history_not_found(self, mock_db_utils, client, underwriter_auth_headers):
        """Test loan history retrieval when loan doesn't exist."""
        mock_db_utils.get_loan_by_loan_id.return_value = None
        
        response = client.get(
            "/api/v1/loans/NONEXISTENT/history",
            headers=underwriter_auth_headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_get_loan_history_insufficient_permissions(self, client, introducer_auth_headers):
        """Test loan history retrieval with insufficient permissions."""
        response = client.get(
            "/api/v1/loans/LOAN_123456/history",
            headers=introducer_auth_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_generate_loan_application_id(self):
        """Test loan application ID generation."""
        loan_id = _generate_loan_application_id()
        assert loan_id.startswith("LOAN_")
        assert len(loan_id) == 17  # LOAN_ + 12 hex chars
        
        # Test uniqueness
        loan_id2 = _generate_loan_application_id()
        assert loan_id != loan_id2


class TestValidation:
    """Test input validation."""
    
    def test_loan_amount_validation(self):
        """Test loan amount validation."""
        from loan_origination.api import LoanApplicationCreate
        
        # Valid amount
        data = {
            "customer_id": "CUST_123",
            "requested_amount": 50000.0,
            "loan_type": "PERSONAL"
        }
        loan = LoanApplicationCreate(**data)
        assert loan.requested_amount == 50000.0
        
        # Invalid amounts
        with pytest.raises(ValueError):
            LoanApplicationCreate(
                customer_id="CUST_123",
                requested_amount=-1000.0,  # Negative
                loan_type="PERSONAL"
            )
        
        with pytest.raises(ValueError):
            LoanApplicationCreate(
                customer_id="CUST_123",
                requested_amount=20_000_000.0,  # Too large
                loan_type="PERSONAL"
            )
    
    def test_loan_type_validation(self):
        """Test loan type validation."""
        from loan_origination.api import LoanApplicationCreate
        
        # Valid loan types
        valid_types = ["PERSONAL", "MORTGAGE", "BUSINESS", "AUTO", "EDUCATION"]
        
        for loan_type in valid_types:
            data = {
                "customer_id": "CUST_123",
                "requested_amount": 50000.0,
                "loan_type": loan_type
            }
            loan = LoanApplicationCreate(**data)
            assert loan.loan_type.value == loan_type
        
        # Invalid loan type
        with pytest.raises(ValueError):
            LoanApplicationCreate(
                customer_id="CUST_123",
                requested_amount=50000.0,
                loan_type="INVALID_TYPE"
            )
    
    def test_status_validation(self):
        """Test application status validation."""
        from loan_origination.api import LoanStatusUpdate
        
        # Valid statuses
        valid_statuses = ["SUBMITTED", "UNDERWRITING", "CREDIT_APPROVAL", "APPROVED", "REJECTED", "DISBURSED"]
        
        for status_val in valid_statuses:
            update = LoanStatusUpdate(new_status=status_val)
            assert update.new_status.value == status_val
        
        # Invalid status
        with pytest.raises(ValueError):
            LoanStatusUpdate(new_status="INVALID_STATUS")
    
    def test_required_fields(self):
        """Test required field validation."""
        from loan_origination.api import LoanApplicationCreate, LoanRejectionRequest
        
        # Missing required fields for loan creation
        with pytest.raises(ValueError):
            LoanApplicationCreate()
        
        with pytest.raises(ValueError):
            LoanApplicationCreate(customer_id="CUST_123")  # Missing amount and type
        
        # Missing required fields for rejection
        with pytest.raises(ValueError):
            LoanRejectionRequest()  # Missing rejection_reason
        
        # Valid minimal data
        loan = LoanApplicationCreate(
            customer_id="CUST_123",
            requested_amount=50000.0,
            loan_type="PERSONAL"
        )
        assert loan.customer_id == "CUST_123"
        assert loan.requested_amount == 50000.0
        assert loan.loan_type == LoanType.PERSONAL


class TestBusinessLogic:
    """Test business logic and edge cases."""
    
    def test_approval_amount_different_from_requested(self):
        """Test approval with different amount than requested."""
        from loan_origination.api import LoanApprovalRequest
        
        approval = LoanApprovalRequest(
            approval_amount=40000.0,  # Less than typical requested amount
            notes="Approved for lower amount due to credit score"
        )
        assert approval.approval_amount == 40000.0
        assert approval.notes == "Approved for lower amount due to credit score"
    
    def test_approval_with_conditions(self):
        """Test approval with conditions."""
        from loan_origination.api import LoanApprovalRequest
        
        approval = LoanApprovalRequest(
            approval_amount=50000.0,
            conditions=[
                "Provide additional income verification",
                "Maintain minimum account balance",
                "Complete financial counseling"
            ]
        )
        assert len(approval.conditions) == 3
        assert "income verification" in approval.conditions[0]
    
    def test_rejection_with_detailed_reason(self):
        """Test rejection with detailed reason."""
        from loan_origination.api import LoanRejectionRequest
        
        rejection = LoanRejectionRequest(
            rejection_reason="Insufficient income",
            notes="Debt-to-income ratio exceeds 40% threshold. Credit score below minimum requirement of 650."
        )
        assert rejection.rejection_reason == "Insufficient income"
        assert "debt-to-income" in rejection.notes.lower()