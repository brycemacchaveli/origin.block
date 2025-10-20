package domain

import (
	"testing"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/shimtest"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// setupMockStubForRepo creates a properly initialized mock stub for testing
func setupMockStubForRepo() *shimtest.MockStub {
	stub := shimtest.NewMockStub("compliance", nil)
	stub.MockTransactionStart("txid")
	return stub
}

func TestFabricRuleRepository_SaveAndGetRule(t *testing.T) {
	// Setup
	repo := NewFabricRuleRepository()
	stub := setupMockStubForRepo()

	// Create a test rule
	testRule := &ComplianceRule{
		RuleID:              "TEST_REPO_RULE",
		RuleName:            "Test Repository Rule",
		RuleDescription:     "A test rule for repository testing",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "threshold", "field": "amount", "threshold": 1000}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "LOAN",
		AppliesToEntityType: "LoanApplication",
		TriggerEvents:       []string{"LoanSubmitted", "LoanUpdated"},
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now(),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now(),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now(),
		BusinessJustification: "Test rule for repository operations",
		Tags:                []string{"test", "repository"},
	}

	// Test saving the rule
	err := repo.SaveRule(stub, testRule)
	assert.NoError(t, err)

	// Test getting the rule by ID and version
	retrievedRule, err := repo.GetRule(stub, "TEST_REPO_RULE", "1.0.0")
	assert.NoError(t, err)
	assert.NotNil(t, retrievedRule)
	assert.Equal(t, testRule.RuleID, retrievedRule.RuleID)
	assert.Equal(t, testRule.RuleName, retrievedRule.RuleName)
	assert.Equal(t, testRule.Version, retrievedRule.Version)
	assert.Equal(t, testRule.RuleLogic, retrievedRule.RuleLogic)
	assert.Equal(t, testRule.Priority, retrievedRule.Priority)
	assert.Equal(t, testRule.AppliesToDomain, retrievedRule.AppliesToDomain)
	assert.Equal(t, testRule.Status, retrievedRule.Status)

	// Test getting the latest rule
	latestRule, err := repo.GetLatestRule(stub, "TEST_REPO_RULE")
	assert.NoError(t, err)
	assert.NotNil(t, latestRule)
	assert.Equal(t, testRule.RuleID, latestRule.RuleID)
	assert.Equal(t, testRule.Version, latestRule.Version)
}

func TestFabricRuleRepository_GetActiveRules(t *testing.T) {
	// Setup
	repo := NewFabricRuleRepository()
	stub := shimtest.NewMockStub("compliance", nil)

	// Create test rules with different statuses
	activeRule := &ComplianceRule{
		RuleID:              "ACTIVE_RULE",
		RuleName:            "Active Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "validation"}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "CUSTOMER",
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour), // Yesterday
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now(),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now(),
		BusinessJustification: "Active test rule",
	}

	inactiveRule := &ComplianceRule{
		RuleID:              "INACTIVE_RULE",
		RuleName:            "Inactive Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "validation"}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "CUSTOMER",
		Status:              RuleStatusInactive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now(),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now(),
		BusinessJustification: "Inactive test rule",
	}

	draftRule := &ComplianceRule{
		RuleID:              "DRAFT_RULE",
		RuleName:            "Draft Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "validation"}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "CUSTOMER",
		Status:              RuleStatusDraft,
		EffectiveDate:       time.Now().Add(-24 * time.Hour),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now(),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now(),
		BusinessJustification: "Draft test rule",
	}

	// Save all rules
	err := repo.SaveRule(stub, activeRule)
	require.NoError(t, err)
	err = repo.SaveRule(stub, inactiveRule)
	require.NoError(t, err)
	err = repo.SaveRule(stub, draftRule)
	require.NoError(t, err)

	// Get active rules
	activeRules, err := repo.GetActiveRules(stub)
	assert.NoError(t, err)
	assert.Len(t, activeRules, 1)
	assert.Equal(t, "ACTIVE_RULE", activeRules[0].RuleID)
}

