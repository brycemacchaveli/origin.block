# Test Directory Quick Reference

## Directory Structure

```
tests/
├── unit/              # Unit tests for individual components
├── api/               # API endpoint tests by domain
├── integration/       # Cross-domain integration tests
├── performance/       # Performance and load tests
├── security/          # Security tests
├── etl/              # ETL service tests
└── event_listener/   # Event listener tests
```

## Quick Commands

### Run All Tests
```bash
pytest
```

### Run by Category
```bash
# Unit tests
pytest tests/unit/
python tests/unit/run_unit_tests.py

# API tests (all domains)
pytest tests/api/
python tests/api/run_api_tests.py --type all

# API tests (specific domain)
python tests/api/run_api_tests.py --type customer
python tests/api/run_api_tests.py --type loan
python tests/api/run_api_tests.py --type compliance

# Integration tests
pytest tests/integration/
python tests/integration/run_integration_tests.py --type all

# Performance tests
pytest tests/performance/
python tests/performance/run_performance_tests.py --config standard

# Security tests
pytest tests/security/
python tests/security/run_security_tests.py --type all

# ETL tests
pytest tests/etl/
python tests/etl/run_etl_tests.py --type all

# Event listener tests
pytest tests/event_listener/
python tests/event_listener/run_event_listener_tests.py --type all
```

### Run with Markers
```bash
# Exclude slow tests
pytest -m "not slow"

# Run only integration tests
pytest -m integration

# Run only unit tests
pytest -m unit

# Run specific domain tests
pytest -m customer_mastery
pytest -m loan_origination
pytest -m compliance_reporting
```

### CLI Runner Options

All CLI runners support these flags:
- `--type <type>` - Select test type/category
- `--markers <markers>` - Filter by pytest markers
- `--output <file>` - Save results to JUnit XML
- `--quiet` or `-q` - Minimal output

### Examples
```bash
# Run customer API tests without slow tests
python tests/api/run_api_tests.py --type customer --markers "not slow"

# Run integration tests with report
python tests/integration/run_integration_tests.py --type workflow --report

# Run security tests with XML output
python tests/security/run_security_tests.py --type all --output results.xml

# Run performance tests (quick mode)
python tests/performance/run_performance_tests.py --config quick
```

## Test Locations

### Unit Tests
- Main app: `tests/unit/test_main.py`
- Auth: `tests/unit/shared/test_auth.py`
- Database: `tests/unit/shared/test_database.py`
- Fabric Gateway: `tests/unit/shared/test_fabric_gateway.py`

### API Tests
- Customer: `tests/api/customer_mastery/test_customer_api.py`
- Loan: `tests/api/loan_origination/test_loan_api.py`
- Loan Documents: `tests/api/loan_origination/test_loan_documents.py`
- Loan History: `tests/api/loan_origination/test_loan_history.py`
- Compliance: `tests/api/compliance_reporting/test_compliance_api.py`

### Integration Tests
- Customer Lifecycle: `tests/integration/test_customer_mastery_lifecycle.py`
- Loan Workflow: `tests/integration/test_loan_origination_workflow.py`
- Compliance Rules: `tests/integration/test_compliance_rule_enforcement.py`
- Cross-Domain: `tests/integration/test_cross_domain_integration.py`

### Performance Tests
- API Load: `tests/performance/test_api_load.py`
- Blockchain: `tests/performance/test_blockchain_throughput.py`
- Database: `tests/performance/test_database_performance.py`
- Stress: `tests/performance/test_stress_scenarios.py`

### Security Tests
- Authentication: `tests/security/test_authentication_security.py`
- Encryption: `tests/security/test_data_encryption_privacy.py`
- Audit Trail: `tests/security/test_audit_trail_immutability.py`
- Compliance: `tests/security/test_regulatory_compliance_validation.py`

## Common Workflows

### Development Testing
```bash
# Quick unit tests during development
pytest tests/unit/ -v

# Test specific API endpoint
pytest tests/api/customer_mastery/test_customer_api.py::TestCustomerCreation -v
```

### Pre-Commit Testing
```bash
# Run unit and API tests
pytest tests/unit/ tests/api/ -m "not slow"
```

### CI/CD Pipeline
```bash
# Stage 1: Fast tests
pytest tests/unit/ -m "not slow"

# Stage 2: API tests
pytest tests/api/

# Stage 3: Integration tests
pytest tests/integration/

# Stage 4: Security tests
pytest tests/security/

# Stage 5: Performance tests (optional)
python tests/performance/run_performance_tests.py --config quick
```

### Full Test Suite
```bash
# Run everything in order
pytest tests/unit/ && \
pytest tests/api/ && \
pytest tests/integration/ && \
pytest tests/security/ && \
pytest tests/etl/ && \
pytest tests/event_listener/
```

## Troubleshooting

### Import Errors
```bash
# Check PYTHONPATH
echo $PYTHONPATH

# Run from backend directory
cd backend
pytest tests/unit/
```

### Marker Errors
```bash
# List available markers
pytest --markers

# Run without strict markers
pytest tests/unit/ --strict-markers=false
```

### Debug Mode
```bash
# Verbose output with logs
pytest -s -vv --log-cli-level=DEBUG tests/unit/test_main.py

# Single test with full output
pytest -s -vv tests/api/customer_mastery/test_customer_api.py::TestCustomerCreation::test_create_customer_success
```
