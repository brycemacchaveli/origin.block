package handlers

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/shimtest"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/compliance/domain"
)

func TestViolationEscalationHandler_CreateEscalation(t *testing.T) {
	stub := shimtest.NewMockStub("escalation_test", nil)
	mockEmitter := &MockEventEmitter{}
	handler := NewViolationEscalationHandler(mockEmitter)

	tests := []struct {
		name          string
		request       EscalationRequest
		expectedLevel EscalationLevel
		expectedError bool
	}{
		{
			name: "Valid critical escalation",
			request: EscalationRequest{
				ViolationID:        "VIOL_001",
				ComplianceEventID:  "EVENT_001",
				ViolationType:      "AML_VIOLATION",
				ViolationSeverity:  domain.PriorityCritical,
				AffectedEntityID:   "CUST_001",
				AffectedEntityType: "Customer",
				Priority:           EscalationPriorityCritical,
				BusinessImpact:     "High - potential regulatory fine",
				RegulatoryImpact:   "Critical - immediate reporting required",
				InitialNotes:       "Critical AML violation detected",
				CreatedBy:          "COMPLIANCE_001",
				Tags:               []string{"AML", "CRITICAL", "REGULATORY"},
			},
			expectedLevel: EscalationLevelL3, // Critical starts at manager level
			expectedError: false,
		},
		{
			name: "Valid high priority escalation",
			request: EscalationRequest{
				ViolationID:        "VIOL_002",
				ComplianceEventID:  "EVENT_002",
				ViolationType:      "SANCTION_MATCH",
				ViolationSeverity:  domain.PriorityHigh,
				AffectedEntityID:   "CUST_002",
				AffectedEntityType: "Customer",
				Priority:           EscalationPriorityHigh,
				BusinessImpact:     "Medium - requires investigation",
				RegulatoryImpact:   "High - potential compliance issue",
				InitialNotes:       "Potential sanction list match",
				CreatedBy:          "COMPLIANCE_002",
			},
			expectedLevel: EscalationLevelL2, // High starts at senior level
			expectedError: false,
		},
		{
			name: "Valid medium priority escalation",
			request: EscalationRequest{
				ViolationID:        "VIOL_003",
				ComplianceEventID:  "EVENT_003",
				ViolationType:      "THRESHOLD_BREACH",
				ViolationSeverity:  domain.PriorityMedium,
				AffectedEntityID:   "LOAN_001",
				AffectedEntityType: "LoanApplication",
				Priority:           EscalationPriorityMedium,
				BusinessImpact:     "Low - routine check required",
				RegulatoryImpact:   "Medium - standard compliance review",
				CreatedBy:          "COMPLIANCE_003",
			},
			expectedLevel: EscalationLevelL1, // Medium starts at analyst level
			expectedError: false,
		},
		{
			name: "Invalid request - missing violation ID",
			request: EscalationRequest{
				ComplianceEventID:  "EVENT_004",
				ViolationType:      "TEST_VIOLATION",
				ViolationSeverity:  domain.PriorityMedium,
				AffectedEntityID:   "TEST_001",
				AffectedEntityType: "Test",
				Priority:           EscalationPriorityMedium,
				CreatedBy:          "TEST_USER",
			},
			expectedError: true,
		},
		{
			name: "Invalid request - missing compliance event ID",
			request: EscalationRequest{
				ViolationID:        "VIOL_005",
				ViolationType:      "TEST_VIOLATION",
				ViolationSeverity:  domain.PriorityMedium,
				AffectedEntityID:   "TEST_001",
				AffectedEntityType: "Test",
				Priority:           EscalationPriorityMedium,
				CreatedBy:          "TEST_USER",
			},
			expectedError: true,
		},
		{
			name: "Invalid request - invalid priority",
			request: EscalationRequest{
				ViolationID:        "VIOL_006",
				ComplianceEventID:  "EVENT_006",
				ViolationType:      "TEST_VIOLATION",
				ViolationSeverity:  domain.PriorityMedium,
				AffectedEntityID:   "TEST_001",
				AffectedEntityType: "Test",
				Priority:           EscalationPriority("INVALID_PRIORITY"),
				CreatedBy:          "TEST_USER",
			},
			expectedError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			requestBytes, err := json.Marshal(tt.request)
			require.NoError(t, err)

			result, err := handler.CreateEscalation(stub, []string{string(requestBytes)})

			if tt.expectedError {
				assert.Error(t, err)
				return
			}

			require.NoError(t, err)
			require.NotNil(t, result)

			var escalation ComplianceViolationEscalation
			err = json.Unmarshal(result, &escalation)
			require.NoError(t, err)

			// Verify basic fields
			assert.NotEmpty(t, escalation.EscalationID)
			assert.Equal(t, tt.request.ViolationID, escalation.ViolationID)
			assert.Equal(t, tt.request.ComplianceEventID, escalation.ComplianceEventID)
			assert.Equal(t, tt.request.ViolationType, escalation.ViolationType)
			assert.Equal(t, tt.request.ViolationSeverity, escalation.ViolationSeverity)
			assert.Equal(t, tt.request.AffectedEntityID, escalation.AffectedEntityID)
			assert.Equal(t, tt.request.AffectedEntityType, escalation.AffectedEntityType)
			assert.Equal(t, tt.request.Priority, escalation.Priority)
			assert.Equal(t, tt.request.CreatedBy, escalation.CreatedBy)

			// Verify escalation level
			assert.Equal(t, tt.expectedLevel, escalation.CurrentLevel)

			// Verify status and timing
			assert.Equal(t, EscalationStatusOpen, escalation.Status)
			assert.NotZero(t, escalation.CreatedDate)
			assert.NotZero(t, escalation.DueDate)
			assert.True(t, escalation.DueDate.After(escalation.CreatedDate))

			// Verify risk score calculation
			assert.GreaterOrEqual(t, escalation.RiskScore, 0.0)
			assert.LessOrEqual(t, escalation.RiskScore, 1.0)

			// Verify history entry was created
			assert.Len(t, escalation.EscalationHistory, 1)
			assert.Equal(t, "ESCALATION_CREATED", escalation.EscalationHistory[0].Action)
			assert.Equal(t, tt.request.CreatedBy, escalation.EscalationHistory[0].ActorID)

			// Verify initial comment if provided
			if tt.request.InitialNotes != "" {
				assert.Len(t, escalation.Comments, 1)
				assert.Equal(t, tt.request.InitialNotes, escalation.Comments[0].Comment)
				assert.True(t, escalation.Comments[0].IsInternal)
			}

			// Verify event was emitted
			assert.Greater(t, len(mockEmitter.EmittedEvents), 0)
		})
	}
}

