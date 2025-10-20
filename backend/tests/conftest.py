"""
Global pytest configuration and shared fixtures.

This file makes shared fixtures available to all test modules
and configures pytest settings for the entire test suite.
"""

import pytest
import asyncio
from unittest.mock import patch


# Configure pytest for async tests
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Mock external dependencies by default (disabled for now to avoid import issues)
# @pytest.fixture(autouse=True)
# def mock_external_services():
#     """Automatically mock external services for all tests."""
#     pass


# Configure test markers
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "blockchain: mark test as requiring blockchain interaction"
    )
    config.addinivalue_line(
        "markers", "database: mark test as requiring database"
    )
    config.addinivalue_line(
        "markers", "workflow: mark test as end-to-end workflow test"
    )
    config.addinivalue_line(
        "markers", "cross_domain: mark test as cross-domain integration test"
    )
    config.addinivalue_line(
        "markers", "data_utilities: mark test as test data management utility"
    )


# Test collection configuration
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        # Add markers based on test file location
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "unit" in str(item.fspath) or "/test_" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        
        # Add domain markers based on directory structure
        if "customer_mastery" in str(item.fspath):
            item.add_marker(pytest.mark.customer_mastery)
        elif "loan_origination" in str(item.fspath):
            item.add_marker(pytest.mark.loan_origination)
        elif "compliance_reporting" in str(item.fspath):
            item.add_marker(pytest.mark.compliance_reporting)
        elif "shared" in str(item.fspath):
            item.add_marker(pytest.mark.shared)
        
        # Add specific integration test markers
        if "workflow" in str(item.fspath):
            item.add_marker(pytest.mark.workflow)
        elif "cross_domain" in str(item.fspath):
            item.add_marker(pytest.mark.cross_domain)
        elif "data_utilities" in str(item.fspath):
            item.add_marker(pytest.mark.data_utilities)