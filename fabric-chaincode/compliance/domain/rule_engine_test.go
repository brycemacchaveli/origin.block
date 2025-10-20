package domain

import (
	"context"
	"encoding/json"
	"fmt"
	"testing"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/hyperledger/fabric-chaincode-go/shimtest"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// setupMockStub creates a properly initialized mock stub for testing
func setupMockStubForRuleEngine() shim.ChaincodeStubInterface {
	stub := shimtest.NewMockStub("compliance", nil)
	stub.MockTransactionStart("txid")
	return stub
}

// MockRuleRepository implements RuleRepository for testing
type MockRuleRepository struct {
	rules map[string]*ComplianceRule
}

func NewMockRuleRepository() *MockRuleRepository {
	return &MockRuleRepository{
		rules: make(map[string]*ComplianceRule),
	}
}

func (m *MockRuleRepository) GetRule(stub shim.ChaincodeStubInterface, ruleID string, version string) (*ComplianceRule, error) {
	key := ruleID + ":" + version
	if rule, exists := m.rules[key]; exists {
		return rule, nil
	}
	return nil, fmt.Errorf("rule not found")
}

func (m *MockRuleRepository) GetLatestRule(stub shim.ChaincodeStubInterface, ruleID string) (*ComplianceRule, error) {
	// Find the latest version (simplified for testing)
	for _, rule := range m.rules {
		if rule.RuleID == ruleID {
			return rule, nil
		}
	}
	return nil, fmt.Errorf("rule not found")
}

func (m *MockRuleRepository) GetActiveRules(stub shim.ChaincodeStubInterface) ([]*ComplianceRule, error) {
	var activeRules []*ComplianceRule
	for _, rule := range m.rules {
		if rule.IsActive() {
			activeRules = append(activeRules, rule)
		}
	}
	return activeRules, nil
}

func (m *MockRuleRepository) GetRulesByDomain(stub shim.ChaincodeStubInterface, domain string) ([]*ComplianceRule, error) {
	var rules []*ComplianceRule
	for _, rule := range m.rules {
		if rule.AppliesToDomain == domain && rule.IsActive() {
			rules = append(rules, rule)
		}
	}
	return rules, nil
}

func (m *MockRuleRepository) GetRulesByEntityType(stub shim.ChaincodeStubInterface, entityType string) ([]*ComplianceRule, error) {
	var rules []*ComplianceRule
	for _, rule := range m.rules {
		if rule.AppliesToEntityType == entityType && rule.IsActive() {
			rules = append(rules, rule)
		}
	}
	return rules, nil
}

func (m *MockRuleRepository) GetRulesByEvent(stub shim.ChaincodeStubInterface, eventType string) ([]*ComplianceRule, error) {
	var rules []*ComplianceRule
	for _, rule := range m.rules {
		for _, trigger := range rule.TriggerEvents {
			if trigger == eventType && rule.IsActive() {
				rules = append(rules, rule)
				break
			}
		}
	}
	return rules, nil
}

func (m *MockRuleRepository) SaveRule(stub shim.ChaincodeStubInterface, rule *ComplianceRule) error {
	// Validate the rule before saving
	validationResults := rule.Validate()
	for _, result := range validationResults {
		if !result.IsValid {
			return fmt.Errorf("validation failed: %v", result.ErrorMessages)
		}
	}
	
	key := rule.RuleID + ":" + rule.Version
	m.rules[key] = rule
	return nil
}

func (m *MockRuleRepository) SaveRuleVersion(stub shim.ChaincodeStubInterface, rule *ComplianceRule) error {
	return m.SaveRule(stub, rule)
}

// MockEventEmitter implements EventEmitter for testing
type MockEventEmitter struct {
	events []*ComplianceEvent
}

func NewMockEventEmitter() *MockEventEmitter {
	return &MockEventEmitter{
		events: make([]*ComplianceEvent, 0),
	}
}

func (m *MockEventEmitter) EmitComplianceEvent(stub shim.ChaincodeStubInterface, event *ComplianceEvent) error {
	m.events = append(m.events, event)
	return nil
}

func (m *MockEventEmitter) EmitRuleExecutionEvent(stub shim.ChaincodeStubInterface, result *RuleExecutionResult) error {
	event := &ComplianceEvent{
		EventID:         fmt.Sprintf("rule_exec_%s", result.ExecutionID),
		Timestamp:       result.Timestamp,
		RuleID:          result.RuleID,
		EventType:       "RULE_EXECUTED",
		ExecutionResult: *result,
	}
	return m.EmitComplianceEvent(stub, event)
}

func TestComplianceRuleEngine_ExecuteRule(t *testing.T) {
	// Setup
	mockRepo := NewMockRuleRepository()
	mockEmitter := NewMockEventEmitter()
	engine := NewComplianceRuleEngine(mockRepo, mockEmitter)
	stub := setupMockStubForRuleEngine()

	// Create a test rule
	testRule := &ComplianceRule{
		RuleID:              "TEST_RULE_001",
		RuleName:            "Test Threshold Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "threshold", "field": "amount", "threshold": 1000, "operator": ">"}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "LOAN",
		AppliesToEntityType: "LoanApplication",
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour), // Yesterday
		ValidationResults: []ValidationResult{
			{
				ValidationID:   "test_validation",
				ValidationType: "SYNTAX",
				IsValid:        true,
				ValidationDate: time.Now(),
			},
		},
	}

	// Save the rule
	err := mockRepo.SaveRule(stub, testRule)
	require.NoError(t, err)

	tests := []struct {
		name           string
		ruleID         string
		entityData     map[string]interface{}
		expectedPassed bool
		expectedError  bool
	}{
		{
			name:   "Rule passes with amount above threshold",
			ruleID: "TEST_RULE_001",
			entityData: map[string]interface{}{
				"amount": 1500.0,
			},
			expectedPassed: true,
			expectedError:  false,
		},
		{
			name:   "Rule fails with amount below threshold",
			ruleID: "TEST_RULE_001",
			entityData: map[string]interface{}{
				"amount": 500.0,
			},
			expectedPassed: false,
			expectedError:  false,
		},
		{
			name:   "Rule fails with missing field",
			ruleID: "TEST_RULE_001",
			entityData: map[string]interface{}{
				"other_field": "value",
			},
			expectedPassed: false,
			expectedError:  false,
		},
		{
			name:          "Error with non-existent rule",
			ruleID:        "NON_EXISTENT_RULE",
			entityData:    map[string]interface{}{},
			expectedError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			ctx := context.Background()
			result, err := engine.ExecuteRule(ctx, stub, tt.ruleID, tt.entityData)

			if tt.expectedError {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
				assert.Equal(t, tt.expectedPassed, result.Passed)
				assert.True(t, result.Success)
				assert.NotEmpty(t, result.ExecutionID)
				if result.ExecutionTime == 0 {
					t.Logf("ExecutionTime is 0, result: %+v", result)
				}
				assert.NotZero(t, result.ExecutionTime)
			}
		})
	}
}