func TestViolationEscalationHandler_AssignEscalation(t *testing.T) {
	stub := shimtest.NewMockStub("escalation_test", nil)
	mockEmitter := &MockEventEmitter{}
	handler := NewViolationEscalationHandler(mockEmitter)

	// First create an escalation
	createRequest := EscalationRequest{
		ViolationID:        "VIOL_ASSIGN_001",
		ComplianceEventID:  "EVENT_ASSIGN_001",
		ViolationType:      "TEST_VIOLATION",
		ViolationSeverity:  domain.PriorityMedium,
		AffectedEntityID:   "TEST_001",
		AffectedEntityType: "Test",
		Priority:           EscalationPriorityMedium,
		BusinessImpact:     "Medium",
		RegulatoryImpact:   "Medium",
		CreatedBy:          "CREATOR_001",
	}

	createBytes, err := json.Marshal(createRequest)
	require.NoError(t, err)

	createResult, err := handler.CreateEscalation(stub, []string{string(createBytes)})
	require.NoError(t, err)

	var createdEscalation ComplianceViolationEscalation
	err = json.Unmarshal(createResult, &createdEscalation)
	require.NoError(t, err)

	tests := []struct {
		name          string
		escalationID  string
		assignedTo    string
		assignedBy    string
		notes         string
		expectedError bool
	}{
		{
			name:         "Valid assignment",
			escalationID: createdEscalation.EscalationID,
			assignedTo:   "ANALYST_001",
			assignedBy:   "MANAGER_001",
			notes:        "Assigning to senior analyst for review",
		},
		{
			name:         "Valid reassignment",
			escalationID: createdEscalation.EscalationID,
			assignedTo:   "ANALYST_002",
			assignedBy:   "MANAGER_001",
			notes:        "Reassigning to different analyst",
		},
		{
			name:          "Invalid escalation ID",
			escalationID:  "INVALID_ID",
			assignedTo:    "ANALYST_001",
			assignedBy:    "MANAGER_001",
			expectedError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			assignRequest := struct {
				EscalationID string `json:"escalationID"`
				AssignedTo   string `json:"assignedTo"`
				AssignedBy   string `json:"assignedBy"`
				Notes        string `json:"notes,omitempty"`
			}{
				EscalationID: tt.escalationID,
				AssignedTo:   tt.assignedTo,
				AssignedBy:   tt.assignedBy,
				Notes:        tt.notes,
			}

			assignBytes, err := json.Marshal(assignRequest)
			require.NoError(t, err)

			result, err := handler.AssignEscalation(stub, []string{string(assignBytes)})

			if tt.expectedError {
				assert.Error(t, err)
				return
			}

			require.NoError(t, err)
			require.NotNil(t, result)

			var assignedEscalation ComplianceViolationEscalation
			err = json.Unmarshal(result, &assignedEscalation)
			require.NoError(t, err)

			assert.Equal(t, tt.assignedTo, assignedEscalation.AssignedTo)
			assert.Equal(t, tt.assignedBy, assignedEscalation.AssignedBy)
			assert.Equal(t, EscalationStatusAssigned, assignedEscalation.Status)
			assert.NotNil(t, assignedEscalation.AssignmentDate)

			// Verify history entry was added
			assert.Greater(t, len(assignedEscalation.EscalationHistory), 1)
			lastHistory := assignedEscalation.EscalationHistory[len(assignedEscalation.EscalationHistory)-1]
			assert.Equal(t, "ESCALATION_ASSIGNED", lastHistory.Action)
			assert.Equal(t, tt.assignedBy, lastHistory.ActorID)
		})
	}
}

