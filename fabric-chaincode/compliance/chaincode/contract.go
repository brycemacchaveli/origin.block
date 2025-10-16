package chaincode

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/hyperledger/fabric-protos-go/peer"
	
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/compliance/domain"
)

// ComplianceContract implements the chaincode interface with comprehensive rule engine
type ComplianceContract struct {
	ruleEngine      domain.RuleEngine
	ruleRepository  domain.RuleRepository
	eventEmitter    domain.EventEmitter
	approvalManager *domain.ApprovalWorkflowManager
}

// NewComplianceContract creates a new compliance contract with full rule engine
func NewComplianceContract() *ComplianceContract {
	repository := domain.NewFabricRuleRepository()
	emitter := domain.NewFabricEventEmitter()
	engine := domain.NewComplianceRuleEngine(repository, emitter)
	approvalManager := domain.NewApprovalWorkflowManager(repository, emitter)
	
	return &ComplianceContract{
		ruleEngine:      engine,
		ruleRepository:  repository,
		eventEmitter:    emitter,
		approvalManager: approvalManager,
	}
}

// Init is called during chaincode instantiation
func (c *ComplianceContract) Init(stub shim.ChaincodeStubInterface) peer.Response {
	return shim.Success(nil)
}

// Invoke is called per transaction on the chaincode
func (c *ComplianceContract) Invoke(stub shim.ChaincodeStubInterface) peer.Response {
	function, args := stub.GetFunctionAndParameters()

	switch function {
	// Rule management
	case "CreateComplianceRule":
		return c.CreateComplianceRule(stub, args)
	case "UpdateComplianceRule":
		return c.UpdateComplianceRule(stub, args)
	case "GetComplianceRule":
		return c.GetComplianceRule(stub, args)
	case "GetRuleHistory":
		return c.GetRuleHistory(stub, args)
	case "GetActiveRules":
		return c.GetActiveRules(stub, args)
	case "GetRulesByDomain":
		return c.GetRulesByDomain(stub, args)
	case "GetRulesByEntityType":
		return c.GetRulesByEntityType(stub, args)
	case "SearchRules":
		return c.SearchRules(stub, args)
	
	// Rule execution
	case "ExecuteRule":
		return c.ExecuteRule(stub, args)
	case "ExecuteRulesForEntity":
		return c.ExecuteRulesForEntity(stub, args)
	case "ExecuteRulesForEvent":
		return c.ExecuteRulesForEvent(stub, args)
	
	// Rule validation and testing
	case "ValidateRule":
		return c.ValidateRule(stub, args)
	case "TestRule":
		return c.TestRule(stub, args)
	case "RunAllTests":
		return c.RunAllTests(stub, args)
	
	// Dependency management
	case "ResolveDependencies":
		return c.ResolveDependencies(stub, args)
	case "CheckConflicts":
		return c.CheckConflicts(stub, args)
	case "GetExecutionOrder":
		return c.GetExecutionOrder(stub, args)
	
	// Approval workflow
	case "SubmitRuleForApproval":
		return c.SubmitRuleForApproval(stub, args)
	case "ApproveRule":
		return c.ApproveRule(stub, args)
	case "RejectRule":
		return c.RejectRule(stub, args)
	case "GetPendingApprovals":
		return c.GetPendingApprovals(stub, args)
	case "GetApprovalHistory":
		return c.GetApprovalHistory(stub, args)
	
	// Event management
	case "GetComplianceEvents":
		return c.GetComplianceEvents(stub, args)
	case "GetEventsByRule":
		return c.GetEventsByRule(stub, args)
	case "GetEventsByEntity":
		return c.GetEventsByEntity(stub, args)
	case "AcknowledgeEvent":
		return c.AcknowledgeEvent(stub, args)
	case "UpdateEventResolution":
		return c.UpdateEventResolution(stub, args)
	
	// Initialization
	case "InitLedger":
		return c.InitLedger(stub)
	
	default:
		return shim.Error(fmt.Sprintf("Unknown function: %s", function))
	}
}

