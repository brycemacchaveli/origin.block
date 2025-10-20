"""
Integration tests for compliance rule enforcement.

Tests automated compliance rule execution, violation detection, reporting,
and integration with customer and loan origination workflows.
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
def compliance_test_data():
    """Test data for compliance rule enforcement."""
    return {
        "compliance_rules": [
            {
                "rule_id": "AML_AMOUNT_THRESHOLD",
                "rule_name": "AML Amount Threshold Check",
                "rule_description": "Flag transactions above $10,000 for AML review",
                "rule_logic": "loan_amount > 10000",
                "applies_to_domain": "LOAN_ORIGINATION",
                "status": "ACTIVE"
            },
            {
                "rule_id": "KYC_VERIFICATION_REQUIRED",
                "rule_name": "KYC Verification Required",
                "rule_description": "Require KYC verification before loan approval",
                "rule_logic": "kyc_status == 'VERIFIED'",
                "applies_to_domain": "CUSTOMER_MASTERY",
                "status": "ACTIVE"
            },
            {
                "rule_id": "SANCTION_LIST_CHECK",
                "rule_name": "Sanction List Screening",
                "rule_description": "Check customer against sanction lists",
                "rule_logic": "not in_sanction_list",
                "applies_to_domain": "CUSTOMER_MASTERY",
                "status": "ACTIVE"
            }
        ],
        "test_scenarios": {
            "high_amount_loan": {
                "customer_id": "CUST_COMPLIANCE_001",
                "requested_amount": 15000.0,
                "loan_type": "PERSONAL",
                "introducer_id": "INTRO_001"
            },
            "low_amount_loan": {
                "customer_id": "CUST_COMPLIANCE_002",
                "requested_amount": 5000.0,
                "loan_type": "PERSONAL",
                "introducer_id": "INTRO_001"
            },
            "unverified_customer": {
                "first_name": "Unverified",
                "last_name": "Customer",
                "date_of_birth": "1990-01-01T00:00:00",
                "national_id": "UNVERIFIED123",
                "address": "123 Unverified St",
                "contact_email": "unverified@example.com",
                "contact_phone": "+1-555-000-0000",
                "kyc_status": "PENDING"
            }
        },
        "actor": {
            "actor_id": "COMPLIANCE_OFFICER_001",
            "actor_type": "Internal_User",
            "actor_name": "Compliance Officer",
            "role": "Compliance_Officer"
        }
    }


@pytest.fixture
def mock_compliance_services():
    """Mock blockchain and external services for compliance tests."""
    from .mock_infrastructure import IntegrationTestMockManager
    
    mock_manager = IntegrationTestMockManager()
    with mock_manager.mock_all_services() as mocks:
        yield {
            'mock_manager': mock_manager,
            'mocks': mocks
        }


class TestComplianceRuleEnforcement:
    """Test automated compliance rule enforcement."""
    
    def test_compliance_rule_creation_and_management(self, client, compliance_test_data, mock_compliance_services):
        """Test compliance rule creation and management."""
        
        # Create compliance rules
        for rule in compliance_test_data["compliance_rules"]:
            response = client.post(
                "/api/v1/compliance/rules",
                json=rule,
                headers={"X-Actor-ID": compliance_test_data["actor"]["actor_id"]}
            )
            
            assert response.status_code == 201
            rule_data = response.json()
            assert rule_data["rule_id"] == rule["rule_id"]
            assert rule_data["status"] == "ACTIVE"
        
        # Retrieve all rules
        response = client.get(
            "/api/v1/compliance/rules",
            headers={"X-Actor-ID": compliance_test_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 200
        rules_data = response.json()
        assert len(rules_data["rules"]) >= len(compliance_test_data["compliance_rules"])
        
        # Update rule status
        response = client.put(
            "/api/v1/compliance/rules/AML_AMOUNT_THRESHOLD",
            json={"status": "INACTIVE", "reason": "Testing rule deactivation"},
            headers={"X-Actor-ID": compliance_test_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 200
        updated_rule = response.json()
        assert updated_rule["status"] == "INACTIVE"
    
    def test_automated_aml_threshold_enforcement(self, client, compliance_test_data, mock_compliance_services):
        """Test automated AML threshold rule enforcement."""
        
        # Submit high-amount loan (should trigger AML rule)
        response = client.post(
            "/api/v1/loans/applications",
            json=compliance_test_data["test_scenarios"]["high_amount_loan"],
            headers={"X-Actor-ID": "UNDERWRITER_001"}
        )
        
        assert response.status_code == 201
        loan_data = response.json()
        loan_id = loan_data["loan_application_id"]
        
        # Check for compliance events
        response = client.get(
            "/api/v1/compliance/events",
            params={
                "affected_entity_id": loan_id,
                "rule_id": "AML_AMOUNT_THRESHOLD"
            },
            headers={"X-Actor-ID": compliance_test_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 200
        events_data = response.json()
        
        # Should have at least one AML threshold violation event
        aml_events = [event for event in events_data["events"] 
                     if event["rule_id"] == "AML_AMOUNT_THRESHOLD"]
        assert len(aml_events) >= 1
        
        # Submit low-amount loan (should not trigger AML rule)
        response = client.post(
            "/api/v1/loans/applications",
            json=compliance_test_data["test_scenarios"]["low_amount_loan"],
            headers={"X-Actor-ID": "UNDERWRITER_001"}
        )
        
        assert response.status_code == 201
        low_loan_data = response.json()
        low_loan_id = low_loan_data["loan_application_id"]
        
        # Check for compliance events (should be none for low amount)
        response = client.get(
            "/api/v1/compliance/events",
            params={
                "affected_entity_id": low_loan_id,
                "rule_id": "AML_AMOUNT_THRESHOLD"
            },
            headers={"X-Actor-ID": compliance_test_data["actor"]["actor_id"]}
        )
        
        events_data = response.json()
        low_aml_events = [event for event in events_data["events"] 
                         if event["rule_id"] == "AML_AMOUNT_THRESHOLD"]
        assert len(low_aml_events) == 0
    
    def test_kyc_verification_enforcement(self, client, compliance_test_data, mock_compliance_services):
        """Test KYC verification requirement enforcement."""
        
        # Create unverified customer
        response = client.post(
            "/api/v1/customers",
            json=compliance_test_data["test_scenarios"]["unverified_customer"],
            headers={"X-Actor-ID": "CSR_001"}
        )
        
        assert response.status_code == 201
        customer_data = response.json()
        unverified_customer_id = customer_data["customer_id"]
        
        # Try to create loan for unverified customer
        loan_data = {
            "customer_id": unverified_customer_id,
            "requested_amount": 5000.0,
            "loan_type": "PERSONAL",
            "introducer_id": "INTRO_001"
        }
        
        response = client.post(
            "/api/v1/loans/applications",
            json=loan_data,
            headers={"X-Actor-ID": "UNDERWRITER_001"}
        )
        
        # Should either reject or create with compliance flag
        if response.status_code == 201:
            loan_id = response.json()["loan_application_id"]
            
            # Check for KYC compliance events
            response = client.get(
                "/api/v1/compliance/events",
                params={
                    "affected_entity_id": loan_id,
                    "rule_id": "KYC_VERIFICATION_REQUIRED"
                },
                headers={"X-Actor-ID": compliance_test_data["actor"]["actor_id"]}
            )
            
            events_data = response.json()
            kyc_events = [event for event in events_data["events"] 
                         if event["rule_id"] == "KYC_VERIFICATION_REQUIRED"]
            assert len(kyc_events) >= 1
        else:
            assert response.status_code == 400
            assert "kyc" in response.json()["detail"].lower()
    
    def test_sanction_list_screening(self, client, compliance_test_data, mock_compliance_services):
        """Test sanction list screening enforcement."""
        
        # Configure for sanctioned customer scenario
        mock_compliance_services['mock_manager'].configure_scenario("sanctioned_customer")
        
        # Try to create sanctioned customer
        sanctioned_customer = {
            "first_name": "Sanctioned",
            "last_name": "Individual",
            "date_of_birth": "1980-01-01T00:00:00",
            "national_id": "SANCT123456",
            "address": "123 Sanctioned St",
            "contact_email": "sanctioned@example.com",
            "contact_phone": "+1-555-000-0001"
        }
        
        response = client.post(
            "/api/v1/customers",
            json=sanctioned_customer,
            headers={"X-Actor-ID": "CSR_001"}
        )
        
        # Should either reject or create with compliance flag
        if response.status_code == 201:
            customer_id = response.json()["customer_id"]
            
            # Check for sanction list compliance events
            response = client.get(
                "/api/v1/compliance/events",
                params={
                    "affected_entity_id": customer_id,
                    "rule_id": "SANCTION_LIST_CHECK"
                },
                headers={"X-Actor-ID": compliance_test_data["actor"]["actor_id"]}
            )
            
            events_data = response.json()
            sanction_events = [event for event in events_data["events"] 
                              if event["rule_id"] == "SANCTION_LIST_CHECK"]
            assert len(sanction_events) >= 1
        else:
            assert response.status_code == 400
            assert "sanction" in response.json()["detail"].lower()
    
    def test_compliance_event_lifecycle(self, client, compliance_test_data, mock_compliance_services):
        """Test complete compliance event lifecycle."""
        
        # Create high-amount loan to trigger compliance event
        response = client.post(
            "/api/v1/loans/applications",
            json=compliance_test_data["test_scenarios"]["high_amount_loan"],
            headers={"X-Actor-ID": "UNDERWRITER_001"}
        )
        loan_id = response.json()["loan_application_id"]
        
        # Get compliance events
        response = client.get(
            "/api/v1/compliance/events",
            params={"affected_entity_id": loan_id},
            headers={"X-Actor-ID": compliance_test_data["actor"]["actor_id"]}
        )
        
        events_data = response.json()
        assert len(events_data["events"]) >= 1
        
        event_id = events_data["events"][0]["event_id"]
        
        # Acknowledge compliance event
        response = client.post(
            f"/api/v1/compliance/events/{event_id}/acknowledge",
            json={
                "acknowledgment_notes": "Reviewed and approved by compliance officer",
                "resolution_action": "APPROVED_WITH_CONDITIONS"
            },
            headers={"X-Actor-ID": compliance_test_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 200
        ack_data = response.json()
        assert ack_data["acknowledged_by"] == compliance_test_data["actor"]["actor_id"]
        assert "acknowledged_date" in ack_data
        
        # Verify event status updated
        response = client.get(
            f"/api/v1/compliance/events/{event_id}",
            headers={"X-Actor-ID": compliance_test_data["actor"]["actor_id"]}
        )
        
        event_data = response.json()
        assert event_data["acknowledged_by"] == compliance_test_data["actor"]["actor_id"]
    
    def test_regulatory_reporting_generation(self, client, compliance_test_data, mock_compliance_services):
        """Test regulatory report generation."""
        
        # Generate compliance events by creating various transactions
        test_loans = [
            compliance_test_data["test_scenarios"]["high_amount_loan"],
            compliance_test_data["test_scenarios"]["low_amount_loan"]
        ]
        
        for loan in test_loans:
            client.post(
                "/api/v1/loans/applications",
                json=loan,
                headers={"X-Actor-ID": "UNDERWRITER_001"}
            )
        
        # Generate regulatory report
        report_request = {
            "report_type": "AML_SUSPICIOUS_ACTIVITY",
            "start_date": (datetime.now() - timedelta(days=30)).isoformat(),
            "end_date": datetime.now().isoformat(),
            "include_acknowledged": False
        }
        
        response = client.post(
            "/api/v1/compliance/reports/generate",
            json=report_request,
            headers={"X-Actor-ID": compliance_test_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 200
        report_data = response.json()
        assert "report_id" in report_data
        assert "total_events" in report_data
        assert "suspicious_activities" in report_data
        
        # Retrieve generated report
        report_id = report_data["report_id"]
        response = client.get(
            f"/api/v1/compliance/reports/{report_id}",
            headers={"X-Actor-ID": compliance_test_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 200
        full_report = response.json()
        assert full_report["report_id"] == report_id
        assert "events" in full_report
    
    def test_cross_domain_compliance_integration(self, client, compliance_test_data, mock_compliance_services):
        """Test compliance integration across customer and loan domains."""
        
        # Create customer with compliance monitoring
        customer_data = {
            "first_name": "Cross",
            "last_name": "Domain",
            "date_of_birth": "1985-01-01T00:00:00",
            "national_id": "CROSS123456",
            "address": "123 Cross Domain St",
            "contact_email": "cross@example.com",
            "contact_phone": "+1-555-123-9999"
        }
        
        response = client.post(
            "/api/v1/customers",
            json=customer_data,
            headers={"X-Actor-ID": "CSR_001"}
        )
        customer_id = response.json()["customer_id"]
        
        # Create high-amount loan for this customer
        loan_data = {
            "customer_id": customer_id,
            "requested_amount": 25000.0,
            "loan_type": "BUSINESS",
            "introducer_id": "INTRO_001"
        }
        
        response = client.post(
            "/api/v1/loans/applications",
            json=loan_data,
            headers={"X-Actor-ID": "UNDERWRITER_001"}
        )
        loan_id = response.json()["loan_application_id"]
        
        # Check compliance events for both customer and loan
        response = client.get(
            "/api/v1/compliance/events",
            params={"affected_entity_id": customer_id},
            headers={"X-Actor-ID": compliance_test_data["actor"]["actor_id"]}
        )
        customer_events = response.json()["events"]
        
        response = client.get(
            "/api/v1/compliance/events",
            params={"affected_entity_id": loan_id},
            headers={"X-Actor-ID": compliance_test_data["actor"]["actor_id"]}
        )
        loan_events = response.json()["events"]
        
        # Should have compliance events for both entities
        total_events = len(customer_events) + len(loan_events)
        assert total_events >= 1
        
        # Verify cross-references in events
        all_events = customer_events + loan_events
        for event in all_events:
            assert event["affected_entity_id"] in [customer_id, loan_id]
    
    def test_compliance_rule_performance_monitoring(self, client, compliance_test_data, mock_compliance_services):
        """Test compliance rule performance and monitoring."""
        
        # Get compliance rule performance metrics
        response = client.get(
            "/api/v1/compliance/rules/performance",
            params={
                "start_date": (datetime.now() - timedelta(days=7)).isoformat(),
                "end_date": datetime.now().isoformat()
            },
            headers={"X-Actor-ID": compliance_test_data["actor"]["actor_id"]}
        )
        
        assert response.status_code == 200
        performance_data = response.json()
        assert "rule_metrics" in performance_data
        
        # Check individual rule performance
        for rule in compliance_test_data["compliance_rules"]:
            rule_id = rule["rule_id"]
            response = client.get(
                f"/api/v1/compliance/rules/{rule_id}/metrics",
                params={
                    "start_date": (datetime.now() - timedelta(days=7)).isoformat(),
                    "end_date": datetime.now().isoformat()
                },
                headers={"X-Actor-ID": compliance_test_data["actor"]["actor_id"]}
            )
            
            assert response.status_code == 200
            rule_metrics = response.json()
            assert "execution_count" in rule_metrics
            assert "violation_count" in rule_metrics
            assert "average_execution_time" in rule_metrics


if __name__ == "__main__":
    pytest.main([__file__, "-v"])