func TestViolationEscalationHandler_EscalateToNextLevel(t *testing.T) {
	stub := shimtest.NewMockStub("escalation_test", nil)
	mockEmitter := &MockEventEmitter{}
	handler := NewViolationEscalationHandler(mockEmitter)

	// Create an escalation at L1 level
	createRequest := EscalationRequest{
		ViolationID:        "VIOL_ESCALATE_001",
		ComplianceEventID:  "EVENT_ESCALATE_001",
		ViolationType:      "TEST_VIOLATION",
		ViolationSeverity:  domain.PriorityMedium,
		AffectedEntityID:   "TEST_001",
		AffectedEntityType: "Test",
		Priority:           EscalationPriorityMedium,
		BusinessImpact:     "Medium",
		RegulatoryImpact:   "Medium",
		CreatedBy:          "CREATOR_001",
	}

	createBytes, err := json.Marshal(createRequest)
	require.NoError(t, err)

	createResult, err := handler.CreateEscalation(stub, []string{string(createBytes)})
	require.NoError(t, err)

	var createdEscalation ComplianceViolationEscalation
	err = json.Unmarshal(createResult, &createdEscalation)
	require.NoError(t, err)

	// Verify it starts at L1
	assert.Equal(t, EscalationLevelL1, createdEscalation.CurrentLevel)

	tests := []struct {
		name          string
		escalationID  string
		reason        string
		notes         string
		escalatedBy   string
		expectedLevel EscalationLevel
		expectedError bool
	}{
		{
			name:          "Valid escalation L1 to L2",
			escalationID:  createdEscalation.EscalationID,
			reason:        "Requires senior review",
			notes:         "Complex case requiring escalation",
			escalatedBy:   "ANALYST_001",
			expectedLevel: EscalationLevelL2,
		},
		{
			name:          "Valid escalation L2 to L3",
			escalationID:  createdEscalation.EscalationID,
			reason:        "Requires management decision",
			notes:         "Escalating to management level",
			escalatedBy:   "SENIOR_001",
			expectedLevel: EscalationLevelL3,
		},
		{
			name:          "Invalid escalation ID",
			escalationID:  "INVALID_ID",
			reason:        "Test",
			escalatedBy:   "TEST_USER",
			expectedError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			escalateRequest := struct {
				EscalationID string `json:"escalationID"`
				Reason       string `json:"reason"`
				Notes        string `json:"notes,omitempty"`
				EscalatedBy  string `json:"escalatedBy"`
			}{
				EscalationID: tt.escalationID,
				Reason:       tt.reason,
				Notes:        tt.notes,
				EscalatedBy:  tt.escalatedBy,
			}

			escalateBytes, err := json.Marshal(escalateRequest)
			require.NoError(t, err)

			result, err := handler.EscalateToNextLevel(stub, []string{string(escalateBytes)})

			if tt.expectedError {
				assert.Error(t, err)
				return
			}

			require.NoError(t, err)
			require.NotNil(t, result)

			var escalatedEscalation ComplianceViolationEscalation
			err = json.Unmarshal(result, &escalatedEscalation)
			require.NoError(t, err)

			assert.Equal(t, tt.expectedLevel, escalatedEscalation.CurrentLevel)
			assert.Equal(t, EscalationStatusEscalated, escalatedEscalation.Status)
			assert.Empty(t, escalatedEscalation.AssignedTo) // Should be cleared for reassignment

			// Verify history entry was added
			assert.Greater(t, len(escalatedEscalation.EscalationHistory), 1)
			lastHistory := escalatedEscalation.EscalationHistory[len(escalatedEscalation.EscalationHistory)-1]
			assert.Equal(t, "ESCALATION_LEVEL_INCREASED", lastHistory.Action)
			assert.Equal(t, tt.escalatedBy, lastHistory.ActorID)
			assert.Equal(t, tt.expectedLevel, lastHistory.ToLevel)
		})
	}
}