// ============================================================================
// RULE MANAGEMENT FUNCTIONS
// ============================================================================

// CreateComplianceRule creates a new comprehensive compliance rule
func (c *ComplianceContract) CreateComplianceRule(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 1 {
		return shim.Error("Incorrect number of arguments. Expecting 1 (JSON rule)")
	}

	var rule domain.ComplianceRule
	if err := json.Unmarshal([]byte(args[0]), &rule); err != nil {
		return shim.Error(fmt.Sprintf("Failed to unmarshal rule: %v", err))
	}

	// Set creation metadata
	rule.CreationDate = time.Now()
	rule.LastModifiedDate = time.Now()
	rule.Status = domain.RuleStatusDraft

	// Save the rule
	if err := c.ruleRepository.SaveRule(stub, &rule); err != nil {
		return shim.Error(fmt.Sprintf("Failed to save rule: %v", err))
	}

	ruleBytes, _ := json.Marshal(rule)
	return shim.Success(ruleBytes)
}

// UpdateComplianceRule updates an existing compliance rule
func (c *ComplianceContract) UpdateComplianceRule(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 1 {
		return shim.Error("Incorrect number of arguments. Expecting 1 (JSON rule)")
	}

	var updatedRule domain.ComplianceRule
	if err := json.Unmarshal([]byte(args[0]), &updatedRule); err != nil {
		return shim.Error(fmt.Sprintf("Failed to unmarshal rule: %v", err))
	}

	// Get existing rule
	existingRule, err := c.ruleRepository.GetLatestRule(stub, updatedRule.RuleID)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get existing rule: %v", err))
	}

	// Check if rule can be updated
	if existingRule.Status == domain.RuleStatusActive {
		return shim.Error("Cannot update active rule. Create a new version or deactivate first.")
	}

	// Update metadata
	updatedRule.CreationDate = existingRule.CreationDate
	updatedRule.CreatedBy = existingRule.CreatedBy
	updatedRule.LastModifiedDate = time.Now()

	// Save updated rule
	if err := c.ruleRepository.SaveRule(stub, &updatedRule); err != nil {
		return shim.Error(fmt.Sprintf("Failed to update rule: %v", err))
	}

	ruleBytes, _ := json.Marshal(updatedRule)
	return shim.Success(ruleBytes)
}

// GetComplianceRule retrieves a compliance rule
func (c *ComplianceContract) GetComplianceRule(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) < 1 || len(args) > 2 {
		return shim.Error("Incorrect number of arguments. Expecting 1 (ruleID) or 2 (ruleID, version)")
	}

	ruleID := args[0]
	var rule *domain.ComplianceRule
	var err error

	if len(args) == 2 {
		version := args[1]
		rule, err = c.ruleRepository.GetRule(stub, ruleID, version)
	} else {
		rule, err = c.ruleRepository.GetLatestRule(stub, ruleID)
	}

	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get rule: %v", err))
	}

	ruleBytes, _ := json.Marshal(rule)
	return shim.Success(ruleBytes)
}

// GetRuleHistory retrieves the version history of a rule
func (c *ComplianceContract) GetRuleHistory(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 1 {
		return shim.Error("Incorrect number of arguments. Expecting 1 (ruleID)")
	}

	ruleID := args[0]
	history, err := c.ruleRepository.(*domain.FabricRuleRepository).GetRuleHistory(stub, ruleID)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get rule history: %v", err))
	}

	historyBytes, _ := json.Marshal(history)
	return shim.Success(historyBytes)
}

// GetActiveRules retrieves all currently active rules
func (c *ComplianceContract) GetActiveRules(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	rules, err := c.ruleRepository.GetActiveRules(stub)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get active rules: %v", err))
	}

	rulesBytes, _ := json.Marshal(rules)
	return shim.Success(rulesBytes)
}

