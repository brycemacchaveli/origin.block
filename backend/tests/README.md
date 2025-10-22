# Backend Tests

This directory contains comprehensive tests for the backend API services, organized by test type and domain.

## Test Structure

The test suite is organized by test category for better maintainability and execution control:

```
tests/
├── conftest.py                    # Global test configuration and shared fixtures
├── unit/                          # Unit tests for individual components
│   ├── __init__.py
│   ├── run_unit_tests.py         # CLI runner for unit tests
│   ├── test_main.py              # Main application unit tests
│   └── shared/                   # Shared utilities unit tests
│       ├── __init__.py
│       ├── conftest.py           # Shared infrastructure fixtures
│       ├── test_fixtures.py      # Common test fixtures
│       ├── test_auth.py          # Authentication tests
│       ├── test_database.py      # Database tests
│       └── test_fabric_gateway.py # Blockchain gateway tests
├── api/                          # API endpoint tests by domain
│   ├── __init__.py
│   ├── run_api_tests.py          # CLI runner for API tests
│   ├── customer_mastery/         # Customer domain API tests
│   │   ├── __init__.py
│   │   ├── conftest.py           # Customer-specific fixtures
│   │   └── test_customer_api.py  # Customer API tests
│   ├── loan_origination/         # Loan domain API tests
│   │   ├── __init__.py
│   │   ├── conftest.py           # Loan-specific fixtures
│   │   ├── test_loan_api.py      # Loan API tests
│   │   ├── test_loan_documents.py # Document management tests
│   │   └── test_loan_history.py  # Loan history tests
│   └── compliance_reporting/     # Compliance domain API tests
│       ├── __init__.py
│       ├── conftest.py           # Compliance-specific fixtures
│       └── test_compliance_api.py # Compliance API tests
├── integration/                  # Cross-domain integration tests
│   ├── __init__.py
│   ├── conftest.py               # Integration test fixtures
│   ├── run_integration_tests.py  # CLI runner for integration tests
│   ├── test_runner.py            # Integration test orchestration
│   ├── mock_infrastructure.py    # Mock infrastructure utilities
│   ├── test_main.py              # Main application integration tests
│   ├── test_customer_mastery_lifecycle.py
│   ├── test_loan_origination_workflow.py
│   ├── test_compliance_rule_enforcement.py
│   ├── test_cross_domain_integration.py
│   ├── test_data_utilities.py
│   └── test_document_integration.py
├── performance/                  # Performance and load tests
│   ├── __init__.py
│   ├── run_performance_tests.py  # CLI runner for performance tests
│   ├── benchmark_runner.py       # Benchmark orchestration
│   ├── test_api_load.py          # API load tests
│   ├── test_blockchain_throughput.py
│   ├── test_database_performance.py
│   ├── test_simple_performance.py
│   ├── test_stress_scenarios.py
│   ├── locust_load_tests.py      # Locust load testing
│   └── README.md                 # Performance testing documentation
├── security/                     # Security tests
│   ├── __init__.py
│   ├── conftest.py               # Security test fixtures
│   ├── run_security_tests.py     # CLI runner for security tests
│   ├── test_authentication_security.py
│   ├── test_data_encryption_privacy.py
│   ├── test_audit_trail_immutability.py
│   ├── test_regulatory_compliance_validation.py
│   ├── test_vulnerability_scanning.py
│   ├── test_security_suite.py
│   └── README.md                 # Security testing documentation
├── etl/                          # ETL service tests
│   ├── __init__.py
│   ├── run_etl_tests.py          # CLI runner for ETL tests
│   ├── analytics/                # Analytics tests
│   ├── orchestration/            # Orchestration tests
│   ├── test_base_transformer.py
│   ├── test_customer_transformer.py
│   ├── test_loan_events_transformer.py
│   └── test_compliance_events_transformer.py
└── event_listener/               # Event listener service tests
    ├── __init__.py
    ├── conftest.py               # Event listener fixtures
    ├── run_event_listener_tests.py # CLI runner for event listener tests
    ├── test_consistency_checker.py
    ├── test_database_sync.py
    ├── test_error_handling.py
    └── test_event_subscription.py
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

### Test Category Execution

```bash
# Run unit tests
pytest tests/unit/
# Or use the CLI runner
python tests/unit/run_unit_tests.py

# Run API tests
pytest tests/api/
# Or use the CLI runner
python tests/api/run_api_tests.py --type all

# Run integration tests
pytest tests/integration/
# Or use the CLI runner
python tests/integration/run_integration_tests.py --type all

# Run performance tests
pytest tests/performance/
# Or use the CLI runner
python tests/performance/run_performance_tests.py --config standard

# Run security tests
pytest tests/security/
# Or use the CLI runner
python tests/security/run_security_tests.py --type all

# Run ETL tests
pytest tests/etl/
# Or use the CLI runner
python tests/etl/run_etl_tests.py --type all

# Run event listener tests
pytest tests/event_listener/
# Or use the CLI runner
python tests/event_listener/run_event_listener_tests.py --type all
```

### Domain-Specific API Tests

```bash
# Run customer mastery API tests
pytest tests/api/customer_mastery/
python tests/api/run_api_tests.py --type customer

# Run loan origination API tests
pytest tests/api/loan_origination/
python tests/api/run_api_tests.py --type loan

