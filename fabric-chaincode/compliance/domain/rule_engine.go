package domain

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/shim"
)

// RuleEngine defines the interface for executing compliance rules
type RuleEngine interface {
	// Rule execution
	ExecuteRule(ctx context.Context, stub shim.ChaincodeStubInterface, ruleID string, entityData map[string]interface{}) (RuleExecutionResult, error)
	ExecuteRulesForEntity(ctx context.Context, stub shim.ChaincodeStubInterface, entityType string, entityData map[string]interface{}) ([]RuleExecutionResult, error)
	ExecuteRulesForEvent(ctx context.Context, stub shim.ChaincodeStubInterface, eventType string, entityData map[string]interface{}) ([]RuleExecutionResult, error)
	
	// Rule validation and testing
	ValidateRule(ctx context.Context, stub shim.ChaincodeStubInterface, rule *ComplianceRule) ([]ValidationResult, error)
	TestRule(ctx context.Context, stub shim.ChaincodeStubInterface, ruleID string, testCaseID string) (RuleExecutionResult, error)
	RunAllTests(ctx context.Context, stub shim.ChaincodeStubInterface, ruleID string) ([]RuleExecutionResult, error)
	
	// Dependency management
	ResolveDependencies(ctx context.Context, stub shim.ChaincodeStubInterface, ruleID string) ([]string, error)
	CheckConflicts(ctx context.Context, stub shim.ChaincodeStubInterface, ruleID string) ([]string, error)
	GetExecutionOrder(ctx context.Context, stub shim.ChaincodeStubInterface, ruleIDs []string) ([]string, error)
}

// ComplianceRuleEngine implements the RuleEngine interface
type ComplianceRuleEngine struct {
	ruleRepository RuleRepository
	eventEmitter   EventEmitter
}

// RuleRepository defines the interface for rule persistence
type RuleRepository interface {
	GetRule(stub shim.ChaincodeStubInterface, ruleID string, version string) (*ComplianceRule, error)
	GetLatestRule(stub shim.ChaincodeStubInterface, ruleID string) (*ComplianceRule, error)
	GetActiveRules(stub shim.ChaincodeStubInterface) ([]*ComplianceRule, error)
	GetRulesByDomain(stub shim.ChaincodeStubInterface, domain string) ([]*ComplianceRule, error)
	GetRulesByEntityType(stub shim.ChaincodeStubInterface, entityType string) ([]*ComplianceRule, error)
	GetRulesByEvent(stub shim.ChaincodeStubInterface, eventType string) ([]*ComplianceRule, error)
	SaveRule(stub shim.ChaincodeStubInterface, rule *ComplianceRule) error
	SaveRuleVersion(stub shim.ChaincodeStubInterface, rule *ComplianceRule) error
}

// EventEmitter defines the interface for emitting compliance events
type EventEmitter interface {
	EmitComplianceEvent(stub shim.ChaincodeStubInterface, event *ComplianceEvent) error
	EmitRuleExecutionEvent(stub shim.ChaincodeStubInterface, result *RuleExecutionResult) error
}

// NewComplianceRuleEngine creates a new rule engine instance
func NewComplianceRuleEngine(repository RuleRepository, emitter EventEmitter) *ComplianceRuleEngine {
	return &ComplianceRuleEngine{
		ruleRepository: repository,
		eventEmitter:   emitter,
	}
}

