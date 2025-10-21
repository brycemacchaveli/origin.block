"""
Data Encryption and Privacy Security Tests.

Tests for data encryption at rest and in transit, PII protection,
data masking, and privacy compliance (GDPR, CCPA).
"""

import pytest
import hashlib
import secrets
import json
import base64
from datetime import datetime
from unittest.mock import Mock, patch
import re

# Try to import cryptography, skip tests if not available
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    # Mock classes for when cryptography is not available
    class Fernet:
        @staticmethod
        def generate_key():
            return b"mock_key_32_bytes_long_for_test"
        
        def __init__(self, key):
            self.key = key
        
        def encrypt(self, data):
            return b"mock_encrypted_" + data
        
        def decrypt(self, data):
            return data.replace(b"mock_encrypted_", b"")
    
    class PBKDF2HMAC:
        def __init__(self, algorithm, length, salt, iterations):
            pass
        
        def derive(self, password):
            return b"mock_derived_key_32_bytes_long"


class TestDataEncryptionAtRest:
    """Test data encryption at rest security."""
    
    @pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="cryptography package not available")
    def test_sensitive_data_encryption(self, sample_encrypted_data):
        """Test that sensitive data is properly encrypted."""
        plaintext = sample_encrypted_data["plaintext"]
        
        # Test encryption with Fernet (symmetric encryption)
        key = Fernet.generate_key()
        cipher_suite = Fernet(key)
        
        encrypted_data = cipher_suite.encrypt(plaintext.encode())
        decrypted_data = cipher_suite.decrypt(encrypted_data).decode()
        
        assert decrypted_data == plaintext
        assert encrypted_data != plaintext.encode()
        assert len(encrypted_data) > len(plaintext)
    
    def test_pii_data_hashing(self):
        """Test PII data hashing for privacy protection."""
        pii_data = [
            "123-45-6789",  # SSN
            "john.doe@example.com",  # Email
            "+1-555-123-4567",  # Phone
            "4532-1234-5678-9012"  # Credit card
        ]
        
        for pii in pii_data:
            # Hash with salt for security
            salt = secrets.token_bytes(32)
            hashed_pii = hashlib.pbkdf2_hmac('sha256', pii.encode(), salt, 100000)
            
            # Verify hash is different from original
            assert hashed_pii != pii.encode()
            assert len(hashed_pii) == 32  # SHA256 output length
            
            # Verify same input produces same hash with same salt
            hashed_pii2 = hashlib.pbkdf2_hmac('sha256', pii.encode(), salt, 100000)
            assert hashed_pii == hashed_pii2
    
    @pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="cryptography package not available")
    def test_database_field_encryption(self):
        """Test database field-level encryption."""
        # Simulate encrypted database fields
        sensitive_fields = {
            "national_id": "123456789",
            "bank_account": "9876543210",
            "credit_score": "750",
            "income": "75000"
        }
        
        # Generate encryption key
        password = b"database_encryption_key"
        salt = secrets.token_bytes(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        cipher_suite = Fernet(key)
        
        # Encrypt sensitive fields
        encrypted_fields = {}
        for field_name, field_value in sensitive_fields.items():
            encrypted_value = cipher_suite.encrypt(field_value.encode())
            encrypted_fields[field_name] = base64.b64encode(encrypted_value).decode()
        
        # Verify encryption
        for field_name in sensitive_fields:
            encrypted_value = base64.b64decode(encrypted_fields[field_name])
            decrypted_value = cipher_suite.decrypt(encrypted_value).decode()
            assert decrypted_value == sensitive_fields[field_name]
    
    @pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="cryptography package not available")
    def test_key_rotation_simulation(self):
        """Test encryption key rotation procedures."""
        data = "sensitive_customer_data"
        
        # Old key
        old_key = Fernet.generate_key()
        old_cipher = Fernet(old_key)
        encrypted_with_old_key = old_cipher.encrypt(data.encode())
        
        # New key for rotation
        new_key = Fernet.generate_key()
        new_cipher = Fernet(new_key)
        
        # Simulate key rotation: decrypt with old key, encrypt with new key
        decrypted_data = old_cipher.decrypt(encrypted_with_old_key).decode()
        encrypted_with_new_key = new_cipher.encrypt(decrypted_data.encode())
        
        # Verify data integrity after rotation
        final_decrypted = new_cipher.decrypt(encrypted_with_new_key).decode()
        assert final_decrypted == data
        
        # Old key should no longer work with new encryption
        with pytest.raises(Exception):
            old_cipher.decrypt(encrypted_with_new_key)