func TestViolationEscalationHandler_ResolveEscalation(t *testing.T) {
	stub := shimtest.NewMockStub("escalation_test", nil)
	mockEmitter := &MockEventEmitter{}
	handler := NewViolationEscalationHandler(mockEmitter)

	// Create an escalation
	createRequest := EscalationRequest{
		ViolationID:        "VIOL_RESOLVE_001",
		ComplianceEventID:  "EVENT_RESOLVE_001",
		ViolationType:      "TEST_VIOLATION",
		ViolationSeverity:  domain.PriorityMedium,
		AffectedEntityID:   "TEST_001",
		AffectedEntityType: "Test",
		Priority:           EscalationPriorityMedium,
		BusinessImpact:     "Medium",
		RegulatoryImpact:   "Medium",
		CreatedBy:          "CREATOR_001",
	}

	createBytes, err := json.Marshal(createRequest)
	require.NoError(t, err)

	createResult, err := handler.CreateEscalation(stub, []string{string(createBytes)})
	require.NoError(t, err)

	var createdEscalation ComplianceViolationEscalation
	err = json.Unmarshal(createResult, &createdEscalation)
	require.NoError(t, err)

	tests := []struct {
		name              string
		escalationID      string
		resolutionSummary string
		resolutionActions []ResolutionAction
		resolutionNotes   string
		resolvedBy        string
		expectedError     bool
	}{
		{
			name:              "Valid resolution",
			escalationID:      createdEscalation.EscalationID,
			resolutionSummary: "False positive - customer cleared",
			resolutionActions: []ResolutionAction{
				{
					ActionType:  "INVESTIGATION",
					Description: "Conducted thorough investigation",
					TakenBy:     "ANALYST_001",
					Status:      "COMPLETED",
				},
				{
					ActionType:  "DOCUMENTATION",
					Description: "Updated customer records",
					TakenBy:     "ANALYST_001",
					Status:      "COMPLETED",
				},
			},
			resolutionNotes: "Investigation confirmed no actual violation",
			resolvedBy:      "MANAGER_001",
		},
		{
			name:          "Invalid escalation ID",
			escalationID:  "INVALID_ID",
			resolvedBy:    "TEST_USER",
			expectedError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			resolveRequest := struct {
				EscalationID      string             `json:"escalationID"`
				ResolutionSummary string             `json:"resolutionSummary"`
				ResolutionActions []ResolutionAction `json:"resolutionActions"`
				ResolutionNotes   string             `json:"resolutionNotes,omitempty"`
				ResolvedBy        string             `json:"resolvedBy"`
			}{
				EscalationID:      tt.escalationID,
				ResolutionSummary: tt.resolutionSummary,
				ResolutionActions: tt.resolutionActions,
				ResolutionNotes:   tt.resolutionNotes,
				ResolvedBy:        tt.resolvedBy,
			}

			resolveBytes, err := json.Marshal(resolveRequest)
			require.NoError(t, err)

			result, err := handler.ResolveEscalation(stub, []string{string(resolveBytes)})

			if tt.expectedError {
				assert.Error(t, err)
				return
			}

			require.NoError(t, err)
			require.NotNil(t, result)

			var resolvedEscalation ComplianceViolationEscalation
			err = json.Unmarshal(result, &resolvedEscalation)
			require.NoError(t, err)

			assert.Equal(t, EscalationStatusResolved, resolvedEscalation.Status)
			assert.Equal(t, tt.resolutionSummary, resolvedEscalation.ResolutionSummary)
			assert.Equal(t, tt.resolutionNotes, resolvedEscalation.ResolutionNotes)
			assert.Equal(t, tt.resolvedBy, resolvedEscalation.ResolvedBy)
			assert.NotNil(t, resolvedEscalation.ResolutionDate)

			// Verify resolution actions have IDs and dates
			assert.Len(t, resolvedEscalation.ResolutionActions, len(tt.resolutionActions))
			for _, action := range resolvedEscalation.ResolutionActions {
				assert.NotEmpty(t, action.ActionID)
				assert.NotZero(t, action.TakenDate)
			}

			// Verify history entry was added
			assert.Greater(t, len(resolvedEscalation.EscalationHistory), 1)
			lastHistory := resolvedEscalation.EscalationHistory[len(resolvedEscalation.EscalationHistory)-1]
			assert.Equal(t, "ESCALATION_RESOLVED", lastHistory.Action)
			assert.Equal(t, tt.resolvedBy, lastHistory.ActorID)
		})
	}
}

