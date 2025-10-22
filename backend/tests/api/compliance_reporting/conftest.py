"""
Compliance Reporting domain-specific test configuration and fixtures.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

# from shared.database import ComplianceEventModel


@pytest.fixture
def compliance_mock_db_utils():
    """Mock database utilities specifically for compliance tests."""
    mock_db_utils = Mock()
    
    # Configure common compliance database operations
    mock_db_utils.get_compliance_events_by_entity.return_value = []
    mock_db_utils.create_compliance_event.return_value = Mock()  # spec=ComplianceEventModel
    mock_db_utils.get_compliance_events_by_date_range.return_value = []
    
    return mock_db_utils


@pytest.fixture
def sample_regulatory_report_request():
    """Sample regulatory report request data."""
    return {
        "report_type": "AML_MONTHLY",
        "period_start": (datetime.utcnow() - timedelta(days=30)).isoformat(),
        "period_end": datetime.utcnow().isoformat(),
        "include_details": True,
        "format": "json"
    }


@pytest.fixture
def sample_compliance_rule():
    """Sample compliance rule data."""
    return {
        "rule_id": "AML_RULE_001",
        "rule_name": "High Value Transaction Monitoring",
        "rule_type": "TRANSACTION_MONITORING",
        "threshold_amount": 10000.0,
        "severity": "HIGH",
        "auto_flag": True,
        "description": "Flag transactions above $10,000 for AML review"
    }


@pytest.fixture
def sample_audit_trail_request():
    """Sample audit trail request data."""
    return {
        "entity_type": "CUSTOMER",
        "entity_id": "CUST_123456789ABC",
        "from_date": (datetime.utcnow() - timedelta(days=7)).isoformat(),
        "to_date": datetime.utcnow().isoformat(),
        "include_blockchain_verification": True
    }


@pytest.fixture
def sample_compliance_alert():
    """Sample compliance alert data."""
    return {
        "alert_type": "SUSPICIOUS_ACTIVITY",
        "severity": "HIGH",
        "entity_type": "LOAN_APPLICATION",
        "entity_id": "LOAN_123456",
        "description": "Multiple loan applications from same IP address",
        "risk_indicators": [
            "rapid_application_submission",
            "duplicate_contact_info",
            "high_requested_amount"
        ]
    }


@pytest.fixture
def mock_regulatory_api():
    """Mock regulatory reporting API."""
    with patch('compliance_reporting.api._submit_regulatory_report') as mock_api:
        mock_api.return_value = {
            "submission_id": "REG_SUBMIT_123",
            "status": "ACCEPTED",
            "confirmation_number": "CONF_789",
            "submission_timestamp": datetime.utcnow().isoformat()
        }
        yield mock_api


@pytest.fixture
def mock_risk_engine():
    """Mock risk assessment engine."""
    with patch('compliance_reporting.api._assess_risk') as mock_risk:
        mock_risk.return_value = {
            "risk_score": 0.3,
            "risk_level": "MEDIUM",
            "risk_factors": ["new_customer", "high_amount"],
            "recommendation": "MANUAL_REVIEW"
        }
        yield mock_risk