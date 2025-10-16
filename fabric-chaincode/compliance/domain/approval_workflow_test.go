package domain

import (
	"fmt"
	"testing"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// setupMockStub creates a properly initialized mock stub for testing
func setupMockStub() shim.ChaincodeStubInterface {
	return NewEnhancedMockStub("compliance", nil)
}

func TestApprovalWorkflowManager_SubmitRuleForApproval(t *testing.T) {
	// Setup
	mockRepo := NewMockRuleRepository()
	mockEmitter := NewMockEventEmitter()
	manager := NewApprovalWorkflowManager(mockRepo, mockEmitter)
	stub := setupMockStub()

	// Create a test rule in draft status
	testRule := &ComplianceRule{
		RuleID:              "APPROVAL_TEST_RULE",
		RuleName:            "Approval Test Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "threshold", "field": "amount", "threshold": 1000}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "LOAN",
		AppliesToEntityType: "LoanApplication",
		Status:              RuleStatusDraft,
		EffectiveDate:       time.Now(),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now(),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now(),
		BusinessJustification: "Test rule for approval workflow",
		TestCases: []RuleTestCase{
			{
				TestID:          "TEST_CASE_001",
				TestName:        "Basic Test",
				TestDescription: "Basic test case",
				InputData:       map[string]interface{}{"amount": 1500.0},
				ExpectedResult:  RuleExecutionResult{Passed: true},
				CreatedBy:       "TEST_USER",
				CreationDate:    time.Now(),
			},
		},
	}

	// Save the rule
	err := mockRepo.SaveRule(stub, testRule)
	require.NoError(t, err)

	tests := []struct {
		name            string
		ruleID          string
		requestedBy     string
		justification   string
		expectedError   bool
		expectedStatus  string
	}{
		{
			name:           "Successful submission",
			ruleID:         "APPROVAL_TEST_RULE",
			requestedBy:    "REQUESTER_USER",
			justification:  "This rule is needed for compliance",
			expectedError:  false,
			expectedStatus: "PENDING",
		},
		{
			name:          "Non-existent rule",
			ruleID:        "NON_EXISTENT_RULE",
			requestedBy:   "REQUESTER_USER",
			justification: "Test justification",
			expectedError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			request, err := manager.SubmitRuleForApproval(stub, tt.ruleID, tt.requestedBy, tt.justification)

			if tt.expectedError {
				assert.Error(t, err)
				assert.Nil(t, request)
			} else {
				assert.NoError(t, err)
				assert.NotNil(t, request)
				assert.Equal(t, tt.ruleID, request.RuleID)
				assert.Equal(t, tt.requestedBy, request.RequestedBy)
				assert.Equal(t, tt.justification, request.Justification)
				assert.Equal(t, tt.expectedStatus, request.Status)
				assert.NotEmpty(t, request.RequestID)
				assert.False(t, request.RequestDate.IsZero())

				// Check that rule status was updated to pending
				updatedRule, err := mockRepo.GetLatestRule(stub, tt.ruleID)
				assert.NoError(t, err)
				assert.Equal(t, RuleStatusPending, updatedRule.Status)
			}
		})
	}
}

