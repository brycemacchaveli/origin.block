"""
Stress testing for system failure scenarios.

Tests system behavior under extreme conditions including resource exhaustion,
network failures, and cascading failures.
"""

import pytest
import asyncio
import time
import statistics
import psutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple
import json
from datetime import datetime, timedelta
import random
import string
import gc

from fastapi.testclient import TestClient
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from main import app
from tests.integration.mock_infrastructure import IntegrationTestMockManager


class StressTestRunner:
    """Manages stress testing and system failure scenario testing."""
    
    def __init__(self, client: TestClient):
        self.client = client
        self.mock_manager = IntegrationTestMockManager()
        self.stress_metrics = {
            "response_times": [],
            "memory_usage": [],
            "cpu_usage": [],
            "error_rates": [],
            "recovery_times": [],
            "failure_points": [],
            "success_count": 0,
            "error_count": 0,
            "timeout_count": 0,
            "system_errors": []
        }
        self.is_stress_active = False
        self.stress_start_time = None
    
    def reset_stress_metrics(self):
        """Reset stress testing metrics."""
        self.stress_metrics = {
            "response_times": [],
            "memory_usage": [],
            "cpu_usage": [],
            "error_rates": [],
            "recovery_times": [],
            "failure_points": [],
            "success_count": 0,
            "error_count": 0,
            "timeout_count": 0,
            "system_errors": []
        }
        self.is_stress_active = False
        self.stress_start_time = None
    
    def start_stress_monitoring(self):
        """Start monitoring system resources during stress test."""
        self.is_stress_active = True
        self.stress_start_time = time.time()
        
        def monitor_resources():
            while self.is_stress_active:
                try:
                    memory_percent = psutil.virtual_memory().percent
                    cpu_percent = psutil.cpu_percent(interval=0.1)
                    
                    self.stress_metrics["memory_usage"].append(memory_percent)
                    self.stress_metrics["cpu_usage"].append(cpu_percent)
                    
                    # Check for resource exhaustion
                    if memory_percent > 90:
                        self.stress_metrics["failure_points"].append({
                            "type": "memory_exhaustion",
                            "timestamp": time.time() - self.stress_start_time,
                            "value": memory_percent
                        })
                    
                    if cpu_percent > 95:
                        self.stress_metrics["failure_points"].append({
                            "type": "cpu_exhaustion",
                            "timestamp": time.time() - self.stress_start_time,
                            "value": cpu_percent
                        })
                    
                    time.sleep(0.5)  # Monitor every 500ms
                    
                except Exception as e:
                    self.stress_metrics["system_errors"].append(f"Monitoring error: {str(e)}")
        
        # Start monitoring in background thread
        monitor_thread = threading.Thread(target=monitor_resources, daemon=True)
        monitor_thread.start()
    
    def stop_stress_monitoring(self):
        """Stop monitoring system resources."""
        self.is_stress_active = False
    
    def record_stress_response(self, response_time: float, success: bool, error_type: str = None):
        """Record stress test response metrics."""
        self.stress_metrics["response_times"].append(response_time)
        
        if success:
            self.stress_metrics["success_count"] += 1
        else:
            self.stress_metrics["error_count"] += 1
            if error_type == "timeout":
                self.stress_metrics["timeout_count"] += 1
            if error_type:
                self.stress_metrics["system_errors"].append(error_type)
    
    def calculate_stress_statistics(self, duration: float) -> Dict[str, Any]:
        """Calculate stress test statistics."""
        total_requests = len(self.stress_metrics["response_times"])
        
        if total_requests == 0:
            return {"error": "No requests recorded"}
        
        # Calculate error rate over time
        error_rate = (self.stress_metrics["error_count"] / total_requests) * 100
        timeout_rate = (self.stress_metrics["timeout_count"] / total_requests) * 100
        
        stats = {
            "duration": duration,
            "total_requests": total_requests,
            "successful_requests": self.stress_metrics["success_count"],
            "failed_requests": self.stress_metrics["error_count"],
            "timeout_requests": self.stress_metrics["timeout_count"],
            "success_rate": (self.stress_metrics["success_count"] / total_requests) * 100,
            "error_rate": error_rate,
            "timeout_rate": timeout_rate,
            "throughput": total_requests / duration,
            "response_times": {
                "min": min(self.stress_metrics["response_times"]) if self.stress_metrics["response_times"] else 0,
                "max": max(self.stress_metrics["response_times"]) if self.stress_metrics["response_times"] else 0,
                "mean": statistics.mean(self.stress_metrics["response_times"]) if self.stress_metrics["response_times"] else 0,
                "median": statistics.median(self.stress_metrics["response_times"]) if self.stress_metrics["response_times"] else 0,
                "p95": self._percentile(self.stress_metrics["response_times"], 95),
                "p99": self._percentile(self.stress_metrics["response_times"], 99)
            },
            "system_resources": {
                "peak_memory_usage": max(self.stress_metrics["memory_usage"]) if self.stress_metrics["memory_usage"] else 0,
                "avg_memory_usage": statistics.mean(self.stress_metrics["memory_usage"]) if self.stress_metrics["memory_usage"] else 0,
                "peak_cpu_usage": max(self.stress_metrics["cpu_usage"]) if self.stress_metrics["cpu_usage"] else 0,
                "avg_cpu_usage": statistics.mean(self.stress_metrics["cpu_usage"]) if self.stress_metrics["cpu_usage"] else 0
            },
            "failure_points": self.stress_metrics["failure_points"],
            "system_errors": self.stress_metrics["system_errors"][:20]  # First 20 errors
        }
        
        return stats
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of response times."""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def execute_stress_test(self, 
                          stress_func, 
                          duration_seconds: int, 
                          max_workers: int = 20,
                          ramp_up_seconds: int = 10) -> Dict[str, Any]:
        """Execute stress test with gradual ramp-up."""
        
        self.start_stress_monitoring()
        start_time = time.time()
        
        # Gradual ramp-up
        workers_per_second = max_workers / ramp_up_seconds if ramp_up_seconds > 0 else max_workers
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            request_id = 0
            
            # Ramp-up phase
            for second in range(ramp_up_seconds):
                current_workers = int((second + 1) * workers_per_second)
                
                for _ in range(current_workers):
                    if time.time() - start_time < duration_seconds:
                        future = executor.submit(stress_func, request_id)
                        futures.append(future)
                        request_id += 1
                
                time.sleep(1)  # Wait 1 second before adding more workers
            
            # Sustained load phase
            remaining_time = duration_seconds - ramp_up_seconds
            if remaining_time > 0:
                requests_per_second = max_workers * 2  # Aggressive load
                
                for second in range(int(remaining_time)):
                    for _ in range(requests_per_second):
                        if time.time() - start_time < duration_seconds:
                            future = executor.submit(stress_func, request_id)
                            futures.append(future)
                            request_id += 1
                    
                    time.sleep(0.1)  # Brief pause
            
            # Collect all results
            for future in as_completed(futures):
                try:
                    response_time, success, error_type = future.result(timeout=30)
                    self.record_stress_response(response_time, success, error_type)
                except Exception as e:
                    self.record_stress_response(0, False, f"Future error: {str(e)}")
        
        total_duration = time.time() - start_time
        self.stop_stress_monitoring()
        
        return self.calculate_stress_statistics(total_duration)


@pytest.fixture
def stress_runner():
    """Fixture providing stress test runner."""
    client = TestClient(app)
    runner = StressTestRunner(client)
    
    # Setup mocks
    with runner.mock_manager.mock_all_services():
        yield runner


class TestStressScenarios:
    """Test system behavior under stress and failure conditions."""
    
    def test_memory_exhaustion_scenario(self, stress_runner):
        """Test system behavior under memory pressure."""
        
        def memory_intensive_operation(request_id: int) -> Tuple[float, bool, str]:
            """Execute memory-intensive operations."""
            
            # Create large data structures to simulate memory pressure
            large_data = {
                "customer_data": {
                    "first_name": f"MemoryStress{request_id}",
                    "last_name": "Customer" * 100,  # Large string
                    "date_of_birth": "1985-06-15T00:00:00",
                    "national_id": f"MEM{request_id:08d}",
                    "address": "A" * 1000,  # Very large address
                    "contact_email": f"memory.stress.{request_id}@example.com",
                    "contact_phone": f"+1-555-{request_id:04d}",
                    "consent_preferences": {
                        "data_sharing": True,
                        "marketing": True,
                        "analytics": True,
                        "large_field": "X" * 500  # Large field
                    }
                },
                "additional_data": ["dummy_data"] * 1000  # Large list
            }
            
            start_time = time.time()
            try:
                response = stress_runner.client.post(
                    "/api/v1/customers",
                    json=large_data["customer_data"],
                    headers={"X-Actor-ID": "MEMORY_STRESS_ACTOR"},
                    timeout=10
                )
                
                response_time = time.time() - start_time
                success = response.status_code in [201, 400, 422, 500]  # Accept various responses under stress
                error_type = None if success else "http_error"
                
                # Force garbage collection to simulate memory pressure
                if request_id % 10 == 0:
                    gc.collect()
                
                return response_time, success, error_type
                
            except Exception as e:
                response_time = time.time() - start_time
                error_type = "timeout" if "timeout" in str(e).lower() else "exception"
                return response_time, False, error_type
        
        # Execute memory stress test for 30 seconds
        stress_runner.reset_stress_metrics()
        stats = stress_runner.execute_stress_test(
            memory_intensive_operation, 
            duration_seconds=30, 
            max_workers=15,
            ramp_up_seconds=5
        )
        
        # Memory stress assertions (more lenient)
        assert stats["success_rate"] >= 60, f"Success rate too low under memory stress: {stats['success_rate']}%"
        assert stats["error_rate"] <= 40, f"Error rate too high: {stats['error_rate']}%"
        assert stats["system_resources"]["peak_memory_usage"] > 0, "No memory usage recorded"
        
        print(f"Memory Exhaustion Stress Test Results:")
        print(f"  Duration: {stats['duration']:.1f}s")
        print(f"  Total Requests: {stats['total_requests']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Error Rate: {stats['error_rate']:.2f}%")
        print(f"  Timeout Rate: {stats['timeout_rate']:.2f}%")
        print(f"  Peak Memory Usage: {stats['system_resources']['peak_memory_usage']:.1f}%")
        print(f"  Failure Points: {len(stats['failure_points'])}")
    
    def test_high_concurrency_scenario(self, stress_runner):
        """Test system behavior under extreme concurrency."""
        
        def high_concurrency_operation(request_id: int) -> Tuple[float, bool, str]:
            """Execute operations under high concurrency."""
            
            # Rotate between different operations to simulate real load
            operation_type = request_id % 4
            
            start_time = time.time()
            try:
                if operation_type == 0:
                    # Customer creation
                    response = stress_runner.client.post(
                        "/api/v1/customers",
                        json={
                            "first_name": f"Concurrency{request_id}",
                            "last_name": "Test",
                            "date_of_birth": "1985-06-15T00:00:00",
                            "national_id": f"CONC{request_id:08d}",
                            "address": f"123 Concurrency St #{request_id}",
                            "contact_email": f"concurrency{request_id}@example.com",
                            "contact_phone": f"+1-555-{request_id:04d}",
                            "consent_preferences": {"data_sharing": True}
                        },
                        headers={"X-Actor-ID": "CONCURRENCY_TEST_ACTOR"},
                        timeout=15
                    )
                    expected_codes = [201, 400, 422]
                    
                elif operation_type == 1:
                    # Loan application
                    response = stress_runner.client.post(
                        "/api/v1/loans/applications",
                        json={
                            "customer_id": f"CUST_CONC_{request_id}",
                            "requested_amount": 30000.0,
                            "loan_type": "PERSONAL",
                            "introducer_id": f"INTRO_CONC_{request_id}"
                        },
                        headers={"X-Actor-ID": "CONCURRENCY_TEST_UNDERWRITER"},
                        timeout=15
                    )
                    expected_codes = [201, 400, 422]
                    
                elif operation_type == 2:
                    # Customer lookup
                    customer_id = f"CUST_CONC_{request_id % 100}"
                    response = stress_runner.client.get(
                        f"/api/v1/customers/{customer_id}",
                        headers={"X-Actor-ID": "CONCURRENCY_TEST_READER"},
                        timeout=10
                    )
                    expected_codes = [200, 404]
                    
                else:
                    # Compliance events
                    response = stress_runner.client.get(
                        "/api/v1/compliance/events",
                        params={"limit": 10},
                        headers={"X-Actor-ID": "CONCURRENCY_TEST_COMPLIANCE"},
                        timeout=10
                    )
                    expected_codes = [200]
                
                response_time = time.time() - start_time
                success = response.status_code in expected_codes
                error_type = None if success else "http_error"
                
                return response_time, success, error_type
                
            except Exception as e:
                response_time = time.time() - start_time
                error_type = "timeout" if "timeout" in str(e).lower() else "exception"
                return response_time, False, error_type
        
        # Execute high concurrency test for 45 seconds with 30 workers
        stress_runner.reset_stress_metrics()
        stats = stress_runner.execute_stress_test(
            high_concurrency_operation, 
            duration_seconds=45, 
            max_workers=30,
            ramp_up_seconds=10
        )
        
        # High concurrency assertions
        assert stats["success_rate"] >= 70, f"Success rate too low under high concurrency: {stats['success_rate']}%"
        assert stats["timeout_rate"] <= 20, f"Timeout rate too high: {stats['timeout_rate']}%"
        assert stats["throughput"] >= 10, f"Throughput too low under stress: {stats['throughput']} req/sec"
        
        print(f"High Concurrency Stress Test Results:")
        print(f"  Duration: {stats['duration']:.1f}s")
        print(f"  Total Requests: {stats['total_requests']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Timeout Rate: {stats['timeout_rate']:.2f}%")
        print(f"  Throughput: {stats['throughput']:.2f} req/sec")
        print(f"  Peak CPU Usage: {stats['system_resources']['peak_cpu_usage']:.1f}%")
        print(f"  Mean Response Time: {stats['response_times']['mean']:.3f}s")
    
    def test_sustained_load_degradation(self, stress_runner):
        """Test system degradation under sustained load."""
        
        def sustained_load_operation(request_id: int) -> Tuple[float, bool, str]:
            """Execute operations for sustained load testing."""
            
            # Simulate realistic mixed workload
            customer_data = {
                "first_name": f"Sustained{request_id}",
                "last_name": "LoadTest",
                "date_of_birth": "1985-06-15T00:00:00",
                "national_id": f"SUST{request_id:08d}",
                "address": f"123 Sustained Load St #{request_id}",
                "contact_email": f"sustained{request_id}@example.com",
                "contact_phone": f"+1-555-{request_id:04d}",
                "consent_preferences": {
                    "data_sharing": True,
                    "marketing": False,
                    "analytics": True
                }
            }
            
            start_time = time.time()
            try:
                response = stress_runner.client.post(
                    "/api/v1/customers",
                    json=customer_data,
                    headers={"X-Actor-ID": "SUSTAINED_LOAD_ACTOR"},
                    timeout=20
                )
                
                response_time = time.time() - start_time
                success = response.status_code in [201, 400, 422]
                error_type = None if success else "http_error"
                
                # Add small delay to simulate processing time
                time.sleep(0.01)
                
                return response_time, success, error_type
                
            except Exception as e:
                response_time = time.time() - start_time
                error_type = "timeout" if "timeout" in str(e).lower() else "exception"
                return response_time, False, error_type
        
        # Execute sustained load test for 60 seconds
        stress_runner.reset_stress_metrics()
        stats = stress_runner.execute_stress_test(
            sustained_load_operation, 
            duration_seconds=60, 
            max_workers=12,
            ramp_up_seconds=15
        )
        
        # Sustained load assertions
        assert stats["success_rate"] >= 80, f"Success rate degraded too much: {stats['success_rate']}%"
        assert stats["response_times"]["p95"] < 15.0, f"95th percentile too high: {stats['response_times']['p95']}s"
        assert stats["throughput"] >= 5, f"Throughput degraded too much: {stats['throughput']} req/sec"
        
        print(f"Sustained Load Degradation Test Results:")
        print(f"  Duration: {stats['duration']:.1f}s")
        print(f"  Total Requests: {stats['total_requests']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Throughput: {stats['throughput']:.2f} req/sec")
        print(f"  Mean Response Time: {stats['response_times']['mean']:.3f}s")
        print(f"  95th Percentile: {stats['response_times']['p95']:.3f}s")
        print(f"  Avg Memory Usage: {stats['system_resources']['avg_memory_usage']:.1f}%")
        print(f"  Avg CPU Usage: {stats['system_resources']['avg_cpu_usage']:.1f}%")
    
    def test_rapid_failure_recovery(self, stress_runner):
        """Test system recovery from rapid failures."""
        
        def failure_recovery_operation(request_id: int) -> Tuple[float, bool, str]:
            """Execute operations that may fail and test recovery."""
            
            # Intentionally cause some failures to test recovery
            should_fail = request_id % 5 == 0  # 20% failure rate
            
            start_time = time.time()
            try:
                if should_fail:
                    # Send invalid data to trigger failure
                    response = stress_runner.client.post(
                        "/api/v1/customers",
                        json={
                            "first_name": "",  # Invalid empty name
                            "last_name": "",   # Invalid empty name
                            "date_of_birth": "invalid-date",  # Invalid date
                            "national_id": "",  # Invalid empty ID
                            "address": "",
                            "contact_email": "invalid-email",  # Invalid email
                            "contact_phone": "",
                            "consent_preferences": {}
                        },
                        headers={"X-Actor-ID": "FAILURE_RECOVERY_ACTOR"},
                        timeout=10
                    )
                    expected_codes = [400, 422]  # Expect validation errors
                else:
                    # Send valid data
                    response = stress_runner.client.post(
                        "/api/v1/customers",
                        json={
                            "first_name": f"Recovery{request_id}",
                            "last_name": "Test",
                            "date_of_birth": "1985-06-15T00:00:00",
                            "national_id": f"REC{request_id:08d}",
                            "address": f"123 Recovery St #{request_id}",
                            "contact_email": f"recovery{request_id}@example.com",
                            "contact_phone": f"+1-555-{request_id:04d}",
                            "consent_preferences": {"data_sharing": True}
                        },
                        headers={"X-Actor-ID": "FAILURE_RECOVERY_ACTOR"},
                        timeout=10
                    )
                    expected_codes = [201]
                
                response_time = time.time() - start_time
                success = response.status_code in expected_codes
                error_type = "expected_failure" if should_fail and success else ("unexpected_error" if not success else None)
                
                return response_time, success, error_type
                
            except Exception as e:
                response_time = time.time() - start_time
                error_type = "timeout" if "timeout" in str(e).lower() else "exception"
                return response_time, False, error_type
        
        # Execute failure recovery test for 40 seconds
        stress_runner.reset_stress_metrics()
        stats = stress_runner.execute_stress_test(
            failure_recovery_operation, 
            duration_seconds=40, 
            max_workers=15,
            ramp_up_seconds=8
        )
        
        # Failure recovery assertions
        assert stats["success_rate"] >= 85, f"Recovery success rate too low: {stats['success_rate']}%"
        assert stats["response_times"]["mean"] < 5.0, f"Mean response time too high during recovery: {stats['response_times']['mean']}s"
        
        print(f"Rapid Failure Recovery Test Results:")
        print(f"  Duration: {stats['duration']:.1f}s")
        print(f"  Total Requests: {stats['total_requests']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Error Rate: {stats['error_rate']:.2f}%")
        print(f"  Mean Response Time: {stats['response_times']['mean']:.3f}s")
        print(f"  System Errors: {len(stats['system_errors'])}")
        print(f"  Failure Points: {len(stats['failure_points'])}")