"""
Shared utilities and infrastructure test configuration and fixtures.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import tempfile
import os


@pytest.fixture
def mock_settings():
    """Mock application settings."""
    with patch('shared.config.settings') as mock_settings:
        mock_settings.DATABASE_URL = "sqlite:///test.db"
        mock_settings.SECRET_KEY = "test_secret_key"
        mock_settings.FABRIC_GATEWAY_ENDPOINT = "localhost:7051"
        mock_settings.FABRIC_MSP_ID = "TestMSP"
        mock_settings.FABRIC_CHANNEL_NAME = "testchannel"
        mock_settings.JWT_ALGORITHM = "HS256"
        mock_settings.ACCESS_TOKEN_EXPIRE_MINUTES = 30
        yield mock_settings


@pytest.fixture
def temp_crypto_files():
    """Create temporary crypto files for testing."""
    files = {}
    
    # Create temporary certificate files
    for file_type in ['admin.pem', 'admin-key.pem', 'ca.pem']:
        fd, path = tempfile.mkstemp(suffix=f'.{file_type}')
        with os.fdopen(fd, 'w') as f:
            f.write(f"-----BEGIN CERTIFICATE-----\ntest_{file_type}_content\n-----END CERTIFICATE-----")
        files[file_type] = path
    
    yield files
    
    # Cleanup
    for path in files.values():
        try:
            os.unlink(path)
        except OSError:
            pass


@pytest.fixture
def mock_fabric_network():
    """Mock Fabric network components."""
    with patch('shared.fabric_gateway.Gateway') as mock_gateway:
        with patch('shared.fabric_gateway.Network') as mock_network:
            with patch('shared.fabric_gateway.Contract') as mock_contract:
                # Configure mock behavior
                gateway_instance = AsyncMock()
                network_instance = AsyncMock()
                contract_instance = AsyncMock()
                
                mock_gateway.return_value = gateway_instance
                mock_network.return_value = network_instance
                mock_contract.return_value = contract_instance
                
                # Configure contract responses
                contract_instance.submit_transaction.return_value = b'{"status": "SUCCESS"}'
                contract_instance.evaluate_transaction.return_value = b'{"result": "test"}'
                
                yield {
                    'gateway': gateway_instance,
                    'network': network_instance,
                    'contract': contract_instance
                }


@pytest.fixture
def mock_jwt_decode():
    """Mock JWT token decoding."""
    with patch('shared.auth.jwt.decode') as mock_decode:
        mock_decode.return_value = {
            "sub": "test_actor_001",
            "actor_type": "Internal_User",
            "role": "Underwriter",
            "permissions": ["read_customer", "read_loan_application"],
            "exp": 9999999999  # Far future expiry
        }
        yield mock_decode


@pytest.fixture
def mock_password_hash():
    """Mock password hashing utilities."""
    with patch('shared.auth.pwd_context') as mock_pwd:
        mock_pwd.hash.return_value = "hashed_password"
        mock_pwd.verify.return_value = True
        yield mock_pwd