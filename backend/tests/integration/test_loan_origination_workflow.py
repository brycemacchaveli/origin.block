"""
Integration tests for complete loan origination workflow.

Tests the end-to-end process from loan application submission through approval/rejection,
including document management, status transitions, and audit trail verification.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def loan_workflow_data():
    """Test data for loan origination workflow."""
    return {
        "customer_id": "CUST_WORKFLOW_001",
        "loan_application": {
            "requested_amount": 50000.0,
            "loan_type": "PERSONAL",
            "introducer_id": "INTRO_001",
            "additional_info": {
                "purpose": "Home improvement",
                "employment_status": "Full-time",
                "annual_income": 75000.0
            }
        },
        "actor": {
            "actor_id": "UNDERWRITER_001",
            "actor_type": "Internal_User",
            "actor_name": "Test Underwriter",
            "role": "Underwriter"
        },
        "documents": [
            {
                "document_type": "INCOME_STATEMENT",
                "content": b"Mock income statement content"
            },
            {
                "document_type": "IDENTITY_PROOF",
                "content": b"Mock identity document content"
            }
        ]
    }


@pytest.fixture
def mock_blockchain_services():
    """Mock blockchain and external services for workflow tests."""
    from .mock_infrastructure import IntegrationTestMockManager
    
    mock_manager = IntegrationTestMockManager()
    with mock_manager.mock_all_services() as mocks:
        yield {
            'mock_manager': mock_manager,
            'mocks': mocks
        }


class TestLoanOriginationWorkflow:
    """Test complete loan origination workflow."""
    
    def test_complete_loan_application_workflow(self, client, loan_workflow_data, mock_blockchain_services):
        """Test complete loan application from submission to approval."""
        
        # Step 1: Submit loan application
        response = client.post(
            "/api/v1/loans/applications",
            json=loan_workflow_data["loan_application"],
            headers={"X-Actor-ID": loan_workflow_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 201
        loan_data = response.json()
        assert "loan_application_id" in loan_data
        assert loan_data["application_status"] == "SUBMITTED"
        loan_id = loan_data["loan_application_id"]
        
        # Verify transaction was recorded
        transaction_history = mock_blockchain_services['mock_manager'].get_transaction_history()
        assert len(transaction_history) >= 1
        assert any("loan" in tx["chaincode_name"].lower() for tx in transaction_history)
        
        # Step 2: Upload required documents
        for doc in loan_workflow_data["documents"]:
            response = client.post(
                f"/api/v1/loans/{loan_id}/documents",
                files={"file": ("test_doc.pdf", doc["content"], "application/pdf")},
                data={"document_type": doc["document_type"]},
                headers={"X-Actor-ID": loan_workflow_data["actor"]["actor_id"]}
            )
            
            assert response.status_code == 201
            doc_data = response.json()
            assert "document_id" in doc_data
            assert doc_data["document_type"] == doc["document_type"]
            assert "file_hash" in doc_data
        
        # Step 3: Update application status to underwriting
        response = client.put(
            f"/api/v1/loans/{loan_id}/status",
            json={
                "new_status": "UNDERWRITING",
                "notes": "Moving to underwriting review"
            },
            headers={"X-Actor-ID": loan_workflow_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 200
        status_data = response.json()
        assert status_data["application_status"] == "UNDERWRITING"
        
        # Step 4: Perform credit check and move to credit approval
        response = client.put(
            f"/api/v1/loans/{loan_id}/status",
            json={
                "new_status": "CREDIT_APPROVAL",
                "notes": "Credit check completed, moving to approval"
            },
            headers={"X-Actor-ID": loan_workflow_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 200
        
        # Step 5: Approve the loan
        response = client.post(
            f"/api/v1/loans/{loan_id}/approve",
            json={
                "approval_notes": "Loan approved based on credit assessment",
                "approved_amount": 45000.0,  # Slightly less than requested
                "conditions": ["Provide updated income statement"]
            },
            headers={"X-Actor-ID": "CREDIT_OFFICER_001"}
        )
        
        assert response.status_code == 200
        approval_data = response.json()
        assert approval_data["application_status"] == "APPROVED"
        assert approval_data["approved_amount"] == 45000.0
        
        # Step 6: Verify complete audit trail
        response = client.get(
            f"/api/v1/loans/{loan_id}/history",
            headers={"X-Actor-ID": loan_workflow_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 200
        history_data = response.json()
        assert len(history_data["history"]) >= 4  # At least 4 status changes
        
        # Verify history contains all expected status transitions
        statuses = [entry["new_value"] for entry in history_data["history"] 
                   if entry["change_type"] == "STATUS_CHANGE"]
        expected_statuses = ["SUBMITTED", "UNDERWRITING", "CREDIT_APPROVAL", "APPROVED"]
        for status in expected_statuses:
            assert status in statuses
    
    def test_loan_rejection_workflow(self, client, loan_workflow_data, mock_blockchain_services):
        """Test loan rejection workflow."""
        
        # Configure for high-risk customer scenario
        mock_blockchain_services['mock_manager'].configure_scenario("high_risk_customer")
        
        # Submit loan application
        response = client.post(
            "/api/v1/loans/applications",
            json=loan_workflow_data["loan_application"],
            headers={"X-Actor-ID": loan_workflow_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 201
        loan_id = response.json()["loan_application_id"]
        
        # Move through underwriting to rejection
        client.put(
            f"/api/v1/loans/{loan_id}/status",
            json={"new_status": "UNDERWRITING"},
            headers={"X-Actor-ID": loan_workflow_data["actor"]["actor_id"]}
        )
        
        # Reject the loan
        response = client.post(
            f"/api/v1/loans/{loan_id}/reject",
            json={
                "rejection_reason": "Insufficient credit score",
                "rejection_notes": "Credit score below minimum threshold"
            },
            headers={"X-Actor-ID": "CREDIT_OFFICER_001"}
        )
        
        assert response.status_code == 200
        rejection_data = response.json()
        assert rejection_data["application_status"] == "REJECTED"
        assert "rejection_reason" in rejection_data
    
    def test_document_verification_workflow(self, client, loan_workflow_data, mock_blockchain_services):
        """Test document upload and verification workflow."""
        
        # Submit loan application
        response = client.post(
            "/api/v1/loans/applications",
            json=loan_workflow_data["loan_application"],
            headers={"X-Actor-ID": loan_workflow_data["actor"]["actor_id"]}
        )
        loan_id = response.json()["loan_application_id"]
        
        # Upload document
        test_content = b"Test document content for verification"
        response = client.post(
            f"/api/v1/loans/{loan_id}/documents",
            files={"file": ("test.pdf", test_content, "application/pdf")},
            data={"document_type": "INCOME_STATEMENT"},
            headers={"X-Actor-ID": loan_workflow_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 201
        doc_data = response.json()
        document_id = doc_data["document_id"]
        original_hash = doc_data["file_hash"]
        
        # Verify document with correct content
        response = client.post(
            f"/api/v1/loans/{loan_id}/documents/{document_id}/verify",
            files={"file": ("verify.pdf", test_content, "application/pdf")},
            headers={"X-Actor-ID": loan_workflow_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 200
        verify_data = response.json()
        assert verify_data["verification_result"] == "VERIFIED"
        assert verify_data["hash_match"] is True
        
        # Verify document with incorrect content
        wrong_content = b"Different document content"
        response = client.post(
            f"/api/v1/loans/{loan_id}/documents/{document_id}/verify",
            files={"file": ("wrong.pdf", wrong_content, "application/pdf")},
            headers={"X-Actor-ID": loan_workflow_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 200
        verify_data = response.json()
        assert verify_data["verification_result"] == "FAILED"
        assert verify_data["hash_match"] is False
    
    def test_workflow_error_handling(self, client, loan_workflow_data, mock_blockchain_services):
        """Test error handling in loan workflow."""
        
        # Test invalid status transition
        response = client.post(
            "/api/v1/loans/applications",
            json=loan_workflow_data["loan_application"],
            headers={"X-Actor-ID": loan_workflow_data["actor"]["actor_id"]}
        )
        loan_id = response.json()["loan_application_id"]
        
        # Try to approve directly from SUBMITTED (should fail)
        response = client.post(
            f"/api/v1/loans/{loan_id}/approve",
            json={"approval_notes": "Direct approval"},
            headers={"X-Actor-ID": "CREDIT_OFFICER_001"}
        )
        
        assert response.status_code == 400
        assert "invalid status transition" in response.json()["detail"].lower()
        
        # Test unauthorized access
        response = client.get(
            f"/api/v1/loans/{loan_id}",
            headers={"X-Actor-ID": "UNAUTHORIZED_USER"}
        )
        
        # Should either return 403 or filter results based on permissions
        assert response.status_code in [200, 403]
    
    def test_concurrent_workflow_operations(self, client, loan_workflow_data, mock_blockchain_services):
        """Test handling of concurrent operations on the same loan."""
        
        # Submit loan application
        response = client.post(
            "/api/v1/loans/applications",
            json=loan_workflow_data["loan_application"],
            headers={"X-Actor-ID": loan_workflow_data["actor"]["actor_id"]}
        )
        loan_id = response.json()["loan_application_id"]
        
        # Simulate concurrent status updates
        # In a real scenario, this would test blockchain transaction ordering
        response1 = client.put(
            f"/api/v1/loans/{loan_id}/status",
            json={"new_status": "UNDERWRITING", "notes": "Update 1"},
            headers={"X-Actor-ID": "UNDERWRITER_001"}
        )
        
        response2 = client.put(
            f"/api/v1/loans/{loan_id}/status",
            json={"new_status": "UNDERWRITING", "notes": "Update 2"},
            headers={"X-Actor-ID": "UNDERWRITER_002"}
        )
        
        # Both should succeed (or one should fail with appropriate error)
        assert response1.status_code in [200, 409]
        assert response2.status_code in [200, 409]
        
        # Verify final state is consistent
        response = client.get(
            f"/api/v1/loans/{loan_id}",
            headers={"X-Actor-ID": loan_workflow_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 200
        final_data = response.json()
        assert final_data["application_status"] == "UNDERWRITING"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])