func TestApprovalWorkflowManager_ApproveRule(t *testing.T) {
	// Setup
	mockRepo := NewMockRuleRepository()
	mockEmitter := NewMockEventEmitter()
	manager := NewApprovalWorkflowManager(mockRepo, mockEmitter)
	stub := setupMockStub()

	// Create a test rule in pending status
	testRule := &ComplianceRule{
		RuleID:              "APPROVE_TEST_RULE",
		RuleName:            "Approve Test Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "threshold", "field": "amount", "threshold": 1000}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "LOAN",
		AppliesToEntityType: "LoanApplication",
		Status:              RuleStatusPending,
		EffectiveDate:       time.Now(),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now(),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now(),
		BusinessJustification: "Test rule for approval",
		TestCases: []RuleTestCase{
			{
				TestID:          "TEST_CASE_001",
				TestName:        "Basic Test",
				TestDescription: "Basic test case",
				InputData:       map[string]interface{}{"amount": 1500.0},
				ExpectedResult:  RuleExecutionResult{Passed: true},
				CreatedBy:       "TEST_USER",
				CreationDate:    time.Now(),
			},
		},
	}

	// Save the rule
	err := mockRepo.SaveRule(stub, testRule)
	require.NoError(t, err)

	// Create an approval request
	request, err := manager.SubmitRuleForApproval(stub, "APPROVE_TEST_RULE", "REQUESTER_USER", "Test justification")
	require.NoError(t, err)
	require.NotNil(t, request)

	tests := []struct {
		name          string
		requestID     string
		reviewedBy    string
		comments      string
		expectedError bool
	}{
		{
			name:          "Successful approval",
			requestID:     request.RequestID,
			reviewedBy:    "APPROVER_USER",
			comments:      "Rule approved after review",
			expectedError: false,
		},
		{
			name:          "Non-existent request",
			requestID:     "NON_EXISTENT_REQUEST",
			reviewedBy:    "APPROVER_USER",
			comments:      "Test comments",
			expectedError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := manager.ApproveRule(stub, tt.requestID, tt.reviewedBy, tt.comments)

			if tt.expectedError {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)

				// Check that rule status was updated to active
				updatedRule, err := mockRepo.GetLatestRule(stub, "APPROVE_TEST_RULE")
				assert.NoError(t, err)
				assert.Equal(t, RuleStatusActive, updatedRule.Status)
				assert.Equal(t, tt.reviewedBy, updatedRule.ApprovedBy)
				assert.NotNil(t, updatedRule.ApprovalDate)
			}
		})
	}
}

func TestApprovalWorkflowManager_RejectRule(t *testing.T) {
	// Setup
	mockRepo := NewMockRuleRepository()
	mockEmitter := NewMockEventEmitter()
	manager := NewApprovalWorkflowManager(mockRepo, mockEmitter)
	stub := setupMockStub()

	// Create a test rule in pending status
	testRule := &ComplianceRule{
		RuleID:              "REJECT_TEST_RULE",
		RuleName:            "Reject Test Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "threshold", "field": "amount", "threshold": 1000}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "LOAN",
		AppliesToEntityType: "LoanApplication",
		Status:              RuleStatusPending,
		EffectiveDate:       time.Now(),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now(),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now(),
		BusinessJustification: "Test rule for rejection",
		TestCases: []RuleTestCase{
			{
				TestID:          "TEST_CASE_001",
				TestName:        "Basic Test",
				TestDescription: "Basic test case",
				InputData:       map[string]interface{}{"amount": 1500.0},
				ExpectedResult:  RuleExecutionResult{Passed: true},
				CreatedBy:       "TEST_USER",
				CreationDate:    time.Now(),
			},
		},
	}

	// Save the rule
	err := mockRepo.SaveRule(stub, testRule)
	require.NoError(t, err)

	// Create an approval request
	request, err := manager.SubmitRuleForApproval(stub, "REJECT_TEST_RULE", "REQUESTER_USER", "Test justification")
	require.NoError(t, err)
	require.NotNil(t, request)

	// Test rejection
	err = manager.RejectRule(stub, request.RequestID, "REVIEWER_USER", "Rule needs more work")
	assert.NoError(t, err)

	// Check that rule status was updated back to draft
	updatedRule, err := mockRepo.GetLatestRule(stub, "REJECT_TEST_RULE")
	assert.NoError(t, err)
	assert.Equal(t, RuleStatusDraft, updatedRule.Status)
}