// GetRulesByDomain retrieves rules for a specific domain
func (c *ComplianceContract) GetRulesByDomain(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 1 {
		return shim.Error("Incorrect number of arguments. Expecting 1 (domain)")
	}

	domain := args[0]
	rules, err := c.ruleRepository.GetRulesByDomain(stub, domain)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get rules by domain: %v", err))
	}

	rulesBytes, _ := json.Marshal(rules)
	return shim.Success(rulesBytes)
}

// GetRulesByEntityType retrieves rules for a specific entity type
func (c *ComplianceContract) GetRulesByEntityType(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 1 {
		return shim.Error("Incorrect number of arguments. Expecting 1 (entityType)")
	}

	entityType := args[0]
	rules, err := c.ruleRepository.GetRulesByEntityType(stub, entityType)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get rules by entity type: %v", err))
	}

	rulesBytes, _ := json.Marshal(rules)
	return shim.Success(rulesBytes)
}

// SearchRules performs a text search across rules
func (c *ComplianceContract) SearchRules(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 1 {
		return shim.Error("Incorrect number of arguments. Expecting 1 (searchTerm)")
	}

	searchTerm := args[0]
	rules, err := c.ruleRepository.(*domain.FabricRuleRepository).SearchRules(stub, searchTerm)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to search rules: %v", err))
	}

	rulesBytes, _ := json.Marshal(rules)
	return shim.Success(rulesBytes)
}

// ============================================================================
// RULE EXECUTION FUNCTIONS
// ============================================================================

// ExecuteRule executes a specific compliance rule
func (c *ComplianceContract) ExecuteRule(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 2 {
		return shim.Error("Incorrect number of arguments. Expecting 2 (ruleID, entityDataJSON)")
	}

	ruleID := args[0]
	var entityData map[string]interface{}
	if err := json.Unmarshal([]byte(args[1]), &entityData); err != nil {
		return shim.Error(fmt.Sprintf("Failed to unmarshal entity data: %v", err))
	}

	ctx := context.Background()
	result, err := c.ruleEngine.ExecuteRule(ctx, stub, ruleID, entityData)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to execute rule: %v", err))
	}

	resultBytes, _ := json.Marshal(result)
	return shim.Success(resultBytes)
}

// ExecuteRulesForEntity executes all rules for a specific entity type
func (c *ComplianceContract) ExecuteRulesForEntity(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 2 {
		return shim.Error("Incorrect number of arguments. Expecting 2 (entityType, entityDataJSON)")
	}

	entityType := args[0]
	var entityData map[string]interface{}
	if err := json.Unmarshal([]byte(args[1]), &entityData); err != nil {
		return shim.Error(fmt.Sprintf("Failed to unmarshal entity data: %v", err))
	}

	ctx := context.Background()
	results, err := c.ruleEngine.ExecuteRulesForEntity(ctx, stub, entityType, entityData)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to execute rules for entity: %v", err))
	}

	resultsBytes, _ := json.Marshal(results)
	return shim.Success(resultsBytes)
}

// ExecuteRulesForEvent executes all rules triggered by a specific event
func (c *ComplianceContract) ExecuteRulesForEvent(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 2 {
		return shim.Error("Incorrect number of arguments. Expecting 2 (eventType, entityDataJSON)")
	}

	eventType := args[0]
	var entityData map[string]interface{}
	if err := json.Unmarshal([]byte(args[1]), &entityData); err != nil {
		return shim.Error(fmt.Sprintf("Failed to unmarshal entity data: %v", err))
	}

	ctx := context.Background()
	results, err := c.ruleEngine.ExecuteRulesForEvent(ctx, stub, eventType, entityData)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to execute rules for event: %v", err))
	}

	resultsBytes, _ := json.Marshal(results)
	return shim.Success(resultsBytes)
}

// ============================================================================
// RULE VALIDATION AND TESTING FUNCTIONS
// ============================================================================

// ValidateRule validates a compliance rule
func (c *ComplianceContract) ValidateRule(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 1 {
		return shim.Error("Incorrect number of arguments. Expecting 1 (JSON rule)")
	}

	var rule domain.ComplianceRule
	if err := json.Unmarshal([]byte(args[0]), &rule); err != nil {
		return shim.Error(fmt.Sprintf("Failed to unmarshal rule: %v", err))
	}

	ctx := context.Background()
	results, err := c.ruleEngine.ValidateRule(ctx, stub, &rule)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to validate rule: %v", err))
	}

	resultsBytes, _ := json.Marshal(results)
	return shim.Success(resultsBytes)
}

