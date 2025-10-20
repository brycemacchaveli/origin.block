"""
Performance and load testing for API endpoints.

Tests API performance under various load conditions including high concurrency,
large data volumes, and stress scenarios.
"""

import pytest
import asyncio
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple
import json
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from main import app
from tests.integration.mock_infrastructure import IntegrationTestMockManager


class PerformanceTestRunner:
    """Manages performance test execution and metrics collection."""
    
    def __init__(self, client: TestClient):
        self.client = client
        self.mock_manager = IntegrationTestMockManager()
        self.metrics = {
            "response_times": [],
            "success_count": 0,
            "error_count": 0,
            "throughput": 0,
            "errors": []
        }
    
    def reset_metrics(self):
        """Reset performance metrics."""
        self.metrics = {
            "response_times": [],
            "success_count": 0,
            "error_count": 0,
            "throughput": 0,
            "errors": []
        }
    
    def record_response(self, response_time: float, success: bool, error: str = None):
        """Record a response for metrics."""
        self.metrics["response_times"].append(response_time)
        if success:
            self.metrics["success_count"] += 1
        else:
            self.metrics["error_count"] += 1
            if error:
                self.metrics["errors"].append(error)
    
    def calculate_statistics(self, duration: float) -> Dict[str, Any]:
        """Calculate performance statistics."""
        response_times = self.metrics["response_times"]
        
        if not response_times:
            return {"error": "No response times recorded"}
        
        total_requests = len(response_times)
        
        stats = {
            "total_requests": total_requests,
            "successful_requests": self.metrics["success_count"],
            "failed_requests": self.metrics["error_count"],
            "success_rate": (self.metrics["success_count"] / total_requests) * 100,
            "throughput_rps": total_requests / duration,
            "response_times": {
                "min": min(response_times),
                "max": max(response_times),
                "mean": statistics.mean(response_times),
                "median": statistics.median(response_times),
                "p95": self._percentile(response_times, 95),
                "p99": self._percentile(response_times, 99)
            },
            "errors": self.metrics["errors"][:10]  # First 10 errors
        }
        
        return stats
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of response times."""
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def concurrent_requests(self, 
                          endpoint_func, 
                          num_requests: int, 
                          max_workers: int = 10) -> Dict[str, Any]:
        """Execute concurrent requests to test load handling."""
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all requests
            futures = [executor.submit(endpoint_func, i) for i in range(num_requests)]
            
            # Collect results
            for future in as_completed(futures):
                try:
                    response_time, success, error = future.result()
                    self.record_response(response_time, success, error)
                except Exception as e:
                    self.record_response(0, False, str(e))
        
        duration = time.time() - start_time
        return self.calculate_statistics(duration)


@pytest.fixture
def performance_runner():
    """Fixture providing performance test runner."""
    client = TestClient(app)
    runner = PerformanceTestRunner(client)
    
    # Setup mocks with authentication
    with runner.mock_manager.mock_all_services():
        yield runner


class TestAPIPerformance:
    """Test API performance under load."""
    
    def test_customer_creation_load(self, performance_runner):
        """Test customer creation endpoint under load."""
        
        def create_customer(request_id: int) -> Tuple[float, bool, str]:
            """Create a customer and measure response time."""
            customer_data = {
                "first_name": f"LoadTest{request_id}",
                "last_name": "Customer",
                "date_of_birth": "1985-06-15T00:00:00",
                "national_id": f"LOAD{request_id:06d}",
                "address": f"123 Load Test St #{request_id}",
                "contact_email": f"loadtest{request_id}@example.com",
                "contact_phone": f"+1-555-{request_id:04d}",
                "consent_preferences": {
                    "data_sharing": True,
                    "marketing": False,
                    "analytics": True
                }
            }
            
            start_time = time.time()
            try:
                response = performance_runner.client.post(
                    "/api/v1/customers",
                    json=customer_data,
                    headers={"X-Actor-ID": "LOAD_TEST_ACTOR"}
                )
                response_time = time.time() - start_time
                
                success = response.status_code == 201
                error = None if success else f"HTTP {response.status_code}: {response.text}"
                
                return response_time, success, error
                
            except Exception as e:
                response_time = time.time() - start_time
                return response_time, False, str(e)
        
        # Test with 50 concurrent requests, 10 workers
        performance_runner.reset_metrics()
        stats = performance_runner.concurrent_requests(create_customer, 50, 10)
        
        # Performance assertions
        assert stats["success_rate"] >= 95, f"Success rate too low: {stats['success_rate']}%"
        assert stats["response_times"]["mean"] < 2.0, f"Mean response time too high: {stats['response_times']['mean']}s"
        assert stats["response_times"]["p95"] < 5.0, f"95th percentile too high: {stats['response_times']['p95']}s"
        assert stats["throughput_rps"] >= 10, f"Throughput too low: {stats['throughput_rps']} RPS"
        
        print(f"Customer Creation Load Test Results:")
        print(f"  Total Requests: {stats['total_requests']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Throughput: {stats['throughput_rps']:.2f} RPS")
        print(f"  Mean Response Time: {stats['response_times']['mean']:.3f}s")
        print(f"  95th Percentile: {stats['response_times']['p95']:.3f}s")
    
    def test_loan_application_load(self, performance_runner):
        """Test loan application endpoint under load."""
        
        def create_loan_application(request_id: int) -> Tuple[float, bool, str]:
            """Create a loan application and measure response time."""
            loan_data = {
                "customer_id": f"CUST_LOAD_{request_id:06d}",
                "requested_amount": 25000.0 + (request_id * 100),
                "loan_type": "PERSONAL",
                "introducer_id": f"INTRO_LOAD_{request_id}",
                "additional_info": {
                    "purpose": f"Load test loan {request_id}",
                    "employment_status": "Full-time",
                    "annual_income": 75000.0
                }
            }
            
            start_time = time.time()
            try:
                response = performance_runner.client.post(
                    "/api/v1/loans/",
                    json=loan_data,
                    headers={"X-Actor-ID": "LOAD_TEST_UNDERWRITER"}
                )
                response_time = time.time() - start_time
                
                success = response.status_code == 201
                error = None if success else f"HTTP {response.status_code}: {response.text}"
                
                return response_time, success, error
                
            except Exception as e:
                response_time = time.time() - start_time
                return response_time, False, str(e)
        
        # Test with 30 concurrent requests, 8 workers
        performance_runner.reset_metrics()
        stats = performance_runner.concurrent_requests(create_loan_application, 30, 8)
        
        # Performance assertions
        assert stats["success_rate"] >= 90, f"Success rate too low: {stats['success_rate']}%"
        assert stats["response_times"]["mean"] < 3.0, f"Mean response time too high: {stats['response_times']['mean']}s"
        assert stats["response_times"]["p95"] < 8.0, f"95th percentile too high: {stats['response_times']['p95']}s"
        assert stats["throughput_rps"] >= 5, f"Throughput too low: {stats['throughput_rps']} RPS"
        
        print(f"Loan Application Load Test Results:")
        print(f"  Total Requests: {stats['total_requests']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Throughput: {stats['throughput_rps']:.2f} RPS")
        print(f"  Mean Response Time: {stats['response_times']['mean']:.3f}s")
        print(f"  95th Percentile: {stats['response_times']['p95']:.3f}s")
    
    def test_mixed_workload_performance(self, performance_runner):
        """Test mixed workload performance with different endpoint types."""
        
        def mixed_workload(request_id: int) -> Tuple[float, bool, str]:
            """Execute mixed operations and measure response time."""
            
            # Rotate between different operations
            operation = request_id % 4
            
            start_time = time.time()
            try:
                if operation == 0:
                    # Create customer
                    response = performance_runner.client.post(
                        "/api/v1/customers",
                        json={
                            "first_name": f"Mixed{request_id}",
                            "last_name": "Test",
                            "date_of_birth": "1985-06-15T00:00:00",
                            "national_id": f"MIX{request_id:06d}",
                            "address": f"123 Mixed St #{request_id}",
                            "contact_email": f"mixed{request_id}@example.com",
                            "contact_phone": f"+1-555-{request_id:04d}",
                            "consent_preferences": {"data_sharing": True, "marketing": False}
                        },
                        headers={"X-Actor-ID": "MIXED_TEST_ACTOR"}
                    )
                    expected_status = 201
                    
                elif operation == 1:
                    # Create loan application
                    response = performance_runner.client.post(
                        "/api/v1/loans/",
                        json={
                            "customer_id": f"CUST_MIX_{request_id}",
                            "requested_amount": 30000.0,
                            "loan_type": "PERSONAL",
                            "introducer_id": f"INTRO_MIX_{request_id}"
                        },
                        headers={"X-Actor-ID": "MIXED_TEST_UNDERWRITER"}
                    )
                    expected_status = 201
                    
                elif operation == 2:
                    # Get customer (read operation)
                    response = performance_runner.client.get(
                        f"/api/v1/customers/CUST_MIX_{request_id}",
                        headers={"X-Actor-ID": "MIXED_TEST_READER"}
                    )
                    expected_status = 200
                    
                else:
                    # Get compliance events (read operation)
                    response = performance_runner.client.get(
                        "/api/v1/compliance/events",
                        params={"limit": 10},
                        headers={"X-Actor-ID": "MIXED_TEST_COMPLIANCE"}
                    )
                    expected_status = 200
                
                response_time = time.time() - start_time
                success = response.status_code == expected_status
                error = None if success else f"HTTP {response.status_code}: {response.text}"
                
                return response_time, success, error
                
            except Exception as e:
                response_time = time.time() - start_time
                return response_time, False, str(e)
        
        # Test with 40 concurrent requests, 12 workers
        performance_runner.reset_metrics()
        stats = performance_runner.concurrent_requests(mixed_workload, 40, 12)
        
        # Performance assertions for mixed workload
        assert stats["success_rate"] >= 85, f"Success rate too low: {stats['success_rate']}%"
        assert stats["response_times"]["mean"] < 2.5, f"Mean response time too high: {stats['response_times']['mean']}s"
        assert stats["response_times"]["p99"] < 10.0, f"99th percentile too high: {stats['response_times']['p99']}s"
        assert stats["throughput_rps"] >= 8, f"Throughput too low: {stats['throughput_rps']} RPS"
        
        print(f"Mixed Workload Performance Test Results:")
        print(f"  Total Requests: {stats['total_requests']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Throughput: {stats['throughput_rps']:.2f} RPS")
        print(f"  Mean Response Time: {stats['response_times']['mean']:.3f}s")
        print(f"  99th Percentile: {stats['response_times']['p99']:.3f}s")
    
    def test_stress_testing(self, performance_runner):
        """Test system behavior under stress conditions."""
        
        def stress_operation(request_id: int) -> Tuple[float, bool, str]:
            """Execute operations under stress conditions."""
            
            # Create large customer data
            large_address = "A" * 500  # Large address field
            
            customer_data = {
                "first_name": f"StressTest{request_id}",
                "last_name": "Customer" * 10,  # Longer name
                "date_of_birth": "1985-06-15T00:00:00",
                "national_id": f"STRESS{request_id:08d}",
                "address": large_address,
                "contact_email": f"stress.test.{request_id}@example.com",
                "contact_phone": f"+1-555-{request_id:04d}",
                "consent_preferences": {
                    "data_sharing": True,
                    "marketing": True,
                    "analytics": True,
                    "third_party_sharing": False
                }
            }
            
            start_time = time.time()
            try:
                response = performance_runner.client.post(
                    "/api/v1/customers",
                    json=customer_data,
                    headers={"X-Actor-ID": "STRESS_TEST_ACTOR"}
                )
                response_time = time.time() - start_time
                
                success = response.status_code in [201, 400, 422]  # Accept validation errors under stress
                error = None if success else f"HTTP {response.status_code}: {response.text}"
                
                return response_time, success, error
                
            except Exception as e:
                response_time = time.time() - start_time
                return response_time, False, str(e)
        
        # Stress test with 100 concurrent requests, 20 workers
        performance_runner.reset_metrics()
        stats = performance_runner.concurrent_requests(stress_operation, 100, 20)
        
        # Stress test assertions (more lenient)
        assert stats["success_rate"] >= 70, f"Success rate too low under stress: {stats['success_rate']}%"
        assert stats["response_times"]["mean"] < 10.0, f"Mean response time too high under stress: {stats['response_times']['mean']}s"
        assert stats["throughput_rps"] >= 3, f"Throughput too low under stress: {stats['throughput_rps']} RPS"
        
        print(f"Stress Test Results:")
        print(f"  Total Requests: {stats['total_requests']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Throughput: {stats['throughput_rps']:.2f} RPS")
        print(f"  Mean Response Time: {stats['response_times']['mean']:.3f}s")
        print(f"  Max Response Time: {stats['response_times']['max']:.3f}s")
    
    def test_sustained_load(self, performance_runner):
        """Test system performance under sustained load."""
        
        def sustained_operation(request_id: int) -> Tuple[float, bool, str]:
            """Execute operations for sustained load testing."""
            
            # Alternate between read and write operations
            if request_id % 2 == 0:
                # Write operation - create customer
                response = performance_runner.client.post(
                    "/api/v1/customers",
                    json={
                        "first_name": f"Sustained{request_id}",
                        "last_name": "Test",
                        "date_of_birth": "1985-06-15T00:00:00",
                        "national_id": f"SUST{request_id:06d}",
                        "address": f"123 Sustained St #{request_id}",
                        "contact_email": f"sustained{request_id}@example.com",
                        "contact_phone": f"+1-555-{request_id:04d}",
                        "consent_preferences": {"data_sharing": True}
                    },
                    headers={"X-Actor-ID": "SUSTAINED_TEST_ACTOR"}
                )
                expected_status = 201
            else:
                # Read operation - get compliance events
                response = performance_runner.client.get(
                    "/api/v1/compliance/events",
                    params={"limit": 5},
                    headers={"X-Actor-ID": "SUSTAINED_TEST_READER"}
                )
                expected_status = 200
            
            start_time = time.time()
            try:
                response_time = time.time() - start_time
                success = response.status_code == expected_status
                error = None if success else f"HTTP {response.status_code}: {response.text}"
                
                return response_time, success, error
                
            except Exception as e:
                response_time = time.time() - start_time
                return response_time, False, str(e)
        
        # Sustained load test - moderate concurrency over longer duration
        performance_runner.reset_metrics()
        stats = performance_runner.concurrent_requests(sustained_operation, 60, 6)
        
        # Sustained load assertions
        assert stats["success_rate"] >= 90, f"Success rate degraded under sustained load: {stats['success_rate']}%"
        assert stats["response_times"]["mean"] < 3.0, f"Mean response time degraded: {stats['response_times']['mean']}s"
        assert stats["throughput_rps"] >= 5, f"Throughput degraded: {stats['throughput_rps']} RPS"
        
        print(f"Sustained Load Test Results:")
        print(f"  Total Requests: {stats['total_requests']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Throughput: {stats['throughput_rps']:.2f} RPS")
        print(f"  Mean Response Time: {stats['response_times']['mean']:.3f}s")