func TestApprovalWorkflowManager_GetPendingApprovals(t *testing.T) {
	// Setup
	mockRepo := NewMockRuleRepository()
	mockEmitter := NewMockEventEmitter()
	manager := NewApprovalWorkflowManager(mockRepo, mockEmitter)
	stub := setupMockStub()

	// Create test rules
	for i := 1; i <= 3; i++ {
		ruleID := fmt.Sprintf("PENDING_RULE_%d", i)
		testRule := &ComplianceRule{
			RuleID:              ruleID,
			RuleName:            fmt.Sprintf("Pending Rule %d", i),
			Version:             "1.0.0",
			RuleLogic:           `{"type": "threshold", "field": "amount", "threshold": 1000}`,
			ExecutionMode:       ExecutionModeSync,
			Priority:            PriorityMedium,
			AppliesToDomain:     "LOAN",
			AppliesToEntityType: "LoanApplication",
			Status:              RuleStatusDraft,
			EffectiveDate:       time.Now(),
			CreatedBy:           "TEST_USER",
			CreationDate:        time.Now(),
			LastModifiedBy:      "TEST_USER",
			LastModifiedDate:    time.Now(),
			BusinessJustification: fmt.Sprintf("Test rule %d", i),
			TestCases: []RuleTestCase{
				{
					TestID:          fmt.Sprintf("TEST_CASE_%d", i),
					TestName:        fmt.Sprintf("Test Case %d", i),
					TestDescription: fmt.Sprintf("Test case %d", i),
					InputData:       map[string]interface{}{"amount": 1500.0},
					ExpectedResult:  RuleExecutionResult{Passed: true},
					CreatedBy:       "TEST_USER",
					CreationDate:    time.Now(),
				},
			},
		}

		err := mockRepo.SaveRule(stub, testRule)
		require.NoError(t, err)

		// Submit for approval
		_, err = manager.SubmitRuleForApproval(stub, ruleID, "REQUESTER_USER", fmt.Sprintf("Justification for rule %d", i))
		require.NoError(t, err)
	}

	// Get pending approvals
	pendingApprovals, err := manager.GetPendingApprovals(stub)
	assert.NoError(t, err)
	assert.Len(t, pendingApprovals, 3)

	// All should be pending
	for _, approval := range pendingApprovals {
		assert.Equal(t, "PENDING", approval.Status)
		assert.Equal(t, "REQUESTER_USER", approval.RequestedBy)
	}
}

func TestApprovalWorkflowManager_GetApprovalHistory(t *testing.T) {
	// Setup
	mockRepo := NewMockRuleRepository()
	mockEmitter := NewMockEventEmitter()
	manager := NewApprovalWorkflowManager(mockRepo, mockEmitter)
	stub := setupMockStub()

	// Create a test rule
	testRule := &ComplianceRule{
		RuleID:              "HISTORY_TEST_RULE",
		RuleName:            "History Test Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "threshold", "field": "amount", "threshold": 1000}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "LOAN",
		AppliesToEntityType: "LoanApplication",
		Status:              RuleStatusDraft,
		EffectiveDate:       time.Now(),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now(),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now(),
		BusinessJustification: "Test rule for history",
		TestCases: []RuleTestCase{
			{
				TestID:          "TEST_CASE_001",
				TestName:        "Basic Test",
				TestDescription: "Basic test case",
				InputData:       map[string]interface{}{"amount": 1500.0},
				ExpectedResult:  RuleExecutionResult{Passed: true},
				CreatedBy:       "TEST_USER",
				CreationDate:    time.Now(),
			},
		},
	}

	err := mockRepo.SaveRule(stub, testRule)
	require.NoError(t, err)

	// Submit for approval multiple times
	request1, err := manager.SubmitRuleForApproval(stub, "HISTORY_TEST_RULE", "REQUESTER_1", "First submission")
	require.NoError(t, err)

	// Reject first request
	err = manager.RejectRule(stub, request1.RequestID, "REVIEWER_1", "Needs improvement")
	require.NoError(t, err)

	// Submit again
	request2, err := manager.SubmitRuleForApproval(stub, "HISTORY_TEST_RULE", "REQUESTER_2", "Second submission")
	require.NoError(t, err)

	// Approve second request
	err = manager.ApproveRule(stub, request2.RequestID, "REVIEWER_2", "Approved after improvements")
	require.NoError(t, err)

	// Get approval history
	history, err := manager.GetApprovalHistory(stub, "HISTORY_TEST_RULE")
	assert.NoError(t, err)
	assert.Len(t, history, 2)

	// Check history entries
	var rejectedRequest, approvedRequest *RuleApprovalRequest
	for _, req := range history {
		if req.Status == "REJECTED" {
			rejectedRequest = req
		} else if req.Status == "APPROVED" {
			approvedRequest = req
		}
	}

	assert.NotNil(t, rejectedRequest)
	assert.Equal(t, "REQUESTER_1", rejectedRequest.RequestedBy)
	assert.Equal(t, "REVIEWER_1", rejectedRequest.ReviewedBy)
	assert.Equal(t, "Needs improvement", rejectedRequest.ReviewComments)

	assert.NotNil(t, approvedRequest)
	assert.Equal(t, "REQUESTER_2", approvedRequest.RequestedBy)
	assert.Equal(t, "REVIEWER_2", approvedRequest.ReviewedBy)
	assert.Equal(t, "Approved after improvements", approvedRequest.ReviewComments)
}