# Run compliance API tests
pytest tests/api/compliance_reporting/
python tests/api/run_api_tests.py --type compliance
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
pytest tests/api/customer_mastery/test_customer_api.py

# Run specific test class
pytest tests/api/loan_origination/test_loan_api.py::TestLoanApplicationCreation

# Run specific test method
pytest tests/unit/shared/test_auth.py::TestJWTManager::test_create_access_token
```

## CLI Test Runners

Each test category has a dedicated CLI runner for enhanced control:

### Unit Tests
```bash
python tests/unit/run_unit_tests.py --type all
python tests/unit/run_unit_tests.py --type shared --markers "not slow"
python tests/unit/run_unit_tests.py --type main --output results.xml
```

### API Tests
```bash
python tests/api/run_api_tests.py --type all
python tests/api/run_api_tests.py --type customer --markers "not slow"
python tests/api/run_api_tests.py --type loan --output results.xml
```

### Integration Tests
```bash
python tests/integration/run_integration_tests.py --type all
python tests/integration/run_integration_tests.py --type workflow --report
python tests/integration/run_integration_tests.py --type cross_domain --output results.xml
```

### Performance Tests
```bash
python tests/performance/run_performance_tests.py --config standard
python tests/performance/run_performance_tests.py --config quick
python tests/performance/run_performance_tests.py --config comprehensive --locust
```

### Security Tests
```bash
python tests/security/run_security_tests.py --type all
python tests/security/run_security_tests.py --type auth
python tests/security/run_security_tests.py --type suite --output results.xml
```

### ETL Tests
```bash
python tests/etl/run_etl_tests.py --type all
python tests/etl/run_etl_tests.py --type transformers
python tests/etl/run_etl_tests.py --type analytics --output results.xml
```

### Event Listener Tests
```bash
python tests/event_listener/run_event_listener_tests.py --type all
python tests/event_listener/run_event_listener_tests.py --type consistency
python tests/event_listener/run_event_listener_tests.py --type sync --output results.xml
```

## Test Categories

### Unit Tests
- Test individual functions and classes in isolation
- Mock external dependencies
- Fast execution
- Located in `unit/` directory

### API Tests
- Test API endpoints by domain
- Test request/response validation
- Test error handling
- Located in `api/` directory with subdirectories per domain:
  - `customer_mastery/`: Customer CRUD, KYC/AML, consent management
  - `loan_origination/`: Loan applications, approvals, document management
  - `compliance_reporting/`: Regulatory reporting, audit trails

### Integration Tests
- Test API endpoints and cross-service interactions
- Test database operations with real database connections
- Test complete workflows
- Located in `integration/` directory

### Performance Tests
- Load testing for API endpoints
- Blockchain throughput testing
- Database performance testing
- Stress testing scenarios
- Located in `performance/` directory

### Security Tests
- Authentication and authorization testing
- Data encryption and privacy validation
- Audit trail immutability verification
- Regulatory compliance validation
- Vulnerability scanning
- Located in `security/` directory

### ETL Tests
- Data transformation testing
- Analytics pipeline testing
- Orchestration workflow testing
- Located in `etl/` directory

### Event Listener Tests
- Blockchain event processing
- Database synchronization
- Consistency checking
- Error handling
- Located in `event_listener/` directory

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
- Organize tests by category (unit, api, integration, etc.)

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

### For New Unit Tests
1. Add tests to `tests/unit/` or `tests/unit/shared/`
2. Use existing shared fixtures when possible
3. Add appropriate markers
4. Update CLI runner if needed

### For New API Tests
1. Add tests to the appropriate domain directory under `tests/api/`
2. Create domain-specific fixtures if needed
3. Use existing shared fixtures when possible
4. Add appropriate markers
5. Update CLI runner if needed

### For New Integration Tests
1. Add to `tests/integration/` directory
2. Use cross-domain fixtures
3. Test complete user workflows
4. Verify end-to-end functionality

### For New Performance Tests
1. Add to `tests/performance/` directory
2. Follow existing performance test patterns
3. Configure appropriate load parameters
4. Update performance test runner if needed

### For New Security Tests
1. Add to `tests/security/` directory
2. Follow security testing best practices
3. Add appropriate markers
4. Update security test runner if needed

## Continuous Integration

The test suite is designed to run efficiently in CI environments:
- Parallel execution support
- Proper test isolation
- Minimal external dependencies
- Clear failure reporting
- Organized by test category for selective execution

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

# Run specific test category with verbose output
python tests/unit/run_unit_tests.py --type all -v
python tests/api/run_api_tests.py --type customer -v
```

## Test Execution Order

For comprehensive testing, run tests in this order:

1. **Unit Tests**: Fast, isolated component tests
2. **API Tests**: Domain-specific endpoint tests
3. **Integration Tests**: Cross-domain workflow tests
4. **Security Tests**: Security validation
5. **Performance Tests**: Load and stress testing
6. **ETL Tests**: Data pipeline tests
7. **Event Listener Tests**: Event processing tests

```bash
# Run all test categories in order
pytest tests/unit/ && \
pytest tests/api/ && \
pytest tests/integration/ && \
pytest tests/security/ && \
pytest tests/performance/ && \
pytest tests/etl/ && \
pytest tests/event_listener/
```
