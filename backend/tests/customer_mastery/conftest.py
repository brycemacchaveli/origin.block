"""
Customer Mastery domain-specific test configuration and fixtures.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from shared.database import CustomerModel, CustomerHistoryModel


@pytest.fixture
def customer_mastery_mock_db_utils():
    """Mock database utilities specifically for customer mastery tests."""
    mock_db_utils = Mock()
    
    # Configure common customer mastery database operations
    mock_db_utils.get_customer_by_customer_id.return_value = None
    mock_db_utils.create_customer.return_value = Mock(spec=CustomerModel)
    mock_db_utils.get_customer_history.return_value = []
    
    return mock_db_utils


@pytest.fixture
def sample_kyc_data():
    """Sample KYC verification data."""
    return {
        "document_type": "passport",
        "document_number": "P123456789",
        "issuing_country": "US",
        "expiry_date": "2030-12-31",
        "verification_provider": "test_provider"
    }


@pytest.fixture
def sample_aml_data():
    """Sample AML check data."""
    return {
        "check_type": "sanctions_screening",
        "provider": "test_aml_provider",
        "risk_score": 0.1,
        "match_found": False,
        "details": {
            "lists_checked": ["OFAC", "EU_SANCTIONS"],
            "check_timestamp": datetime.utcnow().isoformat()
        }
    }


@pytest.fixture
def sample_consent_update():
    """Sample consent preferences update."""
    return {
        "data_sharing": True,
        "marketing": False,
        "analytics": True,
        "third_party_sharing": False,
        "retention_period": 24
    }


@pytest.fixture
def mock_identity_provider():
    """Mock identity verification provider."""
    with patch('customer_mastery.api._simulate_identity_provider_call') as mock_provider:
        mock_provider.return_value = {
            "provider_reference": "test_verification_123",
            "confidence_score": 0.95,
            "checks_performed": ["document_verification", "liveness_check"],
            "estimated_completion": "2-5 minutes"
        }
        yield mock_provider