func TestComplianceRuleEngine_ExecuteRulesForEntity(t *testing.T) {
	// Setup
	mockRepo := NewMockRuleRepository()
	mockEmitter := NewMockEventEmitter()
	engine := NewComplianceRuleEngine(mockRepo, mockEmitter)
	stub := setupMockStubForRuleEngine()

	// Create test rules
	rule1 := &ComplianceRule{
		RuleID:              "ENTITY_RULE_001",
		RuleName:            "Entity Rule 1",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "validation", "validations": [{"field": "status", "required": true}]}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "CUSTOMER",
		AppliesToEntityType: "Customer",
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour),
		ValidationResults: []ValidationResult{
			{IsValid: true, ValidationDate: time.Now()},
		},
	}

	rule2 := &ComplianceRule{
		RuleID:              "ENTITY_RULE_002",
		RuleName:            "Entity Rule 2",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "threshold", "field": "age", "threshold": 18, "operator": ">="}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityHigh,
		AppliesToDomain:     "CUSTOMER",
		AppliesToEntityType: "Customer",
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour),
		ValidationResults: []ValidationResult{
			{IsValid: true, ValidationDate: time.Now()},
		},
	}

	// Save the rules
	err := mockRepo.SaveRule(stub, rule1)
	require.NoError(t, err)
	err = mockRepo.SaveRule(stub, rule2)
	require.NoError(t, err)

	// Test execution
	ctx := context.Background()
	entityData := map[string]interface{}{
		"status": "ACTIVE",
		"age":    25.0,
	}

	results, err := engine.ExecuteRulesForEntity(ctx, stub, "Customer", entityData)
	assert.NoError(t, err)
	assert.Len(t, results, 2)

	// Both rules should pass
	for _, result := range results {
		assert.True(t, result.Success)
		assert.True(t, result.Passed)
	}
}

