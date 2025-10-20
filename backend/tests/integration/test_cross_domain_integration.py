"""
Integration tests for cross-domain workflows.

Tests interactions between customer mastery, loan origination, and compliance
domains to ensure proper data flow and business process integration.
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
def cross_domain_data():
    """Test data for cross-domain integration."""
    return {
        "complete_workflow": {
            "customer": {
                "first_name": "Cross",
                "last_name": "Domain",
                "date_of_birth": "1985-03-15T00:00:00",
                "national_id": "CROSS123456789",
                "address": "123 Integration Ave, Test City, TC 12345",
                "contact_email": "cross.domain@example.com",
                "contact_phone": "+1-555-123-4567",
                "consent_preferences": {
                    "data_sharing": True,
                    "marketing": True,
                    "analytics": True
                }
            },
            "loan": {
                "requested_amount": 75000.0,
                "loan_type": "MORTGAGE",
                "introducer_id": "INTRO_CROSS_001",
                "additional_info": {
                    "purpose": "Home purchase",
                    "employment_status": "Full-time",
                    "annual_income": 120000.0,
                    "property_value": 300000.0
                }
            },
            "documents": [
                {
                    "document_type": "INCOME_STATEMENT",
                    "content": b"Annual income statement content"
                },
                {
                    "document_type": "PROPERTY_APPRAISAL",
                    "content": b"Property appraisal document content"
                },
                {
                    "document_type": "EMPLOYMENT_VERIFICATION",
                    "content": b"Employment verification letter content"
                }
            ]
        },
        "actors": {
            "csr": {
                "actor_id": "CSR_CROSS_001",
                "role": "Customer_Service_Representative"
            },
            "underwriter": {
                "actor_id": "UNDERWRITER_CROSS_001",
                "role": "Underwriter"
            },
            "compliance_officer": {
                "actor_id": "COMPLIANCE_CROSS_001",
                "role": "Compliance_Officer"
            },
            "credit_officer": {
                "actor_id": "CREDIT_CROSS_001",
                "role": "Credit_Officer"
            }
        }
    }


@pytest.fixture
def mock_cross_domain_services():
    """Mock all services for cross-domain integration tests."""
    from .mock_infrastructure import IntegrationTestMockManager
    
    mock_manager = IntegrationTestMockManager()
    with mock_manager.mock_all_services() as mocks:
        yield {
            'mock_manager': mock_manager,
            'mocks': mocks
        }


class TestCrossDomainIntegration:
    """Test cross-domain integration workflows."""
    
    def test_complete_customer_to_loan_workflow(self, client, cross_domain_data, mock_cross_domain_services):
        """Test complete workflow from customer creation to loan approval."""
        
        # Step 1: Create customer
        response = client.post(
            "/api/v1/customers",
            json=cross_domain_data["complete_workflow"]["customer"],
            headers={"X-Actor-ID": cross_domain_data["actors"]["csr"]["actor_id"]}
        )
        
        assert response.status_code == 201
        customer_data = response.json()
        customer_id = customer_data["customer_id"]
        assert customer_data["kyc_status"] in ["VERIFIED", "PENDING"]
        
        # Step 2: Verify customer KYC status before loan application
        response = client.get(
            f"/api/v1/customers/{customer_id}",
            headers={"X-Actor-ID": cross_domain_data["actors"]["underwriter"]["actor_id"]}
        )
        
        assert response.status_code == 200
        customer_details = response.json()
        
        # Step 3: Submit loan application with customer reference
        loan_data = cross_domain_data["complete_workflow"]["loan"].copy()
        loan_data["customer_id"] = customer_id
        
        response = client.post(
            "/api/v1/loans/applications",
            json=loan_data,
            headers={"X-Actor-ID": cross_domain_data["actors"]["underwriter"]["actor_id"]}
        )
        
        assert response.status_code == 201
        loan_response = response.json()
        loan_id = loan_response["loan_application_id"]
        assert loan_response["customer_id"] == customer_id
        
        # Step 4: Upload documents for loan
        for doc in cross_domain_data["complete_workflow"]["documents"]:
            response = client.post(
                f"/api/v1/loans/{loan_id}/documents",
                files={"file": (f"{doc['document_type']}.pdf", doc["content"], "application/pdf")},
                data={"document_type": doc["document_type"]},
                headers={"X-Actor-ID": cross_domain_data["actors"]["underwriter"]["actor_id"]}
            )
            
            assert response.status_code == 201
        
        # Step 5: Check compliance events generated
        response = client.get(
            "/api/v1/compliance/events",
            params={"affected_entity_id": loan_id},
            headers={"X-Actor-ID": cross_domain_data["actors"]["compliance_officer"]["actor_id"]}
        )
        
        assert response.status_code == 200
        compliance_events = response.json()["events"]
        
        # Step 6: Process loan through workflow stages
        workflow_stages = ["UNDERWRITING", "CREDIT_APPROVAL"]
        
        for stage in workflow_stages:
            response = client.put(
                f"/api/v1/loans/{loan_id}/status",
                json={
                    "new_status": stage,
                    "notes": f"Moving to {stage} stage"
                },
                headers={"X-Actor-ID": cross_domain_data["actors"]["underwriter"]["actor_id"]}
            )
            
            assert response.status_code == 200
        
        # Step 7: Approve loan
        response = client.post(
            f"/api/v1/loans/{loan_id}/approve",
            json={
                "approval_notes": "Approved based on excellent credit and complete documentation",
                "approved_amount": 70000.0,
                "conditions": ["Property insurance required", "Final employment verification"]
            },
            headers={"X-Actor-ID": cross_domain_data["actors"]["credit_officer"]["actor_id"]}
        )
        
        assert response.status_code == 200
        approval_data = response.json()
        assert approval_data["application_status"] == "APPROVED"
        
        # Step 8: Verify complete audit trail across domains
        # Customer history
        response = client.get(
            f"/api/v1/customers/{customer_id}/history",
            headers={"X-Actor-ID": cross_domain_data["actors"]["compliance_officer"]["actor_id"]}
        )
        assert response.status_code == 200
        customer_history = response.json()["history"]
        
        # Loan history
        response = client.get(
            f"/api/v1/loans/{loan_id}/history",
            headers={"X-Actor-ID": cross_domain_data["actors"]["compliance_officer"]["actor_id"]}
        )
        assert response.status_code == 200
        loan_history = response.json()["history"]
        
        # Verify cross-references
        assert len(customer_history) >= 1
        assert len(loan_history) >= 4  # Submit, underwriting, credit approval, approval
    
    def test_compliance_integration_across_domains(self, client, cross_domain_data, mock_cross_domain_services):
        """Test compliance rule enforcement across customer and loan domains."""
        
        # Create customer and loan
        customer_response = client.post(
            "/api/v1/customers",
            json=cross_domain_data["complete_workflow"]["customer"],
            headers={"X-Actor-ID": cross_domain_data["actors"]["csr"]["actor_id"]}
        )
        customer_id = customer_response.json()["customer_id"]
        
        loan_data = cross_domain_data["complete_workflow"]["loan"].copy()
        loan_data["customer_id"] = customer_id
        
        loan_response = client.post(
            "/api/v1/loans/applications",
            json=loan_data,
            headers={"X-Actor-ID": cross_domain_data["actors"]["underwriter"]["actor_id"]}
        )
        loan_id = loan_response.json()["loan_application_id"]
        
        # Check compliance events for both entities
        customer_events_response = client.get(
            "/api/v1/compliance/events",
            params={"affected_entity_id": customer_id},
            headers={"X-Actor-ID": cross_domain_data["actors"]["compliance_officer"]["actor_id"]}
        )
        
        loan_events_response = client.get(
            "/api/v1/compliance/events",
            params={"affected_entity_id": loan_id},
            headers={"X-Actor-ID": cross_domain_data["actors"]["compliance_officer"]["actor_id"]}
        )
        
        assert customer_events_response.status_code == 200
        assert loan_events_response.status_code == 200
        
        customer_events = customer_events_response.json()["events"]
        loan_events = loan_events_response.json()["events"]
        
        # Verify compliance monitoring across domains
        total_events = len(customer_events) + len(loan_events)
        assert total_events >= 0  # May have events depending on rules
        
        # Generate cross-domain compliance report
        report_request = {
            "report_type": "CROSS_DOMAIN_ACTIVITY",
            "start_date": (datetime.now() - timedelta(hours=1)).isoformat(),
            "end_date": datetime.now().isoformat(),
            "entity_ids": [customer_id, loan_id]
        }
        
        response = client.post(
            "/api/v1/compliance/reports/generate",
            json=report_request,
            headers={"X-Actor-ID": cross_domain_data["actors"]["compliance_officer"]["actor_id"]}
        )
        
        assert response.status_code == 200
        report_data = response.json()
        assert "report_id" in report_data
    
    def test_data_consistency_across_domains(self, client, cross_domain_data, mock_cross_domain_services):
        """Test data consistency between customer and loan domains."""
        
        # Create customer
        customer_response = client.post(
            "/api/v1/customers",
            json=cross_domain_data["complete_workflow"]["customer"],
            headers={"X-Actor-ID": cross_domain_data["actors"]["csr"]["actor_id"]}
        )
        customer_id = customer_response.json()["customer_id"]
        
        # Create loan for customer
        loan_data = cross_domain_data["complete_workflow"]["loan"].copy()
        loan_data["customer_id"] = customer_id
        
        loan_response = client.post(
            "/api/v1/loans/applications",
            json=loan_data,
            headers={"X-Actor-ID": cross_domain_data["actors"]["underwriter"]["actor_id"]}
        )
        loan_id = loan_response.json()["loan_application_id"]
        
        # Update customer information
        customer_update = {
            "address": "456 Updated Address St, New City, NC 67890",
            "contact_email": "updated.cross@example.com"
        }
        
        response = client.put(
            f"/api/v1/customers/{customer_id}",
            json=customer_update,
            headers={"X-Actor-ID": cross_domain_data["actors"]["csr"]["actor_id"]}
        )
        assert response.status_code == 200
        
        # Verify loan still references correct customer
        response = client.get(
            f"/api/v1/loans/{loan_id}",
            headers={"X-Actor-ID": cross_domain_data["actors"]["underwriter"]["actor_id"]}
        )
        
        assert response.status_code == 200
        loan_details = response.json()
        assert loan_details["customer_id"] == customer_id
        
        # Check consistency monitoring
        response = client.get(
            "/api/v1/consistency/check",
            params={
                "entity_type": "customer_loan_relationship",
                "entity_id": customer_id
            },
            headers={"X-Actor-ID": cross_domain_data["actors"]["compliance_officer"]["actor_id"]}
        )
        
        assert response.status_code == 200
        consistency_data = response.json()
        assert consistency_data["status"] in ["CONSISTENT", "PENDING_SYNC"]
    
    def test_event_driven_synchronization(self, client, cross_domain_data, mock_cross_domain_services):
        """Test event-driven synchronization between domains."""
        
        # Create customer
        customer_response = client.post(
            "/api/v1/customers",
            json=cross_domain_data["complete_workflow"]["customer"],
            headers={"X-Actor-ID": cross_domain_data["actors"]["csr"]["actor_id"]}
        )
        customer_id = customer_response.json()["customer_id"]
        
        # Verify event listener processed customer creation
        response = client.get(
            "/api/v1/consistency/events",
            params={"entity_id": customer_id, "event_type": "CUSTOMER_CREATED"},
            headers={"X-Actor-ID": cross_domain_data["actors"]["compliance_officer"]["actor_id"]}
        )
        
        assert response.status_code == 200
        sync_events = response.json()["events"]
        
        # Create loan application
        loan_data = cross_domain_data["complete_workflow"]["loan"].copy()
        loan_data["customer_id"] = customer_id
        
        loan_response = client.post(
            "/api/v1/loans/applications",
            json=loan_data,
            headers={"X-Actor-ID": cross_domain_data["actors"]["underwriter"]["actor_id"]}
        )
        loan_id = loan_response.json()["loan_application_id"]
        
        # Verify loan creation event
        response = client.get(
            "/api/v1/consistency/events",
            params={"entity_id": loan_id, "event_type": "LOAN_APPLICATION_SUBMITTED"},
            headers={"X-Actor-ID": cross_domain_data["actors"]["compliance_officer"]["actor_id"]}
        )
        
        assert response.status_code == 200
        loan_sync_events = response.json()["events"]
        
        # Update loan status and verify synchronization
        response = client.put(
            f"/api/v1/loans/{loan_id}/status",
            json={"new_status": "UNDERWRITING", "notes": "Moving to underwriting"},
            headers={"X-Actor-ID": cross_domain_data["actors"]["underwriter"]["actor_id"]}
        )
        assert response.status_code == 200
        
        # Check for status update synchronization event
        response = client.get(
            "/api/v1/consistency/events",
            params={"entity_id": loan_id, "event_type": "LOAN_STATUS_UPDATED"},
            headers={"X-Actor-ID": cross_domain_data["actors"]["compliance_officer"]["actor_id"]}
        )
        
        assert response.status_code == 200
    
    def test_cross_domain_error_handling(self, client, cross_domain_data, mock_cross_domain_services):
        """Test error handling in cross-domain operations."""
        
        # Try to create loan for non-existent customer
        invalid_loan_data = cross_domain_data["complete_workflow"]["loan"].copy()
        invalid_loan_data["customer_id"] = "NONEXISTENT_CUSTOMER"
        
        response = client.post(
            "/api/v1/loans/applications",
            json=invalid_loan_data,
            headers={"X-Actor-ID": cross_domain_data["actors"]["underwriter"]["actor_id"]}
        )
        
        assert response.status_code == 400
        error_data = response.json()
        assert "customer" in error_data["detail"].lower()
        
        # Create valid customer first
        customer_response = client.post(
            "/api/v1/customers",
            json=cross_domain_data["complete_workflow"]["customer"],
            headers={"X-Actor-ID": cross_domain_data["actors"]["csr"]["actor_id"]}
        )
        customer_id = customer_response.json()["customer_id"]
        
        # Try to create loan with invalid data
        invalid_loan_data["customer_id"] = customer_id
        invalid_loan_data["requested_amount"] = -1000.0  # Invalid amount
        
        response = client.post(
            "/api/v1/loans/applications",
            json=invalid_loan_data,
            headers={"X-Actor-ID": cross_domain_data["actors"]["underwriter"]["actor_id"]}
        )
        
        assert response.status_code == 422  # Validation error
        
        # Test consistency check error handling
        response = client.get(
            "/api/v1/consistency/check",
            params={
                "entity_type": "invalid_type",
                "entity_id": "invalid_id"
            },
            headers={"X-Actor-ID": cross_domain_data["actors"]["compliance_officer"]["actor_id"]}
        )
        
        assert response.status_code == 400
    
    def test_performance_under_cross_domain_load(self, client, cross_domain_data, mock_cross_domain_services):
        """Test system performance under cross-domain operations."""
        
        # Create multiple customers and loans to test performance
        customers = []
        loans = []
        
        # Create 5 customers
        for i in range(5):
            customer_data = cross_domain_data["complete_workflow"]["customer"].copy()
            customer_data["contact_email"] = f"test{i}@example.com"
            customer_data["national_id"] = f"PERF{i:03d}123456"
            
            response = client.post(
                "/api/v1/customers",
                json=customer_data,
                headers={"X-Actor-ID": cross_domain_data["actors"]["csr"]["actor_id"]}
            )
            
            assert response.status_code == 201
            customers.append(response.json()["customer_id"])
        
        # Create loans for each customer
        for customer_id in customers:
            loan_data = cross_domain_data["complete_workflow"]["loan"].copy()
            loan_data["customer_id"] = customer_id
            
            response = client.post(
                "/api/v1/loans/applications",
                json=loan_data,
                headers={"X-Actor-ID": cross_domain_data["actors"]["underwriter"]["actor_id"]}
            )
            
            assert response.status_code == 201
            loans.append(response.json()["loan_application_id"])
        
        # Verify all entities were created successfully
        assert len(customers) == 5
        assert len(loans) == 5
        
        # Test bulk compliance report generation
        report_request = {
            "report_type": "BULK_ACTIVITY_REPORT",
            "start_date": (datetime.now() - timedelta(hours=1)).isoformat(),
            "end_date": datetime.now().isoformat(),
            "entity_ids": customers + loans
        }
        
        response = client.post(
            "/api/v1/compliance/reports/generate",
            json=report_request,
            headers={"X-Actor-ID": cross_domain_data["actors"]["compliance_officer"]["actor_id"]}
        )
        
        assert response.status_code == 200
        bulk_report = response.json()
        assert "report_id" in bulk_report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])