// TestRule executes a specific test case for a rule
func (c *ComplianceContract) TestRule(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 2 {
		return shim.Error("Incorrect number of arguments. Expecting 2 (ruleID, testCaseID)")
	}

	ruleID := args[0]
	testCaseID := args[1]

	ctx := context.Background()
	result, err := c.ruleEngine.TestRule(ctx, stub, ruleID, testCaseID)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to test rule: %v", err))
	}

	resultBytes, _ := json.Marshal(result)
	return shim.Success(resultBytes)
}

// RunAllTests executes all test cases for a rule
func (c *ComplianceContract) RunAllTests(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 1 {
		return shim.Error("Incorrect number of arguments. Expecting 1 (ruleID)")
	}

	ruleID := args[0]

	ctx := context.Background()
	results, err := c.ruleEngine.RunAllTests(ctx, stub, ruleID)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to run all tests: %v", err))
	}

	resultsBytes, _ := json.Marshal(results)
	return shim.Success(resultsBytes)
}

// ============================================================================
// DEPENDENCY MANAGEMENT FUNCTIONS
// ============================================================================

// ResolveDependencies resolves dependencies for a rule
func (c *ComplianceContract) ResolveDependencies(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 1 {
		return shim.Error("Incorrect number of arguments. Expecting 1 (ruleID)")
	}

	ruleID := args[0]

	ctx := context.Background()
	dependencies, err := c.ruleEngine.ResolveDependencies(ctx, stub, ruleID)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to resolve dependencies: %v", err))
	}

	dependenciesBytes, _ := json.Marshal(dependencies)
	return shim.Success(dependenciesBytes)
}

// CheckConflicts checks for conflicts with a rule
func (c *ComplianceContract) CheckConflicts(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 1 {
		return shim.Error("Incorrect number of arguments. Expecting 1 (ruleID)")
	}

	ruleID := args[0]

	ctx := context.Background()
	conflicts, err := c.ruleEngine.CheckConflicts(ctx, stub, ruleID)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to check conflicts: %v", err))
	}

	conflictsBytes, _ := json.Marshal(conflicts)
	return shim.Success(conflictsBytes)
}

// GetExecutionOrder determines execution order for a set of rules
func (c *ComplianceContract) GetExecutionOrder(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 1 {
		return shim.Error("Incorrect number of arguments. Expecting 1 (JSON array of ruleIDs)")
	}

	var ruleIDs []string
	if err := json.Unmarshal([]byte(args[0]), &ruleIDs); err != nil {
		return shim.Error(fmt.Sprintf("Failed to unmarshal rule IDs: %v", err))
	}

	ctx := context.Background()
	order, err := c.ruleEngine.GetExecutionOrder(ctx, stub, ruleIDs)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get execution order: %v", err))
	}

	orderBytes, _ := json.Marshal(order)
	return shim.Success(orderBytes)
}

// ============================================================================
// APPROVAL WORKFLOW FUNCTIONS
// ============================================================================

// SubmitRuleForApproval submits a rule for approval
func (c *ComplianceContract) SubmitRuleForApproval(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 3 {
		return shim.Error("Incorrect number of arguments. Expecting 3 (ruleID, requestedBy, justification)")
	}

	ruleID := args[0]
	requestedBy := args[1]
	justification := args[2]

	request, err := c.approvalManager.SubmitRuleForApproval(stub, ruleID, requestedBy, justification)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to submit rule for approval: %v", err))
	}

	requestBytes, _ := json.Marshal(request)
	return shim.Success(requestBytes)
}

