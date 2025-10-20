# Performance Testing Suite

This directory contains comprehensive performance and load testing tools for the Blockchain Financial Platform. The testing suite covers API endpoints, blockchain transaction throughput, database performance, and system stress scenarios.

## Overview

The performance testing suite includes:

- **API Load Testing**: Tests API endpoints under concurrent load
- **Blockchain Throughput Testing**: Tests blockchain transaction processing performance
- **Database Performance Testing**: Tests database operations under various loads
- **Stress Testing**: Tests system behavior under extreme conditions
- **Benchmarking Tools**: Comprehensive performance benchmarking and reporting
- **Locust Load Testing**: Advanced load testing with realistic user behavior simulation

## Test Files

### Core Test Files

- `test_api_load.py` - API endpoint load testing
- `test_blockchain_throughput.py` - Blockchain transaction throughput testing
- `test_database_performance.py` - Database performance testing under load
- `test_stress_scenarios.py` - System stress testing and failure scenarios
- `benchmark_runner.py` - Comprehensive benchmarking and reporting tools
- `locust_load_tests.py` - Locust-based advanced load testing
- `run_performance_tests.py` - Unified test runner and configuration

### Supporting Files

- `README.md` - This documentation file
- `performance_results/` - Directory for test results and reports (created automatically)

## Quick Start

### Prerequisites

Install required dependencies:

```bash
cd backend
pip install -r requirements.txt
```

For Locust testing, ensure Locust is installed:

```bash
pip install locust
```

### Running Tests

#### 1. Quick Performance Validation

Run a quick performance test to validate system performance:

```bash
cd backend
python tests/performance/run_performance_tests.py --config quick
```

#### 2. Standard Performance Testing

Run the standard performance test suite:

```bash
python tests/performance/run_performance_tests.py --config standard
```

#### 3. Comprehensive Performance Testing

Run comprehensive performance tests (takes longer):

```bash
python tests/performance/run_performance_tests.py --config comprehensive
```

#### 4. Stress Testing

Run stress tests to test system limits:

```bash
python tests/performance/run_performance_tests.py --config stress
```

#### 5. Individual Test Categories

Run specific test categories:

```bash
# API load tests only
pytest tests/performance/test_api_load.py -v

# Blockchain throughput tests only
pytest tests/performance/test_blockchain_throughput.py -v

# Database performance tests only
pytest tests/performance/test_database_performance.py -v

# Stress tests only
pytest tests/performance/test_stress_scenarios.py -v

# Benchmark suite
pytest tests/performance/benchmark_runner.py::TestPerformanceBenchmarks::test_run_full_benchmark_suite -v
```

#### 6. Locust Load Testing

Run Locust load tests for advanced scenarios:

```bash
# Interactive mode (opens web UI)
locust -f tests/performance/locust_load_tests.py --host=http://localhost:8000

# Headless mode
locust -f tests/performance/locust_load_tests.py --host=http://localhost:8000 --users 50 --spawn-rate 5 --run-time 300s --headless

# Via test runner
python tests/performance/run_performance_tests.py --config standard --locust --users 100 --run-time 600s
```

## Test Configurations

The test runner supports multiple configurations:

### Quick Configuration
- **Purpose**: Fast validation during development
- **API Load**: 25 requests, 5 workers
- **Blockchain**: 15 operations, 3 workers
- **Database**: 30 operations, 6 workers
- **Stress**: 20 seconds, 8 workers

### Standard Configuration (Default)
- **Purpose**: Regular performance testing
- **API Load**: 100 requests, 10 workers
- **Blockchain**: 50 operations, 8 workers
- **Database**: 80 operations, 12 workers
- **Stress**: 60 seconds, 15 workers

### Comprehensive Configuration
- **Purpose**: Thorough performance analysis
- **API Load**: 200 requests, 20 workers
- **Blockchain**: 100 operations, 15 workers
- **Database**: 150 operations, 20 workers
- **Stress**: 120 seconds, 25 workers

### Stress Configuration
- **Purpose**: System limit testing
- **API Load**: 500 requests, 50 workers
- **Blockchain**: 200 operations, 30 workers
- **Database**: 300 operations, 40 workers
- **Stress**: 300 seconds, 50 workers

## Test Categories

### 1. API Load Testing (`test_api_load.py`)