func TestFabricRuleRepository_GetRulesByDomain(t *testing.T) {
	// Setup
	repo := NewFabricRuleRepository()
	stub := shimtest.NewMockStub("compliance", nil)

	// Create test rules for different domains
	loanRule := &ComplianceRule{
		RuleID:              "LOAN_DOMAIN_RULE",
		RuleName:            "Loan Domain Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "threshold"}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "LOAN",
		AppliesToEntityType: "LoanApplication",
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now(),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now(),
		BusinessJustification: "Loan domain test rule",
	}

	customerRule := &ComplianceRule{
		RuleID:              "CUSTOMER_DOMAIN_RULE",
		RuleName:            "Customer Domain Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "validation"}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "CUSTOMER",
		AppliesToEntityType: "Customer",
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now(),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now(),
		BusinessJustification: "Customer domain test rule",
	}

	// Save rules
	err := repo.SaveRule(stub, loanRule)
	require.NoError(t, err)
	err = repo.SaveRule(stub, customerRule)
	require.NoError(t, err)

	// Test getting rules by domain
	loanRules, err := repo.GetRulesByDomain(stub, "LOAN")
	assert.NoError(t, err)
	assert.Len(t, loanRules, 1)
	assert.Equal(t, "LOAN_DOMAIN_RULE", loanRules[0].RuleID)

	customerRules, err := repo.GetRulesByDomain(stub, "CUSTOMER")
	assert.NoError(t, err)
	assert.Len(t, customerRules, 1)
	assert.Equal(t, "CUSTOMER_DOMAIN_RULE", customerRules[0].RuleID)

	// Test getting rules for non-existent domain
	nonExistentRules, err := repo.GetRulesByDomain(stub, "NON_EXISTENT")
	assert.NoError(t, err)
	assert.Len(t, nonExistentRules, 0)
}

func TestFabricRuleRepository_GetRulesByEntityType(t *testing.T) {
	// Setup
	repo := NewFabricRuleRepository()
	stub := shimtest.NewMockStub("compliance", nil)

	// Create test rules for different entity types
	loanAppRule := &ComplianceRule{
		RuleID:              "LOAN_APP_RULE",
		RuleName:            "Loan Application Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "threshold"}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "LOAN",
		AppliesToEntityType: "LoanApplication",
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now(),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now(),
		BusinessJustification: "Loan application test rule",
	}

	customerRule := &ComplianceRule{
		RuleID:              "CUSTOMER_ENTITY_RULE",
		RuleName:            "Customer Entity Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "validation"}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "CUSTOMER",
		AppliesToEntityType: "Customer",
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now(),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now(),
		BusinessJustification: "Customer entity test rule",
	}

	// Save rules
	err := repo.SaveRule(stub, loanAppRule)
	require.NoError(t, err)
	err = repo.SaveRule(stub, customerRule)
	require.NoError(t, err)

	// Test getting rules by entity type
	loanAppRules, err := repo.GetRulesByEntityType(stub, "LoanApplication")
	assert.NoError(t, err)
	assert.Len(t, loanAppRules, 1)
	assert.Equal(t, "LOAN_APP_RULE", loanAppRules[0].RuleID)

	customerRules, err := repo.GetRulesByEntityType(stub, "Customer")
	assert.NoError(t, err)
	assert.Len(t, customerRules, 1)
	assert.Equal(t, "CUSTOMER_ENTITY_RULE", customerRules[0].RuleID)
}

func TestFabricRuleRepository_GetRulesByEvent(t *testing.T) {
	// Setup
	repo := NewFabricRuleRepository()
	stub := shimtest.NewMockStub("compliance", nil)

	// Create test rules with different trigger events
	loanSubmittedRule := &ComplianceRule{
		RuleID:              "LOAN_SUBMITTED_RULE",
		RuleName:            "Loan Submitted Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "threshold"}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "LOAN",
		AppliesToEntityType: "LoanApplication",
		TriggerEvents:       []string{"LoanSubmitted", "LoanUpdated"},
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now(),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now(),
		BusinessJustification: "Loan submitted event rule",
	}

	customerCreatedRule := &ComplianceRule{
		RuleID:              "CUSTOMER_CREATED_RULE",
		RuleName:            "Customer Created Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "validation"}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "CUSTOMER",
		AppliesToEntityType: "Customer",
		TriggerEvents:       []string{"CustomerCreated"},
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now(),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now(),
		BusinessJustification: "Customer created event rule",
	}

	// Save rules
	err := repo.SaveRule(stub, loanSubmittedRule)
	require.NoError(t, err)
	err = repo.SaveRule(stub, customerCreatedRule)
	require.NoError(t, err)

	// Test getting rules by event
	loanSubmittedRules, err := repo.GetRulesByEvent(stub, "LoanSubmitted")
	assert.NoError(t, err)
	assert.Len(t, loanSubmittedRules, 1)
	assert.Equal(t, "LOAN_SUBMITTED_RULE", loanSubmittedRules[0].RuleID)

	customerCreatedRules, err := repo.GetRulesByEvent(stub, "CustomerCreated")
	assert.NoError(t, err)
	assert.Len(t, customerCreatedRules, 1)
	assert.Equal(t, "CUSTOMER_CREATED_RULE", customerCreatedRules[0].RuleID)

	// Test getting rules for event that triggers multiple rules
	loanUpdatedRules, err := repo.GetRulesByEvent(stub, "LoanUpdated")
	assert.NoError(t, err)
	assert.Len(t, loanUpdatedRules, 1)
	assert.Equal(t, "LOAN_SUBMITTED_RULE", loanUpdatedRules[0].RuleID)
}