func TestApprovalWorkflowManager_RuleSupersession(t *testing.T) {
	// Setup
	mockRepo := NewMockRuleRepository()
	mockEmitter := NewMockEventEmitter()
	manager := NewApprovalWorkflowManager(mockRepo, mockEmitter)
	stub := setupMockStub()

	// Create an old rule that will be superseded
	oldRule := &ComplianceRule{
		RuleID:              "OLD_RULE",
		RuleName:            "Old Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "threshold", "field": "amount", "threshold": 500}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "LOAN",
		AppliesToEntityType: "LoanApplication",
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-48 * time.Hour),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now().Add(-48 * time.Hour),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now().Add(-48 * time.Hour),
		BusinessJustification: "Old rule to be superseded",
	}

	err := mockRepo.SaveRule(stub, oldRule)
	require.NoError(t, err)

	// Create a new rule that supersedes the old one
	newRule := &ComplianceRule{
		RuleID:              "NEW_RULE",
		RuleName:            "New Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "threshold", "field": "amount", "threshold": 1000}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "LOAN",
		AppliesToEntityType: "LoanApplication",
		Status:              RuleStatusDraft,
		EffectiveDate:       time.Now(),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now(),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now(),
		Supersedes:          []string{"OLD_RULE"},
		BusinessJustification: "New rule that supersedes old rule",
		TestCases: []RuleTestCase{
			{
				TestID:          "TEST_CASE_001",
				TestName:        "Basic Test",
				TestDescription: "Basic test case",
				InputData:       map[string]interface{}{"amount": 1500.0},
				ExpectedResult:  RuleExecutionResult{Passed: true},
				CreatedBy:       "TEST_USER",
				CreationDate:    time.Now(),
			},
		},
	}

	err = mockRepo.SaveRule(stub, newRule)
	require.NoError(t, err)

	// Submit new rule for approval
	request, err := manager.SubmitRuleForApproval(stub, "NEW_RULE", "REQUESTER_USER", "New rule supersedes old one")
	require.NoError(t, err)

	// Approve the new rule
	err = manager.ApproveRule(stub, request.RequestID, "APPROVER_USER", "Approved - supersedes old rule")
	require.NoError(t, err)

	// Check that the old rule was deprecated
	updatedOldRule, err := mockRepo.GetLatestRule(stub, "OLD_RULE")
	assert.NoError(t, err)
	assert.Equal(t, RuleStatusDeprecated, updatedOldRule.Status)

	// Check that the new rule is active
	updatedNewRule, err := mockRepo.GetLatestRule(stub, "NEW_RULE")
	assert.NoError(t, err)
	assert.Equal(t, RuleStatusActive, updatedNewRule.Status)
}