func TestViolationEscalationHandler_AddComment(t *testing.T) {
	stub := shimtest.NewMockStub("escalation_test", nil)
	mockEmitter := &MockEventEmitter{}
	handler := NewViolationEscalationHandler(mockEmitter)

	// Create an escalation
	createRequest := EscalationRequest{
		ViolationID:        "VIOL_COMMENT_001",
		ComplianceEventID:  "EVENT_COMMENT_001",
		ViolationType:      "TEST_VIOLATION",
		ViolationSeverity:  domain.PriorityMedium,
		AffectedEntityID:   "TEST_001",
		AffectedEntityType: "Test",
		Priority:           EscalationPriorityMedium,
		BusinessImpact:     "Medium",
		RegulatoryImpact:   "Medium",
		CreatedBy:          "CREATOR_001",
	}

	createBytes, err := json.Marshal(createRequest)
	require.NoError(t, err)

	createResult, err := handler.CreateEscalation(stub, []string{string(createBytes)})
	require.NoError(t, err)

	var createdEscalation ComplianceViolationEscalation
	err = json.Unmarshal(createResult, &createdEscalation)
	require.NoError(t, err)

	tests := []struct {
		name          string
		escalationID  string
		comment       string
		authorID      string
		isInternal    bool
		attachments   []string
		expectedError bool
	}{
		{
			name:         "Valid internal comment",
			escalationID: createdEscalation.EscalationID,
			comment:      "Internal investigation notes",
			authorID:     "ANALYST_001",
			isInternal:   true,
		},
		{
			name:         "Valid external comment with attachments",
			escalationID: createdEscalation.EscalationID,
			comment:      "Customer response received",
			authorID:     "ANALYST_001",
			isInternal:   false,
			attachments:  []string{"document1.pdf", "email_thread.txt"},
		},
		{
			name:          "Invalid escalation ID",
			escalationID:  "INVALID_ID",
			comment:       "Test comment",
			authorID:      "TEST_USER",
			expectedError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			commentRequest := struct {
				EscalationID string   `json:"escalationID"`
				Comment      string   `json:"comment"`
				AuthorID     string   `json:"authorID"`
				IsInternal   bool     `json:"isInternal"`
				Attachments  []string `json:"attachments,omitempty"`
			}{
				EscalationID: tt.escalationID,
				Comment:      tt.comment,
				AuthorID:     tt.authorID,
				IsInternal:   tt.isInternal,
				Attachments:  tt.attachments,
			}

			commentBytes, err := json.Marshal(commentRequest)
			require.NoError(t, err)

			result, err := handler.AddComment(stub, []string{string(commentBytes)})

			if tt.expectedError {
				assert.Error(t, err)
				return
			}

			require.NoError(t, err)
			require.NotNil(t, result)

			var addedComment EscalationComment
			err = json.Unmarshal(result, &addedComment)
			require.NoError(t, err)

			assert.NotEmpty(t, addedComment.CommentID)
			assert.Equal(t, tt.comment, addedComment.Comment)
			assert.Equal(t, tt.authorID, addedComment.AuthorID)
			assert.Equal(t, tt.isInternal, addedComment.IsInternal)
			assert.Equal(t, tt.attachments, addedComment.Attachments)
			assert.NotZero(t, addedComment.Timestamp)

			// Verify comment was added to escalation
			escalationKey := fmt.Sprintf("ESCALATION_%s", tt.escalationID)
			var updatedEscalation ComplianceViolationEscalation
			err = handler.persistenceService.Get(stub, escalationKey, &updatedEscalation)
			require.NoError(t, err)

			assert.Greater(t, len(updatedEscalation.Comments), 0)
			lastComment := updatedEscalation.Comments[len(updatedEscalation.Comments)-1]
			assert.Equal(t, addedComment.CommentID, lastComment.CommentID)
		})
	}
}