func TestComplianceRuleEngine_ValidateRule(t *testing.T) {
	// Setup
	mockRepo := NewMockRuleRepository()
	mockEmitter := NewMockEventEmitter()
	engine := NewComplianceRuleEngine(mockRepo, mockEmitter)
	stub := setupMockStubForRuleEngine()

	tests := []struct {
		name          string
		rule          *ComplianceRule
		expectedValid bool
	}{
		{
			name: "Valid rule",
			rule: &ComplianceRule{
				RuleID:              "VALID_RULE",
				RuleName:            "Valid Rule",
				RuleDescription:     "A valid compliance rule",
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
				BusinessJustification: "Test rule for validation",
			},
			expectedValid: true,
		},
		{
			name: "Invalid rule - missing required fields",
			rule: &ComplianceRule{
				RuleID: "INVALID_RULE",
				// Missing required fields
			},
			expectedValid: false,
		},
		{
			name: "Invalid rule - invalid status",
			rule: &ComplianceRule{
				RuleID:              "INVALID_STATUS_RULE",
				RuleName:            "Invalid Status Rule",
				RuleDescription:     "Rule with invalid status",
				Version:             "1.0.0",
				RuleLogic:           `{"type": "threshold", "field": "amount", "threshold": 1000}`,
				ExecutionMode:       ExecutionModeSync,
				Priority:            PriorityMedium,
				AppliesToDomain:     "LOAN",
				Status:              ComplianceRuleStatus("INVALID_STATUS"),
				EffectiveDate:       time.Now(),
				CreatedBy:           "TEST_USER",
				CreationDate:        time.Now(),
				LastModifiedBy:      "TEST_USER",
				LastModifiedDate:    time.Now(),
				BusinessJustification: "Test rule with invalid status",
			},
			expectedValid: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			ctx := context.Background()
			results, err := engine.ValidateRule(ctx, stub, tt.rule)
			assert.NoError(t, err)
			assert.NotEmpty(t, results)

			// Check if all validations passed
			allValid := true
			for _, result := range results {
				if !result.IsValid {
					allValid = false
					break
				}
			}

			assert.Equal(t, tt.expectedValid, allValid)
		})
	}
}

func TestComplianceRuleEngine_TestRule(t *testing.T) {
	// Setup
	mockRepo := NewMockRuleRepository()
	mockEmitter := NewMockEventEmitter()
	engine := NewComplianceRuleEngine(mockRepo, mockEmitter)
	stub := setupMockStubForRuleEngine()

	// Create a test rule with test cases
	testRule := &ComplianceRule{
		RuleID:              "TEST_RULE_WITH_CASES",
		RuleName:            "Test Rule With Cases",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "threshold", "field": "amount", "threshold": 1000, "operator": ">"}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "LOAN",
		AppliesToEntityType: "LoanApplication",
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour),
		ValidationResults: []ValidationResult{
			{IsValid: true, ValidationDate: time.Now()},
		},
		TestCases: []RuleTestCase{
			{
				TestID:          "TEST_CASE_PASS",
				TestName:        "Amount Above Threshold",
				TestDescription: "Test with amount above 1000",
				InputData: map[string]interface{}{
					"amount": 1500.0,
				},
				ExpectedResult: RuleExecutionResult{
					Passed: true,
				},
				CreatedBy:    "TEST_USER",
				CreationDate: time.Now(),
			},
			{
				TestID:          "TEST_CASE_FAIL",
				TestName:        "Amount Below Threshold",
				TestDescription: "Test with amount below 1000",
				InputData: map[string]interface{}{
					"amount": 500.0,
				},
				ExpectedResult: RuleExecutionResult{
					Passed: false,
				},
				CreatedBy:    "TEST_USER",
				CreationDate: time.Now(),
			},
		},
	}

	// Save the rule
	err := mockRepo.SaveRule(stub, testRule)
	require.NoError(t, err)

	// Test individual test case
	ctx := context.Background()
	result, err := engine.TestRule(ctx, stub, "TEST_RULE_WITH_CASES", "TEST_CASE_PASS")
	assert.NoError(t, err)
	assert.True(t, result.Success)
	assert.True(t, result.Passed)
	assert.Contains(t, result.Details, "testCase")
	assert.Contains(t, result.Details, "expectedResult")
	assert.Contains(t, result.Details, "testPassed")

	// Test all test cases
	results, err := engine.RunAllTests(ctx, stub, "TEST_RULE_WITH_CASES")
	assert.NoError(t, err)
	assert.Len(t, results, 2)

	// First test should pass, second should fail
	assert.True(t, results[0].Passed)
	assert.False(t, results[1].Passed)
}