// ApproveRule approves a rule
func (c *ComplianceContract) ApproveRule(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 3 {
		return shim.Error("Incorrect number of arguments. Expecting 3 (requestID, reviewedBy, comments)")
	}

	requestID := args[0]
	reviewedBy := args[1]
	comments := args[2]

	if err := c.approvalManager.ApproveRule(stub, requestID, reviewedBy, comments); err != nil {
		return shim.Error(fmt.Sprintf("Failed to approve rule: %v", err))
	}

	return shim.Success([]byte("Rule approved successfully"))
}

// RejectRule rejects a rule approval request
func (c *ComplianceContract) RejectRule(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 3 {
		return shim.Error("Incorrect number of arguments. Expecting 3 (requestID, reviewedBy, comments)")
	}

	requestID := args[0]
	reviewedBy := args[1]
	comments := args[2]

	if err := c.approvalManager.RejectRule(stub, requestID, reviewedBy, comments); err != nil {
		return shim.Error(fmt.Sprintf("Failed to reject rule: %v", err))
	}

	return shim.Success([]byte("Rule rejected successfully"))
}

// GetPendingApprovals retrieves all pending approval requests
func (c *ComplianceContract) GetPendingApprovals(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	requests, err := c.approvalManager.GetPendingApprovals(stub)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get pending approvals: %v", err))
	}

	requestsBytes, _ := json.Marshal(requests)
	return shim.Success(requestsBytes)
}

// GetApprovalHistory retrieves approval history for a rule
func (c *ComplianceContract) GetApprovalHistory(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 1 {
		return shim.Error("Incorrect number of arguments. Expecting 1 (ruleID)")
	}

	ruleID := args[0]
	history, err := c.approvalManager.GetApprovalHistory(stub, ruleID)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get approval history: %v", err))
	}

	historyBytes, _ := json.Marshal(history)
	return shim.Success(historyBytes)
}

// ============================================================================
// EVENT MANAGEMENT FUNCTIONS
// ============================================================================

// GetComplianceEvents retrieves compliance events by type
func (c *ComplianceContract) GetComplianceEvents(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 1 {
		return shim.Error("Incorrect number of arguments. Expecting 1 (eventType)")
	}

	eventType := args[0]
	events, err := c.eventEmitter.(*domain.FabricEventEmitter).GetEventsByType(stub, eventType)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get compliance events: %v", err))
	}

	eventsBytes, _ := json.Marshal(events)
	return shim.Success(eventsBytes)
}

// GetEventsByRule retrieves events for a specific rule
func (c *ComplianceContract) GetEventsByRule(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 1 {
		return shim.Error("Incorrect number of arguments. Expecting 1 (ruleID)")
	}

	ruleID := args[0]
	events, err := c.eventEmitter.(*domain.FabricEventEmitter).GetEventsByRule(stub, ruleID)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get events by rule: %v", err))
	}

	eventsBytes, _ := json.Marshal(events)
	return shim.Success(eventsBytes)
}

// GetEventsByEntity retrieves events for a specific entity
func (c *ComplianceContract) GetEventsByEntity(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 1 {
		return shim.Error("Incorrect number of arguments. Expecting 1 (entityID)")
	}

	entityID := args[0]
	events, err := c.eventEmitter.(*domain.FabricEventEmitter).GetEventsByEntity(stub, entityID)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get events by entity: %v", err))
	}

	eventsBytes, _ := json.Marshal(events)
	return shim.Success(eventsBytes)
}

// AcknowledgeEvent acknowledges a compliance event
func (c *ComplianceContract) AcknowledgeEvent(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 2 {
		return shim.Error("Incorrect number of arguments. Expecting 2 (eventID, acknowledgedBy)")
	}

	eventID := args[0]
	acknowledgedBy := args[1]

	if err := c.eventEmitter.(*domain.FabricEventEmitter).AcknowledgeEvent(stub, eventID, acknowledgedBy); err != nil {
		return shim.Error(fmt.Sprintf("Failed to acknowledge event: %v", err))
	}

	return shim.Success([]byte("Event acknowledged successfully"))
}

