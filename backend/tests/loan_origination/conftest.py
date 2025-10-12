"""
Loan Origination domain-specific test configuration and fixtures.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from io import BytesIO

from shared.database import LoanApplicationModel, LoanApplicationHistoryModel, LoanDocumentModel


@pytest.fixture
def loan_origination_mock_db_utils():
    """Mock database utilities specifically for loan origination tests."""
    mock_db_utils = Mock()
    
    # Configure common loan origination database operations
    mock_db_utils.get_loan_by_loan_id.return_value = None
    mock_db_utils.create_loan_application.return_value = Mock(spec=LoanApplicationModel)
    mock_db_utils.update_loan_status.return_value = True
    mock_db_utils.get_loan_history.return_value = []
    mock_db_utils.get_loan_documents.return_value = []
    
    return mock_db_utils


@pytest.fixture
def sample_loan_update_data():
    """Sample loan application update data."""
    return {
        "requested_amount": 45000.0,
        "additional_info": {
            "purpose": "Updated purpose",
            "employment_status": "Full-time",
            "annual_income": 75000.0
        }
    }


@pytest.fixture
def sample_loan_approval_data():
    """Sample loan approval data."""
    return {
        "approval_amount": 40000.0,
        "notes": "Approved with conditions",
        "conditions": [
            "Provide additional income verification",
            "Maintain current employment"
        ],
        "interest_rate": 5.5,
        "term_months": 60
    }


@pytest.fixture
def sample_loan_rejection_data():
    """Sample loan rejection data."""
    return {
        "rejection_reason": "Insufficient income",
        "notes": "Credit score below minimum threshold",
        "rejection_code": "INCOME_001"
    }


@pytest.fixture
def sample_document_upload_data():
    """Sample document upload data."""
    return {
        "document_type": "IDENTITY",
        "document_name": "passport.pdf",
        "description": "Customer passport for identity verification"
    }


@pytest.fixture
def sample_document_file():
    """Sample document file for upload testing."""
    content = b"This is a test PDF document content"
    return BytesIO(content)


@pytest.fixture
def sample_loan_status_update():
    """Sample loan status update data."""
    return {
        "new_status": "UNDERWRITING",
        "notes": "Moving to underwriting review",
        "assigned_to": "underwriter_002"
    }


@pytest.fixture
def mock_document_storage():
    """Mock document storage service."""
    with patch('loan_origination.api._store_document') as mock_storage:
        mock_storage.return_value = {
            "storage_path": "/documents/test_document.pdf",
            "storage_id": "storage_123",
            "checksum": "abc123def456"
        }
        yield mock_storage


@pytest.fixture
def mock_credit_scoring():
    """Mock credit scoring service."""
    with patch('loan_origination.api._perform_credit_check') as mock_credit:
        mock_credit.return_value = {
            "credit_score": 720,
            "risk_grade": "B",
            "recommendation": "APPROVE",
            "factors": ["Good payment history", "Stable employment"]
        }
        yield mock_credit