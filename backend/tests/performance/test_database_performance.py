"""
Database performance testing.

Tests database operations under various load conditions including
concurrent connections, large data volumes, and complex queries.
"""

import pytest
import asyncio
import time
import statistics
import psutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple
import json
from datetime import datetime, timedelta
import random
import string

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from main import app
from shared.database import get_db, Base
from shared.config import settings
from tests.integration.mock_infrastructure import IntegrationTestMockManager


class DatabasePerformanceTester:
    """Manages database performance testing and metrics collection."""
    
    def __init__(self, client: TestClient):
        self.client = client
        self.mock_manager = IntegrationTestMockManager()
        
        # Create test database engine
        self.test_engine = create_engine(
            "sqlite:///./test_performance.db",
            connect_args={"check_same_thread": False}
        )
        self.TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.test_engine)
        
        self.metrics = {
            "query_times": [],
            "insert_times": [],
            "update_times": [],
            "delete_times": [],
            "connection_times": [],
            "memory_usage": [],
            "cpu_usage": [],
            "success_count": 0,
            "error_count": 0,
            "database_errors": []
        }
    
    def setup_test_database(self):
        """Setup test database with sample data."""
        Base.metadata.create_all(bind=self.test_engine)
        
        # Insert sample data for performance testing
        with self.TestSessionLocal() as session:
            # Create sample customers
            for i in range(1000):
                customer_data = {
                    "customer_id": f"PERF_CUST_{i:06d}",
                    "first_name": f"PerfTest{i}",
                    "last_name": "Customer",
                    "national_id": f"PERF{i:08d}",
                    "contact_email": f"perf{i}@example.com",
                    "created_at": datetime.utcnow() - timedelta(days=random.randint(1, 365))
                }
                
                # Insert via raw SQL for performance
                session.execute(text("""
                    INSERT OR IGNORE INTO customers 
                    (customer_id, first_name, last_name, national_id, contact_email, created_at)
                    VALUES (:customer_id, :first_name, :last_name, :national_id, :contact_email, :created_at)
                """), customer_data)
            
            session.commit()
    
    def cleanup_test_database(self):
        """Cleanup test database."""
        Base.metadata.drop_all(bind=self.test_engine)
    
    def reset_metrics(self):
        """Reset database performance metrics."""
        self.metrics = {
            "query_times": [],
            "insert_times": [],
            "update_times": [],
            "delete_times": [],
            "connection_times": [],
            "memory_usage": [],
            "cpu_usage": [],
            "success_count": 0,
            "error_count": 0,
            "database_errors": []
        }
    
    def record_database_operation(self, 
                                operation_type: str,
                                operation_time: float, 
                                success: bool, 
                                error: str = None):
        """Record database operation metrics."""
        if operation_type in self.metrics:
            self.metrics[operation_type].append(operation_time)
        
        # Record system metrics
        self.metrics["memory_usage"].append(psutil.virtual_memory().percent)
        self.metrics["cpu_usage"].append(psutil.cpu_percent())
        
        if success:
            self.metrics["success_count"] += 1
        else:
            self.metrics["error_count"] += 1
            if error:
                self.metrics["database_errors"].append(error)
    
    def calculate_database_statistics(self, duration: float) -> Dict[str, Any]:
        """Calculate database performance statistics."""
        all_operations = (
            self.metrics["query_times"] + 
            self.metrics["insert_times"] + 
            self.metrics["update_times"] + 
            self.metrics["delete_times"]
        )
        
        if not all_operations:
            return {"error": "No operations recorded"}
        
        total_operations = len(all_operations)
        
        stats = {
            "total_operations": total_operations,
            "successful_operations": self.metrics["success_count"],
            "failed_operations": self.metrics["error_count"],
            "success_rate": (self.metrics["success_count"] / total_operations) * 100 if total_operations > 0 else 0,
            "operations_per_second": total_operations / duration,
            "query_performance": self._calculate_operation_stats(self.metrics["query_times"]),
            "insert_performance": self._calculate_operation_stats(self.metrics["insert_times"]),
            "update_performance": self._calculate_operation_stats(self.metrics["update_times"]),
            "delete_performance": self._calculate_operation_stats(self.metrics["delete_times"]),
            "system_metrics": {
                "avg_memory_usage": statistics.mean(self.metrics["memory_usage"]) if self.metrics["memory_usage"] else 0,
                "max_memory_usage": max(self.metrics["memory_usage"]) if self.metrics["memory_usage"] else 0,
                "avg_cpu_usage": statistics.mean(self.metrics["cpu_usage"]) if self.metrics["cpu_usage"] else 0,
                "max_cpu_usage": max(self.metrics["cpu_usage"]) if self.metrics["cpu_usage"] else 0
            },
            "database_errors": self.metrics["database_errors"][:10]
        }
        
        return stats
    
    def _calculate_operation_stats(self, times: List[float]) -> Dict[str, float]:
        """Calculate statistics for a specific operation type."""
        if not times:
            return {"count": 0}
        
        return {
            "count": len(times),
            "min": min(times),
            "max": max(times),
            "mean": statistics.mean(times),
            "median": statistics.median(times),
            "p95": self._percentile(times, 95),
            "p99": self._percentile(times, 99)
        }
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of operation times."""
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def concurrent_database_operations(self, 
                                     operation_func, 
                                     num_operations: int, 
                                     max_workers: int = 10) -> Dict[str, Any]:
        """Execute concurrent database operations."""
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all operations
            futures = [executor.submit(operation_func, i) for i in range(num_operations)]
            
            # Collect results
            for future in as_completed(futures):
                try:
                    operation_type, operation_time, success, error = future.result()
                    self.record_database_operation(operation_type, operation_time, success, error)
                except Exception as e:
                    self.record_database_operation("query_times", 0, False, str(e))
        
        duration = time.time() - start_time
        return self.calculate_database_statistics(duration)


@pytest.fixture
def db_tester():
    """Fixture providing database performance tester."""
    client = TestClient(app)
    tester = DatabasePerformanceTester(client)
    
    # Setup test database
    tester.setup_test_database()
    
    # Setup mocks
    with tester.mock_manager.mock_all_services():
        yield tester
    
    # Cleanup
    tester.cleanup_test_database()


class TestDatabasePerformance:
    """Test database performance under various load conditions."""
    
    def test_concurrent_read_performance(self, db_tester):
        """Test database read performance under concurrent load."""
        
        def read_operation(operation_id: int) -> Tuple[str, float, bool, str]:
            """Execute database read operation and measure performance."""
            
            start_time = time.time()
            try:
                # Test customer lookup via API (which hits database)
                customer_id = f"PERF_CUST_{operation_id % 1000:06d}"
                response = db_tester.client.get(
                    f"/api/v1/customers/{customer_id}",
                    headers={"X-Actor-ID": "DB_PERF_TEST_READER"}
                )
                
                operation_time = time.time() - start_time
                success = response.status_code in [200, 404]  # Both are valid responses
                error = None if success else f"HTTP {response.status_code}: {response.text}"
                
                return "query_times", operation_time, success, error
                
            except Exception as e:
                operation_time = time.time() - start_time
                return "query_times", operation_time, False, str(e)
        
        # Test with 100 concurrent read operations
        db_tester.reset_metrics()
        stats = db_tester.concurrent_database_operations(read_operation, 100, 20)
        
        # Read performance assertions
        assert stats["success_rate"] >= 95, f"Read success rate too low: {stats['success_rate']}%"
        assert stats["operations_per_second"] >= 50, f"Read throughput too low: {stats['operations_per_second']} ops/sec"
        assert stats["query_performance"]["mean"] < 0.5, f"Mean query time too high: {stats['query_performance']['mean']}s"
        assert stats["query_performance"]["p95"] < 1.0, f"95th percentile too high: {stats['query_performance']['p95']}s"
        
        print(f"Concurrent Read Performance Results:")
        print(f"  Total Operations: {stats['total_operations']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Throughput: {stats['operations_per_second']:.2f} ops/sec")
        print(f"  Mean Query Time: {stats['query_performance']['mean']:.3f}s")
        print(f"  95th Percentile: {stats['query_performance']['p95']:.3f}s")
        print(f"  Max Memory Usage: {stats['system_metrics']['max_memory_usage']:.1f}%")
    
    def test_concurrent_write_performance(self, db_tester):
        """Test database write performance under concurrent load."""
        
        def write_operation(operation_id: int) -> Tuple[str, float, bool, str]:
            """Execute database write operation and measure performance."""
            
            customer_data = {
                "first_name": f"WriteTest{operation_id}",
                "last_name": "Customer",
                "date_of_birth": "1985-06-15T00:00:00",
                "national_id": f"WRITE{operation_id:08d}",
                "address": f"123 Write Test St #{operation_id}",
                "contact_email": f"writetest{operation_id}@example.com",
                "contact_phone": f"+1-555-{operation_id:04d}",
                "consent_preferences": {
                    "data_sharing": True,
                    "marketing": False,
                    "analytics": True
                }
            }
            
            start_time = time.time()
            try:
                response = db_tester.client.post(
                    "/api/v1/customers",
                    json=customer_data,
                    headers={"X-Actor-ID": "DB_PERF_TEST_WRITER"}
                )
                
                operation_time = time.time() - start_time
                success = response.status_code == 201
                error = None if success else f"HTTP {response.status_code}: {response.text}"
                
                return "insert_times", operation_time, success, error
                
            except Exception as e:
                operation_time = time.time() - start_time
                return "insert_times", operation_time, False, str(e)
        
        # Test with 50 concurrent write operations
        db_tester.reset_metrics()
        stats = db_tester.concurrent_database_operations(write_operation, 50, 10)
        
        # Write performance assertions
        assert stats["success_rate"] >= 90, f"Write success rate too low: {stats['success_rate']}%"
        assert stats["operations_per_second"] >= 20, f"Write throughput too low: {stats['operations_per_second']} ops/sec"
        assert stats["insert_performance"]["mean"] < 1.0, f"Mean insert time too high: {stats['insert_performance']['mean']}s"
        assert stats["insert_performance"]["p95"] < 2.0, f"95th percentile too high: {stats['insert_performance']['p95']}s"
        
        print(f"Concurrent Write Performance Results:")
        print(f"  Total Operations: {stats['total_operations']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Throughput: {stats['operations_per_second']:.2f} ops/sec")
        print(f"  Mean Insert Time: {stats['insert_performance']['mean']:.3f}s")
        print(f"  95th Percentile: {stats['insert_performance']['p95']:.3f}s")
        print(f"  Max CPU Usage: {stats['system_metrics']['max_cpu_usage']:.1f}%")
    
    def test_mixed_database_workload(self, db_tester):
        """Test mixed database workload performance."""
        
        def mixed_operation(operation_id: int) -> Tuple[str, float, bool, str]:
            """Execute mixed database operations and measure performance."""
            
            # 70% reads, 30% writes
            is_read = operation_id % 10 < 7
            
            if is_read:
                # Read operation
                start_time = time.time()
                try:
                    customer_id = f"PERF_CUST_{operation_id % 1000:06d}"
                    response = db_tester.client.get(
                        f"/api/v1/customers/{customer_id}",
                        headers={"X-Actor-ID": "DB_MIXED_TEST_READER"}
                    )
                    
                    operation_time = time.time() - start_time
                    success = response.status_code in [200, 404]
                    error = None if success else f"HTTP {response.status_code}: {response.text}"
                    
                    return "query_times", operation_time, success, error
                    
                except Exception as e:
                    operation_time = time.time() - start_time
                    return "query_times", operation_time, False, str(e)
            else:
                # Write operation
                customer_data = {
                    "first_name": f"MixedTest{operation_id}",
                    "last_name": "Customer",
                    "date_of_birth": "1985-06-15T00:00:00",
                    "national_id": f"MIXED{operation_id:08d}",
                    "address": f"123 Mixed Test St #{operation_id}",
                    "contact_email": f"mixedtest{operation_id}@example.com",
                    "contact_phone": f"+1-555-{operation_id:04d}",
                    "consent_preferences": {"data_sharing": True}
                }
                
                start_time = time.time()
                try:
                    response = db_tester.client.post(
                        "/api/v1/customers",
                        json=customer_data,
                        headers={"X-Actor-ID": "DB_MIXED_TEST_WRITER"}
                    )
                    
                    operation_time = time.time() - start_time
                    success = response.status_code == 201
                    error = None if success else f"HTTP {response.status_code}: {response.text}"
                    
                    return "insert_times", operation_time, success, error
                    
                except Exception as e:
                    operation_time = time.time() - start_time
                    return "insert_times", operation_time, False, str(e)
        
        # Test with 80 mixed operations
        db_tester.reset_metrics()
        stats = db_tester.concurrent_database_operations(mixed_operation, 80, 15)
        
        # Mixed workload assertions
        assert stats["success_rate"] >= 90, f"Mixed workload success rate too low: {stats['success_rate']}%"
        assert stats["operations_per_second"] >= 30, f"Mixed workload throughput too low: {stats['operations_per_second']} ops/sec"
        
        print(f"Mixed Database Workload Results:")
        print(f"  Total Operations: {stats['total_operations']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Throughput: {stats['operations_per_second']:.2f} ops/sec")
        print(f"  Read Operations: {stats['query_performance']['count']}")
        print(f"  Write Operations: {stats['insert_performance']['count']}")
        print(f"  Mean Read Time: {stats['query_performance']['mean']:.3f}s")
        print(f"  Mean Write Time: {stats['insert_performance']['mean']:.3f}s")
        print(f"  Avg Memory Usage: {stats['system_metrics']['avg_memory_usage']:.1f}%")
    
    def test_large_dataset_performance(self, db_tester):
        """Test database performance with large datasets."""
        
        def large_dataset_operation(operation_id: int) -> Tuple[str, float, bool, str]:
            """Execute operations on large datasets and measure performance."""
            
            start_time = time.time()
            try:
                # Query for compliance events (potentially large result set)
                response = db_tester.client.get(
                    "/api/v1/compliance/events",
                    params={
                        "limit": 100,
                        "offset": operation_id * 10,
                        "event_type": "AML_CHECK"
                    },
                    headers={"X-Actor-ID": "DB_LARGE_TEST_READER"}
                )
                
                operation_time = time.time() - start_time
                success = response.status_code == 200
                error = None if success else f"HTTP {response.status_code}: {response.text}"
                
                return "query_times", operation_time, success, error
                
            except Exception as e:
                operation_time = time.time() - start_time
                return "query_times", operation_time, False, str(e)
        
        # Test with 30 large dataset operations
        db_tester.reset_metrics()
        stats = db_tester.concurrent_database_operations(large_dataset_operation, 30, 8)
        
        # Large dataset assertions
        assert stats["success_rate"] >= 95, f"Large dataset success rate too low: {stats['success_rate']}%"
        assert stats["operations_per_second"] >= 10, f"Large dataset throughput too low: {stats['operations_per_second']} ops/sec"
        assert stats["query_performance"]["mean"] < 2.0, f"Mean large query time too high: {stats['query_performance']['mean']}s"
        
        print(f"Large Dataset Performance Results:")
        print(f"  Total Operations: {stats['total_operations']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Throughput: {stats['operations_per_second']:.2f} ops/sec")
        print(f"  Mean Query Time: {stats['query_performance']['mean']:.3f}s")
        print(f"  99th Percentile: {stats['query_performance']['p99']:.3f}s")
        print(f"  Max Memory Usage: {stats['system_metrics']['max_memory_usage']:.1f}%")
    
    def test_connection_pool_performance(self, db_tester):
        """Test database connection pool performance under load."""
        
        def connection_intensive_operation(operation_id: int) -> Tuple[str, float, bool, str]:
            """Execute connection-intensive operations and measure performance."""
            
            start_time = time.time()
            try:
                # Multiple rapid requests to test connection pooling
                responses = []
                for i in range(3):
                    response = db_tester.client.get(
                        f"/api/v1/customers/PERF_CUST_{(operation_id + i) % 1000:06d}",
                        headers={"X-Actor-ID": "DB_CONN_TEST_READER"}
                    )
                    responses.append(response)
                
                operation_time = time.time() - start_time
                success = all(r.status_code in [200, 404] for r in responses)
                error = None if success else "Connection pool error"
                
                return "query_times", operation_time, success, error
                
            except Exception as e:
                operation_time = time.time() - start_time
                return "query_times", operation_time, False, str(e)
        
        # Test with 40 connection-intensive operations
        db_tester.reset_metrics()
        stats = db_tester.concurrent_database_operations(connection_intensive_operation, 40, 12)
        
        # Connection pool assertions
        assert stats["success_rate"] >= 90, f"Connection pool success rate too low: {stats['success_rate']}%"
        assert stats["operations_per_second"] >= 15, f"Connection pool throughput too low: {stats['operations_per_second']} ops/sec"
        
        print(f"Connection Pool Performance Results:")
        print(f"  Total Operations: {stats['total_operations']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Throughput: {stats['operations_per_second']:.2f} ops/sec")
        print(f"  Mean Operation Time: {stats['query_performance']['mean']:.3f}s")
        print(f"  Max CPU Usage: {stats['system_metrics']['max_cpu_usage']:.1f}%")