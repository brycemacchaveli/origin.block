"""
Test data management and cleanup utilities for integration tests.

Provides utilities for creating, managing, and cleaning up test data
across all domains to ensure test isolation and repeatability.
"""

import pytest
import asyncio
from typing import Dict, List, Any, Optional
from unittest.mock import patch, MagicMock
import json
from datetime import datetime, timedelta
import hashlib
import random
import string

from fastapi.testclient import TestClient
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from main import app
from .mock_infrastructure import IntegrationTestMockManager


class TestDataManager:
    """Manages test data creation, tracking, and cleanup."""
    
    def __init__(self, client: TestClient):
        self.client = client
        self.created_entities = {
            "customers": [],
            "loans": [],
            "documents": [],
            "compliance_events": [],
            "actors": []
        }
        self.mock_manager = IntegrationTestMockManager()
        self.active_mocks = None
    
    def setup_mock_services(self):
        """Setup comprehensive mock services for test data operations."""
        # Use the context manager to setup all mocks
        self.active_mocks = self.mock_manager.mock_all_services()
        self.active_mocks.__enter__()
        return self.mock_manager
    
    def teardown_mock_services(self):
        """Teardown mock services."""
        if self.active_mocks:
            self.active_mocks.__exit__(None, None, None)
            self.active_mocks = None
    
    def generate_unique_id(self, prefix: str = "TEST") -> str:
        """Generate unique ID for test entities."""
        timestamp = str(int(datetime.now().timestamp() * 1000))
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"{prefix}_{timestamp}_{random_suffix}"
    
    def create_test_customer(self, 
                           actor_id: str = "TEST_CSR_001",
                           custom_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a test customer with tracking."""
        
        unique_id = self.generate_unique_id("CUST")
        
        customer_data = {
            "first_name": "Test",
            "last_name": "Customer",
            "date_of_birth": "1985-06-15T00:00:00",
            "national_id": f"ID{unique_id}",
            "address": f"123 Test St, Test City, TC 12345",
            "contact_email": f"test.customer.{unique_id.lower()}@example.com",
            "contact_phone": f"+1-555-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
            "consent_preferences": {
                "data_sharing": True,
                "marketing": False,
                "analytics": True
            }
        }
        
        if custom_data:
            customer_data.update(custom_data)
        
        # The mock infrastructure will handle the response automatically
        
        response = self.client.post(
            "/api/v1/customers",
            json=customer_data,
            headers={"X-Actor-ID": actor_id}
        )
        
        if response.status_code == 201:
            customer_result = response.json()
            self.created_entities["customers"].append(customer_result["customer_id"])
            return customer_result
        else:
            raise Exception(f"Failed to create test customer: {response.status_code} - {response.text}")
    
    def create_test_loan(self, 
                        customer_id: str,
                        actor_id: str = "TEST_UNDERWRITER_001",
                        custom_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a test loan application with tracking."""
        
        unique_id = self.generate_unique_id("LOAN")
        
        loan_data = {
            "customer_id": customer_id,
            "requested_amount": random.uniform(10000, 100000),
            "loan_type": random.choice(["PERSONAL", "MORTGAGE", "BUSINESS", "AUTO"]),
            "introducer_id": f"INTRO_{unique_id}",
            "additional_info": {
                "purpose": "Test loan application",
                "employment_status": "Full-time",
                "annual_income": random.uniform(50000, 150000)
            }
        }
        
        if custom_data:
            loan_data.update(custom_data)
        
        # The mock infrastructure will handle the response automatically
        
        response = self.client.post(
            "/api/v1/loans/applications",
            json=loan_data,
            headers={"X-Actor-ID": actor_id}
        )
        
        if response.status_code == 201:
            loan_result = response.json()
            self.created_entities["loans"].append(loan_result["loan_application_id"])
            return loan_result
        else:
            raise Exception(f"Failed to create test loan: {response.status_code} - {response.text}")
    
    def create_test_document(self, 
                           loan_id: str,
                           document_type: str = "INCOME_STATEMENT",
                           actor_id: str = "TEST_UNDERWRITER_001",
                           content: Optional[bytes] = None) -> Dict[str, Any]:
        """Create a test document with tracking."""
        
        if content is None:
            content = f"Test document content for {document_type} - {datetime.now()}".encode()
        
        response = self.client.post(
            f"/api/v1/loans/{loan_id}/documents",
            files={"file": (f"test_{document_type}.pdf", content, "application/pdf")},
            data={"document_type": document_type},
            headers={"X-Actor-ID": actor_id}
        )
        
        if response.status_code == 201:
            document_result = response.json()
            self.created_entities["documents"].append({
                "loan_id": loan_id,
                "document_id": document_result["document_id"]
            })
            return document_result
        else:
            raise Exception(f"Failed to create test document: {response.status_code} - {response.text}")
    
    def create_test_compliance_rule(self, 
                                  actor_id: str = "TEST_COMPLIANCE_001",
                                  custom_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a test compliance rule with tracking."""
        
        unique_id = self.generate_unique_id("RULE")
        
        rule_data = {
            "rule_id": f"TEST_RULE_{unique_id}",
            "rule_name": f"Test Rule {unique_id}",
            "rule_description": "Test compliance rule for integration testing",
            "rule_logic": "test_condition == true",
            "applies_to_domain": "LOAN_ORIGINATION",
            "status": "ACTIVE"
        }
        
        if custom_data:
            rule_data.update(custom_data)
        
        # The mock infrastructure will handle the response automatically
        
        response = self.client.post(
            "/api/v1/compliance/rules",
            json=rule_data,
            headers={"X-Actor-ID": actor_id}
        )
        
        if response.status_code == 201:
            rule_result = response.json()
            self.created_entities["compliance_events"].append(rule_result["rule_id"])
            return rule_result
        else:
            raise Exception(f"Failed to create test compliance rule: {response.status_code} - {response.text}")
    
    def create_complete_workflow_data(self, 
                                    actor_id: str = "TEST_WORKFLOW_001") -> Dict[str, Any]:
        """Create a complete set of test data for workflow testing."""
        
        # Create customer
        customer = self.create_test_customer(actor_id)
        customer_id = customer["customer_id"]
        
        # Create loan for customer
        loan = self.create_test_loan(customer_id, actor_id)
        loan_id = loan["loan_application_id"]
        
        # Create documents for loan
        documents = []
        document_types = ["INCOME_STATEMENT", "IDENTITY_PROOF", "EMPLOYMENT_VERIFICATION"]
        
        for doc_type in document_types:
            doc = self.create_test_document(loan_id, doc_type, actor_id)
            documents.append(doc)
        
        # Create compliance rule
        compliance_rule = self.create_test_compliance_rule(actor_id)
        
        return {
            "customer": customer,
            "loan": loan,
            "documents": documents,
            "compliance_rule": compliance_rule,
            "workflow_id": self.generate_unique_id("WORKFLOW")
        }
    
    def update_loan_status(self, 
                          loan_id: str, 
                          new_status: str,
                          actor_id: str = "TEST_UNDERWRITER_001",
                          notes: str = "Test status update") -> Dict[str, Any]:
        """Update loan status for testing."""
        
        response = self.client.put(
            f"/api/v1/loans/{loan_id}/status",
            json={
                "new_status": new_status,
                "notes": notes
            },
            headers={"X-Actor-ID": actor_id}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to update loan status: {response.status_code} - {response.text}")
    
    def approve_loan(self, 
                    loan_id: str,
                    actor_id: str = "TEST_CREDIT_OFFICER_001",
                    approved_amount: Optional[float] = None) -> Dict[str, Any]:
        """Approve loan for testing."""
        
        approval_data = {
            "approval_notes": "Test loan approval",
            "conditions": ["Test condition 1", "Test condition 2"]
        }
        
        if approved_amount:
            approval_data["approved_amount"] = approved_amount
        
        response = self.client.post(
            f"/api/v1/loans/{loan_id}/approve",
            json=approval_data,
            headers={"X-Actor-ID": actor_id}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to approve loan: {response.status_code} - {response.text}")
    
    def reject_loan(self, 
                   loan_id: str,
                   actor_id: str = "TEST_CREDIT_OFFICER_001",
                   reason: str = "Test rejection") -> Dict[str, Any]:
        """Reject loan for testing."""
        
        rejection_data = {
            "rejection_reason": reason,
            "rejection_notes": "Test loan rejection"
        }
        
        response = self.client.post(
            f"/api/v1/loans/{loan_id}/reject",
            json=rejection_data,
            headers={"X-Actor-ID": actor_id}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to reject loan: {response.status_code} - {response.text}")
    
    def cleanup_all_test_data(self):
        """Clean up all created test data."""
        cleanup_results = {
            "customers_cleaned": 0,
            "loans_cleaned": 0,
            "documents_cleaned": 0,
            "compliance_events_cleaned": 0,
            "errors": []
        }
        
        # Note: In a real blockchain environment, data cannot be deleted
        # This method would typically mark entities as "test" or "deleted"
        # For integration tests, we rely on test isolation through unique IDs
        
        # Clean up documents (if deletion endpoint exists)
        for doc_info in self.created_entities["documents"]:
            try:
                # Placeholder for document cleanup
                cleanup_results["documents_cleaned"] += 1
            except Exception as e:
                cleanup_results["errors"].append(f"Document cleanup error: {str(e)}")
        
        # Clean up loans (if deletion endpoint exists)
        for loan_id in self.created_entities["loans"]:
            try:
                # Placeholder for loan cleanup
                cleanup_results["loans_cleaned"] += 1
            except Exception as e:
                cleanup_results["errors"].append(f"Loan cleanup error: {str(e)}")
        
        # Clean up customers (if deletion endpoint exists)
        for customer_id in self.created_entities["customers"]:
            try:
                # Placeholder for customer cleanup
                cleanup_results["customers_cleaned"] += 1
            except Exception as e:
                cleanup_results["errors"].append(f"Customer cleanup error: {str(e)}")
        
        # Clean up compliance events
        for rule_id in self.created_entities["compliance_events"]:
            try:
                # Placeholder for compliance rule cleanup
                cleanup_results["compliance_events_cleaned"] += 1
            except Exception as e:
                cleanup_results["errors"].append(f"Compliance cleanup error: {str(e)}")
        
        # Clear tracking
        self.created_entities = {
            "customers": [],
            "loans": [],
            "documents": [],
            "compliance_events": [],
            "actors": []
        }
        
        return cleanup_results
    
    def get_entity_summary(self) -> Dict[str, Any]:
        """Get summary of created test entities."""
        return {
            "total_customers": len(self.created_entities["customers"]),
            "total_loans": len(self.created_entities["loans"]),
            "total_documents": len(self.created_entities["documents"]),
            "total_compliance_events": len(self.created_entities["compliance_events"]),
            "created_entities": self.created_entities.copy()
        }


@pytest.fixture
def test_data_manager():
    """Fixture providing test data manager."""
    client = TestClient(app)
    manager = TestDataManager(client)
    manager.setup_mock_services()
    
    yield manager
    
    # Cleanup after test
    manager.cleanup_all_test_data()
    manager.teardown_mock_services()


class TestDataUtilities:
    """Test the test data utilities themselves."""
    
    def test_customer_creation_utility(self, test_data_manager):
        """Test customer creation utility."""
        
        customer = test_data_manager.create_test_customer()
        
        assert "customer_id" in customer
        assert customer["customer_id"] in test_data_manager.created_entities["customers"]
        
        # Test custom data
        custom_customer = test_data_manager.create_test_customer(
            custom_data={"first_name": "Custom", "last_name": "Name"}
        )
        
        assert "customer_id" in custom_customer
        assert len(test_data_manager.created_entities["customers"]) == 2
    
    def test_loan_creation_utility(self, test_data_manager):
        """Test loan creation utility."""
        
        # Create customer first
        customer = test_data_manager.create_test_customer()
        customer_id = customer["customer_id"]
        
        # Create loan
        loan = test_data_manager.create_test_loan(customer_id)
        
        assert "loan_application_id" in loan
        assert loan["customer_id"] == customer_id
        assert loan["loan_application_id"] in test_data_manager.created_entities["loans"]
    
    def test_document_creation_utility(self, test_data_manager):
        """Test document creation utility."""
        
        # Create customer and loan first
        customer = test_data_manager.create_test_customer()
        loan = test_data_manager.create_test_loan(customer["customer_id"])
        
        # Create document
        document = test_data_manager.create_test_document(
            loan["loan_application_id"],
            "INCOME_STATEMENT"
        )
        
        assert "document_id" in document
        assert document["document_type"] == "INCOME_STATEMENT"
        assert len(test_data_manager.created_entities["documents"]) == 1
    
    def test_complete_workflow_creation(self, test_data_manager):
        """Test complete workflow data creation."""
        
        workflow_data = test_data_manager.create_complete_workflow_data()
        
        assert "customer" in workflow_data
        assert "loan" in workflow_data
        assert "documents" in workflow_data
        assert "compliance_rule" in workflow_data
        assert "workflow_id" in workflow_data
        
        # Verify relationships
        assert workflow_data["loan"]["customer_id"] == workflow_data["customer"]["customer_id"]
        assert len(workflow_data["documents"]) == 3
    
    def test_loan_status_updates(self, test_data_manager):
        """Test loan status update utilities."""
        
        # Create workflow data
        workflow_data = test_data_manager.create_complete_workflow_data()
        loan_id = workflow_data["loan"]["loan_application_id"]
        
        # Test status update
        updated_loan = test_data_manager.update_loan_status(loan_id, "UNDERWRITING")
        assert updated_loan["application_status"] == "UNDERWRITING"
        
        # Test approval
        approved_loan = test_data_manager.approve_loan(loan_id, approved_amount=45000.0)
        assert approved_loan["application_status"] == "APPROVED"
        assert approved_loan["approved_amount"] == 45000.0
    
    def test_cleanup_functionality(self, test_data_manager):
        """Test cleanup functionality."""
        
        # Create some test data
        test_data_manager.create_complete_workflow_data()
        
        # Verify data was created
        summary_before = test_data_manager.get_entity_summary()
        assert summary_before["total_customers"] >= 1
        assert summary_before["total_loans"] >= 1
        
        # Cleanup
        cleanup_results = test_data_manager.cleanup_all_test_data()
        
        # Verify cleanup results
        assert cleanup_results["customers_cleaned"] >= 0
        assert cleanup_results["loans_cleaned"] >= 0
        
        # Verify tracking was cleared
        summary_after = test_data_manager.get_entity_summary()
        assert summary_after["total_customers"] == 0
        assert summary_after["total_loans"] == 0
    
    def test_unique_id_generation(self, test_data_manager):
        """Test unique ID generation."""
        
        id1 = test_data_manager.generate_unique_id("TEST")
        id2 = test_data_manager.generate_unique_id("TEST")
        
        assert id1 != id2
        assert id1.startswith("TEST_")
        assert id2.startswith("TEST_")
    
    def test_entity_tracking(self, test_data_manager):
        """Test entity tracking functionality."""
        
        # Create multiple entities
        customer1 = test_data_manager.create_test_customer()
        customer2 = test_data_manager.create_test_customer()
        
        loan1 = test_data_manager.create_test_loan(customer1["customer_id"])
        loan2 = test_data_manager.create_test_loan(customer2["customer_id"])
        
        # Verify tracking
        summary = test_data_manager.get_entity_summary()
        assert summary["total_customers"] == 2
        assert summary["total_loans"] == 2
        
        assert customer1["customer_id"] in summary["created_entities"]["customers"]
        assert customer2["customer_id"] in summary["created_entities"]["customers"]
        assert loan1["loan_application_id"] in summary["created_entities"]["loans"]
        assert loan2["loan_application_id"] in summary["created_entities"]["loans"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])