// UpdateEventResolution updates the resolution status of an event
func (c *ComplianceContract) UpdateEventResolution(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 3 {
		return shim.Error("Incorrect number of arguments. Expecting 3 (eventID, status, notes)")
	}

	eventID := args[0]
	status := args[1]
	notes := args[2]

	if err := c.eventEmitter.(*domain.FabricEventEmitter).UpdateEventResolution(stub, eventID, status, notes); err != nil {
		return shim.Error(fmt.Sprintf("Failed to update event resolution: %v", err))
	}

	return shim.Success([]byte("Event resolution updated successfully"))
}

// ============================================================================
// INITIALIZATION FUNCTIONS
// ============================================================================

// InitLedger initializes the ledger with sample compliance rules
func (c *ComplianceContract) InitLedger(stub shim.ChaincodeStubInterface) peer.Response {
	// Create sample rules with comprehensive structure
	sampleRules := []*domain.ComplianceRule{
		{
			RuleID:              "RULE_KYC_001",
			RuleName:            "Customer KYC Verification Required",
			RuleDescription:     "All customers must complete KYC verification before account activation",
			Version:             "1.0.0",
			RuleLogic:           `{"type": "validation", "validations": [{"field": "kycStatus", "required": true}, {"field": "kycStatus", "value": "VERIFIED"}]}`,
			ExecutionMode:       domain.ExecutionModeSync,
			Priority:            domain.PriorityHigh,
			AppliesToDomain:     "CUSTOMER",
			AppliesToEntityType: "Customer",
			TriggerEvents:       []string{"CustomerCreated", "CustomerUpdated"},
			Status:              domain.RuleStatusActive,
			EffectiveDate:       time.Now(),
			CreatedBy:           "SYSTEM",
			CreationDate:        time.Now(),
			LastModifiedBy:      "SYSTEM",
			LastModifiedDate:    time.Now(),
			BusinessJustification: "Regulatory requirement for customer identification",
			TestCases: []domain.RuleTestCase{
				{
					TestID:          "TEST_KYC_001_PASS",
					TestName:        "Valid KYC Status",
					TestDescription: "Customer with verified KYC status should pass",
					InputData:       map[string]interface{}{"kycStatus": "VERIFIED"},
					ExpectedResult:  domain.RuleExecutionResult{Passed: true},
					CreatedBy:       "SYSTEM",
					CreationDate:    time.Now(),
				},
			},
		},
		{
			RuleID:              "RULE_AML_001",
			RuleName:            "AML Screening Required",
			RuleDescription:     "All transactions above threshold require AML screening",
			Version:             "1.0.0",
			RuleLogic:           `{"type": "threshold", "field": "amount", "threshold": 10000, "operator": ">"}`,
			ExecutionMode:       domain.ExecutionModeSync,
			Priority:            domain.PriorityCritical,
			AppliesToDomain:     "LOAN",
			AppliesToEntityType: "LoanApplication",
			TriggerEvents:       []string{"LoanSubmitted"},
			Status:              domain.RuleStatusActive,
			EffectiveDate:       time.Now(),
			CreatedBy:           "SYSTEM",
			CreationDate:        time.Now(),
			LastModifiedBy:      "SYSTEM",
			LastModifiedDate:    time.Now(),
			BusinessJustification: "Anti-money laundering compliance requirement",
			TestCases: []domain.RuleTestCase{
				{
					TestID:          "TEST_AML_001_TRIGGER",
					TestName:        "High Amount Triggers AML",
					TestDescription: "Loan amount above 10000 should trigger AML screening",
					InputData:       map[string]interface{}{"amount": 15000.0},
					ExpectedResult:  domain.RuleExecutionResult{Passed: true},
					CreatedBy:       "SYSTEM",
					CreationDate:    time.Now(),
				},
			},
		},
	}

	// Save sample rules
	for _, rule := range sampleRules {
		if err := c.ruleRepository.SaveRule(stub, rule); err != nil {
			return shim.Error(fmt.Sprintf("Failed to save sample rule %s: %v", rule.RuleID, err))
		}
	}

	return shim.Success([]byte("Ledger initialized with sample compliance rules"))
}