func TestViolationEscalationHandler_GetEscalation(t *testing.T) {
	stub := shimtest.NewMockStub("escalation_test", nil)
	mockEmitter := &MockEventEmitter{}
	handler := NewViolationEscalationHandler(mockEmitter)

	// Create an escalation
	createRequest := EscalationRequest{
		ViolationID:        "VIOL_GET_001",
		ComplianceEventID:  "EVENT_GET_001",
		ViolationType:      "TEST_VIOLATION",
		ViolationSeverity:  domain.PriorityMedium,
		AffectedEntityID:   "TEST_001",
		AffectedEntityType: "Test",
		Priority:           EscalationPriorityMedium,
		BusinessImpact:     "Medium",
		RegulatoryImpact:   "Medium",
		CreatedBy:          "CREATOR_001",
	}

	createBytes, err := json.Marshal(createRequest)
	require.NoError(t, err)

	createResult, err := handler.CreateEscalation(stub, []string{string(createBytes)})
	require.NoError(t, err)

	var createdEscalation ComplianceViolationEscalation
	err = json.Unmarshal(createResult, &createdEscalation)
	require.NoError(t, err)

	tests := []struct {
		name          string
		escalationID  string
		expectedError bool
	}{
		{
			name:         "Valid escalation ID",
			escalationID: createdEscalation.EscalationID,
		},
		{
			name:          "Invalid escalation ID",
			escalationID:  "INVALID_ID",
			expectedError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result, err := handler.GetEscalation(stub, []string{tt.escalationID})

			if tt.expectedError {
				assert.Error(t, err)
				return
			}

			require.NoError(t, err)
			require.NotNil(t, result)

			var retrievedEscalation ComplianceViolationEscalation
			err = json.Unmarshal(result, &retrievedEscalation)
			require.NoError(t, err)

			assert.Equal(t, createdEscalation.EscalationID, retrievedEscalation.EscalationID)
			assert.Equal(t, createdEscalation.ViolationID, retrievedEscalation.ViolationID)
			assert.Equal(t, createdEscalation.ViolationType, retrievedEscalation.ViolationType)
		})
	}
}

func TestViolationEscalationHandler_GetEscalationsByStatus(t *testing.T) {
	stub := shimtest.NewMockStub("escalation_test", nil)
	mockEmitter := &MockEventEmitter{}
	handler := NewViolationEscalationHandler(mockEmitter)

	// Create multiple escalations with different statuses
	escalations := []struct {
		violationID string
		status      EscalationStatus
	}{
		{"VIOL_STATUS_001", EscalationStatusOpen},
		{"VIOL_STATUS_002", EscalationStatusOpen},
		{"VIOL_STATUS_003", EscalationStatusAssigned},
	}

	var createdEscalations []ComplianceViolationEscalation

	for i, esc := range escalations {
		createRequest := EscalationRequest{
			ViolationID:        esc.violationID,
			ComplianceEventID:  fmt.Sprintf("EVENT_STATUS_%03d", i+1),
			ViolationType:      "TEST_VIOLATION",
			ViolationSeverity:  domain.PriorityMedium,
			AffectedEntityID:   fmt.Sprintf("TEST_%03d", i+1),
			AffectedEntityType: "Test",
			Priority:           EscalationPriorityMedium,
			BusinessImpact:     "Medium",
			RegulatoryImpact:   "Medium",
			CreatedBy:          "CREATOR_001",
		}

		createBytes, err := json.Marshal(createRequest)
		require.NoError(t, err)

		createResult, err := handler.CreateEscalation(stub, []string{string(createBytes)})
		require.NoError(t, err)

		var createdEscalation ComplianceViolationEscalation
		err = json.Unmarshal(createResult, &createdEscalation)
		require.NoError(t, err)

		// Assign one escalation to change its status
		if esc.status == EscalationStatusAssigned {
			assignRequest := struct {
				EscalationID string `json:"escalationID"`
				AssignedTo   string `json:"assignedTo"`
				AssignedBy   string `json:"assignedBy"`
			}{
				EscalationID: createdEscalation.EscalationID,
				AssignedTo:   "ANALYST_001",
				AssignedBy:   "MANAGER_001",
			}

			assignBytes, err := json.Marshal(assignRequest)
			require.NoError(t, err)

			assignResult, err := handler.AssignEscalation(stub, []string{string(assignBytes)})
			require.NoError(t, err)

			err = json.Unmarshal(assignResult, &createdEscalation)
			require.NoError(t, err)
		}

		createdEscalations = append(createdEscalations, createdEscalation)
	}

	tests := []struct {
		name          string
		status        string
		expectedCount int
	}{
		{
			name:          "Get open escalations",
			status:        string(EscalationStatusOpen),
			expectedCount: 2,
		},
		{
			name:          "Get assigned escalations",
			status:        string(EscalationStatusAssigned),
			expectedCount: 1,
		},
		{
			name:          "Get non-existent status",
			status:        string(EscalationStatusResolved),
			expectedCount: 0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result, err := handler.GetEscalationsByStatus(stub, []string{tt.status})
			require.NoError(t, err)
			require.NotNil(t, result)

			var escalations []ComplianceViolationEscalation
			err = json.Unmarshal(result, &escalations)
			require.NoError(t, err)

			assert.Len(t, escalations, tt.expectedCount)

			// Verify all returned escalations have the correct status
			for _, escalation := range escalations {
				assert.Equal(t, tt.status, string(escalation.Status))
			}
		})
	}
}

