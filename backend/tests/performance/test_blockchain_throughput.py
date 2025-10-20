"""
Blockchain transaction throughput testing.

Tests the performance of blockchain operations including chaincode invocations,
transaction processing, and event handling under various load conditions.
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
from shared.fabric_gateway import FabricGateway


class BlockchainThroughputTester:
    """Manages blockchain throughput testing and metrics collection."""
    
    def __init__(self, client: TestClient):
        self.client = client
        self.mock_manager = IntegrationTestMockManager()
        self.metrics = {
            "transaction_times": [],
            "chaincode_invocation_times": [],
            "event_processing_times": [],
            "success_count": 0,
            "error_count": 0,
            "blockchain_errors": [],
            "consensus_delays": []
        }
    
    def reset_metrics(self):
        """Reset blockchain performance metrics."""
        self.metrics = {
            "transaction_times": [],
            "chaincode_invocation_times": [],
            "event_processing_times": [],
            "success_count": 0,
            "error_count": 0,
            "blockchain_errors": [],
            "consensus_delays": []
        }
    
    def record_blockchain_transaction(self, 
                                   transaction_time: float, 
                                   chaincode_time: float,
                                   event_time: float,
                                   success: bool, 
                                   error: str = None):
        """Record blockchain transaction metrics."""
        self.metrics["transaction_times"].append(transaction_time)
        self.metrics["chaincode_invocation_times"].append(chaincode_time)
        self.metrics["event_processing_times"].append(event_time)
        
        if success:
            self.metrics["success_count"] += 1
        else:
            self.metrics["error_count"] += 1
            if error:
                self.metrics["blockchain_errors"].append(error)
    
    def calculate_blockchain_statistics(self, duration: float) -> Dict[str, Any]:
        """Calculate blockchain performance statistics."""
        transaction_times = self.metrics["transaction_times"]
        chaincode_times = self.metrics["chaincode_invocation_times"]
        event_times = self.metrics["event_processing_times"]
        
        if not transaction_times:
            return {"error": "No transaction times recorded"}
        
        total_transactions = len(transaction_times)
        
        stats = {
            "total_transactions": total_transactions,
            "successful_transactions": self.metrics["success_count"],
            "failed_transactions": self.metrics["error_count"],
            "success_rate": (self.metrics["success_count"] / total_transactions) * 100,
            "transaction_throughput_tps": total_transactions / duration,
            "transaction_times": {
                "min": min(transaction_times),
                "max": max(transaction_times),
                "mean": statistics.mean(transaction_times),
                "median": statistics.median(transaction_times),
                "p95": self._percentile(transaction_times, 95),
                "p99": self._percentile(transaction_times, 99)
            },
            "chaincode_performance": {
                "min": min(chaincode_times) if chaincode_times else 0,
                "max": max(chaincode_times) if chaincode_times else 0,
                "mean": statistics.mean(chaincode_times) if chaincode_times else 0,
                "median": statistics.median(chaincode_times) if chaincode_times else 0
            },
            "event_processing": {
                "min": min(event_times) if event_times else 0,
                "max": max(event_times) if event_times else 0,
                "mean": statistics.mean(event_times) if event_times else 0,
                "median": statistics.median(event_times) if event_times else 0
            },
            "blockchain_errors": self.metrics["blockchain_errors"][:10]
        }
        
        return stats
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of response times."""
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def concurrent_blockchain_operations(self, 
                                       operation_func, 
                                       num_operations: int, 
                                       max_workers: int = 5) -> Dict[str, Any]:
        """Execute concurrent blockchain operations."""
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all operations
            futures = [executor.submit(operation_func, i) for i in range(num_operations)]
            
            # Collect results
            for future in as_completed(futures):
                try:
                    tx_time, cc_time, event_time, success, error = future.result()
                    self.record_blockchain_transaction(tx_time, cc_time, event_time, success, error)
                except Exception as e:
                    self.record_blockchain_transaction(0, 0, 0, False, str(e))
        
        duration = time.time() - start_time
        return self.calculate_blockchain_statistics(duration)


