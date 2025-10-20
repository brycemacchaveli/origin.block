"""
Locust-based load testing for advanced performance scenarios.

Provides realistic user behavior simulation and advanced load testing patterns
using the Locust framework for distributed load testing.
"""

from locust import HttpUser, task, between, events
import json
import random
import string
from datetime import datetime, timedelta
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BlockchainFinancialPlatformUser(HttpUser):
    """Simulates a user interacting with the blockchain financial platform."""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def on_start(self):
        """Called when a user starts. Setup user session."""
        self.user_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        self.customer_ids = []
        self.loan_application_ids = []
        
        # Set common headers
        self.client.headers.update({
            "Content-Type": "application/json",
            "X-Actor-ID": f"LOCUST_USER_{self.user_id}"
        })
        
        logger.info(f"User {self.user_id} started session")
    
    @task(3)
    def create_customer(self):
        """Create a new customer (30% of traffic)."""
        customer_data = {
            "first_name": f"LoadTest{random.randint(1000, 9999)}",
            "last_name": f"User{random.randint(100, 999)}",
            "date_of_birth": self._random_date_of_birth(),
            "national_id": f"LOAD{random.randint(10000000, 99999999)}",
            "address": f"{random.randint(1, 9999)} Load Test Street, City {random.randint(1, 100)}",
            "contact_email": f"loadtest{random.randint(1000, 9999)}@example.com",
            "contact_phone": f"+1-555-{random.randint(1000, 9999)}",
            "consent_preferences": {
                "data_sharing": random.choice([True, False]),
                "marketing": random.choice([True, False]),
                "analytics": random.choice([True, False])
            }
        }
        
        with self.client.post(
            "/api/v1/customers",
            json=customer_data,
            catch_response=True
        ) as response:
            if response.status_code == 201:
                response_data = response.json()
                customer_id = response_data.get("customer_id")
                if customer_id:
                    self.customer_ids.append(customer_id)
                response.success()
            elif response.status_code in [400, 422]:
                # Validation errors are expected in load testing
                response.success()
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(2)
    def create_loan_application(self):
        """Create a loan application (20% of traffic)."""
        # Use existing customer or create a random customer ID
        if self.customer_ids:
            customer_id = random.choice(self.customer_ids)
        else:
            customer_id = f"CUST_LOAD_{random.randint(100000, 999999)}"
        
        loan_data = {
            "customer_id": customer_id,
            "requested_amount": random.uniform(5000, 100000),
            "loan_type": random.choice(["PERSONAL", "MORTGAGE", "AUTO", "BUSINESS"]),
            "introducer_id": f"INTRO_LOAD_{random.randint(1000, 9999)}",
            "additional_info": {
                "purpose": random.choice([
                    "Home improvement", "Debt consolidation", "Business expansion",
                    "Vehicle purchase", "Education", "Medical expenses"
                ]),
                "employment_status": random.choice(["Full-time", "Part-time", "Self-employed", "Unemployed"]),
                "annual_income": random.uniform(30000, 150000)
            }
        }
        
        with self.client.post(
            "/api/v1/loans/applications",
            json=loan_data,
            catch_response=True
        ) as response:
            if response.status_code == 201:
                response_data = response.json()
                loan_id = response_data.get("loan_application_id")
                if loan_id:
                    self.loan_application_ids.append(loan_id)
                response.success()
            elif response.status_code in [400, 422]:
                # Validation errors are expected in load testing
                response.success()
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(4)
    def get_customer(self):
        """Retrieve customer information (40% of traffic)."""
        if self.customer_ids:
            customer_id = random.choice(self.customer_ids)
        else:
            # Use a random customer ID that might not exist
            customer_id = f"CUST_LOAD_{random.randint(100000, 999999)}"
        
        with self.client.get(
            f"/api/v1/customers/{customer_id}",
            catch_response=True
        ) as response:
            if response.status_code in [200, 404]:
                # Both found and not found are acceptable
                response.success()
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(2)
    def get_loan_applications(self):
        """Retrieve loan applications (20% of traffic)."""
        params = {
            "limit": random.randint(5, 20),
            "offset": random.randint(0, 100)
        }
        
        # Sometimes filter by status
        if random.random() < 0.3:
            params["status"] = random.choice(["SUBMITTED", "UNDERWRITING", "APPROVED", "REJECTED"])
        
        with self.client.get(
            "/api/v1/loans/applications",
            params=params,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(1)
    def get_compliance_events(self):
        """Retrieve compliance events (10% of traffic)."""
        params = {
            "limit": random.randint(10, 50),
            "offset": random.randint(0, 200)
        }
        
        # Sometimes filter by event type
        if random.random() < 0.4:
            params["event_type"] = random.choice(["AML_CHECK", "KYC_VERIFICATION", "SANCTION_SCREENING"])
        
        with self.client.get(
            "/api/v1/compliance/events",
            params=params,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(1)
    def update_loan_status(self):
        """Update loan application status (10% of traffic)."""
        if not self.loan_application_ids:
            return
        
        loan_id = random.choice(self.loan_application_ids)
        new_status = random.choice(["UNDERWRITING", "APPROVED", "REJECTED"])
        
        update_data = {
            "status": new_status,
            "notes": f"Status updated by load test user {self.user_id}"
        }
        
        with self.client.put(
            f"/api/v1/loans/applications/{loan_id}/status",
            json=update_data,
            catch_response=True
        ) as response:
            if response.status_code in [200, 404, 400]:
                # Accept various responses during load testing
                response.success()
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    def _random_date_of_birth(self):
        """Generate a random date of birth."""
        start_date = datetime(1950, 1, 1)
        end_date = datetime(2000, 12, 31)
        
        time_between = end_date - start_date
        days_between = time_between.days
        random_days = random.randrange(days_between)
        
        random_date = start_date + timedelta(days=random_days)
        return random_date.strftime("%Y-%m-%dT00:00:00")


class HighVolumeUser(BlockchainFinancialPlatformUser):
    """Simulates high-volume users with more aggressive patterns."""
    
    wait_time = between(0.1, 0.5)  # Much shorter wait times
    
    @task(5)
    def rapid_customer_creation(self):
        """Rapid customer creation for high-volume testing."""
        self.create_customer()
    
    @task(3)
    def rapid_loan_applications(self):
        """Rapid loan application creation."""
        self.create_loan_application()
    
    @task(2)
    def batch_customer_lookup(self):
        """Perform multiple customer lookups in sequence."""
        for _ in range(random.randint(3, 8)):
            self.get_customer()
            time.sleep(0.05)  # Very short delay between requests


class ComplianceOfficerUser(HttpUser):
    """Simulates compliance officer behavior patterns."""
    
    wait_time = between(2, 8)  # Longer wait times, more thoughtful usage
    
    def on_start(self):
        """Setup compliance officer session."""
        self.user_id = f"COMPLIANCE_{random.randint(1000, 9999)}"
        self.client.headers.update({
            "Content-Type": "application/json",
            "X-Actor-ID": f"COMPLIANCE_OFFICER_{self.user_id}"
        })
    
    @task(4)
    def review_compliance_events(self):
        """Review compliance events (primary task)."""
        params = {
            "limit": random.randint(20, 100),
            "event_type": random.choice(["AML_CHECK", "KYC_VERIFICATION", "SANCTION_SCREENING"]),
            "start_date": (datetime.utcnow() - timedelta(days=7)).isoformat(),
            "end_date": datetime.utcnow().isoformat()
        }
        
        with self.client.get(
            "/api/v1/compliance/events",
            params=params,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Compliance events request failed: {response.status_code}")
    
    @task(2)
    def generate_compliance_report(self):
        """Generate compliance reports."""
        report_params = {
            "report_type": random.choice(["AML_SUMMARY", "KYC_STATUS", "VIOLATION_REPORT"]),
            "start_date": (datetime.utcnow() - timedelta(days=30)).isoformat(),
            "end_date": datetime.utcnow().isoformat(),
            "format": random.choice(["JSON", "CSV"])
        }
        
        with self.client.get(
            "/api/v1/compliance/reports",
            params=report_params,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Compliance report request failed: {response.status_code}")
    
    @task(1)
    def audit_customer_records(self):
        """Audit customer records for compliance."""
        # Simulate auditing random customers
        customer_id = f"CUST_AUDIT_{random.randint(100000, 999999)}"
        
        with self.client.get(
            f"/api/v1/customers/{customer_id}/audit",
            catch_response=True
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Customer audit request failed: {response.status_code}")


# Event handlers for custom metrics and logging
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, context, **kwargs):
    """Log request details for analysis."""
    if exception:
        logger.error(f"Request failed: {request_type} {name} - {exception}")
    elif response_time > 5000:  # Log slow requests (>5 seconds)
        logger.warning(f"Slow request: {request_type} {name} - {response_time}ms")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when the test starts."""
    logger.info("Load test started")
    logger.info(f"Target host: {environment.host}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when the test stops."""
    logger.info("Load test completed")
    
    # Log final statistics
    stats = environment.stats
    logger.info(f"Total requests: {stats.total.num_requests}")
    logger.info(f"Total failures: {stats.total.num_failures}")
    logger.info(f"Average response time: {stats.total.avg_response_time:.2f}ms")
    logger.info(f"Requests per second: {stats.total.current_rps:.2f}")


# Custom load test scenarios
class StressTestUser(BlockchainFinancialPlatformUser):
    """User class for stress testing scenarios."""
    
    wait_time = between(0.01, 0.1)  # Very aggressive timing
    
    @task
    def stress_test_operations(self):
        """Perform stress test operations."""
        # Randomly choose an operation to stress test
        operations = [
            self.create_customer,
            self.create_loan_application,
            self.get_customer,
            self.get_compliance_events
        ]
        
        operation = random.choice(operations)
        operation()


if __name__ == "__main__":
    """
    Run locust load tests from command line:
    
    # Basic load test
    locust -f locust_load_tests.py --host=http://localhost:8000
    
    # Headless mode with specific parameters
    locust -f locust_load_tests.py --host=http://localhost:8000 --users 50 --spawn-rate 5 --run-time 300s --headless
    
    # Stress test
    locust -f locust_load_tests.py StressTestUser --host=http://localhost:8000 --users 100 --spawn-rate 10 --run-time 600s --headless
    
    # Compliance officer simulation
    locust -f locust_load_tests.py ComplianceOfficerUser --host=http://localhost:8000 --users 10 --spawn-rate 2 --run-time 1800s --headless
    """
    print("Locust load test configuration loaded.")
    print("Use 'locust -f locust_load_tests.py --host=http://localhost:8000' to start the test.")