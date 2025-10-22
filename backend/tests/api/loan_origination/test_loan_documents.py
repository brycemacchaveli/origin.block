"""
Unit tests for loan document management endpoints.

Tests document upload, retrieval, status updates, and hash verification
functionality in the loan origination API.
"""

import pytest
import json
import hashlib
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from io import BytesIO

from fastapi.testclient import TestClient
from fastapi import FastAPI, UploadFile

from loan_origination.api import router
from shared.auth import Actor, ActorType, Role, Permission
from shared.database import LoanApplicationModel, CustomerModel, LoanDocumentModel, ActorModel


@pytest.fixture
def mock_actor():
    """Create a mock actor for testing."""
    return Actor(
        actor_id="TEST_ACTOR_001",
        actor_type=ActorType.INTERNAL_USER,
        actor_name="Test User",
        role=Role.UNDERWRITER,
        permissions={
            Permission.READ_LOAN_APPLICATION,
            Permission.MANAGE_LOAN_DOCUMENTS
        }
    )


@pytest.fixture
def mock_loan():
    """Create a mock loan application."""
    return LoanApplicationModel(
        id=1,
        loan_application_id="LOAN_TEST123",
        customer_id=1,
        application_date=datetime.utcnow(),
        requested_amount=50000.0,
        loan_type="PERSONAL",
        application_status="SUBMITTED",
        current_owner_actor_id=1,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def mock_customer():
    """Create a mock customer."""
    return CustomerModel(
        id=1,
        customer_id="CUST_TEST123",
        first_name="John",
        last_name="Doe",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def mock_document():
    """Create a mock loan document."""
    return LoanDocumentModel(
        id=1,
        loan_application_id=1,
        document_type="IDENTITY",
        document_name="passport.pdf",
        document_hash="abc123def456",
        file_size=1024,
        mime_type="application/pdf",
        verification_status="PENDING",
        uploaded_by_actor_id=1,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def sample_file_content():
    """Create sample file content for testing."""
    return b"This is a test document content for hashing"


@pytest.fixture
def test_app():
    """Create a test FastAPI app."""
    app = FastAPI()
    app.include_router(router, prefix="/loans")
    return app


class TestDocumentUpload:
    """Test document upload functionality."""
    
    @patch('loan_origination.api.db_utils')
    @patch('loan_origination.api.get_fabric_gateway')
    @patch('loan_origination.api.require_permissions')
    def test_upload_document_success(self, mock_require_permissions, mock_gateway, mock_db_utils, 
                                   mock_actor, mock_loan, mock_customer, sample_file_content):
        """Test successful document upload."""
        # Setup mocks
        mock_require_permissions.return_value = mock_actor
        mock_db_utils.get_loan_by_loan_id.return_value = mock_loan
        mock_db_utils.get_customer_by_customer_id.return_value = mock_customer
        mock_db_utils.get_actor_by_actor_id.return_value = ActorModel(id=1, actor_id="TEST_ACTOR_001")
        
        # Mock document creation
        mock_document = LoanDocumentModel(
            id=1,
            loan_application_id=1,
            document_type="IDENTITY",
            document_name="test_document.pdf",
            document_hash=hashlib.sha256(sample_file_content).hexdigest(),
            file_size=len(sample_file_content),
            mime_type="application/pdf",
            verification_status="PENDING",
            uploaded_by_actor_id=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        mock_db_utils.create_loan_document.return_value = mock_document
        
        # Mock blockchain gateway
        mock_gateway_instance = AsyncMock()
        mock_gateway_instance.invoke_chaincode.return_value = {"transaction_id": "tx123"}
        mock_gateway.return_value = mock_gateway_instance
        
        # Create test file
        file_data = BytesIO(sample_file_content)
        
        with TestClient(router) as client:
            response = client.post(
                "/LOAN_TEST123/documents",
                files={"file": ("test_document.pdf", file_data, "application/pdf")},
                data={
                    "document_type": "IDENTITY",
                    "document_name": "test_document.pdf"
                }
            )
        
        assert response.status_code == 201
        response_data = response.json()
        assert response_data["document_type"] == "IDENTITY"
        assert response_data["document_name"] == "test_document.pdf"
        assert response_data["verification_status"] == "PENDING"
        assert "document_hash" in response_data
    
    @patch('loan_origination.api.db_utils')
    @patch('loan_origination.api.require_permissions')
    def test_upload_document_loan_not_found(self, mock_require_permissions, mock_db_utils, mock_actor):
        """Test document upload when loan doesn't exist."""
        # Setup mocks
        mock_require_permissions.return_value = mock_actor
        mock_db_utils.get_loan_by_loan_id.return_value = None
        
        file_data = BytesIO(b"test content")
        
        with TestClient(router) as client:
            response = client.post(
                "/NONEXISTENT_LOAN/documents",
                files={"file": ("test.pdf", file_data, "application/pdf")},
                data={"document_type": "IDENTITY"}
            )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    @patch('loan_origination.api.require_permissions')
    def test_upload_document_file_too_large(self, mock_require_permissions, mock_actor):
        """Test document upload with file too large."""
        mock_require_permissions.return_value = mock_actor
        
        # Create a large file (>10MB)
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB
        file_data = BytesIO(large_content)
        
        with TestClient(router) as client:
            response = client.post(
                "/LOAN_TEST123/documents",
                files={"file": ("large_file.pdf", file_data, "application/pdf")},
                data={"document_type": "IDENTITY"}
            )
        
        assert response.status_code == 413
        assert "exceeds" in response.json()["detail"].lower()
    
    @patch('loan_origination.api.require_permissions')
    def test_upload_document_invalid_file_type(self, mock_require_permissions, mock_actor):
        """Test document upload with invalid file type."""
        mock_require_permissions.return_value = mock_actor
        
        file_data = BytesIO(b"test content")
        
        with TestClient(router) as client:
            response = client.post(
                "/LOAN_TEST123/documents",
                files={"file": ("test.exe", file_data, "application/x-executable")},
                data={"document_type": "IDENTITY"}
            )
        
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"].lower()


class TestDocumentRetrieval:
    """Test document retrieval functionality."""
    
    @patch('loan_origination.api.db_utils')
    @patch('loan_origination.api.require_permissions')
    def test_get_loan_documents_success(self, mock_require_permissions, mock_db_utils, 
                                      mock_actor, mock_loan, mock_document, test_app):
        """Test successful document retrieval."""
        # Setup mocks
        mock_require_permissions.return_value = mock_actor
        mock_db_utils.get_loan_by_loan_id.return_value = mock_loan
        mock_db_utils.get_loan_documents.return_value = [mock_document]
        
        with TestClient(test_app) as client:
            response = client.get("/loans/LOAN_TEST123/documents")
        
        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data) == 1
        assert response_data[0]["document_type"] == "IDENTITY"
        assert response_data[0]["document_name"] == "passport.pdf"
    
    @patch('loan_origination.api.db_utils')
    @patch('loan_origination.api.require_permissions')
    def test_get_loan_documents_with_filters(self, mock_require_permissions, mock_db_utils, 
                                           mock_actor, mock_loan):
        """Test document retrieval with filters."""
        # Setup mocks
        mock_require_permissions.return_value = mock_actor
        mock_db_utils.get_loan_by_loan_id.return_value = mock_loan
        
        # Create multiple documents with different types and statuses
        documents = [
            LoanDocumentModel(
                id=1, loan_application_id=1, document_type="IDENTITY",
                document_name="passport.pdf", document_hash="hash1",
                verification_status="VERIFIED", uploaded_by_actor_id=1,
                created_at=datetime.utcnow(), updated_at=datetime.utcnow()
            ),
            LoanDocumentModel(
                id=2, loan_application_id=1, document_type="INCOME_PROOF",
                document_name="salary.pdf", document_hash="hash2",
                verification_status="PENDING", uploaded_by_actor_id=1,
                created_at=datetime.utcnow(), updated_at=datetime.utcnow()
            )
        ]
        mock_db_utils.get_loan_documents.return_value = documents
        
        with TestClient(router) as client:
            # Test filter by document type
            response = client.get("/LOAN_TEST123/documents?document_type=IDENTITY")
            assert response.status_code == 200
            response_data = response.json()
            assert len(response_data) == 1
            assert response_data[0]["document_type"] == "IDENTITY"
            
            # Test filter by verification status
            response = client.get("/LOAN_TEST123/documents?verification_status=VERIFIED")
            assert response.status_code == 200
            response_data = response.json()
            assert len(response_data) == 1
            assert response_data[0]["verification_status"] == "VERIFIED"
    
    @patch('loan_origination.api.db_utils')
    @patch('loan_origination.api.require_permissions')
    def test_get_loan_documents_empty_result(self, mock_require_permissions, mock_db_utils, 
                                           mock_actor, mock_loan):
        """Test document retrieval with no documents."""
        # Setup mocks
        mock_require_permissions.return_value = mock_actor
        mock_db_utils.get_loan_by_loan_id.return_value = mock_loan
        mock_db_utils.get_loan_documents.return_value = []
        
        with TestClient(router) as client:
            response = client.get("/LOAN_TEST123/documents")
        
        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data) == 0


class TestDocumentStatusUpdate:
    """Test document status update functionality."""
    
    @patch('loan_origination.api.db_utils')
    @patch('loan_origination.api.get_fabric_gateway')
    @patch('loan_origination.api.require_permissions')
    def test_update_document_status_success(self, mock_require_permissions, mock_gateway, 
                                          mock_db_utils, mock_actor, mock_loan, mock_document):
        """Test successful document status update."""
        # Setup mocks
        mock_require_permissions.return_value = mock_actor
        mock_db_utils.get_loan_by_loan_id.return_value = mock_loan
        mock_db_utils.get_loan_document_by_id.return_value = mock_document
        mock_db_utils.update_document_verification_status.return_value = True
        
        # Mock updated document
        updated_document = mock_document
        updated_document.verification_status = "VERIFIED"
        mock_db_utils.get_loan_document_by_id.return_value = updated_document
        
        # Mock blockchain gateway
        mock_gateway_instance = AsyncMock()
        mock_gateway_instance.invoke_chaincode.return_value = {"transaction_id": "tx123"}
        mock_gateway.return_value = mock_gateway_instance
        
        with TestClient(router) as client:
            response = client.put(
                "/LOAN_TEST123/documents/1/status",
                json={
                    "verification_status": "VERIFIED",
                    "notes": "Document verified successfully"
                }
            )
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["verification_status"] == "VERIFIED"
    
    @patch('loan_origination.api.db_utils')
    @patch('loan_origination.api.require_permissions')
    def test_update_document_status_document_not_found(self, mock_require_permissions, 
                                                     mock_db_utils, mock_actor, mock_loan):
        """Test document status update when document doesn't exist."""
        # Setup mocks
        mock_require_permissions.return_value = mock_actor
        mock_db_utils.get_loan_by_loan_id.return_value = mock_loan
        mock_db_utils.get_loan_document_by_id.return_value = None
        
        with TestClient(router) as client:
            response = client.put(
                "/LOAN_TEST123/documents/999/status",
                json={"verification_status": "VERIFIED"}
            )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    @patch('loan_origination.api.db_utils')
    @patch('loan_origination.api.require_permissions')
    def test_update_document_status_wrong_loan(self, mock_require_permissions, mock_db_utils, 
                                             mock_actor, mock_loan, mock_document):
        """Test document status update when document belongs to different loan."""
        # Setup mocks
        mock_require_permissions.return_value = mock_actor
        mock_db_utils.get_loan_by_loan_id.return_value = mock_loan
        
        # Document belongs to different loan
        wrong_document = mock_document
        wrong_document.loan_application_id = 999
        mock_db_utils.get_loan_document_by_id.return_value = wrong_document
        
        with TestClient(router) as client:
            response = client.put(
                "/LOAN_TEST123/documents/1/status",
                json={"verification_status": "VERIFIED"}
            )
        
        assert response.status_code == 400
        assert "does not belong" in response.json()["detail"].lower()


class TestDocumentHashVerification:
    """Test document hash verification functionality."""
    
    @patch('loan_origination.api.db_utils')
    @patch('loan_origination.api.get_fabric_gateway')
    @patch('loan_origination.api.require_permissions')
    def test_verify_document_hash_success(self, mock_require_permissions, mock_gateway, 
                                        mock_db_utils, mock_actor, mock_loan, mock_document):
        """Test successful document hash verification."""
        # Setup mocks
        mock_require_permissions.return_value = mock_actor
        mock_db_utils.get_loan_by_loan_id.return_value = mock_loan
        mock_db_utils.get_loan_document_by_id.return_value = mock_document
        
        # Mock blockchain gateway
        mock_gateway_instance = AsyncMock()
        mock_gateway_instance.invoke_chaincode.return_value = {
            "success": True,
            "stored_hash": "abc123def456",
            "hash_match": True,
            "transaction_id": "tx123"
        }
        mock_gateway.return_value = mock_gateway_instance
        
        with TestClient(router) as client:
            response = client.post("/LOAN_TEST123/documents/1/verify")
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["blockchain_verified"] is True
        assert response_data["verification_details"]["match"] is True
        assert response_data["document_hash"] == "abc123def456"
    
    @patch('loan_origination.api.db_utils')
    @patch('loan_origination.api.get_fabric_gateway')
    @patch('loan_origination.api.require_permissions')
    def test_verify_document_hash_mismatch(self, mock_require_permissions, mock_gateway, 
                                         mock_db_utils, mock_actor, mock_loan, mock_document):
        """Test document hash verification with hash mismatch."""
        # Setup mocks
        mock_require_permissions.return_value = mock_actor
        mock_db_utils.get_loan_by_loan_id.return_value = mock_loan
        mock_db_utils.get_loan_document_by_id.return_value = mock_document
        
        # Mock blockchain gateway with hash mismatch
        mock_gateway_instance = AsyncMock()
        mock_gateway_instance.invoke_chaincode.return_value = {
            "success": True,
            "stored_hash": "different_hash",
            "hash_match": False,
            "transaction_id": "tx123"
        }
        mock_gateway.return_value = mock_gateway_instance
        
        with TestClient(router) as client:
            response = client.post("/LOAN_TEST123/documents/1/verify")
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["blockchain_verified"] is True
        assert response_data["verification_details"]["match"] is False
    
    @patch('loan_origination.api.db_utils')
    @patch('loan_origination.api.get_fabric_gateway')
    @patch('loan_origination.api.require_permissions')
    def test_verify_document_hash_blockchain_error(self, mock_require_permissions, mock_gateway, 
                                                  mock_db_utils, mock_actor, mock_loan, mock_document):
        """Test document hash verification with blockchain error."""
        # Setup mocks
        mock_require_permissions.return_value = mock_actor
        mock_db_utils.get_loan_by_loan_id.return_value = mock_loan
        mock_db_utils.get_loan_document_by_id.return_value = mock_document
        
        # Mock blockchain gateway with error
        mock_gateway_instance = AsyncMock()
        mock_gateway_instance.invoke_chaincode.side_effect = Exception("Blockchain connection failed")
        mock_gateway.return_value = mock_gateway_instance
        
        with TestClient(router) as client:
            response = client.post("/LOAN_TEST123/documents/1/verify")
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["blockchain_verified"] is False
        assert "error" in response_data["verification_details"]


class TestDocumentValidation:
    """Test document validation functionality."""
    
    def test_calculate_file_hash(self, sample_file_content):
        """Test file hash calculation."""
        from loan_origination.api import _calculate_file_hash
        
        expected_hash = hashlib.sha256(sample_file_content).hexdigest()
        calculated_hash = _calculate_file_hash(sample_file_content)
        
        assert calculated_hash == expected_hash
    
    def test_generate_document_id(self):
        """Test document ID generation."""
        from loan_origination.api import _generate_document_id
        
        doc_id = _generate_document_id()
        assert doc_id.startswith("DOC_")
        assert len(doc_id) == 20  # DOC_ + 16 hex characters
    
    def test_validate_file_upload_valid_file(self):
        """Test file upload validation with valid file."""
        from loan_origination.api import _validate_file_upload
        
        # Create mock UploadFile
        mock_file = Mock(spec=UploadFile)
        mock_file.size = 1024  # 1KB
        mock_file.content_type = "application/pdf"
        
        # Should not raise exception
        _validate_file_upload(mock_file)
    
    def test_validate_file_upload_file_too_large(self):
        """Test file upload validation with file too large."""
        from loan_origination.api import _validate_file_upload
        from fastapi import HTTPException
        
        # Create mock UploadFile
        mock_file = Mock(spec=UploadFile)
        mock_file.size = 11 * 1024 * 1024  # 11MB
        mock_file.content_type = "application/pdf"
        
        with pytest.raises(HTTPException) as exc_info:
            _validate_file_upload(mock_file)
        
        assert exc_info.value.status_code == 413
    
    def test_validate_file_upload_invalid_type(self):
        """Test file upload validation with invalid file type."""
        from loan_origination.api import _validate_file_upload
        from fastapi import HTTPException
        
        # Create mock UploadFile
        mock_file = Mock(spec=UploadFile)
        mock_file.size = 1024  # 1KB
        mock_file.content_type = "application/x-executable"
        
        with pytest.raises(HTTPException) as exc_info:
            _validate_file_upload(mock_file)
        
        assert exc_info.value.status_code == 400