func TestApprovalWorkflowManager_ValidationBeforeApproval(t *testing.T) {
	// Setup
	mockRepo := NewMockRuleRepository()
	mockEmitter := NewMockEventEmitter()
	manager := NewApprovalWorkflowManager(mockRepo, mockEmitter)
	stub := setupMockStub()

	tests := []struct {
		name          string
		rule          *ComplianceRule
		expectedError bool
		errorContains string
	}{
		{
			name: "Valid rule with test cases",
			rule: &ComplianceRule{
				RuleID:              "VALID_APPROVAL_RULE",
				RuleName:            "Valid Approval Rule",
				Version:             "1.0.0",
				RuleLogic:           `{"type": "threshold", "field": "amount", "threshold": 1000}`,
				ExecutionMode:       ExecutionModeSync,
				Priority:            PriorityMedium,
				AppliesToDomain:     "LOAN",
				AppliesToEntityType: "LoanApplication",
				Status:              RuleStatusDraft,
				EffectiveDate:       time.Now(),
				CreatedBy:           "TEST_USER",
				CreationDate:        time.Now(),
				LastModifiedBy:      "TEST_USER",
				LastModifiedDate:    time.Now(),
				BusinessJustification: "Valid rule for approval",
				TestCases: []RuleTestCase{
					{
						TestID:          "TEST_CASE_001",
						TestName:        "Basic Test",
						TestDescription: "Basic test case",
						InputData:       map[string]interface{}{"amount": 1500.0},
						ExpectedResult:  RuleExecutionResult{Passed: true},
						CreatedBy:       "TEST_USER",
						CreationDate:    time.Now(),
					},
				},
			},
			expectedError: false,
		},
		{
			name: "Invalid rule - no test cases",
			rule: &ComplianceRule{
				RuleID:              "NO_TESTS_RULE",
				RuleName:            "No Tests Rule",
				Version:             "1.0.0",
				RuleLogic:           `{"type": "threshold", "field": "amount", "threshold": 1000}`,
				ExecutionMode:       ExecutionModeSync,
				Priority:            PriorityMedium,
				AppliesToDomain:     "LOAN",
				AppliesToEntityType: "LoanApplication",
				Status:              RuleStatusDraft,
				EffectiveDate:       time.Now(),
				CreatedBy:           "TEST_USER",
				CreationDate:        time.Now(),
				LastModifiedBy:      "TEST_USER",
				LastModifiedDate:    time.Now(),
				BusinessJustification: "Rule without test cases",
				TestCases:           []RuleTestCase{}, // No test cases
			},
			expectedError: true,
			errorContains: "must have at least one test case",
		},
		{
			name: "Invalid rule - missing required fields",
			rule: &ComplianceRule{
				RuleID: "INVALID_RULE",
				// Missing required fields
				Status:       RuleStatusDraft,
				CreatedBy:    "TEST_USER",
				CreationDate: time.Now(),
			},
			expectedError: true,
			errorContains: "validation failed",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Save the rule
			err := mockRepo.SaveRule(stub, tt.rule)
			if tt.expectedError && tt.errorContains == "validation failed" {
				// Rule should fail to save due to validation
				assert.Error(t, err)
				return
			}
			require.NoError(t, err)

			// Try to submit for approval
			_, err = manager.SubmitRuleForApproval(stub, tt.rule.RuleID, "REQUESTER_USER", "Test justification")

			if tt.expectedError {
				assert.Error(t, err)
				if tt.errorContains != "" {
					assert.Contains(t, err.Error(), tt.errorContains)
				}
			} else {
				assert.NoError(t, err)
			}
		})
	}
}