// ExecuteRule executes a specific compliance rule against entity data
func (e *ComplianceRuleEngine) ExecuteRule(ctx context.Context, stub shim.ChaincodeStubInterface, ruleID string, entityData map[string]interface{}) (RuleExecutionResult, error) {
	startTime := time.Now()
	
	result := RuleExecutionResult{
		RuleID:      ruleID,
		ExecutionID: fmt.Sprintf("exec_%s_%d", ruleID, startTime.Unix()),
		Timestamp:   startTime,
		Success:     false,
		Passed:      false,
		Details:     make(map[string]interface{}),
	}
	
	// Get the latest version of the rule
	rule, err := e.ruleRepository.GetLatestRule(stub, ruleID)
	if err != nil {
		result.ErrorMessage = fmt.Sprintf("Failed to retrieve rule: %v", err)
		result.ExecutionTime = time.Since(startTime).Milliseconds()
		return result, err
	}
	
	// Check if rule can be executed
	if !rule.CanExecute() {
		result.ErrorMessage = "Rule is not in executable state"
		result.ExecutionTime = calculateExecutionTime(startTime)
		return result, fmt.Errorf("rule %s is not executable", ruleID)
	}
	
	// Execute rule dependencies first
	if len(rule.Dependencies) > 0 {
		dependencyResults, err := e.executeDependencies(ctx, stub, rule.Dependencies, entityData)
		if err != nil {
			result.ErrorMessage = fmt.Sprintf("Failed to execute dependencies: %v", err)
			result.ExecutionTime = calculateExecutionTime(startTime)
			return result, err
		}
		
		// Check if all dependencies passed
		for _, depResult := range dependencyResults {
			if !depResult.Passed {
				result.ErrorMessage = fmt.Sprintf("Dependency rule %s failed", depResult.RuleID)
				result.ExecutionTime = calculateExecutionTime(startTime)
				return result, fmt.Errorf("dependency rule %s failed", depResult.RuleID)
			}
		}
		
		result.Details["dependencyResults"] = dependencyResults
	}
	
	// Execute the rule logic
	ruleResult, err := e.executeRuleLogic(rule, entityData)
	if err != nil {
		result.ErrorMessage = fmt.Sprintf("Rule execution failed: %v", err)
		result.ExecutionTime = calculateExecutionTime(startTime)
		return result, err
	}
	
	result.Success = true
	result.Passed = ruleResult.Passed
	result.Score = ruleResult.Score
	result.Details = ruleResult.Details
	result.ExecutionTime = calculateExecutionTime(startTime)
	
	// Emit execution event
	if e.eventEmitter != nil {
		e.eventEmitter.EmitRuleExecutionEvent(stub, &result)
	}
	
	return result, nil
}

// ExecuteRulesForEntity executes all applicable rules for a specific entity type
func (e *ComplianceRuleEngine) ExecuteRulesForEntity(ctx context.Context, stub shim.ChaincodeStubInterface, entityType string, entityData map[string]interface{}) ([]RuleExecutionResult, error) {
	rules, err := e.ruleRepository.GetRulesByEntityType(stub, entityType)
	if err != nil {
		return nil, fmt.Errorf("failed to get rules for entity type %s: %v", entityType, err)
	}
	
	var results []RuleExecutionResult
	
	// Get execution order based on dependencies
	ruleIDs := make([]string, len(rules))
	for i, rule := range rules {
		ruleIDs[i] = rule.RuleID
	}
	
	executionOrder, err := e.GetExecutionOrder(ctx, stub, ruleIDs)
	if err != nil {
		return nil, fmt.Errorf("failed to determine execution order: %v", err)
	}
	
	// Execute rules in dependency order
	for _, ruleID := range executionOrder {
		result, err := e.ExecuteRule(ctx, stub, ruleID, entityData)
		if err != nil {
			// Continue with other rules even if one fails
			result.Success = false
			result.ErrorMessage = err.Error()
		}
		results = append(results, result)
	}
	
	return results, nil
}

// ExecuteRulesForEvent executes all rules triggered by a specific event
func (e *ComplianceRuleEngine) ExecuteRulesForEvent(ctx context.Context, stub shim.ChaincodeStubInterface, eventType string, entityData map[string]interface{}) ([]RuleExecutionResult, error) {
	rules, err := e.ruleRepository.GetRulesByEvent(stub, eventType)
	if err != nil {
		return nil, fmt.Errorf("failed to get rules for event %s: %v", eventType, err)
	}
	
	var results []RuleExecutionResult
	
	for _, rule := range rules {
		result, err := e.ExecuteRule(ctx, stub, rule.RuleID, entityData)
		if err != nil {
			// Continue with other rules even if one fails
			result.Success = false
			result.ErrorMessage = err.Error()
		}
		results = append(results, result)
	}
	
	return results, nil
}

