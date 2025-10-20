"""
Performance benchmarking and reporting tools.

Provides comprehensive performance testing suite with detailed reporting,
historical comparison, and automated performance regression detection.
"""

import pytest
import time
import json
import statistics
import csv
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
from dataclasses import dataclass, asdict
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi.testclient import TestClient
from main import app
from tests.integration.mock_infrastructure import IntegrationTestMockManager


@dataclass
class BenchmarkResult:
    """Data class for benchmark results."""
    test_name: str
    timestamp: datetime
    duration: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate: float
    throughput: float
    response_times: Dict[str, float]
    system_metrics: Dict[str, float]
    error_details: List[str]
    test_parameters: Dict[str, Any]


class PerformanceBenchmarkRunner:
    """Comprehensive performance benchmarking and reporting system."""
    
    def __init__(self, client: TestClient):
        self.client = client
        self.mock_manager = IntegrationTestMockManager()
        self.results_dir = Path("performance_results")
        self.results_dir.mkdir(exist_ok=True)
        
        self.benchmark_results: List[BenchmarkResult] = []
        self.baseline_results: Optional[Dict[str, BenchmarkResult]] = None
    
    def load_baseline_results(self, baseline_file: str = "baseline_results.json"):
        """Load baseline performance results for comparison."""
        baseline_path = self.results_dir / baseline_file
        
        if baseline_path.exists():
            try:
                with open(baseline_path, 'r') as f:
                    baseline_data = json.load(f)
                
                self.baseline_results = {}
                for test_name, data in baseline_data.items():
                    # Convert timestamp string back to datetime
                    data['timestamp'] = datetime.fromisoformat(data['timestamp'])
                    self.baseline_results[test_name] = BenchmarkResult(**data)
                
                print(f"Loaded baseline results from {baseline_path}")
            except Exception as e:
                print(f"Error loading baseline results: {e}")
                self.baseline_results = None
        else:
            print(f"No baseline results found at {baseline_path}")
            self.baseline_results = None
    
    def save_baseline_results(self, baseline_file: str = "baseline_results.json"):
        """Save current results as baseline for future comparisons."""
        if not self.benchmark_results:
            print("No benchmark results to save as baseline")
            return
        
        baseline_path = self.results_dir / baseline_file
        baseline_data = {}
        
        for result in self.benchmark_results:
            # Convert datetime to string for JSON serialization
            result_dict = asdict(result)
            result_dict['timestamp'] = result.timestamp.isoformat()
            baseline_data[result.test_name] = result_dict
        
        try:
            with open(baseline_path, 'w') as f:
                json.dump(baseline_data, f, indent=2)
            print(f"Saved baseline results to {baseline_path}")
        except Exception as e:
            print(f"Error saving baseline results: {e}")
    
    def run_api_endpoint_benchmark(self, 
                                 endpoint_name: str,
                                 test_func,
                                 num_requests: int = 100,
                                 max_workers: int = 10,
                                 **test_parameters) -> BenchmarkResult:
        """Run benchmark for a specific API endpoint."""
        
        print(f"Running benchmark: {endpoint_name}")
        print(f"  Requests: {num_requests}, Workers: {max_workers}")
        
        start_time = time.time()
        
        # Execute the test function
        with self.mock_manager.mock_all_services():
            stats = test_func(num_requests, max_workers)
        
        duration = time.time() - start_time
        
        # Create benchmark result
        result = BenchmarkResult(
            test_name=endpoint_name,
            timestamp=datetime.utcnow(),
            duration=duration,
            total_requests=stats.get("total_requests", 0),
            successful_requests=stats.get("successful_requests", 0),
            failed_requests=stats.get("failed_requests", 0),
            success_rate=stats.get("success_rate", 0),
            throughput=stats.get("throughput_rps", 0),
            response_times=stats.get("response_times", {}),
            system_metrics=stats.get("system_metrics", {}),
            error_details=stats.get("errors", []),
            test_parameters={
                "num_requests": num_requests,
                "max_workers": max_workers,
                **test_parameters
            }
        )
        
        self.benchmark_results.append(result)
        return result
    
    def compare_with_baseline(self, result: BenchmarkResult) -> Dict[str, Any]:
        """Compare benchmark result with baseline."""
        if not self.baseline_results or result.test_name not in self.baseline_results:
            return {"status": "no_baseline", "message": "No baseline available for comparison"}
        
        baseline = self.baseline_results[result.test_name]
        
        # Calculate performance differences
        throughput_diff = ((result.throughput - baseline.throughput) / baseline.throughput) * 100
        success_rate_diff = result.success_rate - baseline.success_rate
        mean_response_diff = ((result.response_times.get("mean", 0) - baseline.response_times.get("mean", 0)) / baseline.response_times.get("mean", 1)) * 100
        p95_response_diff = ((result.response_times.get("p95", 0) - baseline.response_times.get("p95", 0)) / baseline.response_times.get("p95", 1)) * 100
        
        # Determine regression status
        regression_indicators = []
        
        if throughput_diff < -10:  # 10% decrease in throughput
            regression_indicators.append(f"Throughput decreased by {abs(throughput_diff):.1f}%")
        
        if success_rate_diff < -5:  # 5% decrease in success rate
            regression_indicators.append(f"Success rate decreased by {abs(success_rate_diff):.1f}%")
        
        if mean_response_diff > 20:  # 20% increase in mean response time
            regression_indicators.append(f"Mean response time increased by {mean_response_diff:.1f}%")
        
        if p95_response_diff > 25:  # 25% increase in 95th percentile
            regression_indicators.append(f"95th percentile response time increased by {p95_response_diff:.1f}%")
        
        comparison = {
            "status": "regression" if regression_indicators else "acceptable",
            "throughput_change": throughput_diff,
            "success_rate_change": success_rate_diff,
            "mean_response_change": mean_response_diff,
            "p95_response_change": p95_response_diff,
            "regression_indicators": regression_indicators,
            "baseline_date": baseline.timestamp.isoformat(),
            "current_date": result.timestamp.isoformat()
        }
        
        return comparison
    
    def generate_performance_report(self, output_file: str = None) -> str:
        """Generate comprehensive performance report."""
        if not self.benchmark_results:
            return "No benchmark results available for reporting"
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        if not output_file:
            output_file = f"performance_report_{timestamp}.html"
        
        report_path = self.results_dir / output_file
        
        # Generate HTML report
        html_content = self._generate_html_report()
        
        try:
            with open(report_path, 'w') as f:
                f.write(html_content)
            
            # Also save raw data as JSON
            json_file = report_path.with_suffix('.json')
            self._save_results_json(json_file)
            
            # Generate CSV summary
            csv_file = report_path.with_suffix('.csv')
            self._save_results_csv(csv_file)
            
            print(f"Performance report generated: {report_path}")
            print(f"Raw data saved: {json_file}")
            print(f"CSV summary saved: {csv_file}")
            
            return str(report_path)
            
        except Exception as e:
            print(f"Error generating performance report: {e}")
            return f"Error: {e}"
    
    def _generate_html_report(self) -> str:
        """Generate HTML performance report."""
        
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>Performance Benchmark Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f0f0f0; padding: 20px; border-radius: 5px; }
        .summary { margin: 20px 0; }
        .test-result { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
        .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }
        .metric { background-color: #f9f9f9; padding: 10px; border-radius: 3px; }
        .regression { background-color: #ffebee; border-left: 4px solid #f44336; }
        .acceptable { background-color: #e8f5e8; border-left: 4px solid #4caf50; }
        .no-baseline { background-color: #fff3e0; border-left: 4px solid #ff9800; }
        table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
"""
        
        # Header
        html += f"""
    <div class="header">
        <h1>Performance Benchmark Report</h1>
        <p>Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        <p>Total Tests: {len(self.benchmark_results)}</p>
    </div>
"""
        
        # Summary table
        html += """
    <div class="summary">
        <h2>Summary</h2>
        <table>
            <tr>
                <th>Test Name</th>
                <th>Success Rate</th>
                <th>Throughput (req/s)</th>
                <th>Mean Response (s)</th>
                <th>95th Percentile (s)</th>
                <th>Status</th>
            </tr>
"""
        
        for result in self.benchmark_results:
            comparison = self.compare_with_baseline(result)
            status_class = comparison["status"]
            
            html += f"""
            <tr class="{status_class}">
                <td>{result.test_name}</td>
                <td>{result.success_rate:.1f}%</td>
                <td>{result.throughput:.1f}</td>
                <td>{result.response_times.get('mean', 0):.3f}</td>
                <td>{result.response_times.get('p95', 0):.3f}</td>
                <td>{status_class.replace('_', ' ').title()}</td>
            </tr>
"""
        
        html += """
        </table>
    </div>
"""
        
        # Detailed results
        html += "<h2>Detailed Results</h2>"
        
        for result in self.benchmark_results:
            comparison = self.compare_with_baseline(result)
            status_class = comparison["status"]
            
            html += f"""
    <div class="test-result {status_class}">
        <h3>{result.test_name}</h3>
        <div class="metrics">
            <div class="metric">
                <strong>Duration:</strong> {result.duration:.1f}s
            </div>
            <div class="metric">
                <strong>Total Requests:</strong> {result.total_requests}
            </div>
            <div class="metric">
                <strong>Success Rate:</strong> {result.success_rate:.1f}%
            </div>
            <div class="metric">
                <strong>Throughput:</strong> {result.throughput:.1f} req/s
            </div>
            <div class="metric">
                <strong>Mean Response:</strong> {result.response_times.get('mean', 0):.3f}s
            </div>
            <div class="metric">
                <strong>95th Percentile:</strong> {result.response_times.get('p95', 0):.3f}s
            </div>
        </div>
"""
            
            # Baseline comparison
            if comparison["status"] != "no_baseline":
                html += f"""
        <h4>Baseline Comparison</h4>
        <ul>
            <li>Throughput Change: {comparison['throughput_change']:+.1f}%</li>
            <li>Success Rate Change: {comparison['success_rate_change']:+.1f}%</li>
            <li>Mean Response Change: {comparison['mean_response_change']:+.1f}%</li>
            <li>95th Percentile Change: {comparison['p95_response_change']:+.1f}%</li>
        </ul>
"""
                
                if comparison["regression_indicators"]:
                    html += "<h4>Regression Indicators</h4><ul>"
                    for indicator in comparison["regression_indicators"]:
                        html += f"<li>{indicator}</li>"
                    html += "</ul>"
            
            html += "</div>"
        
        html += """
</body>
</html>
"""
        
        return html
    
    def _save_results_json(self, json_file: Path):
        """Save benchmark results as JSON."""
        results_data = []
        
        for result in self.benchmark_results:
            result_dict = asdict(result)
            result_dict['timestamp'] = result.timestamp.isoformat()
            results_data.append(result_dict)
        
        with open(json_file, 'w') as f:
            json.dump(results_data, f, indent=2)
    
    def _save_results_csv(self, csv_file: Path):
        """Save benchmark results summary as CSV."""
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'Test Name', 'Timestamp', 'Duration (s)', 'Total Requests',
                'Success Rate (%)', 'Throughput (req/s)', 'Mean Response (s)',
                'Median Response (s)', '95th Percentile (s)', '99th Percentile (s)'
            ])
            
            # Data rows
            for result in self.benchmark_results:
                writer.writerow([
                    result.test_name,
                    result.timestamp.isoformat(),
                    f"{result.duration:.1f}",
                    result.total_requests,
                    f"{result.success_rate:.1f}",
                    f"{result.throughput:.1f}",
                    f"{result.response_times.get('mean', 0):.3f}",
                    f"{result.response_times.get('median', 0):.3f}",
                    f"{result.response_times.get('p95', 0):.3f}",
                    f"{result.response_times.get('p99', 0):.3f}"
                ])


@pytest.fixture
def benchmark_runner():
    """Fixture providing performance benchmark runner."""
    client = TestClient(app)
    runner = PerformanceBenchmarkRunner(client)
    
    # Load baseline results if available
    runner.load_baseline_results()
    
    yield runner


class TestPerformanceBenchmarks:
    """Comprehensive performance benchmark test suite."""
    
    def test_run_full_benchmark_suite(self, benchmark_runner):
        """Run complete performance benchmark suite."""
        
        # Import test functions from other performance test files
        from test_api_load import PerformanceTestRunner
        from test_blockchain_throughput import BlockchainThroughputTester
        from test_database_performance import DatabasePerformanceTester
        
        print("Starting comprehensive performance benchmark suite...")
        
        # API Load Tests
        def customer_creation_benchmark(num_requests, max_workers):
            runner = PerformanceTestRunner(benchmark_runner.client)
            with benchmark_runner.mock_manager.mock_all_services():
                return runner.concurrent_requests(
                    lambda i: self._create_customer_operation(runner, i),
                    num_requests, max_workers
                )
        
        def loan_application_benchmark(num_requests, max_workers):
            runner = PerformanceTestRunner(benchmark_runner.client)
            with benchmark_runner.mock_manager.mock_all_services():
                return runner.concurrent_requests(
                    lambda i: self._create_loan_operation(runner, i),
                    num_requests, max_workers
                )
        
        def mixed_workload_benchmark(num_requests, max_workers):
            runner = PerformanceTestRunner(benchmark_runner.client)
            with benchmark_runner.mock_manager.mock_all_services():
                return runner.concurrent_requests(
                    lambda i: self._mixed_operation(runner, i),
                    num_requests, max_workers
                )
        
        # Run benchmarks
        benchmarks = [
            ("Customer Creation API", customer_creation_benchmark, 50, 8),
            ("Loan Application API", loan_application_benchmark, 30, 6),
            ("Mixed Workload API", mixed_workload_benchmark, 40, 10),
        ]
        
        for test_name, test_func, requests, workers in benchmarks:
            result = benchmark_runner.run_api_endpoint_benchmark(
                test_name, test_func, requests, workers
            )
            
            # Compare with baseline
            comparison = benchmark_runner.compare_with_baseline(result)
            
            print(f"\n{test_name} Results:")
            print(f"  Success Rate: {result.success_rate:.1f}%")
            print(f"  Throughput: {result.throughput:.1f} req/s")
            print(f"  Mean Response: {result.response_times.get('mean', 0):.3f}s")
            
            if comparison["status"] == "regression":
                print(f"  ⚠️  REGRESSION DETECTED:")
                for indicator in comparison["regression_indicators"]:
                    print(f"    - {indicator}")
            elif comparison["status"] == "acceptable":
                print(f"  ✅ Performance acceptable compared to baseline")
            else:
                print(f"  ℹ️  No baseline available for comparison")
        
        # Generate comprehensive report
        report_path = benchmark_runner.generate_performance_report()
        print(f"\nComprehensive performance report generated: {report_path}")
        
        # Save current results as baseline if requested
        # benchmark_runner.save_baseline_results()
        
        # Assert overall benchmark success
        overall_success_rate = sum(r.success_rate for r in benchmark_runner.benchmark_results) / len(benchmark_runner.benchmark_results)
        assert overall_success_rate >= 85, f"Overall benchmark success rate too low: {overall_success_rate:.1f}%"
        
        print(f"\n🎯 Benchmark suite completed successfully!")
        print(f"   Overall success rate: {overall_success_rate:.1f}%")
        print(f"   Total tests: {len(benchmark_runner.benchmark_results)}")
    
    def _create_customer_operation(self, runner, request_id):
        """Helper method for customer creation benchmark."""
        customer_data = {
            "first_name": f"BenchmarkCustomer{request_id}",
            "last_name": "Test",
            "date_of_birth": "1985-06-15T00:00:00",
            "national_id": f"BENCH{request_id:08d}",
            "address": f"123 Benchmark St #{request_id}",
            "contact_email": f"benchmark{request_id}@example.com",
            "contact_phone": f"+1-555-{request_id:04d}",
            "consent_preferences": {"data_sharing": True}
        }
        
        start_time = time.time()
        try:
            response = runner.client.post(
                "/api/v1/customers",
                json=customer_data,
                headers={"X-Actor-ID": "BENCHMARK_ACTOR"}
            )
            response_time = time.time() - start_time
            success = response.status_code == 201
            error = None if success else f"HTTP {response.status_code}"
            return response_time, success, error
        except Exception as e:
            response_time = time.time() - start_time
            return response_time, False, str(e)
    
    def _create_loan_operation(self, runner, request_id):
        """Helper method for loan application benchmark."""
        loan_data = {
            "customer_id": f"CUST_BENCH_{request_id}",
            "requested_amount": 25000.0,
            "loan_type": "PERSONAL",
            "introducer_id": f"INTRO_BENCH_{request_id}"
        }
        
        start_time = time.time()
        try:
            response = runner.client.post(
                "/api/v1/loans/applications",
                json=loan_data,
                headers={"X-Actor-ID": "BENCHMARK_UNDERWRITER"}
            )
            response_time = time.time() - start_time
            success = response.status_code == 201
            error = None if success else f"HTTP {response.status_code}"
            return response_time, success, error
        except Exception as e:
            response_time = time.time() - start_time
            return response_time, False, str(e)
    
    def _mixed_operation(self, runner, request_id):
        """Helper method for mixed workload benchmark."""
        if request_id % 2 == 0:
            return self._create_customer_operation(runner, request_id)
        else:
            # Read operation
            start_time = time.time()
            try:
                response = runner.client.get(
                    "/api/v1/compliance/events",
                    params={"limit": 10},
                    headers={"X-Actor-ID": "BENCHMARK_READER"}
                )
                response_time = time.time() - start_time
                success = response.status_code == 200
                error = None if success else f"HTTP {response.status_code}"
                return response_time, success, error
            except Exception as e:
                response_time = time.time() - start_time
                return response_time, False, str(e)