func TestFabricRuleRepository_GetRulesByStatus(t *testing.T) {
	// Setup
	repo := NewFabricRuleRepository()
	stub := shimtest.NewMockStub("compliance", nil)

	// Create test rules with different statuses
	activeRule := &ComplianceRule{
		RuleID:              "STATUS_ACTIVE_RULE",
		RuleName:            "Status Active Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "validation"}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "CUSTOMER",
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now(),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now(),
		BusinessJustification: "Active status test rule",
	}

	draftRule := &ComplianceRule{
		RuleID:              "STATUS_DRAFT_RULE",
		RuleName:            "Status Draft Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "validation"}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "CUSTOMER",
		Status:              RuleStatusDraft,
		EffectiveDate:       time.Now(),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now(),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now(),
		BusinessJustification: "Draft status test rule",
	}

	// Save rules
	err := repo.SaveRule(stub, activeRule)
	require.NoError(t, err)
	err = repo.SaveRule(stub, draftRule)
	require.NoError(t, err)

	// Test getting rules by status
	activeRules, err := repo.GetRulesByStatus(stub, RuleStatusActive)
	assert.NoError(t, err)
	assert.Len(t, activeRules, 1)
	assert.Equal(t, "STATUS_ACTIVE_RULE", activeRules[0].RuleID)

	draftRules, err := repo.GetRulesByStatus(stub, RuleStatusDraft)
	assert.NoError(t, err)
	assert.Len(t, draftRules, 1)
	assert.Equal(t, "STATUS_DRAFT_RULE", draftRules[0].RuleID)
}

func TestFabricRuleRepository_GetRulesByPriority(t *testing.T) {
	// Setup
	repo := NewFabricRuleRepository()
	stub := shimtest.NewMockStub("compliance", nil)

	// Create test rules with different priorities
	highPriorityRule := &ComplianceRule{
		RuleID:              "HIGH_PRIORITY_RULE",
		RuleName:            "High Priority Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "validation"}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityHigh,
		AppliesToDomain:     "CUSTOMER",
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now(),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now(),
		BusinessJustification: "High priority test rule",
	}

	lowPriorityRule := &ComplianceRule{
		RuleID:              "LOW_PRIORITY_RULE",
		RuleName:            "Low Priority Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "validation"}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityLow,
		AppliesToDomain:     "CUSTOMER",
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now(),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now(),
		BusinessJustification: "Low priority test rule",
	}

	// Save rules
	err := repo.SaveRule(stub, highPriorityRule)
	require.NoError(t, err)
	err = repo.SaveRule(stub, lowPriorityRule)
	require.NoError(t, err)

	// Test getting rules by priority
	highPriorityRules, err := repo.GetRulesByPriority(stub, PriorityHigh)
	assert.NoError(t, err)
	assert.Len(t, highPriorityRules, 1)
	assert.Equal(t, "HIGH_PRIORITY_RULE", highPriorityRules[0].RuleID)

	lowPriorityRules, err := repo.GetRulesByPriority(stub, PriorityLow)
	assert.NoError(t, err)
	assert.Len(t, lowPriorityRules, 1)
	assert.Equal(t, "LOW_PRIORITY_RULE", lowPriorityRules[0].RuleID)
}