Tests API endpoints under concurrent load:

- **Customer Creation Load**: Tests customer creation endpoint performance
- **Loan Application Load**: Tests loan application submission performance
- **Mixed Workload**: Tests realistic mixed read/write operations
- **Stress Testing**: Tests API behavior under extreme load
- **Sustained Load**: Tests performance degradation over time

**Key Metrics**:
- Success rate (target: ≥95%)
- Throughput (requests per second)
- Response times (mean, median, 95th percentile)
- Error rates and types

### 2. Blockchain Throughput Testing (`test_blockchain_throughput.py`)

Tests blockchain transaction processing performance:

- **Customer Chaincode Throughput**: Tests customer-related blockchain operations
- **Loan Chaincode Throughput**: Tests loan-related blockchain operations
- **Compliance Chaincode Throughput**: Tests compliance-related blockchain operations
- **Mixed Chaincode Workload**: Tests realistic mixed blockchain operations

**Key Metrics**:
- Transaction throughput (TPS - Transactions Per Second)
- Chaincode execution time
- Event processing time
- Blockchain success rates

### 3. Database Performance Testing (`test_database_performance.py`)

Tests database operations under various loads:

- **Concurrent Read Performance**: Tests database read operations under load
- **Concurrent Write Performance**: Tests database write operations under load
- **Mixed Database Workload**: Tests realistic read/write mix
- **Large Dataset Performance**: Tests performance with large result sets
- **Connection Pool Performance**: Tests database connection management

**Key Metrics**:
- Operations per second
- Query execution times
- Memory and CPU usage
- Connection pool efficiency

### 4. Stress Testing (`test_stress_scenarios.py`)

Tests system behavior under extreme conditions:

- **Memory Exhaustion Scenario**: Tests behavior under memory pressure
- **High Concurrency Scenario**: Tests extreme concurrent load handling
- **Sustained Load Degradation**: Tests performance degradation over time
- **Rapid Failure Recovery**: Tests system recovery from failures

**Key Metrics**:
- System resource usage (memory, CPU)
- Failure points and recovery times
- Error rates under stress
- System stability metrics

### 5. Benchmarking (`benchmark_runner.py`)

Comprehensive benchmarking and reporting:

- **Baseline Comparison**: Compares current performance with historical baselines
- **Regression Detection**: Automatically detects performance regressions
- **Comprehensive Reporting**: Generates detailed HTML and CSV reports
- **Historical Tracking**: Tracks performance trends over time

**Features**:
- Automated baseline management
- Performance regression alerts
- Detailed HTML reports
- CSV data export
- Historical comparison

### 6. Locust Load Testing (`locust_load_tests.py`)

Advanced load testing with realistic user behavior:

- **Realistic User Simulation**: Simulates actual user behavior patterns
- **Multiple User Types**: Different user personas (regular users, compliance officers, high-volume users)
- **Distributed Testing**: Supports distributed load testing
- **Advanced Scenarios**: Complex user workflows and interactions

**User Types**:
- `BlockchainFinancialPlatformUser`: Standard user behavior
- `HighVolumeUser`: Aggressive usage patterns
- `ComplianceOfficerUser`: Compliance-focused workflows
- `StressTestUser`: Extreme load patterns

## Performance Targets

### API Performance Targets

| Metric | Target | Acceptable |
|--------|--------|------------|
| Success Rate | ≥95% | ≥90% |
| Mean Response Time | <2.0s | <3.0s |
| 95th Percentile | <5.0s | <8.0s |
| Throughput | ≥10 RPS | ≥5 RPS |

### Blockchain Performance Targets

| Metric | Target | Acceptable |
|--------|--------|------------|
| Transaction Throughput | ≥3 TPS | ≥2 TPS |
| Success Rate | ≥95% | ≥90% |
| Mean Transaction Time | <5.0s | <8.0s |
| 95th Percentile | <10.0s | <15.0s |

### Database Performance Targets

| Metric | Target | Acceptable |
|--------|--------|------------|
| Read Operations/sec | ≥50 | ≥30 |
| Write Operations/sec | ≥20 | ≥15 |
| Mean Query Time | <0.5s | <1.0s |
| 95th Percentile | <1.0s | <2.0s |

### System Resource Targets