// ValidateRule performs comprehensive validation of a compliance rule
func (e *ComplianceRuleEngine) ValidateRule(ctx context.Context, stub shim.ChaincodeStubInterface, rule *ComplianceRule) ([]ValidationResult, error) {
	// Perform built-in validations
	results := rule.Validate()
	
	// Additional validations that require repository access
	
	// Validate dependencies exist
	for _, depID := range rule.Dependencies {
		_, err := e.ruleRepository.GetLatestRule(stub, depID)
		if err != nil {
			depResult := ValidationResult{
				ValidationID:   fmt.Sprintf("dep_exist_%s_%d", rule.RuleID, time.Now().Unix()),
				ValidationType: "DEPENDENCY",
				IsValid:        false,
				ErrorMessages:  []string{fmt.Sprintf("Dependency rule %s does not exist", depID)},
				ValidationDate: time.Now(),
			}
			results = append(results, depResult)
		}
	}
	
	// Validate conflicts
	for _, conflictID := range rule.ConflictsWith {
		conflictRule, err := e.ruleRepository.GetLatestRule(stub, conflictID)
		if err == nil && conflictRule.IsActive() {
			conflictResult := ValidationResult{
				ValidationID:   fmt.Sprintf("conflict_%s_%d", rule.RuleID, time.Now().Unix()),
				ValidationType: "CONFLICT",
				IsValid:        false,
				ErrorMessages:  []string{fmt.Sprintf("Conflicting rule %s is currently active", conflictID)},
				ValidationDate: time.Now(),
			}
			results = append(results, conflictResult)
		}
	}
	
	return results, nil
}

// TestRule executes a specific test case for a rule
func (e *ComplianceRuleEngine) TestRule(ctx context.Context, stub shim.ChaincodeStubInterface, ruleID string, testCaseID string) (RuleExecutionResult, error) {
	rule, err := e.ruleRepository.GetLatestRule(stub, ruleID)
	if err != nil {
		return RuleExecutionResult{}, fmt.Errorf("failed to get rule %s: %v", ruleID, err)
	}
	
	// Find the test case
	var testCase *RuleTestCase
	for _, tc := range rule.TestCases {
		if tc.TestID == testCaseID {
			testCase = &tc
			break
		}
	}
	
	if testCase == nil {
		return RuleExecutionResult{}, fmt.Errorf("test case %s not found for rule %s", testCaseID, ruleID)
	}
	
	// Execute the rule with test data
	result, err := e.ExecuteRule(ctx, stub, ruleID, testCase.InputData)
	if err != nil {
		return result, err
	}
	
	// Compare with expected result
	result.Details["testCase"] = testCase
	result.Details["expectedResult"] = testCase.ExpectedResult
	result.Details["testPassed"] = result.Passed == testCase.ExpectedResult.Passed
	
	return result, nil
}

// RunAllTests executes all test cases for a rule
func (e *ComplianceRuleEngine) RunAllTests(ctx context.Context, stub shim.ChaincodeStubInterface, ruleID string) ([]RuleExecutionResult, error) {
	rule, err := e.ruleRepository.GetLatestRule(stub, ruleID)
	if err != nil {
		return nil, fmt.Errorf("failed to get rule %s: %v", ruleID, err)
	}
	
	var results []RuleExecutionResult
	
	for _, testCase := range rule.TestCases {
		result, err := e.TestRule(ctx, stub, ruleID, testCase.TestID)
		if err != nil {
			result = RuleExecutionResult{
				RuleID:       ruleID,
				ExecutionID:  fmt.Sprintf("test_%s_%s", ruleID, testCase.TestID),
				Timestamp:    time.Now(),
				Success:      false,
				ErrorMessage: err.Error(),
			}
		}
		results = append(results, result)
	}
	
	return results, nil
}

// ResolveDependencies returns the list of dependencies for a rule in execution order
func (e *ComplianceRuleEngine) ResolveDependencies(ctx context.Context, stub shim.ChaincodeStubInterface, ruleID string) ([]string, error) {
	visited := make(map[string]bool)
	visiting := make(map[string]bool)
	var result []string
	
	err := e.resolveDependenciesRecursive(stub, ruleID, visited, visiting, &result)
	if err != nil {
		return nil, err
	}
	
	return result, nil
}

// CheckConflicts returns the list of rules that conflict with the given rule
func (e *ComplianceRuleEngine) CheckConflicts(ctx context.Context, stub shim.ChaincodeStubInterface, ruleID string) ([]string, error) {
	rule, err := e.ruleRepository.GetLatestRule(stub, ruleID)
	if err != nil {
		return nil, fmt.Errorf("failed to get rule %s: %v", ruleID, err)
	}
	
	var conflicts []string
	
	for _, conflictID := range rule.ConflictsWith {
		conflictRule, err := e.ruleRepository.GetLatestRule(stub, conflictID)
		if err == nil && conflictRule.IsActive() {
			conflicts = append(conflicts, conflictID)
		}
	}
	
	return conflicts, nil
}