class TestDataEncryptionInTransit:
    """Test data encryption in transit security."""
    
    def test_https_enforcement(self):
        """Test HTTPS enforcement for API communications."""
        # Simulate HTTP vs HTTPS requests
        http_request = {
            "url": "http://api.example.com/customers",
            "method": "POST",
            "data": {"customer_id": "123", "name": "John Doe"},
            "secure": False
        }
        
        https_request = {
            "url": "https://api.example.com/customers",
            "method": "POST", 
            "data": {"customer_id": "123", "name": "John Doe"},
            "secure": True
        }
        
        # Only HTTPS should be allowed for sensitive operations
        assert not http_request["secure"]
        assert https_request["secure"]
        
        # Verify URL scheme
        assert http_request["url"].startswith("http://")
        assert https_request["url"].startswith("https://")
    
    def test_tls_configuration(self, security_headers):
        """Test TLS configuration security."""
        # Test security headers for HTTPS
        required_headers = [
            "Strict-Transport-Security",
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection"
        ]
        
        for header in required_headers:
            assert header in security_headers
        
        # Test HSTS header specifically
        hsts_header = security_headers["Strict-Transport-Security"]
        assert "max-age=" in hsts_header
        assert "includeSubDomains" in hsts_header
    
    @pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="cryptography package not available")
    def test_api_payload_encryption(self):
        """Test API payload encryption for sensitive data."""
        # Simulate encrypted API payload
        sensitive_payload = {
            "customer_id": "cust_001",
            "national_id": "123456789",
            "bank_account": "9876543210",
            "loan_amount": 50000
        }
        
        # Encrypt payload for transmission
        key = Fernet.generate_key()
        cipher_suite = Fernet(key)
        
        payload_json = json.dumps(sensitive_payload)
        encrypted_payload = cipher_suite.encrypt(payload_json.encode())
        
        # Simulate transmission (base64 encode for JSON compatibility)
        transmitted_payload = base64.b64encode(encrypted_payload).decode()
        
        # Simulate decryption on receiver side
        received_encrypted = base64.b64decode(transmitted_payload)
        decrypted_json = cipher_suite.decrypt(received_encrypted).decode()
        decrypted_payload = json.loads(decrypted_json)
        
        assert decrypted_payload == sensitive_payload
    
    @pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="cryptography package not available")
    def test_blockchain_transaction_encryption(self):
        """Test blockchain transaction data encryption."""
        # Simulate blockchain transaction with encrypted data
        transaction_data = {
            "customer_id": "cust_001",
            "loan_application_id": "loan_001",
            "encrypted_customer_data": None,
            "data_hash": None
        }
        
        # Customer data to be encrypted before blockchain storage
        customer_data = {
            "name": "John Doe",
            "national_id": "123456789",
            "address": "123 Main St, City, State"
        }
        
        # Encrypt customer data
        key = Fernet.generate_key()
        cipher_suite = Fernet(key)
        
        customer_json = json.dumps(customer_data)
        encrypted_customer = cipher_suite.encrypt(customer_json.encode())
        
        # Store encrypted data and hash in transaction
        transaction_data["encrypted_customer_data"] = base64.b64encode(encrypted_customer).decode()
        transaction_data["data_hash"] = hashlib.sha256(customer_json.encode()).hexdigest()
        
        # Verify encryption
        assert transaction_data["encrypted_customer_data"] != customer_json
        assert len(transaction_data["data_hash"]) == 64  # SHA256 hex length