func TestComplianceRuleEngine_DependencyResolution(t *testing.T) {
	// Setup
	mockRepo := NewMockRuleRepository()
	mockEmitter := NewMockEventEmitter()
	engine := NewComplianceRuleEngine(mockRepo, mockEmitter)
	stub := setupMockStubForRuleEngine()

	// Create rules with dependencies
	baseRule := &ComplianceRule{
		RuleID:              "BASE_RULE",
		RuleName:            "Base Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "validation", "validations": [{"field": "base", "required": true}]}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "CUSTOMER",
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour),
		ValidationResults: []ValidationResult{
			{IsValid: true, ValidationDate: time.Now()},
		},
	}

	dependentRule := &ComplianceRule{
		RuleID:              "DEPENDENT_RULE",
		RuleName:            "Dependent Rule",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "validation", "validations": [{"field": "dependent", "required": true}]}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "CUSTOMER",
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour),
		Dependencies:        []string{"BASE_RULE"},
		ValidationResults: []ValidationResult{
			{IsValid: true, ValidationDate: time.Now()},
		},
	}

	// Save the rules
	err := mockRepo.SaveRule(stub, baseRule)
	require.NoError(t, err)
	err = mockRepo.SaveRule(stub, dependentRule)
	require.NoError(t, err)

	// Test dependency resolution
	ctx := context.Background()
	dependencies, err := engine.ResolveDependencies(ctx, stub, "DEPENDENT_RULE")
	assert.NoError(t, err)
	assert.Contains(t, dependencies, "BASE_RULE")
	assert.Contains(t, dependencies, "DEPENDENT_RULE")

	// Test execution order
	ruleIDs := []string{"DEPENDENT_RULE", "BASE_RULE"}
	order, err := engine.GetExecutionOrder(ctx, stub, ruleIDs)
	assert.NoError(t, err)
	assert.Len(t, order, 2)
	// BASE_RULE should come before DEPENDENT_RULE
	baseIndex := -1
	dependentIndex := -1
	for i, ruleID := range order {
		if ruleID == "BASE_RULE" {
			baseIndex = i
		}
		if ruleID == "DEPENDENT_RULE" {
			dependentIndex = i
		}
	}
	assert.True(t, baseIndex < dependentIndex, "BASE_RULE should come before DEPENDENT_RULE")
}

func TestComplianceRuleEngine_ConflictDetection(t *testing.T) {
	// Setup
	mockRepo := NewMockRuleRepository()
	mockEmitter := NewMockEventEmitter()
	engine := NewComplianceRuleEngine(mockRepo, mockEmitter)
	stub := setupMockStubForRuleEngine()

	// Create conflicting rules
	rule1 := &ComplianceRule{
		RuleID:              "RULE_1",
		RuleName:            "Rule 1",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "validation", "validations": [{"field": "field1", "required": true}]}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "CUSTOMER",
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour),
		ConflictsWith:       []string{"RULE_2"},
		ValidationResults: []ValidationResult{
			{IsValid: true, ValidationDate: time.Now()},
		},
	}

	rule2 := &ComplianceRule{
		RuleID:              "RULE_2",
		RuleName:            "Rule 2",
		Version:             "1.0.0",
		RuleLogic:           `{"type": "validation", "validations": [{"field": "field2", "required": true}]}`,
		ExecutionMode:       ExecutionModeSync,
		Priority:            PriorityMedium,
		AppliesToDomain:     "CUSTOMER",
		Status:              RuleStatusActive,
		EffectiveDate:       time.Now().Add(-24 * time.Hour),
		ValidationResults: []ValidationResult{
			{IsValid: true, ValidationDate: time.Now()},
		},
	}

	// Save the rules
	err := mockRepo.SaveRule(stub, rule1)
	require.NoError(t, err)
	err = mockRepo.SaveRule(stub, rule2)
	require.NoError(t, err)

	// Test conflict detection
	ctx := context.Background()
	conflicts, err := engine.CheckConflicts(ctx, stub, "RULE_1")
	assert.NoError(t, err)
	assert.Contains(t, conflicts, "RULE_2")
}