// GetExecutionOrder determines the optimal execution order for a set of rules
func (e *ComplianceRuleEngine) GetExecutionOrder(ctx context.Context, stub shim.ChaincodeStubInterface, ruleIDs []string) ([]string, error) {
	// Build dependency graph
	graph := make(map[string][]string)
	inDegree := make(map[string]int)
	
	// Initialize
	for _, ruleID := range ruleIDs {
		graph[ruleID] = []string{}
		inDegree[ruleID] = 0
	}
	
	// Build edges
	for _, ruleID := range ruleIDs {
		rule, err := e.ruleRepository.GetLatestRule(stub, ruleID)
		if err != nil {
			continue // Skip rules that can't be loaded
		}
		
		for _, dep := range rule.Dependencies {
			if _, exists := inDegree[dep]; exists {
				graph[dep] = append(graph[dep], ruleID)
				inDegree[ruleID]++
			}
		}
	}
	
	// Topological sort using Kahn's algorithm
	var queue []string
	for ruleID, degree := range inDegree {
		if degree == 0 {
			queue = append(queue, ruleID)
		}
	}
	
	var result []string
	for len(queue) > 0 {
		current := queue[0]
		queue = queue[1:]
		result = append(result, current)
		
		for _, neighbor := range graph[current] {
			inDegree[neighbor]--
			if inDegree[neighbor] == 0 {
				queue = append(queue, neighbor)
			}
		}
	}
	
	// Check for circular dependencies
	if len(result) != len(ruleIDs) {
		return nil, fmt.Errorf("circular dependency detected in rules")
	}
	
	return result, nil
}

// Helper methods

// executeDependencies executes all dependency rules
func (e *ComplianceRuleEngine) executeDependencies(ctx context.Context, stub shim.ChaincodeStubInterface, dependencies []string, entityData map[string]interface{}) ([]RuleExecutionResult, error) {
	var results []RuleExecutionResult
	
	for _, depID := range dependencies {
		result, err := e.ExecuteRule(ctx, stub, depID, entityData)
		if err != nil {
			return nil, fmt.Errorf("failed to execute dependency %s: %v", depID, err)
		}
		results = append(results, result)
	}
	
	return results, nil
}

// executeRuleLogic executes the actual rule logic
func (e *ComplianceRuleEngine) executeRuleLogic(rule *ComplianceRule, entityData map[string]interface{}) (RuleExecutionResult, error) {
	result := RuleExecutionResult{
		RuleID:    rule.RuleID,
		Timestamp: time.Now(),
		Success:   true,
		Details:   make(map[string]interface{}),
	}
	
	// Parse rule logic (simplified implementation)
	// In a real implementation, this would use a proper rule engine like Drools or a custom DSL
	var ruleLogic map[string]interface{}
	if err := json.Unmarshal([]byte(rule.RuleLogic), &ruleLogic); err != nil {
		return result, fmt.Errorf("failed to parse rule logic: %v", err)
	}
	
	// Execute rule based on logic type
	logicType, ok := ruleLogic["type"].(string)
	if !ok {
		return result, fmt.Errorf("rule logic must specify a type")
	}
	
	switch logicType {
	case "threshold":
		return e.executeThresholdRule(ruleLogic, entityData)
	case "validation":
		return e.executeValidationRule(ruleLogic, entityData)
	case "comparison":
		return e.executeComparisonRule(ruleLogic, entityData)
	default:
		return result, fmt.Errorf("unsupported rule logic type: %s", logicType)
	}
}

// executeThresholdRule executes a threshold-based rule
func (e *ComplianceRuleEngine) executeThresholdRule(ruleLogic map[string]interface{}, entityData map[string]interface{}) (RuleExecutionResult, error) {
	result := RuleExecutionResult{
		Timestamp: time.Now(),
		Success:   true,
		Details:   make(map[string]interface{}),
	}
	
	field, ok := ruleLogic["field"].(string)
	if !ok {
		return result, fmt.Errorf("threshold rule must specify a field")
	}
	
	threshold, ok := ruleLogic["threshold"].(float64)
	if !ok {
		return result, fmt.Errorf("threshold rule must specify a threshold value")
	}
	
	operator, ok := ruleLogic["operator"].(string)
	if !ok {
		operator = ">" // default operator
	}
	
	value, exists := entityData[field]
	if !exists {
		result.Passed = false
		result.Details["error"] = fmt.Sprintf("field %s not found in entity data", field)
		return result, nil
	}
	
	numValue, ok := value.(float64)
	if !ok {
		result.Passed = false
		result.Details["error"] = fmt.Sprintf("field %s is not a number", field)
		return result, nil
	}
	
	switch operator {
	case ">":
		result.Passed = numValue > threshold
	case ">=":
		result.Passed = numValue >= threshold
	case "<":
		result.Passed = numValue < threshold
	case "<=":
		result.Passed = numValue <= threshold
	case "==":
		result.Passed = numValue == threshold
	case "!=":
		result.Passed = numValue != threshold
	default:
		return result, fmt.Errorf("unsupported operator: %s", operator)
	}
	
	result.Details["field"] = field
	result.Details["value"] = numValue
	result.Details["threshold"] = threshold
	result.Details["operator"] = operator
	
	return result, nil
}