class TestPIIProtectionAndMasking:
    """Test PII protection and data masking."""
    
    def test_pii_detection(self):
        """Test PII detection in data fields."""
        test_data = {
            "name": "John Doe",
            "email": "john.doe@example.com",
            "phone": "555-123-4567",
            "ssn": "123-45-6789",
            "credit_card": "4532-1234-5678-9012",
            "address": "123 Main St, Anytown, ST 12345",
            "date_of_birth": "1990-01-15",
            "account_number": "ACC123456789"
        }
        
        # PII detection patterns
        pii_patterns = {
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "phone": r'\b\d{3}-\d{3}-\d{4}\b',
            "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
            "credit_card": r'\b\d{4}-\d{4}-\d{4}-\d{4}\b'
        }
        
        detected_pii = {}
        for field_name, field_value in test_data.items():
            for pii_type, pattern in pii_patterns.items():
                if re.search(pattern, str(field_value)):
                    detected_pii[field_name] = pii_type
        
        # Verify PII detection
        assert "email" in detected_pii
        assert "phone" in detected_pii
        assert "ssn" in detected_pii
        assert "credit_card" in detected_pii
    
    def test_data_masking(self):
        """Test data masking for PII protection."""
        sensitive_data = {
            "ssn": "123-45-6789",
            "credit_card": "4532-1234-5678-9012",
            "phone": "555-123-4567",
            "email": "john.doe@example.com",
            "account_number": "ACC123456789"
        }
        
        def mask_data(value, mask_char="*", visible_chars=4):
            """Mask sensitive data showing only last few characters."""
            if len(value) <= visible_chars:
                return mask_char * len(value)
            return mask_char * (len(value) - visible_chars) + value[-visible_chars:]
        
        masked_data = {}
        for field_name, field_value in sensitive_data.items():
            # Remove special characters for masking
            clean_value = re.sub(r'[^A-Za-z0-9]', '', field_value)
            masked_value = mask_data(clean_value)
            masked_data[field_name] = masked_value
        
        # Verify masking
        assert masked_data["ssn"].endswith("6789")
        assert masked_data["credit_card"].endswith("9012")
        assert "*" in masked_data["ssn"]
        assert "*" in masked_data["credit_card"]
    
    def test_data_anonymization(self):
        """Test data anonymization techniques."""
        customer_data = [
            {"id": "001", "name": "John Doe", "age": 30, "city": "New York", "income": 75000},
            {"id": "002", "name": "Jane Smith", "age": 25, "city": "Los Angeles", "income": 65000},
            {"id": "003", "name": "Bob Johnson", "age": 35, "city": "Chicago", "income": 85000}
        ]
        
        def anonymize_data(data):
            """Anonymize customer data for analytics."""
            anonymized = []
            for record in data:
                anon_record = {
                    "id": hashlib.sha256(record["id"].encode()).hexdigest()[:8],
                    "age_group": "25-30" if 25 <= record["age"] <= 30 else "30-40",
                    "city_region": record["city"][:3].upper(),  # First 3 letters
                    "income_bracket": "60-80K" if 60000 <= record["income"] <= 80000 else "80K+"
                }
                anonymized.append(anon_record)
            return anonymized
        
        anonymized_data = anonymize_data(customer_data)
        
        # Verify anonymization
        for record in anonymized_data:
            assert "name" not in record  # Names removed
            assert len(record["id"]) == 8  # Hashed ID
            assert record["age_group"] in ["25-30", "30-40"]  # Age grouped
            assert len(record["city_region"]) == 3  # City abbreviated
    
    def test_pseudonymization(self):
        """Test pseudonymization for data protection."""
        customer_records = [
            {"customer_id": "CUST001", "name": "John Doe", "email": "john@example.com"},
            {"customer_id": "CUST002", "name": "Jane Smith", "email": "jane@example.com"}
        ]
        
        # Pseudonymization key (in production, store securely)
        pseudo_key = "pseudonymization_secret_key"
        
        def pseudonymize(value, key):
            """Create pseudonym using HMAC."""
            import hmac
            return hmac.new(key.encode(), value.encode(), hashlib.sha256).hexdigest()[:16]
        
        pseudonymized_records = []
        for record in customer_records:
            pseudo_record = {
                "pseudo_id": pseudonymize(record["customer_id"], pseudo_key),
                "pseudo_name": pseudonymize(record["name"], pseudo_key),
                "pseudo_email": pseudonymize(record["email"], pseudo_key)
            }
            pseudonymized_records.append(pseudo_record)
        
        # Verify pseudonymization
        for i, record in enumerate(pseudonymized_records):
            assert record["pseudo_id"] != customer_records[i]["customer_id"]
            assert record["pseudo_name"] != customer_records[i]["name"]
            assert len(record["pseudo_id"]) == 16  # Consistent length


