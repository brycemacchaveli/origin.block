"""
Comprehensive unit tests for loan history and audit functionality.

Tests cover history retrieval, pagination, filtering, audit reports,
and blockchain integrity verification.
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import status

from main import app
from shared.auth import Actor, ActorType, Role, Permission, jwt_manager
from shared.database import (
    LoanApplicationModel, 
    LoanApplicationHistoryModel,
    CustomerModel,
    ActorModel,
    DatabaseUtilities
)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_underwriter():
    """Create test actor with history read permissions."""
    from shared.auth import actor_manager
    
    actor = Actor(
        actor_id="underwriter_001",
        actor_type=ActorType.INTERNAL_USER,
        actor_name="Test Underwriter",
        role=Role.UNDERWRITER,
        permissions={
            Permission.READ_LOAN_APPLICATION,
            Permission.READ_LOAN_HISTORY
        }
    )
    
    actor_manager._actors[actor.actor_id] = actor
    return actor


@pytest.fixture
def underwriter_auth_headers(test_underwriter):
    """Create authentication headers for underwriter requests."""
    token = jwt_manager.create_access_token(test_underwriter)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_loan():
    """Create a mock loan application."""
    loan = Mock(spec=LoanApplicationModel)
    loan.id = 1
    loan.loan_application_id = "LOAN_TEST001"
    loan.customer_id = 1
    loan.application_date = datetime.utcnow()
    loan.requested_amount = 50000.0
    loan.loan_type = "PERSONAL"
    loan.application_status = "APPROVED"
    loan.introducer_id = "INTRO_001"
    loan.current_owner_actor_id = 1
    loan.approval_amount = 45000.0
    loan.created_at = datetime.utcnow()
    loan.updated_at = datetime.utcnow()
    return loan


@pytest.fixture
def mock_customer():
    """Create a mock customer."""
    customer = Mock(spec=CustomerModel)
    customer.id = 1
    customer.customer_id = "CUST_TEST001"
    customer.first_name = "John"
    customer.last_name = "Doe"
    customer.created_by_actor_id = 1
    customer.created_at = datetime.utcnow()
    customer.updated_at = datetime.utcnow()
    return customer


@pytest.fixture
def mock_history_records():
    """Create mock history records."""
    base_time = datetime.utcnow()
    return [
        Mock(
            id=1,
            loan_application_id=1,
            change_type="STATUS_CHANGE",
            previous_status="SUBMITTED",
            new_status="UNDERWRITING",
            field_name="application_status",
            old_value="SUBMITTED",
            new_value="UNDERWRITING",
            changed_by_actor_id=1,
            blockchain_transaction_id="TX_001",
            timestamp=base_time - timedelta(days=2),
            notes="Status updated to underwriting"
        ),
        Mock(
            id=2,
            loan_application_id=1,
            change_type="APPROVAL",
            previous_status="UNDERWRITING",
            new_status="APPROVED",
            field_name="approval_amount",
            old_value="50000.0",
            new_value="45000.0",
            changed_by_actor_id=2,
            blockchain_transaction_id="TX_002",
            timestamp=base_time - timedelta(days=1),
            notes="Loan approved with reduced amount"
        )
    ]


class TestLoanHistoryRetrieval:
    """Test cases for basic loan history retrieval."""
    
    @patch('loan_origination.api.db_utils')
    def test_get_loan_history_success(self, mock_db_utils, client, underwriter_auth_headers, 
                                    mock_loan, mock_history_records):
        """Test successful loan history retrieval."""
        mock_db_utils.get_loan_by_loan_id.return_value = mock_loan
        mock_db_utils.get_loan_history.return_value = mock_history_records
        
        response = client.get(
            "/api/v1/loans/LOAN_TEST001/history",
            headers=underwriter_auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert len(data["items"]) == 2
        assert data["total"] == 2
        assert data["items"][0]["change_type"] == "STATUS_CHANGE"
        assert data["items"][1]["change_type"] == "APPROVAL"
        
        mock_db_utils.get_loan_history.assert_called_once_with("LOAN_TEST001")
    
    @patch('loan_origination.api.db_utils')
    def test_get_loan_history_not_found(self, mock_db_utils, client, underwriter_auth_headers):
        """Test loan history retrieval when loan doesn't exist."""
        mock_db_utils.get_loan_by_loan_id.return_value = None
        
        response = client.get(
            "/api/v1/loans/NONEXISTENT/history",
            headers=underwriter_auth_headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_get_loan_history_unauthorized(self, client):
        """Test loan history retrieval without authentication."""
        response = client.get("/api/v1/loans/LOAN_TEST001/history")
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestLoanHistoryPagination:
    """Test cases for paginated loan history functionality."""
    
    @patch('loan_origination.api.db_utils')
    def test_get_loan_history_with_pagination(self, mock_db_utils, client, underwriter_auth_headers,
                                            mock_loan, mock_history_records):
        """Test loan history with pagination parameters."""
        mock_db_utils.get_loan_by_loan_id.return_value = mock_loan
        mock_db_utils.get_loan_history_paginated.return_value = (mock_history_records[:1], 2)
        
        response = client.get(
            "/api/v1/loans/LOAN_TEST001/history?page=1&page_size=1",
            headers=underwriter_auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 2
        assert data["page"] == 1
        assert data["page_size"] == 1
        assert data["total_pages"] == 2
        assert data["has_next"] == True
        assert data["has_previous"] == False
        assert len(data["items"]) == 1
    
    def test_get_loan_history_invalid_pagination(self, client, underwriter_auth_headers):
        """Test loan history with invalid pagination parameters."""
        # Test invalid page
        response = client.get(
            "/api/v1/loans/LOAN_TEST001/history?page=0",
            headers=underwriter_auth_headers
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        
        # Test invalid page_size
        response = client.get(
            "/api/v1/loans/LOAN_TEST001/history?page_size=2000",
            headers=underwriter_auth_headers
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestLoanHistoryFiltering:
    """Test cases for loan history filtering."""
    
    @patch('loan_origination.api.db_utils')
    def test_get_loan_history_with_filters(self, mock_db_utils, client, underwriter_auth_headers,
                                         mock_loan, mock_history_records):
        """Test loan history with filtering parameters."""
        mock_db_utils.get_loan_by_loan_id.return_value = mock_loan
        mock_db_utils.get_loan_history_paginated.return_value = (mock_history_records[:1], 1)
        
        response = client.get(
            "/api/v1/loans/LOAN_TEST001/history?change_type=STATUS_CHANGE&actor_id=1",
            headers=underwriter_auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["change_type"] == "STATUS_CHANGE"
    
    def test_filter_by_change_type(self, mock_history_records):
        """Test filtering history by change type."""
        filtered = [r for r in mock_history_records if r.change_type == "STATUS_CHANGE"]
        
        assert len(filtered) == 1
        assert all(r.change_type == "STATUS_CHANGE" for r in filtered)
    
    def test_filter_by_date_range(self):
        """Test filtering history by date range."""
        base_time = datetime.utcnow()
        
        history_records = [
            Mock(timestamp=base_time - timedelta(days=5)),
            Mock(timestamp=base_time - timedelta(days=2)),
            Mock(timestamp=base_time - timedelta(days=1)),
            Mock(timestamp=base_time)
        ]
        
        from_date = base_time - timedelta(days=3)
        filtered = [r for r in history_records if r.timestamp >= from_date]
        
        assert len(filtered) == 3
        assert all(r.timestamp >= from_date for r in filtered)


class TestAuditReportGeneration:
    """Test cases for audit report generation."""
    
    @patch('loan_origination.api.db_utils')
    @patch('loan_origination.api._verify_history_integrity')
    def test_generate_audit_report_basic(self, mock_verify_integrity, mock_db_utils, 
                                       client, underwriter_auth_headers, mock_loan, 
                                       mock_customer, mock_history_records):
        """Test basic audit report generation."""
        mock_db_utils.get_loan_by_loan_id.return_value = mock_loan
        mock_loan.customer = mock_customer
        mock_db_utils.get_loan_history.return_value = mock_history_records
        mock_verify_integrity.return_value = True
        
        report_request = {
            "report_type": "COMPREHENSIVE",
            "include_blockchain_verification": True,
            "format": "json"
        }
        
        response = client.post(
            "/api/v1/loans/LOAN_TEST001/audit-report",
            json=report_request,
            headers=underwriter_auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["report_type"] == "COMPREHENSIVE"
        assert data["total_records"] == 2
        assert data["integrity_verified"] == True
        assert data["blockchain_hash_matches"] == 2
        assert "loan_application" in data["data"]
        assert "history_summary" in data["data"]
        assert "timeline" in data["data"]
        assert "blockchain_verification" in data["data"]
    
    @patch('loan_origination.api.db_utils')
    def test_generate_audit_report_with_date_filter(self, mock_db_utils, client, 
                                                  underwriter_auth_headers, mock_loan, 
                                                  mock_customer, mock_history_records):
        """Test audit report generation with date filtering."""
        mock_db_utils.get_loan_by_loan_id.return_value = mock_loan
        mock_loan.customer = mock_customer
        mock_db_utils.get_loan_history.return_value = mock_history_records
        
        from_date = (datetime.utcnow() - timedelta(days=1)).isoformat()
        report_request = {
            "report_type": "FILTERED",
            "from_date": from_date,
            "include_blockchain_verification": False,
            "format": "json"
        }
        
        response = client.post(
            "/api/v1/loans/LOAN_TEST001/audit-report",
            json=report_request,
            headers=underwriter_auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["report_type"] == "FILTERED"
        assert data["total_records"] == 1  # Should only include recent records
        assert data["data"]["blockchain_verification"]["enabled"] == False


class TestHistoryIntegrityVerification:
    """Test cases for blockchain integrity verification."""
    
    @patch('loan_origination.api.get_fabric_gateway')
    async def test_verify_history_integrity_success(self, mock_get_gateway, mock_history_records):
        """Test successful history integrity verification."""
        mock_gateway = AsyncMock()
        mock_get_gateway.return_value = mock_gateway
        
        blockchain_history = [
            {
                "transactionID": "TX_001",
                "changeType": "STATUS_CHANGE",
                "timestamp": (datetime.utcnow() - timedelta(days=2)).isoformat() + "Z",
                "previousStatus": "SUBMITTED",
                "newStatus": "UNDERWRITING"
            }
        ]
        mock_gateway.query_chaincode.return_value = json.dumps(blockchain_history)
        
        from loan_origination.api import _verify_history_integrity
        
        mock_loan_app = Mock()
        mock_loan_app.loan_application_id = "LOAN_TEST001"
        mock_history_records[0].loan_application = mock_loan_app
        
        result = await _verify_history_integrity(mock_history_records[0])
        
        assert result == True
        mock_gateway.query_chaincode.assert_called_once_with(
            "loan", "GetLoanHistory", ["LOAN_TEST001"]
        )
    
    @patch('loan_origination.api.get_fabric_gateway')
    async def test_verify_history_integrity_no_blockchain_tx(self, mock_get_gateway, mock_history_records):
        """Test integrity verification with no blockchain transaction ID."""
        from loan_origination.api import _verify_history_integrity
        
        mock_history_records[0].blockchain_transaction_id = None
        
        result = await _verify_history_integrity(mock_history_records[0])
        
        assert result == False
        mock_get_gateway.assert_not_called()
    
    @patch('loan_origination.api.get_fabric_gateway')
    async def test_verify_history_integrity_blockchain_error(self, mock_get_gateway, mock_history_records):
        """Test integrity verification with blockchain query error."""
        mock_gateway = AsyncMock()
        mock_get_gateway.return_value = mock_gateway
        mock_gateway.query_chaincode.side_effect = Exception("Blockchain unavailable")
        
        from loan_origination.api import _verify_history_integrity
        
        mock_loan_app = Mock()
        mock_loan_app.loan_application_id = "LOAN_TEST001"
        mock_history_records[0].loan_application = mock_loan_app
        
        result = await _verify_history_integrity(mock_history_records[0])
        
        assert result == False


class TestDatabaseUtilities:
    """Test cases for database utilities used by history functionality."""
    
    @patch('shared.database.DatabaseManager')
    def test_get_loan_history_paginated_basic(self, mock_db_manager):
        """Test basic paginated loan history retrieval."""
        mock_session = Mock()
        mock_db_manager.session_scope.return_value.__enter__.return_value = mock_session
        
        mock_loan = Mock()
        mock_loan.id = 1
        mock_session.query.return_value.filter.return_value.first.return_value = mock_loan
        
        mock_query = Mock()
        mock_session.query.return_value.filter.return_value = mock_query
        mock_query.count.return_value = 5
        mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        
        db_utils = DatabaseUtilities(mock_db_manager)
        
        result, total = db_utils.get_loan_history_paginated("LOAN_TEST001", 1, 10, None)
        
        assert total == 5
        assert isinstance(result, list)
        mock_query.count.assert_called_once()
        mock_query.order_by.assert_called_once()


class TestPaginationLogic:
    """Test cases for pagination calculations."""
    
    def test_pagination_metadata_calculation(self):
        """Test pagination metadata calculations."""
        test_cases = [
            {"total": 25, "page": 1, "page_size": 10, "expected_pages": 3, "has_next": True, "has_prev": False},
            {"total": 25, "page": 2, "page_size": 10, "expected_pages": 3, "has_next": True, "has_prev": True},
            {"total": 25, "page": 3, "page_size": 10, "expected_pages": 3, "has_next": False, "has_prev": True},
            {"total": 10, "page": 1, "page_size": 10, "expected_pages": 1, "has_next": False, "has_prev": False},
            {"total": 0, "page": 1, "page_size": 10, "expected_pages": 0, "has_next": False, "has_prev": False}
        ]
        
        for case in test_cases:
            total_pages = (case["total"] + case["page_size"] - 1) // case["page_size"] if case["total"] > 0 else 0
            has_next = case["page"] < total_pages
            has_previous = case["page"] > 1
            
            assert total_pages == case["expected_pages"], f"Failed for case: {case}"
            assert has_next == case["has_next"], f"Failed has_next for case: {case}"
            assert has_previous == case["has_prev"], f"Failed has_prev for case: {case}"
    
    def test_validation_logic(self):
        """Test validation of pagination and filter parameters."""
        # Valid pagination cases
        valid_cases = [
            {"page": 1, "page_size": 10},
            {"page": 5, "page_size": 50},
            {"page": 1, "page_size": 1000}
        ]
        
        for case in valid_cases:
            page_valid = case["page"] >= 1
            page_size_valid = 1 <= case["page_size"] <= 1000
            assert page_valid and page_size_valid, f"Valid case failed: {case}"
        
        # Invalid pagination cases
        invalid_cases = [
            {"page": 0, "page_size": 10},
            {"page": -1, "page_size": 10},
            {"page": 1, "page_size": 0},
            {"page": 1, "page_size": 2000}
        ]
        
        for case in invalid_cases:
            page_valid = case["page"] >= 1
            page_size_valid = 1 <= case["page_size"] <= 1000
            assert not (page_valid and page_size_valid), f"Invalid case passed: {case}"


class TestAuditDataAggregation:
    """Test cases for audit report data aggregation logic."""
    
    def test_history_summary_calculation(self, mock_history_records):
        """Test calculation of history summary statistics."""
        summary = {
            "total_changes": len(mock_history_records),
            "status_changes": len([r for r in mock_history_records if r.change_type == 'STATUS_CHANGE']),
            "approvals": len([r for r in mock_history_records if r.change_type == 'APPROVAL']),
            "rejections": len([r for r in mock_history_records if r.change_type == 'REJECTION']),
            "updates": len([r for r in mock_history_records if r.change_type == 'UPDATE'])
        }
        
        assert summary["total_changes"] == 2
        assert summary["status_changes"] == 1
        assert summary["approvals"] == 1
        assert summary["rejections"] == 0
        assert summary["updates"] == 0
    
    def test_actors_involved_calculation(self, mock_history_records):
        """Test calculation of unique actors involved."""
        actors_involved = list(set([r.changed_by_actor_id for r in mock_history_records]))
        
        assert len(actors_involved) == 2
        assert 1 in actors_involved
        assert 2 in actors_involved
    
    def test_timeline_creation(self, mock_history_records):
        """Test creation of timeline data structure."""
        timeline = [
            {
                "id": record.id,
                "timestamp": record.timestamp.isoformat(),
                "change_type": record.change_type,
                "previous_status": record.previous_status,
                "new_status": record.new_status
            }
            for record in mock_history_records
        ]
        
        assert len(timeline) == 2
        assert timeline[0]["change_type"] == "STATUS_CHANGE"
        assert timeline[1]["change_type"] == "APPROVAL"
        assert timeline[0]["id"] == 1
        assert timeline[1]["id"] == 2