@pytest.fixture
def blockchain_tester():
    """Fixture providing blockchain throughput tester."""
    client = TestClient(app)
    tester = BlockchainThroughputTester(client)
    
    # Setup mocks
    with tester.mock_manager.mock_all_services():
        yield tester


class TestBlockchainThroughput:
    """Test blockchain transaction throughput and performance."""
    
    def test_customer_chaincode_throughput(self, blockchain_tester):
        """Test Customer chaincode transaction throughput."""
        
        def customer_blockchain_operation(operation_id: int) -> Tuple[float, float, float, bool, str]:
            """Execute customer chaincode operation and measure performance."""
            
            customer_data = {
                "first_name": f"BlockchainTest{operation_id}",
                "last_name": "Customer",
                "date_of_birth": "1985-06-15T00:00:00",
                "national_id": f"BC{operation_id:08d}",
                "address": f"123 Blockchain St #{operation_id}",
                "contact_email": f"blockchain{operation_id}@example.com",
                "contact_phone": f"+1-555-{operation_id:04d}",
                "consent_preferences": {
                    "data_sharing": True,
                    "marketing": False,
                    "analytics": True
                }
            }
            
            # Measure transaction time
            tx_start = time.time()
            try:
                response = blockchain_tester.client.post(
                    "/api/v1/customers",
                    json=customer_data,
                    headers={"X-Actor-ID": "BLOCKCHAIN_TEST_ACTOR"}
                )
                tx_time = time.time() - tx_start
                
                # Simulate chaincode invocation time (mocked)
                cc_time = tx_time * 0.6  # Assume 60% of time is chaincode
                
                # Simulate event processing time (mocked)
                event_time = tx_time * 0.2  # Assume 20% of time is event processing
                
                success = response.status_code == 201
                error = None if success else f"HTTP {response.status_code}: {response.text}"
                
                return tx_time, cc_time, event_time, success, error
                
            except Exception as e:
                tx_time = time.time() - tx_start
                return tx_time, 0, 0, False, str(e)
        
        # Test blockchain throughput with 25 concurrent operations
        blockchain_tester.reset_metrics()
        stats = blockchain_tester.concurrent_blockchain_operations(
            customer_blockchain_operation, 25, 5
        )
        
        # Blockchain throughput assertions
        assert stats["success_rate"] >= 95, f"Blockchain success rate too low: {stats['success_rate']}%"
        assert stats["transaction_throughput_tps"] >= 3, f"Transaction throughput too low: {stats['transaction_throughput_tps']} TPS"
        assert stats["transaction_times"]["mean"] < 5.0, f"Mean transaction time too high: {stats['transaction_times']['mean']}s"
        assert stats["transaction_times"]["p95"] < 10.0, f"95th percentile too high: {stats['transaction_times']['p95']}s"
        
        print(f"Customer Chaincode Throughput Results:")
        print(f"  Total Transactions: {stats['total_transactions']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Throughput: {stats['transaction_throughput_tps']:.2f} TPS")
        print(f"  Mean Transaction Time: {stats['transaction_times']['mean']:.3f}s")
        print(f"  Mean Chaincode Time: {stats['chaincode_performance']['mean']:.3f}s")
    
    def test_loan_chaincode_throughput(self, blockchain_tester):
        """Test Loan chaincode transaction throughput."""
        
        def loan_blockchain_operation(operation_id: int) -> Tuple[float, float, float, bool, str]:
            """Execute loan chaincode operation and measure performance."""
            
            loan_data = {
                "customer_id": f"CUST_BC_{operation_id:06d}",
                "requested_amount": 25000.0 + (operation_id * 100),
                "loan_type": "PERSONAL",
                "introducer_id": f"INTRO_BC_{operation_id}",
                "additional_info": {
                    "purpose": f"Blockchain test loan {operation_id}",
                    "employment_status": "Full-time",
                    "annual_income": 75000.0
                }
            }
            
            # Measure transaction time
            tx_start = time.time()
            try:
                response = blockchain_tester.client.post(
                    "/api/v1/loans/applications",
                    json=loan_data,
                    headers={"X-Actor-ID": "BLOCKCHAIN_TEST_UNDERWRITER"}
                )
                tx_time = time.time() - tx_start
                
                # Simulate chaincode invocation time (mocked)
                cc_time = tx_time * 0.7  # Loan operations are more complex
                
                # Simulate event processing time (mocked)
                event_time = tx_time * 0.15
                
                success = response.status_code == 201
                error = None if success else f"HTTP {response.status_code}: {response.text}"
                
                return tx_time, cc_time, event_time, success, error
                
            except Exception as e:
                tx_time = time.time() - tx_start
                return tx_time, 0, 0, False, str(e)
        
        # Test loan chaincode throughput with 20 concurrent operations
        blockchain_tester.reset_metrics()
        stats = blockchain_tester.concurrent_blockchain_operations(
            loan_blockchain_operation, 20, 4
        )
        
        # Loan chaincode throughput assertions
        assert stats["success_rate"] >= 90, f"Loan chaincode success rate too low: {stats['success_rate']}%"
        assert stats["transaction_throughput_tps"] >= 2, f"Loan transaction throughput too low: {stats['transaction_throughput_tps']} TPS"
        assert stats["transaction_times"]["mean"] < 8.0, f"Mean loan transaction time too high: {stats['transaction_times']['mean']}s"
        
        print(f"Loan Chaincode Throughput Results:")
        print(f"  Total Transactions: {stats['total_transactions']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Throughput: {stats['transaction_throughput_tps']:.2f} TPS")
        print(f"  Mean Transaction Time: {stats['transaction_times']['mean']:.3f}s")
        print(f"  Mean Chaincode Time: {stats['chaincode_performance']['mean']:.3f}s")
    
    def test_compliance_chaincode_throughput(self, blockchain_tester):
        """Test Compliance chaincode transaction throughput."""
        
        def compliance_blockchain_operation(operation_id: int) -> Tuple[float, float, float, bool, str]:
            """Execute compliance chaincode operation and measure performance."""
            
            # Measure transaction time for compliance event recording
            tx_start = time.time()
            try:
                # Simulate compliance event creation via API
                response = blockchain_tester.client.get(
                    "/api/v1/compliance/events",
                    params={"limit": 10, "event_type": "AML_CHECK"},
                    headers={"X-Actor-ID": "BLOCKCHAIN_TEST_COMPLIANCE"}
                )
                tx_time = time.time() - tx_start
                
                # Simulate chaincode invocation time (mocked)
                cc_time = tx_time * 0.5  # Compliance reads are lighter
                
                # Simulate event processing time (mocked)
                event_time = tx_time * 0.1
                
                success = response.status_code == 200
                error = None if success else f"HTTP {response.status_code}: {response.text}"
                
                return tx_time, cc_time, event_time, success, error
                
            except Exception as e:
                tx_time = time.time() - tx_start
                return tx_time, 0, 0, False, str(e)
        
        # Test compliance chaincode throughput with 30 concurrent operations
        blockchain_tester.reset_metrics()
        stats = blockchain_tester.concurrent_blockchain_operations(
            compliance_blockchain_operation, 30, 6
        )
        
        # Compliance chaincode throughput assertions
        assert stats["success_rate"] >= 95, f"Compliance chaincode success rate too low: {stats['success_rate']}%"
        assert stats["transaction_throughput_tps"] >= 5, f"Compliance transaction throughput too low: {stats['transaction_throughput_tps']} TPS"
        assert stats["transaction_times"]["mean"] < 3.0, f"Mean compliance transaction time too high: {stats['transaction_times']['mean']}s"
        
        print(f"Compliance Chaincode Throughput Results:")
        print(f"  Total Transactions: {stats['total_transactions']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Throughput: {stats['transaction_throughput_tps']:.2f} TPS")
        print(f"  Mean Transaction Time: {stats['transaction_times']['mean']:.3f}s")
        print(f"  Mean Chaincode Time: {stats['chaincode_performance']['mean']:.3f}s")
    
    def test_mixed_chaincode_workload(self, blockchain_tester):
        """Test mixed chaincode workload performance."""
        
        def mixed_chaincode_operation(operation_id: int) -> Tuple[float, float, float, bool, str]:
            """Execute mixed chaincode operations and measure performance."""
            
            # Rotate between different chaincode operations
            operation_type = operation_id % 3
            
            tx_start = time.time()
            try:
                if operation_type == 0:
                    # Customer operation
                    response = blockchain_tester.client.post(
                        "/api/v1/customers",
                        json={
                            "first_name": f"Mixed{operation_id}",
                            "last_name": "Test",
                            "date_of_birth": "1985-06-15T00:00:00",
                            "national_id": f"MX{operation_id:08d}",
                            "address": f"123 Mixed St #{operation_id}",
                            "contact_email": f"mixed{operation_id}@example.com",
                            "contact_phone": f"+1-555-{operation_id:04d}",
                            "consent_preferences": {"data_sharing": True}
                        },
                        headers={"X-Actor-ID": "MIXED_BLOCKCHAIN_ACTOR"}
                    )
                    expected_status = 201
                    cc_ratio = 0.6
                    
                elif operation_type == 1:
                    # Loan operation
                    response = blockchain_tester.client.post(
                        "/api/v1/loans/applications",
                        json={
                            "customer_id": f"CUST_MX_{operation_id}",
                            "requested_amount": 30000.0,
                            "loan_type": "PERSONAL",
                            "introducer_id": f"INTRO_MX_{operation_id}"
                        },
                        headers={"X-Actor-ID": "MIXED_BLOCKCHAIN_UNDERWRITER"}
                    )
                    expected_status = 201
                    cc_ratio = 0.7
                    
                else:
                    # Compliance operation
                    response = blockchain_tester.client.get(
                        "/api/v1/compliance/events",
                        params={"limit": 5},
                        headers={"X-Actor-ID": "MIXED_BLOCKCHAIN_COMPLIANCE"}
                    )
                    expected_status = 200
                    cc_ratio = 0.5
                
                tx_time = time.time() - tx_start
                cc_time = tx_time * cc_ratio
                event_time = tx_time * 0.15
                
                success = response.status_code == expected_status
                error = None if success else f"HTTP {response.status_code}: {response.text}"
                
                return tx_time, cc_time, event_time, success, error
                
            except Exception as e:
                tx_time = time.time() - tx_start
                return tx_time, 0, 0, False, str(e)
        
        # Test mixed chaincode workload with 35 concurrent operations
        blockchain_tester.reset_metrics()
        stats = blockchain_tester.concurrent_blockchain_operations(
            mixed_chaincode_operation, 35, 7
        )
        
        # Mixed workload assertions
        assert stats["success_rate"] >= 85, f"Mixed chaincode success rate too low: {stats['success_rate']}%"
        assert stats["transaction_throughput_tps"] >= 3, f"Mixed transaction throughput too low: {stats['transaction_throughput_tps']} TPS"
        assert stats["transaction_times"]["mean"] < 6.0, f"Mean mixed transaction time too high: {stats['transaction_times']['mean']}s"
        
        print(f"Mixed Chaincode Workload Results:")
        print(f"  Total Transactions: {stats['total_transactions']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Throughput: {stats['transaction_throughput_tps']:.2f} TPS")
        print(f"  Mean Transaction Time: {stats['transaction_times']['mean']:.3f}s")
        print(f"  Mean Chaincode Time: {stats['chaincode_performance']['mean']:.3f}s")
        print(f"  Mean Event Processing Time: {stats['event_processing']['mean']:.3f}s")