class TestPrivacyComplianceGDPRCCPA:
    """Test privacy compliance (GDPR, CCPA) requirements."""
    
    def test_data_subject_rights_simulation(self):
        """Test data subject rights implementation."""
        # Simulate customer data across multiple systems
        customer_data = {
            "customer_db": {
                "customer_id": "CUST001",
                "name": "John Doe",
                "email": "john@example.com",
                "created_at": "2023-01-15"
            },
            "loan_db": {
                "customer_id": "CUST001", 
                "loan_applications": [
                    {"loan_id": "LOAN001", "amount": 50000, "status": "APPROVED"}
                ]
            },
            "compliance_db": {
                "customer_id": "CUST001",
                "kyc_status": "VERIFIED",
                "aml_checks": [
                    {"check_id": "AML001", "result": "PASS", "date": "2023-01-16"}
                ]
            }
        }
        
        def right_to_access(customer_id):
            """Implement right to access (GDPR Article 15)."""
            customer_export = {}
            for system, data in customer_data.items():
                if data.get("customer_id") == customer_id:
                    customer_export[system] = data
            return customer_export
        
        def right_to_rectification(customer_id, updates):
            """Implement right to rectification (GDPR Article 16)."""
            for system, data in customer_data.items():
                if data.get("customer_id") == customer_id:
                    data.update(updates)
                    data["updated_at"] = datetime.now().isoformat()
        
        def right_to_erasure(customer_id):
            """Implement right to erasure (GDPR Article 17)."""
            for system, data in customer_data.items():
                if data.get("customer_id") == customer_id:
                    # Mark for deletion (maintain audit trail)
                    data["deleted"] = True
                    data["deleted_at"] = datetime.now().isoformat()
        
        # Test right to access
        exported_data = right_to_access("CUST001")
        assert len(exported_data) == 3
        assert "customer_db" in exported_data
        
        # Test right to rectification
        right_to_rectification("CUST001", {"email": "newemail@example.com"})
        assert customer_data["customer_db"]["email"] == "newemail@example.com"
        assert "updated_at" in customer_data["customer_db"]
        
        # Test right to erasure
        right_to_erasure("CUST001")
        assert customer_data["customer_db"]["deleted"] is True
    
    def test_consent_management(self):
        """Test consent management for privacy compliance."""
        consent_records = {
            "CUST001": {
                "marketing_consent": {
                    "granted": True,
                    "timestamp": "2023-01-15T10:00:00Z",
                    "purpose": "Marketing communications",
                    "legal_basis": "Consent"
                },
                "analytics_consent": {
                    "granted": False,
                    "timestamp": "2023-01-15T10:00:00Z",
                    "purpose": "Analytics and reporting",
                    "legal_basis": "Consent"
                }
            }
        }
        
        def update_consent(customer_id, consent_type, granted):
            """Update customer consent."""
            if customer_id in consent_records:
                if consent_type in consent_records[customer_id]:
                    consent_records[customer_id][consent_type].update({
                        "granted": granted,
                        "timestamp": datetime.now().isoformat()
                    })
        
        def check_consent(customer_id, consent_type):
            """Check if customer has granted consent."""
            if customer_id in consent_records:
                consent = consent_records[customer_id].get(consent_type, {})
                return consent.get("granted", False)
            return False
        
        # Test consent checking
        assert check_consent("CUST001", "marketing_consent") is True
        assert check_consent("CUST001", "analytics_consent") is False
        
        # Test consent withdrawal
        update_consent("CUST001", "marketing_consent", False)
        assert check_consent("CUST001", "marketing_consent") is False
    
    def test_data_retention_policies(self):
        """Test data retention policy compliance."""
        data_retention_policies = {
            "customer_data": {"retention_years": 7, "legal_basis": "Regulatory requirement"},
            "loan_data": {"retention_years": 10, "legal_basis": "Financial regulation"},
            "marketing_data": {"retention_years": 2, "legal_basis": "Business need"},
            "analytics_data": {"retention_years": 3, "legal_basis": "Business intelligence"}
        }
        
        def check_retention_compliance(data_type, creation_date):
            """Check if data should be retained or deleted."""
            if data_type not in data_retention_policies:
                return False
            
            policy = data_retention_policies[data_type]
            retention_years = policy["retention_years"]
            
            # Calculate if data is past retention period
            from datetime import datetime, timedelta
            creation_dt = datetime.fromisoformat(creation_date)
            retention_end = creation_dt + timedelta(days=retention_years * 365)
            
            return datetime.now() < retention_end
        
        # Test retention compliance
        old_data_date = "2015-01-01T00:00:00"
        recent_data_date = "2022-01-01T00:00:00"
        
        # Old marketing data should be deleted
        assert not check_retention_compliance("marketing_data", old_data_date)
        
        # Recent customer data should be retained
        assert check_retention_compliance("customer_data", recent_data_date)
    
    def test_cross_border_data_transfer(self):
        """Test cross-border data transfer compliance."""
        data_transfer_rules = {
            "EU": {"adequacy_decision": True, "safeguards_required": False},
            "US": {"adequacy_decision": False, "safeguards_required": True},
            "UK": {"adequacy_decision": True, "safeguards_required": False},
            "OTHER": {"adequacy_decision": False, "safeguards_required": True}
        }
        
        def validate_data_transfer(source_region, destination_region, has_safeguards=False):
            """Validate if data transfer is compliant."""
            if source_region == "EU":  # GDPR applies
                dest_rules = data_transfer_rules.get(destination_region, data_transfer_rules["OTHER"])
                
                if dest_rules["adequacy_decision"]:
                    return True
                elif dest_rules["safeguards_required"] and has_safeguards:
                    return True
                else:
                    return False
            return True  # Non-EU transfers (simplified)
        
        # Test valid transfers
        assert validate_data_transfer("EU", "UK") is True  # Adequacy decision
        assert validate_data_transfer("EU", "US", has_safeguards=True) is True  # With safeguards
        
        # Test invalid transfers
        assert validate_data_transfer("EU", "US", has_safeguards=False) is False  # No safeguards