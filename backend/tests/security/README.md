# Security Testing Suite

This directory contains comprehensive security tests for the blockchain financial platform, covering authentication, authorization, data protection, audit trails, regulatory compliance, and vulnerability scanning.

## Test Categories

### 1. Authentication Security (`test_authentication_security.py`)
- **JWT Security Vulnerabilities**: Token tampering, algorithm confusion, secret key strength
- **Role-Based Access Control**: Privilege escalation prevention, permission validation
- **Session Management**: Concurrent sessions, session fixation, token leakage
- **Authentication Bypass**: Missing tokens, malformed tokens, brute force protection
- **Cryptographic Security**: Token entropy, timing attack resistance

### 2. Data Encryption & Privacy (`test_data_encryption_privacy.py`)
- **Data Encryption at Rest**: Sensitive data encryption, field-level encryption, key rotation
- **Data Encryption in Transit**: HTTPS enforcement, TLS configuration, payload encryption
- **PII Protection**: Data masking, anonymization, pseudonymization
- **Privacy Compliance**: GDPR/CCPA compliance, data subject rights, consent management

### 3. Audit Trail & Immutability (`test_audit_trail_immutability.py`)
- **Audit Trail Completeness**: Transaction coverage, actor traceability, entity lifecycle
- **Immutability Testing**: Hash chain integrity, tamper detection, digital signatures
- **Forensic Capabilities**: Transaction reconstruction, behavior analysis, data lineage

### 4. Regulatory Compliance (`test_regulatory_compliance_validation.py`)
- **AML/KYC Compliance**: Verification requirements, sanction screening, enhanced due diligence
- **Regulatory Reporting**: SAR generation, CTR compliance, capital adequacy reporting
- **Compliance Rule Enforcement**: Automated execution, versioning, exception handling

### 5. Vulnerability Scanning (`test_vulnerability_scanning.py`)
- **Injection Vulnerabilities**: SQL, NoSQL, command, LDAP injection prevention
- **Cross-Site Scripting (XSS)**: Reflected, stored, DOM-based XSS protection
- **CSRF Protection**: Token validation, SameSite cookies, referer validation
- **API Security**: Rate limiting, input validation, authentication bypass, IDOR

### 6. Security Suite Orchestration (`test_security_suite.py`)
- **Comprehensive Assessment**: Security scoring, compliance matrix, incident response
- **Security Metrics**: Monitoring capabilities, alerting, coverage analysis

## Running Security Tests

### Run All Security Tests
```bash
cd backend
python -m pytest tests/security/ -v
```

### Run Specific Test Categories
```bash
# Authentication security tests
python -m pytest tests/security/test_authentication_security.py -v

# Data encryption and privacy tests
python -m pytest tests/security/test_data_encryption_privacy.py -v

# Audit trail immutability tests
python -m pytest tests/security/test_audit_trail_immutability.py -v

# Regulatory compliance tests
python -m pytest tests/security/test_regulatory_compliance_validation.py -v

# Vulnerability scanning tests
python -m pytest tests/security/test_vulnerability_scanning.py -v

# Security suite orchestration
python -m pytest tests/security/test_security_suite.py -v
```

### Run Tests with Coverage
```bash
python -m pytest tests/security/ --cov=shared --cov-report=html
```

## Test Fixtures and Configuration

### Security Test Fixtures (`conftest.py`)
- **security_test_actors**: Pre-configured test actors with various roles and permissions
- **jwt_test_manager**: JWT manager for testing token operations
- **mock_blockchain_identity_mapper**: Blockchain identity mapping for testing
- **sample_encrypted_data**: Sample encrypted data for encryption tests
- **audit_trail_data**: Sample audit trail data for immutability tests
- **compliance_test_data**: Compliance rules and events for testing
- **vulnerability_test_payloads**: Malicious payloads for vulnerability testing

## Security Requirements Coverage

This test suite addresses the following security requirements from the specification:

### Requirement 4.1: Actor Management and Access Control
- ✅ Complete Actor registry with blockchain identity, role, and type information
- ✅ Granular access control based on authorization levels
- ✅ Role-based permission validation

