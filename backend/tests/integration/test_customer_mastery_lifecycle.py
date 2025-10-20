"""
Integration tests for customer mastery data lifecycle.

Tests the complete customer data management workflow including creation, updates,
consent management, KYC/AML validation, and data integrity verification.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json
from datetime import datetime, timedelta

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def customer_lifecycle_data():
    """Test data for customer lifecycle testing."""
    return {
        "initial_customer": {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "1985-06-15T00:00:00",
            "national_id": "ID123456789",
            "address": "123 Main St, Anytown, AT 12345",
            "contact_email": "john.doe@example.com",
            "contact_phone": "+1-555-123-4567",
            "consent_preferences": {
                "data_sharing": True,
                "marketing": False,
                "analytics": True
            }
        },
        "updated_customer": {
            "address": "456 New St, Newtown, NT 67890",
            "contact_email": "john.doe.new@example.com",
            "contact_phone": "+1-555-987-6543"
        },
        "consent_update": {
            "data_sharing": False,
            "marketing": True,
            "analytics": True
        },
        "actor": {
            "actor_id": "CSR_001",
            "actor_type": "Internal_User",
            "actor_name": "Customer Service Rep",
            "role": "Customer_Service_Representative"
        }
    }


@pytest.fixture
def mock_customer_services():
    """Mock blockchain and external services for customer tests."""
    from .mock_infrastructure import IntegrationTestMockManager
    
    mock_manager = IntegrationTestMockManager()
    with mock_manager.mock_all_services() as mocks:
        yield {
            'mock_manager': mock_manager,
            'mocks': mocks
        }


class TestCustomerMasteryLifecycle:
    """Test complete customer data lifecycle."""
    
    def test_complete_customer_lifecycle(self, client, customer_lifecycle_data, mock_customer_services):
        """Test complete customer lifecycle from creation to updates."""
        
        # Step 1: Create new customer
        response = client.post(
            "/api/v1/customers",
            json=customer_lifecycle_data["initial_customer"],
            headers={"X-Actor-ID": customer_lifecycle_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 201
        customer_data = response.json()
        assert "customer_id" in customer_data
        assert customer_data["kyc_status"] == "PENDING"
        assert customer_data["aml_status"] == "PENDING"
        customer_id = customer_data["customer_id"]
        
        # Verify transaction was recorded
        transaction_history = mock_customer_services['mock_manager'].get_transaction_history()
        assert len(transaction_history) >= 1
        assert any("customer" in tx["chaincode_name"].lower() for tx in transaction_history)
        
        # Step 3: Retrieve customer data
        response = client.get(
            f"/api/v1/customers/{customer_id}",
            headers={"X-Actor-ID": customer_lifecycle_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 200
        retrieved_data = response.json()
        assert retrieved_data["customer_id"] == customer_id
        assert retrieved_data["first_name"] == customer_lifecycle_data["initial_customer"]["first_name"]
        
        # Step 4: Update customer information
        response = client.put(
            f"/api/v1/customers/{customer_id}",
            json=customer_lifecycle_data["updated_customer"],
            headers={"X-Actor-ID": customer_lifecycle_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 200
        updated_data = response.json()
        assert updated_data["address"] == customer_lifecycle_data["updated_customer"]["address"]
        assert updated_data["contact_email"] == customer_lifecycle_data["updated_customer"]["contact_email"]
        
        # Step 5: Update consent preferences
        response = client.put(
            f"/api/v1/customers/{customer_id}/consent",
            json=customer_lifecycle_data["consent_update"],
            headers={"X-Actor-ID": customer_lifecycle_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 200
        consent_data = response.json()
        assert consent_data["consent_preferences"]["data_sharing"] == customer_lifecycle_data["consent_update"]["data_sharing"]
        assert consent_data["consent_preferences"]["marketing"] == customer_lifecycle_data["consent_update"]["marketing"]
        
        # Step 6: Verify complete history tracking
        response = client.get(
            f"/api/v1/customers/{customer_id}/history",
            headers={"X-Actor-ID": customer_lifecycle_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 200
        history_data = response.json()
        assert len(history_data["history"]) >= 3  # Creation, update, consent update
        
        # Verify history contains expected change types
        change_types = [entry["change_type"] for entry in history_data["history"]]
        assert "CUSTOMER_CREATED" in change_types
        assert "CUSTOMER_UPDATED" in change_types
        assert "CONSENT_UPDATED" in change_types
    
    def test_kyc_aml_validation_workflow(self, client, customer_lifecycle_data, mock_customer_services):
        """Test KYC/AML validation workflow."""
        
        # Create customer
        response = client.post(
            "/api/v1/customers",
            json=customer_lifecycle_data["initial_customer"],
            headers={"X-Actor-ID": customer_lifecycle_data["actor"]["actor_id"]}
        )
        customer_id = response.json()["customer_id"]
        
        # Trigger identity verification
        response = client.post(
            f"/api/v1/customers/{customer_id}/verify-identity",
            json={
                "verification_type": "ENHANCED_KYC",
                "documents_provided": ["PASSPORT", "UTILITY_BILL"]
            },
            headers={"X-Actor-ID": customer_lifecycle_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 200
        verification_data = response.json()
        assert "provider_reference" in verification_data
        assert verification_data["confidence_score"] >= 0.8
        
        # Check KYC status update
        response = client.get(
            f"/api/v1/customers/{customer_id}",
            headers={"X-Actor-ID": customer_lifecycle_data["actor"]["actor_id"]}
        )
        
        customer_data = response.json()
        assert customer_data["kyc_status"] in ["VERIFIED", "PENDING"]
    
    def test_consent_management_workflow(self, client, customer_lifecycle_data, mock_customer_services):
        """Test comprehensive consent management."""
        
        # Create customer
        response = client.post(
            "/api/v1/customers",
            json=customer_lifecycle_data["initial_customer"],
            headers={"X-Actor-ID": customer_lifecycle_data["actor"]["actor_id"]}
        )
        customer_id = response.json()["customer_id"]
        
        # Test consent retrieval
        response = client.get(
            f"/api/v1/customers/{customer_id}/consent",
            headers={"X-Actor-ID": customer_lifecycle_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 200
        consent_data = response.json()
        assert "consent_preferences" in consent_data
        assert "consent_history" in consent_data
        
        # Test granular consent updates
        granular_consent = {
            "data_sharing": False,
            "marketing": True,
            "analytics": False,
            "third_party_sharing": False
        }
        
        response = client.put(
            f"/api/v1/customers/{customer_id}/consent",
            json=granular_consent,
            headers={"X-Actor-ID": customer_lifecycle_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 200
        
        # Verify consent history tracking
        response = client.get(
            f"/api/v1/customers/{customer_id}/consent",
            headers={"X-Actor-ID": customer_lifecycle_data["actor"]["actor_id"]}
        )
        
        consent_data = response.json()
        assert len(consent_data["consent_history"]) >= 2  # Initial + update
    
    def test_data_integrity_and_versioning(self, client, customer_lifecycle_data, mock_customer_services):
        """Test data integrity and versioning capabilities."""
        
        # Create customer
        response = client.post(
            "/api/v1/customers",
            json=customer_lifecycle_data["initial_customer"],
            headers={"X-Actor-ID": customer_lifecycle_data["actor"]["actor_id"]}
        )
        customer_id = response.json()["customer_id"]
        
        # Make multiple updates to test versioning
        updates = [
            {"address": "First Update Address"},
            {"contact_phone": "+1-555-111-1111"},
            {"address": "Second Update Address", "contact_email": "updated@example.com"}
        ]
        
        for i, update in enumerate(updates):
            response = client.put(
                f"/api/v1/customers/{customer_id}",
                json=update,
                headers={"X-Actor-ID": customer_lifecycle_data["actor"]["actor_id"]}
            )
            assert response.status_code == 200
        
        # Verify version history
        response = client.get(
            f"/api/v1/customers/{customer_id}/history",
            headers={"X-Actor-ID": customer_lifecycle_data["actor"]["actor_id"]}
        )
        
        history_data = response.json()
        update_entries = [entry for entry in history_data["history"] 
                         if entry["change_type"] == "CUSTOMER_UPDATED"]
        assert len(update_entries) == len(updates)
        
        # Test retrieving specific version (if supported)
        if "versions" in history_data:
            for version in history_data["versions"]:
                response = client.get(
                    f"/api/v1/customers/{customer_id}",
                    params={"version": version["version_id"]},
                    headers={"X-Actor-ID": customer_lifecycle_data["actor"]["actor_id"]}
                )
                assert response.status_code == 200
    
    def test_cross_domain_customer_integration(self, client, customer_lifecycle_data, mock_customer_services):
        """Test customer integration with loan origination."""
        
        # Create customer
        response = client.post(
            "/api/v1/customers",
            json=customer_lifecycle_data["initial_customer"],
            headers={"X-Actor-ID": customer_lifecycle_data["actor"]["actor_id"]}
        )
        customer_id = response.json()["customer_id"]
        
        # Create loan application for this customer
        loan_data = {
            "customer_id": customer_id,
            "requested_amount": 25000.0,
            "loan_type": "PERSONAL",
            "introducer_id": "INTRO_001"
        }
        
        response = client.post(
            "/api/v1/loans/applications",
            json=loan_data,
            headers={"X-Actor-ID": "UNDERWRITER_001"}
        )
        
        assert response.status_code == 201
        loan_response = response.json()
        assert loan_response["customer_id"] == customer_id
        
        # Verify customer-loan relationship
        response = client.get(
            f"/api/v1/customers/{customer_id}/loans",
            headers={"X-Actor-ID": customer_lifecycle_data["actor"]["actor_id"]}
        )
        
        # Should return customer's loan applications
        assert response.status_code == 200
        customer_loans = response.json()
        assert len(customer_loans["loan_applications"]) >= 1
    
    def test_customer_data_privacy_controls(self, client, customer_lifecycle_data, mock_customer_services):
        """Test data privacy and access controls."""
        
        # Create customer
        response = client.post(
            "/api/v1/customers",
            json=customer_lifecycle_data["initial_customer"],
            headers={"X-Actor-ID": customer_lifecycle_data["actor"]["actor_id"]}
        )
        customer_id = response.json()["customer_id"]
        
        # Test access with different actor roles
        test_actors = [
            {"actor_id": "COMPLIANCE_001", "role": "Compliance_Officer"},
            {"actor_id": "AUDITOR_001", "role": "Auditor"},
            {"actor_id": "EXTERNAL_001", "role": "External_Partner"}
        ]
        
        for actor in test_actors:
            response = client.get(
                f"/api/v1/customers/{customer_id}",
                headers={"X-Actor-ID": actor["actor_id"]}
            )
            
            # Response should vary based on actor permissions
            if actor["role"] in ["Compliance_Officer", "Auditor"]:
                assert response.status_code == 200
            else:
                # External partners might have limited access or no access
                assert response.status_code in [200, 403]
                
                if response.status_code == 200:
                    # Should have filtered/masked data
                    customer_data = response.json()
                    # Sensitive fields might be masked or excluded
                    assert "national_id" not in customer_data or customer_data["national_id"] == "***MASKED***"
    
    def test_customer_error_handling(self, client, customer_lifecycle_data, mock_customer_services):
        """Test error handling in customer lifecycle."""
        
        # Test duplicate customer creation
        response1 = client.post(
            "/api/v1/customers",
            json=customer_lifecycle_data["initial_customer"],
            headers={"X-Actor-ID": customer_lifecycle_data["actor"]["actor_id"]}
        )
        assert response1.status_code == 201
        
        # Try to create duplicate (same national_id)
        response2 = client.post(
            "/api/v1/customers",
            json=customer_lifecycle_data["initial_customer"],
            headers={"X-Actor-ID": customer_lifecycle_data["actor"]["actor_id"]}
        )
        assert response2.status_code == 409  # Conflict
        
        # Test invalid data updates
        customer_id = response1.json()["customer_id"]
        
        invalid_update = {
            "contact_email": "invalid-email-format",
            "contact_phone": "invalid-phone"
        }
        
        response = client.put(
            f"/api/v1/customers/{customer_id}",
            json=invalid_update,
            headers={"X-Actor-ID": customer_lifecycle_data["actor"]["actor_id"]}
        )
        assert response.status_code == 422  # Validation error
        
        # Test non-existent customer access
        response = client.get(
            "/api/v1/customers/NONEXISTENT_ID",
            headers={"X-Actor-ID": customer_lifecycle_data["actor"]["actor_id"]}
        )
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])