"""
Comprehensive mock infrastructure for integration tests.

Provides realistic mocks for all external dependencies while maintaining
the full complexity and scope of integration testing scenarios.
"""

import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from unittest.mock import MagicMock, patch
from contextlib import contextmanager

from shared.auth import Actor, Role


class MockFabricGateway:
    """Comprehensive mock for Hyperledger Fabric gateway operations."""
    
    def __init__(self):
        self.transaction_counter = 0
        self.stored_data = {}
        self.transaction_history = []
    
    def invoke_chaincode(self, chaincode_name: str, function_name: str, args: List[str], **kwargs) -> Dict[str, Any]:
        """Mock chaincode invocation with realistic responses."""
        self.transaction_counter += 1
        tx_id = f"tx_{chaincode_name}_{self.transaction_counter:06d}"
        
        # Store transaction for history
        transaction = {
            "transaction_id": tx_id,
            "chaincode_name": chaincode_name,
            "function_name": function_name,
            "args": args,
            "timestamp": datetime.now().isoformat(),
            "status": "SUCCESS"
        }
        self.transaction_history.append(transaction)
        
        # Generate realistic responses based on chaincode and function
        if chaincode_name == "customer":
            return self._handle_customer_chaincode(function_name, args, tx_id)
        elif chaincode_name == "loan":
            return self._handle_loan_chaincode(function_name, args, tx_id)
        elif chaincode_name == "compliance":
            return self._handle_compliance_chaincode(function_name, args, tx_id)
        
        # Default response
        return {
            "transaction_id": tx_id,
            "status": "SUCCESS",
            "payload": json.dumps({"result": "success"})
        }
    
    def query_chaincode(self, chaincode_name: str, function_name: str, args: List[str], **kwargs) -> Dict[str, Any]:
        """Mock chaincode query with realistic responses."""
        
        if chaincode_name == "customer" and function_name == "GetCustomer":
            customer_id = args[0] if args else "CUST_MOCK_001"
            return self._get_customer_data(customer_id)
        elif chaincode_name == "loan" and function_name == "GetLoanApplication":
            loan_id = args[0] if args else "LOAN_MOCK_001"
            return self._get_loan_data(loan_id)
        elif chaincode_name == "compliance" and function_name == "GetComplianceEvents":
            return self._get_compliance_events(args)
        
        # Default query response
        return {
            "status": "SUCCESS",
            "payload": json.dumps({"result": "query_success"})
        }
    
    def _handle_customer_chaincode(self, function_name: str, args: List[str], tx_id: str) -> Dict[str, Any]:
        """Handle customer chaincode operations."""
        if function_name == "CreateCustomer":
            customer_data = json.loads(args[0]) if args else {}
            customer_id = f"CUST_{tx_id.split('_')[-1]}"
            
            # Store customer data
            self.stored_data[customer_id] = {
                **customer_data,
                "customer_id": customer_id,
                "kyc_status": "PENDING",
                "aml_status": "PENDING",
                "creation_date": datetime.now().isoformat()
            }
            
            return {
                "transaction_id": tx_id,
                "status": "SUCCESS",
                "payload": json.dumps({
                    "customer_id": customer_id,
                    "kyc_status": "PENDING",
                    "aml_status": "PENDING"
                })
            }
        
        elif function_name == "UpdateCustomer":
            customer_id = args[0] if args else "CUST_MOCK_001"
            update_data = json.loads(args[1]) if len(args) > 1 else {}
            
            if customer_id in self.stored_data:
                self.stored_data[customer_id].update(update_data)
                self.stored_data[customer_id]["last_updated"] = datetime.now().isoformat()
            
            return {
                "transaction_id": tx_id,
                "status": "SUCCESS",
                "payload": json.dumps({"customer_id": customer_id, "updated": True})
            }
        
        elif function_name == "UpdateConsent":
            customer_id = args[0] if args else "CUST_MOCK_001"
            consent_data = json.loads(args[1]) if len(args) > 1 else {}
            
            if customer_id in self.stored_data:
                self.stored_data[customer_id]["consent_preferences"] = consent_data
                self.stored_data[customer_id]["consent_updated"] = datetime.now().isoformat()
            
            return {
                "transaction_id": tx_id,
                "status": "SUCCESS",
                "payload": json.dumps({"customer_id": customer_id, "consent_updated": True})
            }
        
        return {"transaction_id": tx_id, "status": "SUCCESS", "payload": json.dumps({})}
    
    def _handle_loan_chaincode(self, function_name: str, args: List[str], tx_id: str) -> Dict[str, Any]:
        """Handle loan chaincode operations."""
        if function_name == "SubmitApplication":
            loan_data = json.loads(args[0]) if args else {}
            loan_id = f"LOAN_{tx_id.split('_')[-1]}"
            
            # Store loan data
            self.stored_data[loan_id] = {
                **loan_data,
                "loan_application_id": loan_id,
                "application_status": "SUBMITTED",
                "application_date": datetime.now().isoformat(),
                "status_history": [
                    {
                        "status": "SUBMITTED",
                        "timestamp": datetime.now().isoformat(),
                        "actor_id": loan_data.get("actor_id", "SYSTEM")
                    }
                ]
            }
            
            return {
                "transaction_id": tx_id,
                "status": "SUCCESS",
                "payload": json.dumps({
                    "loan_application_id": loan_id,
                    "customer_id": loan_data.get("customer_id"),
                    "application_status": "SUBMITTED"
                })
            }
        
        elif function_name == "UpdateLoanStatus":
            loan_id = args[0] if args else "LOAN_MOCK_001"
            new_status = args[1] if len(args) > 1 else "UPDATED"
            actor_id = args[2] if len(args) > 2 else "SYSTEM"
            
            if loan_id in self.stored_data:
                self.stored_data[loan_id]["application_status"] = new_status
                self.stored_data[loan_id]["last_updated"] = datetime.now().isoformat()
                
                # Add to status history
                if "status_history" not in self.stored_data[loan_id]:
                    self.stored_data[loan_id]["status_history"] = []
                
                self.stored_data[loan_id]["status_history"].append({
                    "status": new_status,
                    "timestamp": datetime.now().isoformat(),
                    "actor_id": actor_id
                })
            
            return {
                "transaction_id": tx_id,
                "status": "SUCCESS",
                "payload": json.dumps({
                    "loan_application_id": loan_id,
                    "application_status": new_status
                })
            }
        
        elif function_name == "ApproveLoan":
            loan_id = args[0] if args else "LOAN_MOCK_001"
            approval_data = json.loads(args[1]) if len(args) > 1 else {}
            
            if loan_id in self.stored_data:
                self.stored_data[loan_id].update({
                    "application_status": "APPROVED",
                    "approved_amount": approval_data.get("approved_amount"),
                    "approval_date": datetime.now().isoformat(),
                    "approval_conditions": approval_data.get("conditions", [])
                })
            
            return {
                "transaction_id": tx_id,
                "status": "SUCCESS",
                "payload": json.dumps({
                    "loan_application_id": loan_id,
                    "application_status": "APPROVED"
                })
            }
        
        return {"transaction_id": tx_id, "status": "SUCCESS", "payload": json.dumps({})}
    
    def _handle_compliance_chaincode(self, function_name: str, args: List[str], tx_id: str) -> Dict[str, Any]:
        """Handle compliance chaincode operations."""
        if function_name == "RecordComplianceEvent":
            event_data = json.loads(args[0]) if args else {}
            event_id = f"EVENT_{tx_id.split('_')[-1]}"
            
            # Store compliance event
            self.stored_data[event_id] = {
                **event_data,
                "event_id": event_id,
                "timestamp": datetime.now().isoformat(),
                "status": "RECORDED"
            }
            
            return {
                "transaction_id": tx_id,
                "status": "SUCCESS",
                "payload": json.dumps({
                    "event_id": event_id,
                    "status": "RECORDED"
                })
            }
        
        return {"transaction_id": tx_id, "status": "SUCCESS", "payload": json.dumps({})}
    
    def _get_customer_data(self, customer_id: str) -> Dict[str, Any]:
        """Get stored customer data."""
        if customer_id in self.stored_data:
            return {
                "status": "SUCCESS",
                "payload": json.dumps(self.stored_data[customer_id])
            }
        
        # Return default customer data
        return {
            "status": "SUCCESS",
            "payload": json.dumps({
                "customer_id": customer_id,
                "first_name": "Mock",
                "last_name": "Customer",
                "kyc_status": "VERIFIED",
                "aml_status": "CLEARED",
                "creation_date": datetime.now().isoformat()
            })
        }
    
    def _get_loan_data(self, loan_id: str) -> Dict[str, Any]:
        """Get stored loan data."""
        if loan_id in self.stored_data:
            return {
                "status": "SUCCESS",
                "payload": json.dumps(self.stored_data[loan_id])
            }
        
        # Return default loan data
        return {
            "status": "SUCCESS",
            "payload": json.dumps({
                "loan_application_id": loan_id,
                "customer_id": "CUST_MOCK_001",
                "requested_amount": 50000.0,
                "application_status": "SUBMITTED",
                "application_date": datetime.now().isoformat()
            })
        }
    
    def _get_compliance_events(self, args: List[str]) -> Dict[str, Any]:
        """Get compliance events with filtering."""
        # Filter stored compliance events
        events = [data for key, data in self.stored_data.items() 
                 if key.startswith("EVENT_")]
        
        return {
            "status": "SUCCESS",
            "payload": json.dumps(events)
        }