### Requirement 4.2: Data Integrity and Traceability
- ✅ Immutable history with timestamp, actor identity, and transaction details
- ✅ Cryptographic hashes for document verification
- ✅ Referential integrity between entities

### Requirement 4.3: Data Security and Encryption
- ✅ Data encryption both in transit and at rest
- ✅ Appropriate encryption or hashing with proper access controls
- ✅ Predefined schema and validation rules

### Requirement 4.4: Audit Trail and Compliance
- ✅ Comprehensive, tamper-proof audit trail
- ✅ Independent verification of data integrity and accuracy
- ✅ Regulatory compliance validation

### Requirement 4.5: System Security and Availability
- ✅ 99.9% uptime availability testing
- ✅ Security vulnerability scanning
- ✅ Performance impact assessment of security measures

### Requirement 4.6: Regulatory and Legal Compliance
- ✅ Automated regulatory rule enforcement
- ✅ Real-time compliance monitoring
- ✅ Regulatory reporting accuracy validation

## Security Test Results Interpretation

### Test Status Indicators
- **PASSED**: Security control is working correctly
- **FAILED**: Security vulnerability or misconfiguration detected
- **SKIPPED**: Test requires dependencies not available in current environment

### Security Scoring
The security suite provides scoring based on:
- **Critical Issues**: Immediate security risks (score impact: -50 points)
- **High Issues**: Significant security concerns (score impact: -25 points)
- **Medium Issues**: Moderate security improvements needed (score impact: -10 points)
- **Low Issues**: Minor security enhancements (score impact: -5 points)

### Compliance Standards Coverage
- **OWASP Top 10**: Web application security risks
- **PCI DSS**: Payment card industry data security
- **SOC 2 Type 2**: Security, availability, processing integrity, confidentiality, privacy
- **GDPR/CCPA**: Data privacy and protection regulations

## Security Testing Best Practices

### 1. Regular Execution
- Run security tests as part of CI/CD pipeline
- Execute comprehensive security assessment monthly
- Perform targeted security tests after security-related code changes

### 2. Test Data Management
- Use synthetic test data for security testing
- Avoid using production data in security tests
- Regularly update test payloads with new attack vectors

### 3. Vulnerability Management
- Document all security test failures
- Prioritize fixes based on risk assessment
- Verify fixes with targeted security tests

### 4. Compliance Monitoring
- Track compliance scores over time
- Generate regular compliance reports
- Update tests when regulations change

## Dependencies

### Required Python Packages
```
pytest>=7.4.3
pytest-asyncio>=0.21.1
pytest-mock>=3.12.0
cryptography>=41.0.0
python-jose[cryptography]>=3.3.0
```

### Optional Dependencies
- `coverage`: For test coverage reporting
- `pytest-html`: For HTML test reports
- `pytest-benchmark`: For performance testing

## Security Test Maintenance

### Adding New Security Tests
1. Identify security requirement or vulnerability
2. Create test case in appropriate test module
3. Add necessary fixtures to `conftest.py`
4. Update this README with test description
5. Verify test passes and fails appropriately

### Updating Existing Tests
1. Review test effectiveness regularly
2. Update test payloads with new attack vectors
3. Adjust test assertions based on security improvements
4. Maintain backward compatibility where possible

### Test Environment Security
- Isolate security testing environment
- Use dedicated test credentials and keys
- Monitor test execution for security events
- Clean up test artifacts after execution

## Troubleshooting

### Common Issues
1. **Cryptography Import Errors**: Install `cryptography` package
2. **JWT Token Failures**: Check system clock synchronization
3. **Permission Errors**: Verify test actor permissions are correctly configured
4. **Timeout Issues**: Increase test timeouts for complex security operations

### Debug Mode
```bash
# Run with verbose output and no capture
python -m pytest tests/security/ -v -s --tb=long

# Run specific failing test with debug
python -m pytest tests/security/test_authentication_security.py::TestJWTSecurityVulnerabilities::test_jwt_token_expiration_enforcement -v -s --pdb
```

## Security Contact

For security-related questions or to report security vulnerabilities found during testing:
- Review security test failures carefully
- Document security issues with detailed reproduction steps
- Follow responsible disclosure practices
- Update security tests to prevent regression