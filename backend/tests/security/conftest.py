"""
Security testing fixtures and configuration.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
import hashlib
import secrets
import json
from typing import Dict, Any

from shared.auth import (
    Actor, ActorType, Role, Permission, JWTManager, ActorManager,
    BlockchainIdentityMapper, jwt_manager, actor_manager
)


@pytest.fixture
def security_test_actors():
    """Create test actors for security testing."""
    actors = {
        "admin": Actor(
            actor_id="security_admin_001",
            actor_type=ActorType.INTERNAL_USER,
            actor_name="Security Admin",
            role=Role.SYSTEM_ADMINISTRATOR,
            permissions={
                Permission.MANAGE_ACTORS,
                Permission.SYSTEM_MONITORING,
                Permission.API_ACCESS
            }
        ),
        "underwriter": Actor(
            actor_id="security_underwriter_001",
            actor_type=ActorType.INTERNAL_USER,
            actor_name="Security Test Underwriter",
            role=Role.UNDERWRITER,
            permissions={
                Permission.READ_CUSTOMER,
                Permission.READ_LOAN_APPLICATION,
                Permission.UPDATE_LOAN_APPLICATION
            }
        ),
        "compliance_officer": Actor(
            actor_id="security_compliance_001",
            actor_type=ActorType.INTERNAL_USER,
            actor_name="Security Test Compliance Officer",
            role=Role.COMPLIANCE_OFFICER,
            permissions={
                Permission.READ_COMPLIANCE_EVENTS,
                Permission.GENERATE_REGULATORY_REPORT,
                Permission.CREATE_COMPLIANCE_RULE
            }
        ),
        "regulator": Actor(
            actor_id="security_regulator_001",
            actor_type=ActorType.EXTERNAL_PARTNER,
            actor_name="Security Test Regulator",
            role=Role.REGULATOR,
            permissions={
                Permission.ACCESS_REGULATORY_VIEW,
                Permission.READ_COMPLIANCE_EVENTS
            }
        ),
        "inactive_user": Actor(
            actor_id="security_inactive_001",
            actor_type=ActorType.INTERNAL_USER,
            actor_name="Inactive User",
            role=Role.UNDERWRITER,
            permissions={Permission.READ_CUSTOMER},
            is_active=False
        )
    }
    
    # Register actors with actor manager
    for actor in actors.values():
        try:
            actor_manager.create_actor(actor)
        except ValueError:
            # Actor already exists, update it
            actor_manager.update_actor(actor.actor_id, {
                "actor_name": actor.actor_name,
                "role": actor.role,
                "permissions": actor.permissions,
                "is_active": actor.is_active
            })
    
    return actors


@pytest.fixture
def jwt_test_manager():
    """Create JWT manager for testing with known secret."""
    return JWTManager("test_security_secret_key_12345", "HS256")


@pytest.fixture
def mock_blockchain_identity_mapper():
    """Create mock blockchain identity mapper."""
    mapper = BlockchainIdentityMapper()
    # Add some test mappings
    mapper.map_actor_to_blockchain_identity("security_admin_001", "x509_admin_cert")
    mapper.map_actor_to_blockchain_identity("security_underwriter_001", "x509_underwriter_cert")
    return mapper


@pytest.fixture
def sample_encrypted_data():
    """Generate sample encrypted data for testing."""
    return {
        "plaintext": "sensitive_customer_data_12345",
        "encrypted": hashlib.sha256("sensitive_customer_data_12345".encode()).hexdigest(),
        "salt": secrets.token_hex(16),
        "algorithm": "SHA256"
    }


@pytest.fixture
def audit_trail_data():
    """Generate sample audit trail data."""
    # Use a fixed base time in the past to avoid timezone issues
    base_time = datetime.now() - timedelta(hours=1)
    return [
        {
            "transaction_id": "tx_001",
            "actor_id": "security_underwriter_001",
            "action": "CREATE_CUSTOMER",
            "entity_type": "Customer",
            "entity_id": "cust_001",
            "timestamp": base_time.isoformat(),
            "data_hash": hashlib.sha256("customer_data_001".encode()).hexdigest(),
            "previous_hash": None
        },
        {
            "transaction_id": "tx_002",
            "actor_id": "security_underwriter_001",
            "action": "UPDATE_CUSTOMER",
            "entity_type": "Customer",
            "entity_id": "cust_001",
            "timestamp": (base_time + timedelta(minutes=5)).isoformat(),
            "data_hash": hashlib.sha256("updated_customer_data_001".encode()).hexdigest(),
            "previous_hash": hashlib.sha256("customer_data_001".encode()).hexdigest()
        },
        {
            "transaction_id": "tx_003",
            "actor_id": "security_compliance_001",
            "action": "CREATE_COMPLIANCE_EVENT",
            "entity_type": "ComplianceEvent",
            "entity_id": "event_001",
            "timestamp": (base_time + timedelta(minutes=10)).isoformat(),
            "data_hash": hashlib.sha256("compliance_event_001".encode()).hexdigest(),
            "previous_hash": hashlib.sha256("updated_customer_data_001".encode()).hexdigest()
        }
    ]


@pytest.fixture
def compliance_test_data():
    """Generate compliance test data."""
    return {
        "rules": [
            {
                "rule_id": "AML_001",
                "rule_name": "Basic AML Check",
                "rule_logic": "customer.kyc_status == 'VERIFIED'",
                "domain": "CUSTOMER",
                "status": "ACTIVE"
            },
            {
                "rule_id": "LOAN_001", 
                "rule_name": "Loan Amount Limit",
                "rule_logic": "loan.amount <= 1000000",
                "domain": "LOAN",
                "status": "ACTIVE"
            }
        ],
        "events": [
            {
                "event_id": "evt_001",
                "rule_id": "AML_001",
                "event_type": "RULE_VIOLATION",
                "severity": "ERROR",
                "affected_entity_type": "CUSTOMER",
                "affected_entity_id": "cust_001",
                "description": "Customer KYC not verified",
                "resolution_status": "OPEN"
            },
            {
                "event_id": "evt_002",
                "rule_id": "LOAN_001",
                "event_type": "RULE_CHECK",
                "severity": "INFO",
                "affected_entity_type": "LOAN",
                "affected_entity_id": "loan_001",
                "description": "Loan amount within limits",
                "resolution_status": "RESOLVED"
            }
        ]
    }


@pytest.fixture
def vulnerability_test_payloads():
    """Generate test payloads for vulnerability testing."""
    return {
        "sql_injection": [
            "'; DROP TABLE customers; --",
            "' OR '1'='1",
            "admin'--",
            "' UNION SELECT * FROM users --"
        ],
        "xss": [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "';alert(String.fromCharCode(88,83,83))//';alert(String.fromCharCode(88,83,83))//\";alert(String.fromCharCode(88,83,83))//\";alert(String.fromCharCode(88,83,83))//--></SCRIPT>\">'><SCRIPT>alert(String.fromCharCode(88,83,83))</SCRIPT>"
        ],
        "command_injection": [
            "; ls -la",
            "| cat /etc/passwd",
            "&& rm -rf /",
            "`whoami`"
        ],
        "path_traversal": [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd"
        ]
    }


@pytest.fixture
def mock_fabric_gateway():
    """Mock Fabric Gateway for security testing."""
    mock_gateway = Mock()
    
    # Mock successful blockchain operations
    mock_gateway.invoke_chaincode.return_value = {
        "status": "SUCCESS",
        "payload": json.dumps({"result": "success"}),
        "transaction_id": "tx_mock_001"
    }
    
    mock_gateway.query_chaincode.return_value = {
        "status": "SUCCESS", 
        "payload": json.dumps({"data": "mock_data"}),
        "transaction_id": "query_mock_001"
    }
    
    return mock_gateway


@pytest.fixture
def security_headers():
    """Standard security headers for testing."""
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
        "Referrer-Policy": "strict-origin-when-cross-origin"
    }


@pytest.fixture
def rate_limit_config():
    """Rate limiting configuration for testing."""
    return {
        "requests_per_minute": 60,
        "requests_per_hour": 1000,
        "burst_limit": 10,
        "block_duration": 300  # 5 minutes
    }