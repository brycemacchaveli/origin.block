# Backend Tests

This directory contains comprehensive tests for the backend API services, organized by domain and service type.

## Test Structure

The test suite is organized following the domain-driven architecture:

```
tests/
├── conftest.py                    # Global test configuration and shared fixtures
├── customer_mastery/              # Customer domain tests
│   ├── conftest.py               # Customer-specific fixtures
│   └── test_customer_api.py      # Customer API tests
├── loan_origination/             # Loan domain tests
│   ├── conftest.py               # Loan-specific fixtures
│   ├── test_loan_api.py          # Loan API tests
│   ├── test_loan_documents.py    # Document management tests
│   └── test_loan_history.py      # Loan history tests
├── compliance_reporting/         # Compliance domain tests
│   └── conftest.py               # Compliance-specific fixtures
├── event_listener/               # Event listener service tests
│   └── conftest.py               # Event listener fixtures
├── shared/                       # Shared utilities tests
│   ├── conftest.py               # Shared infrastructure fixtures
│   ├── test_fixtures.py          # Common test fixtures
│   ├── test_auth.py              # Authentication tests
│   ├── test_database.py          # Database tests
│   └── test_fabric_gateway.py    # Blockchain gateway tests
└── integration/                  # Cross-domain integration tests
    ├── conftest.py               # Integration test fixtures
    ├── test_main.py              # Main application tests
    └── test_document_integration.py # Document integration tests
```

## Running Tests

### Basic Test Execution

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=. --cov-report=html

# Run tests with verbose output
pytest -v
```

### Domain-Specific Tests

```bash
# Run customer mastery tests
pytest tests/customer_mastery/

# Run loan origination tests
pytest tests/loan_origination/

# Run compliance tests
pytest tests/compliance_reporting/

# Run shared utility tests
pytest tests/shared/

# Run integration tests
pytest tests/integration/
```

### Test Categories by Markers

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run tests for specific domain
pytest -m customer_mastery
pytest -m loan_origination

# Exclude slow tests
pytest -m "not slow"

# Run database-related tests
pytest -m database

# Run blockchain-related tests
pytest -m blockchain
```

### Specific Test Files

```bash
# Run specific test file
pytest tests/customer_mastery/test_customer_api.py

# Run specific test class
pytest tests/loan_origination/test_loan_api.py::TestLoanApplicationCreation

# Run specific test method
pytest tests/shared/test_auth.py::TestJWTManager::test_create_access_token
```

## Test Categories

### Unit Tests
- Test individual functions and classes in isolation
- Mock external dependencies
- Fast execution
- Located in domain-specific directories

### Integration Tests
- Test API endpoints and cross-service interactions
- Test database operations with real database connections
- Test complete workflows
- Located in `integration/` directory

### Domain Tests
- **Customer Mastery**: Customer CRUD, KYC/AML, consent management
- **Loan Origination**: Loan applications, approvals, document management
- **Compliance Reporting**: Regulatory reporting, audit trails
- **Event Listener**: Blockchain event processing
- **Shared**: Authentication, database, blockchain gateway

## Fixtures and Mocking

### Global Fixtures (conftest.py)
- `test_client`: FastAPI test client
- Actor fixtures for different roles (underwriter, credit officer, etc.)
- Authentication header fixtures
- Sample data fixtures
- Database utilities

### Domain-Specific Fixtures
Each domain has its own `conftest.py` with specialized fixtures:
- Domain-specific mock objects
- Sample data relevant to the domain
- Mock external services

### Automatic Mocking
- External blockchain calls are automatically mocked
- Database operations can use real or mocked databases
- External API calls are mocked by default

## Test Data Management

### Sample Data
Consistent sample data is provided through fixtures:
- `sample_customer_data`: Standard customer information
- `sample_loan_data`: Standard loan application data
- `sample_compliance_event_data`: Compliance event data

### Database Testing
- Tests can use temporary SQLite databases
- Database utilities provide helper methods
- Automatic cleanup after tests

### Authentication Testing
- Pre-configured actors with different permission sets
- JWT token generation for authenticated requests
- Role-based access control testing

## Best Practices

### Test Organization
- Group related tests in classes
- Use descriptive test names
- Follow AAA pattern (Arrange, Act, Assert)

### Mocking Strategy
- Mock external dependencies at the boundary
- Use real objects for internal logic when possible
- Verify mock interactions when relevant

### Fixtures Usage
- Use appropriate fixture scope (function, class, module, session)
- Prefer composition over inheritance for test setup
- Keep fixtures focused and single-purpose

### Performance
- Mark slow tests with `@pytest.mark.slow`
- Use appropriate database strategies (in-memory vs file)
- Minimize test interdependencies

## Adding New Tests

### For New Domain Features
1. Add tests to the appropriate domain directory
2. Create domain-specific fixtures if needed
3. Use existing shared fixtures when possible
4. Add appropriate markers

### For New Domains
1. Create new domain directory under `tests/`
2. Add domain-specific `conftest.py`
3. Update global `conftest.py` with new markers
4. Update this README

### For Integration Tests
1. Add to `integration/` directory
2. Use cross-domain fixtures
3. Test complete user workflows
4. Verify end-to-end functionality

## Continuous Integration

The test suite is designed to run efficiently in CI environments:
- Parallel execution support
- Proper test isolation
- Minimal external dependencies
- Clear failure reporting

## Troubleshooting

### Common Issues
- **Import errors**: Check PYTHONPATH and module structure
- **Database errors**: Ensure proper cleanup and isolation
- **Authentication errors**: Verify JWT configuration and actor setup
- **Async errors**: Check event loop configuration

### Debug Mode
```bash
# Run with debug output
pytest -s --log-cli-level=DEBUG

# Run single test with full output
pytest -s -vv tests/path/to/test.py::test_name
```