func TestViolationEscalationHandler_HelperMethods(t *testing.T) {
	handler := NewViolationEscalationHandler(nil)

	t.Run("determineInitialEscalationLevel", func(t *testing.T) {
		tests := []struct {
			severity      domain.ComplianceRulePriority
			priority      EscalationPriority
			expectedLevel EscalationLevel
		}{
			{domain.PriorityCritical, EscalationPriorityMedium, EscalationLevelL3},
			{domain.PriorityMedium, EscalationPriorityCritical, EscalationLevelL3},
			{domain.PriorityHigh, EscalationPriorityHigh, EscalationLevelL2},
			{domain.PriorityMedium, EscalationPriorityMedium, EscalationLevelL1},
			{domain.PriorityLow, EscalationPriorityLow, EscalationLevelL1},
		}

		for _, tt := range tests {
			level := handler.determineInitialEscalationLevel(tt.severity, tt.priority)
			assert.Equal(t, tt.expectedLevel, level,
				"Severity: %s, Priority: %s", tt.severity, tt.priority)
		}
	})

	t.Run("calculateSLADueDate", func(t *testing.T) {
		baseTime := time.Now()
		
		tests := []struct {
			level    EscalationLevel
			priority EscalationPriority
			minHours int
			maxHours int
		}{
			{EscalationLevelL1, EscalationPriorityCritical, 10, 15},  // 24 * 0.5 = 12 hours
			{EscalationLevelL1, EscalationPriorityMedium, 20, 30},   // 24 * 1.0 = 24 hours
			{EscalationLevelL2, EscalationPriorityHigh, 30, 40},     // 48 * 0.75 = 36 hours
			{EscalationLevelL3, EscalationPriorityMedium, 65, 75},   // 72 * 1.0 = 72 hours
		}

		for _, tt := range tests {
			dueDate := handler.calculateSLADueDate(tt.level, tt.priority)
			hoursDiff := dueDate.Sub(baseTime).Hours()
			
			assert.GreaterOrEqual(t, hoursDiff, float64(tt.minHours),
				"Level: %s, Priority: %s", tt.level, tt.priority)
			assert.LessOrEqual(t, hoursDiff, float64(tt.maxHours),
				"Level: %s, Priority: %s", tt.level, tt.priority)
		}
	})

	t.Run("calculateRiskScore", func(t *testing.T) {
		tests := []struct {
			severity         domain.ComplianceRulePriority
			priority         EscalationPriority
			businessImpact   string
			regulatoryImpact string
			minScore         float64
			maxScore         float64
		}{
			{domain.PriorityCritical, EscalationPriorityCritical, "HIGH", "CRITICAL", 0.8, 1.0},
			{domain.PriorityMedium, EscalationPriorityMedium, "MEDIUM", "MEDIUM", 0.4, 0.6},
			{domain.PriorityLow, EscalationPriorityLow, "LOW", "LOW", 0.1, 0.3},
		}

		for _, tt := range tests {
			score := handler.calculateRiskScore(tt.severity, tt.priority, tt.businessImpact, tt.regulatoryImpact)
			
			assert.GreaterOrEqual(t, score, tt.minScore,
				"Severity: %s, Priority: %s", tt.severity, tt.priority)
			assert.LessOrEqual(t, score, tt.maxScore,
				"Severity: %s, Priority: %s", tt.severity, tt.priority)
		}
	})

	t.Run("getNextEscalationLevel", func(t *testing.T) {
		tests := []struct {
			currentLevel  EscalationLevel
			expectedNext  EscalationLevel
			expectError   bool
		}{
			{EscalationLevelL1, EscalationLevelL2, false},
			{EscalationLevelL2, EscalationLevelL3, false},
			{EscalationLevelL3, EscalationLevelL4, false},
			{EscalationLevelL4, EscalationLevelL5, false},
			{EscalationLevelL5, "", true}, // Already at highest level
		}

		for _, tt := range tests {
			nextLevel, err := handler.getNextEscalationLevel(tt.currentLevel)
			
			if tt.expectError {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
				assert.Equal(t, tt.expectedNext, nextLevel)
			}
		}
	})
}