class MockExternalServices:
    """Mock external service providers."""
    
    @staticmethod
    def mock_kyc_provider(customer_id: str, verification_type: str = "STANDARD", **kwargs) -> Dict[str, Any]:
        """Mock KYC identity provider."""
        # Simulate different KYC results based on customer data
        confidence_scores = {
            "STANDARD": 0.85,
            "ENHANCED": 0.95,
            "PREMIUM": 0.98
        }
        
        return {
            "provider_reference": f"kyc_{customer_id}_{datetime.now().timestamp()}",
            "confidence_score": confidence_scores.get(verification_type, 0.85),
            "checks_performed": [
                "document_verification",
                "liveness_check",
                "address_verification" if verification_type != "STANDARD" else None
            ],
            "verification_status": "VERIFIED" if confidence_scores.get(verification_type, 0.85) > 0.8 else "FAILED",
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def mock_credit_check(customer_id: str, loan_amount: float, **kwargs) -> Dict[str, Any]:
        """Mock credit check service."""
        # Simulate credit scores based on loan amount and customer
        base_score = 700
        
        # Adjust score based on loan amount (higher amounts = more scrutiny)
        if loan_amount > 100000:
            base_score -= 50
        elif loan_amount > 50000:
            base_score -= 20
        
        # Add some variation based on customer ID
        customer_hash = int(hashlib.md5(customer_id.encode()).hexdigest()[:8], 16)
        score_variation = (customer_hash % 100) - 50
        final_score = max(300, min(850, base_score + score_variation))
        
        # Determine risk grade and recommendation
        if final_score >= 750:
            risk_grade = "A"
            recommendation = "APPROVE"
        elif final_score >= 700:
            risk_grade = "B+"
            recommendation = "APPROVE"
        elif final_score >= 650:
            risk_grade = "B"
            recommendation = "APPROVE_WITH_CONDITIONS"
        elif final_score >= 600:
            risk_grade = "C"
            recommendation = "MANUAL_REVIEW"
        else:
            risk_grade = "D"
            recommendation = "REJECT"
        
        return {
            "credit_score": final_score,
            "risk_grade": risk_grade,
            "recommendation": recommendation,
            "debt_to_income_ratio": min(0.5, (loan_amount / 100000) * 0.3),
            "credit_history_length": "5+ years",
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def mock_sanction_check(customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock sanction list screening."""
        # Simulate sanction check based on customer name
        full_name = f"{customer_data.get('first_name', '')} {customer_data.get('last_name', '')}".lower()
        
        # Predefined "sanctioned" names for testing
        sanctioned_names = ["sanctioned individual", "blocked person", "test sanctioned"]
        
        is_sanctioned = any(name in full_name for name in sanctioned_names)
        match_score = 0.95 if is_sanctioned else 0.0
        
        return {
            "is_sanctioned": is_sanctioned,
            "match_score": match_score,
            "matched_list": "OFAC" if is_sanctioned else None,
            "matched_entry": full_name if is_sanctioned else None,
            "checked_lists": ["OFAC", "EU", "UN", "HMT"],
            "timestamp": datetime.now().isoformat()
        }


class MockDatabaseModels:
    """Mock database models for testing."""
    
    class MockCustomerModel:
        def __init__(self, **kwargs):
            self.customer_id = kwargs.get('customer_id', 'CUST_MOCK_001')
            self.first_name = kwargs.get('first_name', 'Mock')
            self.last_name = kwargs.get('last_name', 'Customer')
            self.national_id_hash = kwargs.get('national_id_hash', 'mock_hash')
            self.kyc_status = kwargs.get('kyc_status', 'VERIFIED')
            self.aml_status = kwargs.get('aml_status', 'CLEARED')
            self.creation_date = kwargs.get('creation_date', datetime.now())
    
    class MockLoanApplicationModel:
        def __init__(self, **kwargs):
            self.loan_application_id = kwargs.get('loan_application_id', 'LOAN_MOCK_001')
            self.customer_id = kwargs.get('customer_id', 'CUST_MOCK_001')
            self.requested_amount = kwargs.get('requested_amount', 50000.0)
            self.loan_type = kwargs.get('loan_type', 'PERSONAL')
            self.application_status = kwargs.get('application_status', 'SUBMITTED')
            self.application_date = kwargs.get('application_date', datetime.now())


class MockDatabaseUtilities:
    """Mock database utilities for testing."""
    
    def __init__(self):
        self.db_manager = MagicMock()
        self._actors = {}
        self._customers = {}
        self._history = {}
        
        # Mock the session_scope context manager
        @contextmanager
        def mock_session_scope():
            mock_session = MagicMock()
            yield mock_session
        
        self.db_manager.session_scope = mock_session_scope
    
    def get_actor_by_actor_id(self, actor_id: str):
        """Mock get actor by actor ID."""
        if actor_id not in self._actors:
            # Create a mock actor using a simple object instead of SQLAlchemy model
            class MockActor:
                def __init__(self):
                    self.id = 1
                    self.actor_id = actor_id
                    self.actor_type = "Internal_User"
                    self.actor_name = "Test Actor"
                    self.role = "Underwriter"
                    self.is_active = True
                    self.created_at = datetime.now()
                    self.updated_at = datetime.now()
            
            self._actors[actor_id] = MockActor()
        
        return self._actors[actor_id]
    
    def create_actor(self, actor_data: Dict[str, Any]):
        """Mock create actor."""
        actor_count = len(self._actors)
        
        class MockActor:
            def __init__(self):
                self.id = actor_count + 1
                self.actor_id = actor_data.get('actor_id', 'TEST_ACTOR')
                self.actor_type = actor_data.get('actor_type', 'Internal_User')
                self.actor_name = actor_data.get('actor_name', 'Test Actor')
                self.role = actor_data.get('role', 'Underwriter')
                self.is_active = True
                self.created_at = datetime.now()
                self.updated_at = datetime.now()
        
        mock_actor = MockActor()
        self._actors[mock_actor.actor_id] = mock_actor
        return mock_actor
    
    def create_customer(self, customer_data: Dict[str, Any]):
        """Mock create customer."""
        customer_count = len(self._customers)
        customer_id = customer_data.get('customer_id', f'CUST_MOCK_{customer_count + 1:03d}')
        
        class MockCustomer:
            def __init__(self):
                self.id = customer_count + 1
                self.customer_id = customer_id
                self.first_name = customer_data.get('first_name', 'Mock')
                self.last_name = customer_data.get('last_name', 'Customer')
                self.national_id_hash = customer_data.get('national_id_hash', 'mock_hash')
                self.kyc_status = 'PENDING'
                self.aml_status = 'PENDING'
                self.created_at = datetime.now()
                self.updated_at = datetime.now()
        
        mock_customer = MockCustomer()
        self._customers[mock_customer.customer_id] = mock_customer
        return mock_customer
    
    def get_customer_by_customer_id(self, customer_id: str):
        """Mock get customer by customer ID."""
        if customer_id not in self._customers:
            # Create a mock customer if it doesn't exist (for loan validation)
            customer_count = len(self._customers)
            
            class MockCustomer:
                def __init__(self):
                    self.id = customer_count + 1
                    self.customer_id = customer_id
                    self.first_name = "Mock"
                    self.last_name = "Customer"
                    self.national_id_hash = "mock_hash"
                    self.kyc_status = "VERIFIED"
                    self.aml_status = "CLEARED"
                    self.created_at = datetime.now()
                    self.updated_at = datetime.now()
            
            mock_customer = MockCustomer()
            self._customers[customer_id] = mock_customer
        
        return self._customers.get(customer_id)
    
    def get_customer_history(self, customer_id: str):
        """Mock get customer history."""
        return self._history.get(customer_id, [])
    
    def create_loan_application(self, loan_data: Dict[str, Any]):
        """Mock create loan application."""
        loan_count = len(self._customers)  # Use customers count for simplicity
        loan_id = loan_data.get('loan_application_id', f'LOAN_MOCK_{loan_count + 1:03d}')
        
        class MockLoanApplication:
            def __init__(self):
                self.id = loan_count + 1
                self.loan_application_id = loan_id
                self.customer_id = loan_data.get('customer_id', 'CUST_MOCK_001')
                self.requested_amount = loan_data.get('requested_amount', 25000.0)
                self.loan_type = loan_data.get('loan_type', 'PERSONAL')
                self.introducer_id = loan_data.get('introducer_id', 'INTRO_MOCK_001')
                self.application_status = 'SUBMITTED'
                self.application_date = datetime.now()
                self.current_owner_actor_id = loan_data.get('current_owner_actor_id', 1)
                self.approval_amount = None
                self.rejection_reason = None
                self.blockchain_record_hash = None
                self.created_by_actor_id = loan_data.get('created_by_actor_id', 1)
                self.created_at = datetime.now()
                self.updated_at = datetime.now()
        
        mock_loan = MockLoanApplication()
        return mock_loan


class IntegrationTestMockManager:
    """Manages all mocks for integration tests."""
    
    def __init__(self):
        self.fabric_gateway = MockFabricGateway()
        self.external_services = MockExternalServices()
        self.database_utilities = MockDatabaseUtilities()
        self.active_patches = []
    
    @contextmanager
    def mock_all_services(self):
        """Context manager to mock all external services."""
        from main import app
        from shared.auth import require_permissions, require_roles, Permission, Role
        from shared.database import get_db_session
        
        # Create a mock actor for authentication with all permissions
        mock_actor = Actor(
            actor_id="TEST_ACTOR", 
            actor_type="Internal_User", 
            actor_name="Test Actor", 
            role=Role.UNDERWRITER,
            permissions=set(Permission)  # Grant all permissions for testing
        )
        
        # Create mock database session
        mock_db_session = MagicMock()
        
        # Override FastAPI dependencies
        def override_auth():
            return mock_actor
        
        def override_db():
            return mock_db_session
        
        # Store original dependencies
        original_dependencies = app.dependency_overrides.copy()
        
        # Override the base authentication dependency - this will handle all permission checks
        from shared.auth import get_current_user
        app.dependency_overrides[get_current_user] = override_auth
        app.dependency_overrides[get_db_session] = override_db
        
        # Create a mock chaincode client that has the invoke_chaincode method
        mock_chaincode_client = MagicMock()
        
        async def mock_invoke_chaincode(*args, **kwargs):
            return {
                "transaction_id": "mock_tx_123",
                "status": "SUCCESS",
                "payload": json.dumps({"result": "success"})
            }
        
        mock_chaincode_client.invoke_chaincode = mock_invoke_chaincode
        
        # Mock the ChaincodeClient constructor to return our mock
        def mock_chaincode_client_constructor(gateway, chaincode_type):
            return mock_chaincode_client
        
        patches = [
            patch('shared.fabric_gateway.get_fabric_gateway', return_value=self.fabric_gateway),
            patch('shared.fabric_gateway.ChaincodeClient', side_effect=mock_chaincode_client_constructor),
            patch('customer_mastery.api.ChaincodeClient', side_effect=mock_chaincode_client_constructor),
            patch('loan_origination.api.ChaincodeClient', side_effect=mock_chaincode_client_constructor),
            patch('customer_mastery.api._simulate_identity_provider_call', 
                  side_effect=self.external_services.mock_kyc_provider),
            # Remove this patch since we're mocking db_utils instead
            # patch('loan_origination.api._validate_customer_exists', 
            #       return_value=MockDatabaseModels.MockCustomerModel()),
            patch('shared.database.db_utils', self.database_utilities),
            patch('customer_mastery.api.db_utils', self.database_utilities),
            patch('loan_origination.api.db_utils', self.database_utilities),
        ]
        
        # Start all patches
        mocks = {}
        for p in patches:
            mock_obj = p.start()
            mocks[p.attribute] = mock_obj
        
        try:
            yield mocks
        finally:
            # Stop all patches
            for p in patches:
                p.stop()
            
            # Restore original dependencies
            app.dependency_overrides = original_dependencies
    
    def configure_scenario(self, scenario_name: str):
        """Configure mocks for specific test scenarios."""
        if scenario_name == "high_risk_customer":
            # Configure for high-risk customer scenario
            original_credit_check = self.external_services.mock_credit_check
            
            def high_risk_credit_check(*args, **kwargs):
                result = original_credit_check(*args, **kwargs)
                result.update({
                    "credit_score": 580,
                    "risk_grade": "D",
                    "recommendation": "REJECT"
                })
                return result
            
            self.external_services.mock_credit_check = high_risk_credit_check
        
        elif scenario_name == "sanctioned_customer":
            # Configure for sanctioned customer scenario
            original_sanction_check = self.external_services.mock_sanction_check
            
            def sanctioned_check(*args, **kwargs):
                return {
                    "is_sanctioned": True,
                    "match_score": 0.95,
                    "matched_list": "OFAC",
                    "matched_entry": "Test Sanctioned Individual",
                    "checked_lists": ["OFAC", "EU", "UN"],
                    "timestamp": datetime.now().isoformat()
                }
            
            self.external_services.mock_sanction_check = sanctioned_check
        
        elif scenario_name == "kyc_failure":
            # Configure for KYC failure scenario
            original_kyc_provider = self.external_services.mock_kyc_provider
            
            def failed_kyc(*args, **kwargs):
                result = original_kyc_provider(*args, **kwargs)
                result.update({
                    "confidence_score": 0.65,
                    "verification_status": "FAILED"
                })
                return result
            
            self.external_services.mock_kyc_provider = failed_kyc
    
    def reset_scenarios(self):
        """Reset all scenario configurations to defaults."""
        self.external_services = MockExternalServices()
        self.fabric_gateway = MockFabricGateway()
    
    def get_transaction_history(self) -> List[Dict[str, Any]]:
        """Get complete transaction history for verification."""
        return self.fabric_gateway.transaction_history.copy()
    
    def get_stored_data(self, entity_type: Optional[str] = None) -> Dict[str, Any]:
        """Get all stored data, optionally filtered by entity type."""
        if entity_type:
            return {k: v for k, v in self.fabric_gateway.stored_data.items() 
                   if k.startswith(entity_type.upper())}
        return self.fabric_gateway.stored_data.copy()