func TestComplianceRule_Validation(t *testing.T) {
	tests := []struct {
		name          string
		rule          *ComplianceRule
		expectedValid bool
	}{
		{
			name: "Valid rule",
			rule: &ComplianceRule{
				RuleID:              "VALID_RULE",
				RuleName:            "Valid Rule",
				RuleDescription:     "A valid compliance rule",
				RuleLogic:           `{"type": "threshold", "field": "amount", "threshold": 1000}`,
				ExecutionMode:       ExecutionModeSync,
				Priority:            PriorityMedium,
				AppliesToDomain:     "LOAN",
				Status:              RuleStatusDraft,
				EffectiveDate:       time.Now(),
				BusinessJustification: "Test rule",
			},
			expectedValid: true,
		},
		{
			name: "Invalid rule - missing RuleID",
			rule: &ComplianceRule{
				RuleName:        "Invalid Rule",
				RuleDescription: "Rule without ID",
				RuleLogic:       `{"type": "threshold"}`,
				ExecutionMode:   ExecutionModeSync,
				Priority:        PriorityMedium,
				AppliesToDomain: "LOAN",
				Status:          RuleStatusDraft,
			},
			expectedValid: false,
		},
		{
			name: "Invalid rule - circular dependency",
			rule: &ComplianceRule{
				RuleID:              "CIRCULAR_RULE",
				RuleName:            "Circular Rule",
				RuleDescription:     "Rule with circular dependency",
				RuleLogic:           `{"type": "validation"}`,
				ExecutionMode:       ExecutionModeSync,
				Priority:            PriorityMedium,
				AppliesToDomain:     "LOAN",
				Status:              RuleStatusDraft,
				Dependencies:        []string{"CIRCULAR_RULE"}, // Self-dependency
				BusinessJustification: "Test rule",
			},
			expectedValid: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			results := tt.rule.Validate()
			assert.NotEmpty(t, results)

			// Check if all validations passed
			allValid := true
			for _, result := range results {
				if !result.IsValid {
					allValid = false
					break
				}
			}

			assert.Equal(t, tt.expectedValid, allValid)
		})
	}
}

func TestComplianceRule_IsActive(t *testing.T) {
	now := time.Now()

	tests := []struct {
		name           string
		rule           *ComplianceRule
		expectedActive bool
	}{
		{
			name: "Active rule",
			rule: &ComplianceRule{
				Status:        RuleStatusActive,
				EffectiveDate: now.Add(-24 * time.Hour), // Yesterday
			},
			expectedActive: true,
		},
		{
			name: "Inactive rule - wrong status",
			rule: &ComplianceRule{
				Status:        RuleStatusDraft,
				EffectiveDate: now.Add(-24 * time.Hour),
			},
			expectedActive: false,
		},
		{
			name: "Inactive rule - future effective date",
			rule: &ComplianceRule{
				Status:        RuleStatusActive,
				EffectiveDate: now.Add(24 * time.Hour), // Tomorrow
			},
			expectedActive: false,
		},
		{
			name: "Inactive rule - expired",
			rule: &ComplianceRule{
				Status:         RuleStatusActive,
				EffectiveDate:  now.Add(-48 * time.Hour), // 2 days ago
				ExpirationDate: &[]time.Time{now.Add(-24 * time.Hour)}[0], // Yesterday
			},
			expectedActive: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			assert.Equal(t, tt.expectedActive, tt.rule.IsActive())
		})
	}
}

func TestRuleExecutionResult_JSON(t *testing.T) {
	result := RuleExecutionResult{
		RuleID:        "TEST_RULE",
		ExecutionID:   "exec_123",
		Timestamp:     time.Now(),
		Success:       true,
		Passed:        true,
		Score:         0.95,
		Details:       map[string]interface{}{"field": "value"},
		ExecutionTime: 150,
	}

	// Test JSON marshaling
	jsonBytes, err := json.Marshal(result)
	assert.NoError(t, err)
	assert.NotEmpty(t, jsonBytes)

	// Test JSON unmarshaling
	var unmarshaled RuleExecutionResult
	err = json.Unmarshal(jsonBytes, &unmarshaled)
	assert.NoError(t, err)
	assert.Equal(t, result.RuleID, unmarshaled.RuleID)
	assert.Equal(t, result.Success, unmarshaled.Success)
	assert.Equal(t, result.Passed, unmarshaled.Passed)
}