// Benchmark tests for performance validation

func BenchmarkViolationEscalationHandler_CreateEscalation(b *testing.B) {
	stub := shimtest.NewMockStub("escalation_benchmark", nil)
	handler := NewViolationEscalationHandler(nil)

	request := EscalationRequest{
		ViolationID:        "BENCH_VIOL_001",
		ComplianceEventID:  "BENCH_EVENT_001",
		ViolationType:      "BENCHMARK_VIOLATION",
		ViolationSeverity:  domain.PriorityMedium,
		AffectedEntityID:   "BENCH_ENTITY_001",
		AffectedEntityType: "BenchmarkEntity",
		Priority:           EscalationPriorityMedium,
		BusinessImpact:     "Medium benchmark impact",
		RegulatoryImpact:   "Medium regulatory impact",
		CreatedBy:          "BENCH_USER",
	}

	requestBytes, _ := json.Marshal(request)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		// Use unique IDs for each iteration
		request.ViolationID = fmt.Sprintf("BENCH_VIOL_%d", i)
		request.ComplianceEventID = fmt.Sprintf("BENCH_EVENT_%d", i)
		requestBytes, _ = json.Marshal(request)
		
		_, err := handler.CreateEscalation(stub, []string{string(requestBytes)})
		if err != nil {
			b.Fatal(err)
		}
	}
}

func BenchmarkViolationEscalationHandler_AssignEscalation(b *testing.B) {
	stub := shimtest.NewMockStub("escalation_benchmark", nil)
	handler := NewViolationEscalationHandler(nil)

	// Create a base escalation
	createRequest := EscalationRequest{
		ViolationID:        "BENCH_ASSIGN_VIOL",
		ComplianceEventID:  "BENCH_ASSIGN_EVENT",
		ViolationType:      "BENCHMARK_VIOLATION",
		ViolationSeverity:  domain.PriorityMedium,
		AffectedEntityID:   "BENCH_ENTITY",
		AffectedEntityType: "BenchmarkEntity",
		Priority:           EscalationPriorityMedium,
		BusinessImpact:     "Medium",
		RegulatoryImpact:   "Medium",
		CreatedBy:          "BENCH_USER",
	}

	createBytes, _ := json.Marshal(createRequest)
	result, err := handler.CreateEscalation(stub, []string{string(createBytes)})
	if err != nil {
		b.Fatal(err)
	}

	var createdEscalation ComplianceViolationEscalation
	json.Unmarshal(result, &createdEscalation)

	assignRequest := struct {
		EscalationID string `json:"escalationID"`
		AssignedTo   string `json:"assignedTo"`
		AssignedBy   string `json:"assignedBy"`
	}{
		EscalationID: createdEscalation.EscalationID,
		AssignedTo:   "BENCH_ANALYST",
		AssignedBy:   "BENCH_MANAGER",
	}

	assignBytes, _ := json.Marshal(assignRequest)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		// Use different assignee for each iteration
		assignRequest.AssignedTo = fmt.Sprintf("BENCH_ANALYST_%d", i)
		assignBytes, _ = json.Marshal(assignRequest)
		
		_, err := handler.AssignEscalation(stub, []string{string(assignBytes)})
		if err != nil {
			b.Fatal(err)
		}
	}
}