// executeValidationRule executes a validation-based rule
func (e *ComplianceRuleEngine) executeValidationRule(ruleLogic map[string]interface{}, entityData map[string]interface{}) (RuleExecutionResult, error) {
	result := RuleExecutionResult{
		Timestamp: time.Now(),
		Success:   true,
		Passed:    true,
		Details:   make(map[string]interface{}),
	}
	
	validations, ok := ruleLogic["validations"].([]interface{})
	if !ok {
		return result, fmt.Errorf("validation rule must specify validations")
	}
	
	var errors []string
	
	for _, v := range validations {
		validation, ok := v.(map[string]interface{})
		if !ok {
			continue
		}
		
		field, ok := validation["field"].(string)
		if !ok {
			continue
		}
		
		required, ok := validation["required"].(bool)
		if ok && required {
			if _, exists := entityData[field]; !exists {
				errors = append(errors, fmt.Sprintf("required field %s is missing", field))
				result.Passed = false
			}
		}
		
		// Add more validation types as needed
	}
	
	result.Details["validationErrors"] = errors
	
	return result, nil
}

// executeComparisonRule executes a comparison-based rule
func (e *ComplianceRuleEngine) executeComparisonRule(ruleLogic map[string]interface{}, entityData map[string]interface{}) (RuleExecutionResult, error) {
	result := RuleExecutionResult{
		Timestamp: time.Now(),
		Success:   true,
		Details:   make(map[string]interface{}),
	}
	
	field1, ok := ruleLogic["field1"].(string)
	if !ok {
		return result, fmt.Errorf("comparison rule must specify field1")
	}
	
	field2, ok := ruleLogic["field2"].(string)
	if !ok {
		return result, fmt.Errorf("comparison rule must specify field2")
	}
	
	operator, ok := ruleLogic["operator"].(string)
	if !ok {
		operator = "==" // default operator
	}
	
	value1, exists1 := entityData[field1]
	value2, exists2 := entityData[field2]
	
	if !exists1 || !exists2 {
		result.Passed = false
		result.Details["error"] = "one or both fields not found"
		return result, nil
	}
	
	// Simple comparison (extend as needed)
	switch operator {
	case "==":
		result.Passed = value1 == value2
	case "!=":
		result.Passed = value1 != value2
	default:
		return result, fmt.Errorf("unsupported comparison operator: %s", operator)
	}
	
	result.Details["field1"] = field1
	result.Details["field2"] = field2
	result.Details["value1"] = value1
	result.Details["value2"] = value2
	result.Details["operator"] = operator
	
	return result, nil
}

// resolveDependenciesRecursive recursively resolves dependencies using DFS
func (e *ComplianceRuleEngine) resolveDependenciesRecursive(stub shim.ChaincodeStubInterface, ruleID string, visited, visiting map[string]bool, result *[]string) error {
	if visiting[ruleID] {
		return fmt.Errorf("circular dependency detected involving rule %s", ruleID)
	}
	
	if visited[ruleID] {
		return nil
	}
	
	visiting[ruleID] = true
	
	rule, err := e.ruleRepository.GetLatestRule(stub, ruleID)
	if err != nil {
		return fmt.Errorf("failed to get rule %s: %v", ruleID, err)
	}
	
	for _, dep := range rule.Dependencies {
		if err := e.resolveDependenciesRecursive(stub, dep, visited, visiting, result); err != nil {
			return err
		}
	}
	
	visiting[ruleID] = false
	visited[ruleID] = true
	*result = append(*result, ruleID)
	
	return nil
}

// calculateExecutionTime calculates execution time ensuring it's at least 1ms
func calculateExecutionTime(startTime time.Time) int64 {
	executionTimeMs := time.Since(startTime).Nanoseconds() / 1000000
	if executionTimeMs == 0 {
		executionTimeMs = 1 // Ensure at least 1ms for very fast executions
	}
	return executionTimeMs
}