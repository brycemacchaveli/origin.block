"""
Integration test configuration and fixtures.
"""

import pytest
from unittest.mock import patch
import asyncio


@pytest.fixture(scope="session")
def integration_event_loop():
    """Event loop for integration tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture
def integration_test_data():
    """Complete test data set for integration tests."""
    return {
        "actor": {
            "actor_id": "integration_test_001",
            "actor_type": "Internal_User",
            "actor_name": "Integration Test User",
            "role": "Underwriter",
            "permissions": ["read_customer", "read_loan_application", "update_loan_application"]
        },
        "customer": {
            "first_name": "Integration",
            "last_name": "Test",
            "date_of_birth": "1985-06-15T00:00:00",
            "national_id": "INT123456789",
            "address": "123 Integration St, Test City, TC 12345",
            "contact_email": "integration.test@example.com",
            "contact_phone": "+1-555-999-0000",
            "consent_preferences": {
                "data_sharing": True,
                "marketing": True,
                "analytics": False
            }
        },
        "loan": {
            "requested_amount": 75000.0,
            "loan_type": "PERSONAL",
            "introducer_id": "INTRO_INTEGRATION",
            "additional_info": {
                "purpose": "Integration testing",
                "employment_status": "Full-time",
                "annual_income": 90000.0
            }
        }
    }


@pytest.fixture
def mock_external_apis():
    """Mock all external API calls for integration tests."""
    with patch('shared.fabric_gateway.get_fabric_gateway') as mock_fabric:
        with patch('customer_mastery.api._simulate_identity_provider_call') as mock_kyc:
            with patch('loan_origination.api._perform_credit_check') as mock_credit:
                # Configure fabric gateway
                mock_fabric.return_value.invoke_chaincode.return_value = {
                    "transaction_id": "integration_tx_123",
                    "status": "SUCCESS"
                }
                
                # Configure KYC provider
                mock_kyc.return_value = {
                    "provider_reference": "integration_kyc_123",
                    "confidence_score": 0.98,
                    "checks_performed": ["document_verification", "liveness_check"]
                }
                
                # Configure credit check
                mock_credit.return_value = {
                    "credit_score": 750,
                    "risk_grade": "A",
                    "recommendation": "APPROVE"
                }
                
                yield {
                    'fabric': mock_fabric,
                    'kyc': mock_kyc,
                    'credit': mock_credit
                }