| Metric | Target | Acceptable |
|--------|--------|------------|
| Memory Usage | <80% | <90% |
| CPU Usage | <70% | <85% |
| Error Rate | <5% | <10% |

## Reports and Results

### Automatic Report Generation

All test runs automatically generate comprehensive reports:

- **HTML Reports**: Detailed visual reports with charts and metrics
- **JSON Data**: Raw test data for further analysis
- **CSV Summaries**: Tabular data for spreadsheet analysis

### Report Locations

Reports are saved in the `performance_results/` directory:

```
performance_results/
├── performance_test_report_standard_20231201_143022.html
├── performance_test_report_standard_20231201_143022.json
├── performance_test_report_standard_20231201_143022.csv
├── locust_report_20231201_143500.html
└── baseline_results.json
```

### Baseline Management

The benchmarking system supports baseline management:

```bash
# Save current results as baseline
python -c "
from tests.performance.benchmark_runner import PerformanceBenchmarkRunner
from fastapi.testclient import TestClient
from main import app
runner = PerformanceBenchmarkRunner(TestClient(app))
# ... run tests ...
runner.save_baseline_results()
"

# Load and compare with baseline
# Automatic when running benchmark_runner.py tests
```

## Integration with CI/CD

### GitHub Actions Integration

Add to your GitHub Actions workflow:

```yaml
- name: Run Performance Tests
  run: |
    cd backend
    python tests/performance/run_performance_tests.py --config quick
    
- name: Upload Performance Reports
  uses: actions/upload-artifact@v3
  with:
    name: performance-reports
    path: backend/performance_results/
```

### Performance Regression Detection

The benchmark runner automatically detects performance regressions:

- **Throughput Decrease**: >10% decrease triggers regression alert
- **Success Rate Decrease**: >5% decrease triggers regression alert
- **Response Time Increase**: >20% increase in mean response time triggers alert
- **95th Percentile Increase**: >25% increase triggers alert

## Troubleshooting

### Common Issues

1. **Tests Timeout**
   - Increase timeout values in test configurations
   - Reduce load parameters for slower systems
   - Check system resources (memory, CPU)

2. **High Error Rates**
   - Verify application is running and accessible
   - Check database connectivity
   - Review application logs for errors

3. **Locust Not Found**
   - Install Locust: `pip install locust`
   - Ensure it's in your PATH

4. **Memory Issues**
   - Reduce concurrent workers
   - Use quick configuration for resource-constrained environments
   - Monitor system memory usage

### Performance Optimization Tips

1. **Database Optimization**
   - Ensure proper indexing
   - Optimize query performance
   - Configure connection pooling

2. **API Optimization**
   - Enable response caching where appropriate
   - Optimize serialization/deserialization
   - Use async operations for I/O bound tasks

3. **System Resources**
   - Monitor memory and CPU usage
   - Optimize garbage collection settings
   - Use appropriate worker/thread counts

## Advanced Usage

### Custom Test Scenarios

Create custom test scenarios by extending the base classes:

```python
from tests.performance.test_api_load import PerformanceTestRunner

class CustomPerformanceTest:
    def test_custom_scenario(self, performance_runner):
        def custom_operation(request_id):
            # Your custom test logic here
            pass
        
        stats = performance_runner.concurrent_requests(custom_operation, 100, 10)
        # Assert your performance requirements
```

### Custom Locust Users

Create custom Locust user behaviors:

```python
from tests.performance.locust_load_tests import BlockchainFinancialPlatformUser

class CustomUser(BlockchainFinancialPlatformUser):
    @task
    def custom_behavior(self):
        # Your custom user behavior
        pass
```

### Performance Monitoring Integration

Integrate with monitoring systems:

```python
# Example: Send metrics to monitoring system
def send_metrics_to_monitoring(results):
    for test_name, result in results.items():
        # Send to your monitoring system
        pass
```

## Contributing

When adding new performance tests:

1. Follow the existing patterns and naming conventions
2. Include appropriate assertions for performance targets
3. Add comprehensive documentation
4. Update this README with new test descriptions
5. Ensure tests are deterministic and repeatable

## Support

For issues or questions about performance testing:

1. Check the troubleshooting section above
2. Review test logs and error messages
3. Verify system requirements and dependencies
4. Check application logs for underlying issues