func TestFabricRuleRepository_GetRuleHistory(t *testing.T) {
	// Setup
	repo := NewFabricRuleRepository()
	stub := shimtest.NewMockStub("compliance", nil)

	// Create multiple versions of the same rule
	ruleV1 := &ComplianceRule{
		RuleID:              "VERSIONED_RULE",
		RuleName:            "Versioned Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "threshold", "threshold": 1000}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "LOAN",
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-48 * time.Hour),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now().Add(-48 * time.Hour),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now().Add(-48 * time.Hour),
		BusinessJustification: "Version 1.0.0 of the rule",
	}

	ruleV2 := &ComplianceRule{
		RuleID:              "VERSIONED_RULE",
		RuleName:            "Versioned Rule",
		Version:             "2.0.0",
		RuleLogic:           `{"type": "threshold", "threshold": 2000}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityHigh,
		AppliesToDomain:     "LOAN",
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now().Add(-24 * time.Hour),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now().Add(-24 * time.Hour),
		BusinessJustification: "Version 2.0.0 of the rule",
	}

	// Save both versions
	err := repo.SaveRuleVersion(stub, ruleV1)
	require.NoError(t, err)
	err = repo.SaveRuleVersion(stub, ruleV2)
	require.NoError(t, err)

	// Update latest version pointer to v2
	latestKey := ruleV2.GetLatestVersionKey()
	err = stub.PutState(latestKey, []byte(ruleV2.Version))
	require.NoError(t, err)

	// Test getting rule history
	history, err := repo.GetRuleHistory(stub, "VERSIONED_RULE")
	assert.NoError(t, err)
	assert.Len(t, history, 2)

	// Check that both versions are present
	versions := make(map[string]*ComplianceRule)
	for _, rule := range history {
		versions[rule.Version] = rule
	}

	assert.Contains(t, versions, "1.0.0")
	assert.Contains(t, versions, "2.0.0")
	assert.Equal(t, PriorityMedium, versions["1.0.0"].Priority)
	assert.Equal(t, PriorityHigh, versions["2.0.0"].Priority)
}

func TestFabricRuleRepository_SearchRules(t *testing.T) {
	// Setup
	repo := NewFabricRuleRepository()
	stub := shimtest.NewMockStub("compliance", nil)

	// Create test rules with different names and descriptions
	rule1 := &ComplianceRule{
		RuleID:              "SEARCH_RULE_1",
		RuleName:            "KYC Verification Rule",
		RuleDescription:     "Rule for customer identity verification",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "validation"}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "CUSTOMER",
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now(),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now(),
		BusinessJustification: "Customer verification compliance",
	}

	rule2 := &ComplianceRule{
		RuleID:              "SEARCH_RULE_2",
		RuleName:            "AML Screening Rule",
		RuleDescription:     "Anti-money laundering screening rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "threshold"}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityHigh,
		AppliesToDomain:     "LOAN",
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now(),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now(),
		BusinessJustification: "Anti-money laundering compliance",
	}

	rule3 := &ComplianceRule{
		RuleID:              "SEARCH_RULE_3",
		RuleName:            "Loan Amount Validation",
		RuleDescription:     "Validates loan amounts against limits",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "threshold"}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "LOAN",
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now(),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now(),
		BusinessJustification: "Loan amount validation",
	}

	// Save all rules
	err := repo.SaveRule(stub, rule1)
	require.NoError(t, err)
	err = repo.SaveRule(stub, rule2)
	require.NoError(t, err)
	err = repo.SaveRule(stub, rule3)
	require.NoError(t, err)

	tests := []struct {
		name           string
		searchTerm     string
		expectedCount  int
		expectedRuleIDs []string
	}{
		{
			name:           "Search by 'verification'",
			searchTerm:     "verification",
			expectedCount:  2, // rule1 (name and description) and rule3 (business justification)
			expectedRuleIDs: []string{"SEARCH_RULE_1"},
		},
		{
			name:           "Search by 'AML'",
			searchTerm:     "AML",
			expectedCount:  1,
			expectedRuleIDs: []string{"SEARCH_RULE_2"},
		},
		{
			name:           "Search by 'loan'",
			searchTerm:     "loan",
			expectedCount:  2, // rule2 (description) and rule3 (name and justification)
			expectedRuleIDs: []string{"SEARCH_RULE_2", "SEARCH_RULE_3"},
		},
		{
			name:           "Search by 'compliance'",
			searchTerm:     "compliance",
			expectedCount:  2, // rule1 and rule2 (business justification)
			expectedRuleIDs: []string{"SEARCH_RULE_1", "SEARCH_RULE_2"},
		},
		{
			name:          "Search with no matches",
			searchTerm:    "nonexistent",
			expectedCount: 0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			results, err := repo.SearchRules(stub, tt.searchTerm)
			assert.NoError(t, err)
			assert.Len(t, results, tt.expectedCount)

			if tt.expectedCount > 0 {
				resultIDs := make([]string, len(results))
				for i, rule := range results {
					resultIDs[i] = rule.RuleID
				}

				for _, expectedID := range tt.expectedRuleIDs {
					assert.Contains(t, resultIDs, expectedID)
				}
			}
		})
	}
}

func TestFabricRuleRepository_DeleteRule(t *testing.T) {
	// Setup
	repo := NewFabricRuleRepository()
	stub := shimtest.NewMockStub("compliance", nil)

	// Create a test rule
	testRule := &ComplianceRule{
		RuleID:              "DELETE_TEST_RULE",
		RuleName:            "Delete Test Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "validation"}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "CUSTOMER",
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour),
		CreatedBy:           "TEST_USER",
		CreationDate:        time.Now(),
		LastModifiedBy:      "TEST_USER",
		LastModifiedDate:    time.Now(),
		BusinessJustification: "Rule to be deleted",
	}

	// Save the rule
	err := repo.SaveRule(stub, testRule)
	require.NoError(t, err)

	// Verify rule exists and is active
	rule, err := repo.GetLatestRule(stub, "DELETE_TEST_RULE")
	assert.NoError(t, err)
	assert.Equal(t, RuleStatusActive, rule.Status)

	// Delete the rule (soft delete - should mark as deprecated)
	err = repo.DeleteRule(stub, "DELETE_TEST_RULE")
	assert.NoError(t, err)

	// Verify rule is now deprecated
	deletedRule, err := repo.GetLatestRule(stub, "DELETE_TEST_RULE")
	assert.NoError(t, err)
	assert.Equal(t, RuleStatusDeprecated, deletedRule.Status)
}

func TestFabricRuleRepository_ValidationOnSave(t *testing.T) {
	// Setup
	repo := NewFabricRuleRepository()
	stub := shimtest.NewMockStub("compliance", nil)

	tests := []struct {
		name          string
		rule          *ComplianceRule
		expectedError bool
	}{
		{
			name: "Valid rule",
			rule: &ComplianceRule{
				RuleID:              "VALID_SAVE_RULE",
				RuleName:            "Valid Save Rule",
				RuleDescription:     "A valid rule for save testing",
				Version:             "1.0.0",
				RuleLogic:           `{"type": "validation"}`,
				ExecutionMode:       ExecutionModeSync,
				Priority:            PriorityMedium,
				AppliesToDomain:     "CUSTOMER",
				Status:              RuleStatusDraft,
				EffectiveDate:       time.Now(),
				CreatedBy:           "TEST_USER",
				CreationDate:        time.Now(),
				LastModifiedBy:      "TEST_USER",
				LastModifiedDate:    time.Now(),
				BusinessJustification: "Valid rule for testing",
			},
			expectedError: false,
		},
		{
			name: "Invalid rule - missing required fields",
			rule: &ComplianceRule{
				RuleID: "INVALID_SAVE_RULE",
				// Missing required fields
			},
			expectedError: true,
		},
		{
			name: "Invalid rule - invalid status",
			rule: &ComplianceRule{
				RuleID:              "INVALID_STATUS_SAVE_RULE",
				RuleName:            "Invalid Status Rule",
				RuleDescription:     "Rule with invalid status",
				Version:             "1.0.0",
				RuleLogic:           `{"type": "validation"}`,
				ExecutionMode:       ExecutionModeSync,
				Priority:            PriorityMedium,
				AppliesToDomain:     "CUSTOMER",
				Status:              ComplianceRuleStatus("INVALID_STATUS"),
				EffectiveDate:       time.Now(),
				CreatedBy:           "TEST_USER",
				CreationDate:        time.Now(),
				LastModifiedBy:      "TEST_USER",
				LastModifiedDate:    time.Now(),
				BusinessJustification: "Invalid status rule",
			},
			expectedError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := repo.SaveRule(stub, tt.rule)

			if tt.expectedError {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)

				// Verify rule was saved correctly
				savedRule, err := repo.GetLatestRule(stub, tt.rule.RuleID)
				assert.NoError(t, err)
				assert.Equal(t, tt.rule.RuleID, savedRule.RuleID)
				assert.Equal(t, tt.rule.RuleName, savedRule.RuleName)
			}
		})
	}
}