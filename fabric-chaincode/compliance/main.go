package main

import (
	"encoding/json"
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/hyperledger/fabric-protos-go/peer"
	"github.com/blockchain-financial-platform/fabric-chaincode/shared"
)

// ComplianceRule represents a compliance rule with logic and metadata
type ComplianceRule struct {
	RuleID              string    `json:"ruleID"`
	RuleName           string    `json:"ruleName"`
	RuleDescription    string    `json:"ruleDescription"`
	RuleLogic          string    `json:"ruleLogic"`
	AppliesToDomain    string    `json:"appliesToDomain"`
	Status             string    `json:"status"`
	LastModifiedBy     string    `json:"lastModifiedBy"`
	LastModifiedDate   time.Time `json:"lastModifiedDate"`
	CreatedBy          string    `json:"createdBy"`
	CreatedDate        time.Time `json:"createdDate"`
}

// ComplianceEvent represents a compliance check event
type ComplianceEvent struct {
	EventID             string    `json:"eventID"`
	Timestamp          time.Time `json:"timestamp"`
	RuleID             string    `json:"ruleID"`
	AffectedEntityID   string    `json:"affectedEntityID"`
	AffectedEntityType string    `json:"affectedEntityType"`
	EventType          string    `json:"eventType"`
	Details            string    `json:"details"`
	ActorID            string    `json:"actorID"`
	IsAlerted          bool      `json:"isAlerted"`
	AcknowledgedBy     string    `json:"acknowledgedBy"`
	AcknowledgedDate   time.Time `json:"acknowledgedDate"`
	TransactionID      string    `json:"transactionID"`
}

// ComplianceChaincode implements the fabric Contract interface
type ComplianceChaincode struct {
}

// Init is called during chaincode instantiation to initialize any data
func (t *ComplianceChaincode) Init(stub shim.ChaincodeStubInterface) peer.Response {
	return shim.Success(nil)
}

// Invoke is called per transaction on the chaincode
func (t *ComplianceChaincode) Invoke(stub shim.ChaincodeStubInterface) peer.Response {
	function, args := stub.GetFunctionAndParameters()
	
	switch function {
	case "ping":
		return shim.Success([]byte("pong"))
	case "GetComplianceRule":
		return t.GetComplianceRule(stub, args)
	case "UpdateComplianceRule":
		return t.UpdateComplianceRule(stub, args)
	case "RecordComplianceEvent":
		return t.RecordComplianceEvent(stub, args)
	case "GetComplianceEvent":
		return t.GetComplianceEvent(stub, args)
	case "GetComplianceEventsByRule":
		return t.GetComplianceEventsByRule(stub, args)
	case "GetComplianceEventsByEntity":
		return t.GetComplianceEventsByEntity(stub, args)
	case "ValidateComplianceRules":
		return t.ValidateComplianceRules(stub, args)
	case "ValidateLoanApplication":
		return t.ValidateLoanApplication(stub, args)
	case "ValidateCustomer":
		return t.ValidateCustomer(stub, args)
	case "GetHardcodedRules":
		return t.GetHardcodedRules(stub, args)
	case "AddSanctionListEntry":
		return t.AddSanctionListEntry(stub, args)
	case "GetSanctionListEntry":
		return t.GetSanctionListEntry(stub, args)
	case "ScreenAgainstSanctionLists":
		return t.ScreenAgainstSanctionLists(stub, args)
	case "GetScreeningResult":
		return t.GetScreeningResult(stub, args)
	case "GetScreeningResultsByEntity":
		return t.GetScreeningResultsByEntity(stub, args)
	default:
		return shim.Error("Invalid function name: " + function)
	}
}

// GetComplianceRule retrieves a compliance rule by ID
func (t *ComplianceChaincode) GetComplianceRule(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 1 {
		return shim.Error("Incorrect number of arguments. Expecting 1: ruleID")
	}

	ruleID := args[0]
	if ruleID == "" {
		return shim.Error("Rule ID cannot be empty")
	}

	// Get rule from ledger
	var rule ComplianceRule
	err := shared.GetStateAsJSON(stub, "RULE_"+ruleID, &rule)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get compliance rule %s: %v", ruleID, err))
	}

	// Marshal rule to JSON
	ruleJSON, err := json.Marshal(rule)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to marshal compliance rule: %v", err))
	}

	return shim.Success(ruleJSON)
}

// UpdateComplianceRule creates or updates a compliance rule
func (t *ComplianceChaincode) UpdateComplianceRule(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 6 {
		return shim.Error("Incorrect number of arguments. Expecting 6: ruleID, ruleName, ruleDescription, ruleLogic, appliesToDomain, actorID")
	}

	ruleID := args[0]
	ruleName := args[1]
	ruleDescription := args[2]
	ruleLogic := args[3]
	appliesToDomain := args[4]
	actorID := args[5]

	// Validate required fields
	requiredFields := map[string]string{
		"ruleID":           ruleID,
		"ruleName":         ruleName,
		"ruleDescription":  ruleDescription,
		"ruleLogic":        ruleLogic,
		"appliesToDomain":  appliesToDomain,
		"actorID":          actorID,
	}

	if err := shared.ValidateRequired(requiredFields); err != nil {
		return shim.Error(fmt.Sprintf("Validation failed: %v", err))
	}

	// Validate actor access
	_, err := shared.ValidateActorAccess(stub, actorID, shared.PermissionUpdateCompliance)
	if err != nil {
		return shim.Error(fmt.Sprintf("Access denied: %v", err))
	}

	// Validate domain
	allowedDomains := []string{"Customer", "Loan", "Compliance", "All"}
	if err := shared.ValidateStatus(appliesToDomain, allowedDomains); err != nil {
		return shim.Error(fmt.Sprintf("Invalid domain: %v", err))
	}

	// Check if rule exists
	var existingRule ComplianceRule
	ruleExists := true
	err = shared.GetStateAsJSON(stub, "RULE_"+ruleID, &existingRule)
	if err != nil {
		ruleExists = false
	}

	// Create or update rule
	var rule ComplianceRule
	now := time.Now()

	if ruleExists {
		// Update existing rule
		rule = existingRule
		rule.RuleName = ruleName
		rule.RuleDescription = ruleDescription
		rule.RuleLogic = ruleLogic
		rule.AppliesToDomain = appliesToDomain
		rule.LastModifiedBy = actorID
		rule.LastModifiedDate = now
		rule.Status = "Active"
	} else {
		// Create new rule
		rule = ComplianceRule{
			RuleID:              ruleID,
			RuleName:           ruleName,
			RuleDescription:    ruleDescription,
			RuleLogic:          ruleLogic,
			AppliesToDomain:    appliesToDomain,
			Status:             "Active",
			LastModifiedBy:     actorID,
			LastModifiedDate:   now,
			CreatedBy:          actorID,
			CreatedDate:        now,
		}
	}

	// Store rule
	err = shared.PutStateAsJSON(stub, "RULE_"+ruleID, rule)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to store compliance rule: %v", err))
	}

	// Record history
	changeType := "UPDATE"
	if !ruleExists {
		changeType = "CREATE"
	}
	
	err = shared.RecordHistoryEntry(stub, ruleID, "ComplianceRule", changeType, "rule", "", "", actorID)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to record history: %v", err))
	}

	// Emit event
	eventPayload := map[string]interface{}{
		"ruleID":    ruleID,
		"ruleName":  ruleName,
		"actorID":   actorID,
		"action":    changeType,
		"timestamp": now,
	}
	
	err = shared.EmitEvent(stub, "ComplianceRuleUpdated", eventPayload)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to emit event: %v", err))
	}

	// Marshal rule to JSON for response
	ruleJSON, err := json.Marshal(rule)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to marshal compliance rule: %v", err))
	}

	return shim.Success(ruleJSON)
}

// RecordComplianceEvent records a compliance event
func (t *ComplianceChaincode) RecordComplianceEvent(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 6 {
		return shim.Error("Incorrect number of arguments. Expecting 6: ruleID, affectedEntityID, affectedEntityType, eventType, details, actorID")
	}

	ruleID := args[0]
	affectedEntityID := args[1]
	affectedEntityType := args[2]
	eventType := args[3]
	details := args[4]
	actorID := args[5]

	// Validate required fields
	requiredFields := map[string]string{
		"ruleID":             ruleID,
		"affectedEntityID":   affectedEntityID,
		"affectedEntityType": affectedEntityType,
		"eventType":          eventType,
		"actorID":            actorID,
	}

	if err := shared.ValidateRequired(requiredFields); err != nil {
		return shim.Error(fmt.Sprintf("Validation failed: %v", err))
	}

	// Validate event type
	allowedEventTypes := []string{"RULE_EVALUATION", "VIOLATION", "COMPLIANCE_CHECK", "ALERT", "ACKNOWLEDGMENT"}
	if err := shared.ValidateStatus(eventType, allowedEventTypes); err != nil {
		return shim.Error(fmt.Sprintf("Invalid event type: %v", err))
	}

	// Validate entity type
	allowedEntityTypes := []string{"Customer", "LoanApplication", "ComplianceRule", "Actor"}
	if err := shared.ValidateStatus(affectedEntityType, allowedEntityTypes); err != nil {
		return shim.Error(fmt.Sprintf("Invalid entity type: %v", err))
	}

	// Verify rule exists
	var rule ComplianceRule
	err := shared.GetStateAsJSON(stub, "RULE_"+ruleID, &rule)
	if err != nil {
		return shim.Error(fmt.Sprintf("Compliance rule %s not found: %v", ruleID, err))
	}

	// Generate event ID
	eventID := shared.GenerateID("EVENT")
	now := time.Now()
	txID := stub.GetTxID()

	// Determine if this should trigger an alert
	isAlerted := (eventType == "VIOLATION" || eventType == "ALERT")

	// Create compliance event
	event := ComplianceEvent{
		EventID:             eventID,
		Timestamp:          now,
		RuleID:             ruleID,
		AffectedEntityID:   affectedEntityID,
		AffectedEntityType: affectedEntityType,
		EventType:          eventType,
		Details:            details,
		ActorID:            actorID,
		IsAlerted:          isAlerted,
		TransactionID:      txID,
	}

	// Store event
	err = shared.PutStateAsJSON(stub, "EVENT_"+eventID, event)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to store compliance event: %v", err))
	}

	// Create composite keys for efficient querying
	// By rule ID
	ruleCompositeKey, err := stub.CreateCompositeKey("EVENT_BY_RULE", []string{ruleID, eventID})
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to create rule composite key: %v", err))
	}
	err = stub.PutState(ruleCompositeKey, []byte(eventID))
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to store rule composite key: %v", err))
	}

	// By entity ID
	entityCompositeKey, err := stub.CreateCompositeKey("EVENT_BY_ENTITY", []string{affectedEntityID, eventID})
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to create entity composite key: %v", err))
	}
	err = stub.PutState(entityCompositeKey, []byte(eventID))
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to store entity composite key: %v", err))
	}

	// Emit event
	eventPayload := map[string]interface{}{
		"eventID":             eventID,
		"ruleID":             ruleID,
		"affectedEntityID":   affectedEntityID,
		"affectedEntityType": affectedEntityType,
		"eventType":          eventType,
		"isAlerted":          isAlerted,
		"actorID":            actorID,
		"timestamp":          now,
	}
	
	err = shared.EmitEvent(stub, "ComplianceEventRecorded", eventPayload)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to emit event: %v", err))
	}

	// Marshal event to JSON for response
	eventJSON, err := json.Marshal(event)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to marshal compliance event: %v", err))
	}

	return shim.Success(eventJSON)
}

// GetComplianceEvent retrieves a compliance event by ID
func (t *ComplianceChaincode) GetComplianceEvent(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 1 {
		return shim.Error("Incorrect number of arguments. Expecting 1: eventID")
	}

	eventID := args[0]
	if eventID == "" {
		return shim.Error("Event ID cannot be empty")
	}

	// Get event from ledger
	var event ComplianceEvent
	err := shared.GetStateAsJSON(stub, "EVENT_"+eventID, &event)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get compliance event %s: %v", eventID, err))
	}

	// Marshal event to JSON
	eventJSON, err := json.Marshal(event)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to marshal compliance event: %v", err))
	}

	return shim.Success(eventJSON)
}

// GetComplianceEventsByRule retrieves all compliance events for a specific rule
func (t *ComplianceChaincode) GetComplianceEventsByRule(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 1 {
		return shim.Error("Incorrect number of arguments. Expecting 1: ruleID")
	}

	ruleID := args[0]
	if ruleID == "" {
		return shim.Error("Rule ID cannot be empty")
	}

	// Query events by rule using composite key
	iterator, err := stub.GetStateByPartialCompositeKey("EVENT_BY_RULE", []string{ruleID})
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get events iterator: %v", err))
	}
	defer iterator.Close()

	var events []ComplianceEvent
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return shim.Error(fmt.Sprintf("Failed to iterate events: %v", err))
		}

		eventID := string(response.Value)
		var event ComplianceEvent
		err = shared.GetStateAsJSON(stub, "EVENT_"+eventID, &event)
		if err != nil {
			return shim.Error(fmt.Sprintf("Failed to get event %s: %v", eventID, err))
		}

		events = append(events, event)
	}

	// Marshal events to JSON
	eventsJSON, err := json.Marshal(events)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to marshal compliance events: %v", err))
	}

	return shim.Success(eventsJSON)
}

// GetComplianceEventsByEntity retrieves all compliance events for a specific entity
func (t *ComplianceChaincode) GetComplianceEventsByEntity(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 1 {
		return shim.Error("Incorrect number of arguments. Expecting 1: entityID")
	}

	entityID := args[0]
	if entityID == "" {
		return shim.Error("Entity ID cannot be empty")
	}

	// Query events by entity using composite key
	iterator, err := stub.GetStateByPartialCompositeKey("EVENT_BY_ENTITY", []string{entityID})
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get events iterator: %v", err))
	}
	defer iterator.Close()

	var events []ComplianceEvent
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return shim.Error(fmt.Sprintf("Failed to iterate events: %v", err))
		}

		eventID := string(response.Value)
		var event ComplianceEvent
		err = shared.GetStateAsJSON(stub, "EVENT_"+eventID, &event)
		if err != nil {
			return shim.Error(fmt.Sprintf("Failed to get event %s: %v", eventID, err))
		}

		events = append(events, event)
	}

	// Marshal events to JSON
	eventsJSON, err := json.Marshal(events)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to marshal compliance events: %v", err))
	}

	return shim.Success(eventsJSON)
}

// ============================================================================
// AUTOMATED COMPLIANCE RULE ENFORCEMENT
// ============================================================================

// ComplianceRuleEngine represents the rule execution engine
type ComplianceRuleEngine struct {
	Rules []HardcodedComplianceRule
}

// HardcodedComplianceRule represents a hardcoded compliance rule
type HardcodedComplianceRule struct {
	RuleID      string
	RuleName    string
	Domain      string
	Description string
	Validator   func(data map[string]interface{}) (bool, string)
}

// InitializeHardcodedRules creates the hardcoded compliance rules
func (t *ComplianceChaincode) InitializeHardcodedRules() ComplianceRuleEngine {
	rules := []HardcodedComplianceRule{
		{
			RuleID:      "LOAN_AMOUNT_THRESHOLD",
			RuleName:    "Loan Amount Threshold Rule",
			Domain:      "Loan",
			Description: "Loans above $100,000 require additional approval",
			Validator: func(data map[string]interface{}) (bool, string) {
				if amount, ok := data["requestedAmount"].(float64); ok {
					if amount > 100000 {
						return false, fmt.Sprintf("Loan amount $%.2f exceeds $100,000 threshold and requires additional approval", amount)
					}
				}
				return true, "Loan amount within acceptable threshold"
			},
		},
		{
			RuleID:      "LOAN_AMOUNT_MAXIMUM",
			RuleName:    "Maximum Loan Amount Rule",
			Domain:      "Loan",
			Description: "Loans cannot exceed $1,000,000",
			Validator: func(data map[string]interface{}) (bool, string) {
				if amount, ok := data["requestedAmount"].(float64); ok {
					if amount > 1000000 {
						return false, fmt.Sprintf("Loan amount $%.2f exceeds maximum allowed amount of $1,000,000", amount)
					}
				}
				return true, "Loan amount within maximum limit"
			},
		},
		{
			RuleID:      "CUSTOMER_KYC_REQUIRED",
			RuleName:    "KYC Completion Required",
			Domain:      "Customer",
			Description: "Customer must have completed KYC before loan application",
			Validator: func(data map[string]interface{}) (bool, string) {
				if kycStatus, ok := data["kycStatus"].(string); ok {
					if kycStatus != "Completed" && kycStatus != "Approved" {
						return false, fmt.Sprintf("Customer KYC status '%s' is not completed", kycStatus)
					}
				}
				return true, "Customer KYC requirements satisfied"
			},
		},
		{
			RuleID:      "CUSTOMER_AML_CLEARED",
			RuleName:    "AML Clearance Required",
			Domain:      "Customer",
			Description: "Customer must pass AML checks",
			Validator: func(data map[string]interface{}) (bool, string) {
				if amlStatus, ok := data["amlStatus"].(string); ok {
					if amlStatus == "Failed" || amlStatus == "Flagged" {
						return false, fmt.Sprintf("Customer AML status '%s' indicates compliance risk", amlStatus)
					}
				}
				return true, "Customer AML status cleared"
			},
		},
		{
			RuleID:      "LOAN_STATUS_TRANSITION",
			RuleName:    "Valid Loan Status Transition",
			Domain:      "Loan",
			Description: "Loan status transitions must follow defined workflow",
			Validator: func(data map[string]interface{}) (bool, string) {
				currentStatus, currentOk := data["currentStatus"].(string)
				newStatus, newOk := data["newStatus"].(string)
				
				if !currentOk || !newOk {
					return true, "Status transition validation skipped - missing status data"
				}

				validTransitions := map[string][]string{
					"Submitted":    {"Under_Review", "Rejected"},
					"Under_Review": {"Credit_Check", "Rejected"},
					"Credit_Check": {"Approved", "Rejected"},
					"Approved":     {"Disbursed"},
					"Rejected":     {}, // No transitions from rejected
					"Disbursed":    {}, // No transitions from disbursed
				}

				if allowedNext, exists := validTransitions[currentStatus]; exists {
					for _, allowed := range allowedNext {
						if newStatus == allowed {
							return true, fmt.Sprintf("Status transition from '%s' to '%s' is valid", currentStatus, newStatus)
						}
					}
					return false, fmt.Sprintf("Invalid status transition from '%s' to '%s'", currentStatus, newStatus)
				}
				
				return false, fmt.Sprintf("Unknown current status '%s'", currentStatus)
			},
		},
	}

	return ComplianceRuleEngine{Rules: rules}
}

// ValidateComplianceRules validates data against all applicable hardcoded rules
func (t *ComplianceChaincode) ValidateComplianceRules(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 4 {
		return shim.Error("Incorrect number of arguments. Expecting 4: domain, entityID, entityType, dataJSON")
	}

	domain := args[0]
	entityID := args[1]
	entityType := args[2]
	dataJSON := args[3]

	// Validate required fields
	requiredFields := map[string]string{
		"domain":     domain,
		"entityID":   entityID,
		"entityType": entityType,
		"dataJSON":   dataJSON,
	}

	if err := shared.ValidateRequired(requiredFields); err != nil {
		return shim.Error(fmt.Sprintf("Validation failed: %v", err))
	}

	// Parse data JSON
	var data map[string]interface{}
	err := json.Unmarshal([]byte(dataJSON), &data)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to parse data JSON: %v", err))
	}

	// Initialize rule engine
	ruleEngine := t.InitializeHardcodedRules()

	// Get caller identity for event recording
	callerID, err := shared.GetCallerIdentity(stub)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get caller identity: %v", err))
	}

	var violations []map[string]interface{}
	var complianceChecks []map[string]interface{}

	// Execute applicable rules
	for _, rule := range ruleEngine.Rules {
		if rule.Domain == domain || rule.Domain == "All" {
			isCompliant, message := rule.Validator(data)
			
			if isCompliant {
				// Record compliance check event
				checkEvent := map[string]interface{}{
					"ruleID":      rule.RuleID,
					"ruleName":    rule.RuleName,
					"entityID":    entityID,
					"entityType":  entityType,
					"result":      "PASSED",
					"message":     message,
				}
				complianceChecks = append(complianceChecks, checkEvent)

				// Record the compliance event
				t.recordAutomatedComplianceEvent(stub, rule.RuleID, entityID, entityType, "COMPLIANCE_CHECK", message, callerID)
			} else {
				// Record violation event
				violationEvent := map[string]interface{}{
					"ruleID":      rule.RuleID,
					"ruleName":    rule.RuleName,
					"entityID":    entityID,
					"entityType":  entityType,
					"result":      "VIOLATION",
					"message":     message,
				}
				violations = append(violations, violationEvent)

				// Record the violation event
				t.recordAutomatedComplianceEvent(stub, rule.RuleID, entityID, entityType, "VIOLATION", message, callerID)
			}
		}
	}

	// Prepare response
	response := map[string]interface{}{
		"domain":           domain,
		"entityID":         entityID,
		"entityType":       entityType,
		"isCompliant":      len(violations) == 0,
		"violationCount":   len(violations),
		"checkCount":       len(complianceChecks),
		"violations":       violations,
		"complianceChecks": complianceChecks,
		"timestamp":        time.Now(),
	}

	// Marshal response to JSON
	responseJSON, err := json.Marshal(response)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to marshal response: %v", err))
	}

	return shim.Success(responseJSON)
}

// recordAutomatedComplianceEvent is a helper function to record compliance events
func (t *ComplianceChaincode) recordAutomatedComplianceEvent(stub shim.ChaincodeStubInterface, ruleID, entityID, entityType, eventType, details, actorID string) error {
	// Generate event ID
	eventID := shared.GenerateID("EVENT")
	now := time.Now()
	txID := stub.GetTxID()

	// Determine if this should trigger an alert
	isAlerted := (eventType == "VIOLATION" || eventType == "ALERT")

	// Create compliance event
	event := ComplianceEvent{
		EventID:             eventID,
		Timestamp:          now,
		RuleID:             ruleID,
		AffectedEntityID:   entityID,
		AffectedEntityType: entityType,
		EventType:          eventType,
		Details:            details,
		ActorID:            actorID,
		IsAlerted:          isAlerted,
		TransactionID:      txID,
	}

	// Store event
	err := shared.PutStateAsJSON(stub, "EVENT_"+eventID, event)
	if err != nil {
		return fmt.Errorf("failed to store compliance event: %v", err)
	}

	// Create composite keys for efficient querying
	// By rule ID
	ruleCompositeKey, err := stub.CreateCompositeKey("EVENT_BY_RULE", []string{ruleID, eventID})
	if err != nil {
		return fmt.Errorf("failed to create rule composite key: %v", err)
	}
	err = stub.PutState(ruleCompositeKey, []byte(eventID))
	if err != nil {
		return fmt.Errorf("failed to store rule composite key: %v", err)
	}

	// By entity ID
	entityCompositeKey, err := stub.CreateCompositeKey("EVENT_BY_ENTITY", []string{entityID, eventID})
	if err != nil {
		return fmt.Errorf("failed to create entity composite key: %v", err)
	}
	err = stub.PutState(entityCompositeKey, []byte(eventID))
	if err != nil {
		return fmt.Errorf("failed to store entity composite key: %v", err)
	}

	// Emit event
	eventPayload := map[string]interface{}{
		"eventID":             eventID,
		"ruleID":             ruleID,
		"affectedEntityID":   entityID,
		"affectedEntityType": entityType,
		"eventType":          eventType,
		"isAlerted":          isAlerted,
		"actorID":            actorID,
		"timestamp":          now,
	}
	
	err = shared.EmitEvent(stub, "ComplianceEventRecorded", eventPayload)
	if err != nil {
		return fmt.Errorf("failed to emit event: %v", err)
	}

	return nil
}

// ValidateLoanApplication validates a loan application against compliance rules
func (t *ComplianceChaincode) ValidateLoanApplication(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 2 {
		return shim.Error("Incorrect number of arguments. Expecting 2: loanApplicationID, loanDataJSON")
	}

	loanApplicationID := args[0]
	loanDataJSON := args[1]

	if loanApplicationID == "" || loanDataJSON == "" {
		return shim.Error("Loan application ID and data cannot be empty")
	}

	// Use the general validation function
	validationArgs := []string{
		"Loan",
		loanApplicationID,
		"LoanApplication",
		loanDataJSON,
	}

	return t.ValidateComplianceRules(stub, validationArgs)
}

// ValidateCustomer validates a customer against compliance rules
func (t *ComplianceChaincode) ValidateCustomer(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 2 {
		return shim.Error("Incorrect number of arguments. Expecting 2: customerID, customerDataJSON")
	}

	customerID := args[0]
	customerDataJSON := args[1]

	if customerID == "" || customerDataJSON == "" {
		return shim.Error("Customer ID and data cannot be empty")
	}

	// Use the general validation function
	validationArgs := []string{
		"Customer",
		customerID,
		"Customer",
		customerDataJSON,
	}

	return t.ValidateComplianceRules(stub, validationArgs)
}

// GetHardcodedRules returns all hardcoded compliance rules
func (t *ComplianceChaincode) GetHardcodedRules(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 0 {
		return shim.Error("Incorrect number of arguments. Expecting 0")
	}

	// Initialize rule engine
	ruleEngine := t.InitializeHardcodedRules()

	// Convert rules to response format (without validator functions)
	var rulesResponse []map[string]interface{}
	for _, rule := range ruleEngine.Rules {
		ruleInfo := map[string]interface{}{
			"ruleID":      rule.RuleID,
			"ruleName":    rule.RuleName,
			"domain":      rule.Domain,
			"description": rule.Description,
		}
		rulesResponse = append(rulesResponse, ruleInfo)
	}

	// Marshal response to JSON
	responseJSON, err := json.Marshal(rulesResponse)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to marshal rules response: %v", err))
	}

	return shim.Success(responseJSON)
}

// ============================================================================
// SANCTION LIST SCREENING INTEGRATION
// ============================================================================

// SanctionListEntry represents an entry in a sanction list
type SanctionListEntry struct {
	EntryID          string    `json:"entryID"`
	ListName         string    `json:"listName"`
	EntityName       string    `json:"entityName"`
	EntityType       string    `json:"entityType"` // Individual, Organization, Vessel, etc.
	Aliases          []string  `json:"aliases"`
	DateOfBirth      string    `json:"dateOfBirth,omitempty"`
	PlaceOfBirth     string    `json:"placeOfBirth,omitempty"`
	Nationality      string    `json:"nationality,omitempty"`
	Address          string    `json:"address,omitempty"`
	IdentificationNo string    `json:"identificationNo,omitempty"`
	SanctionType     string    `json:"sanctionType"`
	ListingDate      time.Time `json:"listingDate"`
	LastUpdated      time.Time `json:"lastUpdated"`
	IsActive         bool      `json:"isActive"`
	Source           string    `json:"source"`
}

// SanctionScreeningResult represents the result of a sanction screening
type SanctionScreeningResult struct {
	ScreeningID      string                 `json:"screeningID"`
	EntityID         string                 `json:"entityID"`
	EntityType       string                 `json:"entityType"`
	EntityName       string                 `json:"entityName"`
	ScreeningDate    time.Time              `json:"screeningDate"`
	IsMatch          bool                   `json:"isMatch"`
	MatchScore       float64                `json:"matchScore"`
	Matches          []SanctionMatch        `json:"matches"`
	Status           string                 `json:"status"` // CLEARED, FLAGGED, REQUIRES_REVIEW
	ReviewedBy       string                 `json:"reviewedBy,omitempty"`
	ReviewDate       time.Time              `json:"reviewDate,omitempty"`
	ReviewComments   string                 `json:"reviewComments,omitempty"`
	ActorID          string                 `json:"actorID"`
	TransactionID    string                 `json:"transactionID"`
}

// SanctionMatch represents a potential match with a sanction list entry
type SanctionMatch struct {
	EntryID       string  `json:"entryID"`
	ListName      string  `json:"listName"`
	EntityName    string  `json:"entityName"`
	MatchType     string  `json:"matchType"` // EXACT, PARTIAL, ALIAS
	MatchScore    float64 `json:"matchScore"`
	MatchedFields []string `json:"matchedFields"`
}

// AddSanctionListEntry adds or updates a sanction list entry
func (t *ComplianceChaincode) AddSanctionListEntry(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 10 {
		return shim.Error("Incorrect number of arguments. Expecting 10: entryID, listName, entityName, entityType, aliases, dateOfBirth, nationality, sanctionType, source, actorID")
	}

	entryID := args[0]
	listName := args[1]
	entityName := args[2]
	entityType := args[3]
	aliasesJSON := args[4]
	dateOfBirth := args[5]
	nationality := args[6]
	sanctionType := args[7]
	source := args[8]
	actorID := args[9]

	// Validate required fields
	requiredFields := map[string]string{
		"entryID":      entryID,
		"listName":     listName,
		"entityName":   entityName,
		"entityType":   entityType,
		"sanctionType": sanctionType,
		"source":       source,
		"actorID":      actorID,
	}

	if err := shared.ValidateRequired(requiredFields); err != nil {
		return shim.Error(fmt.Sprintf("Validation failed: %v", err))
	}

	// Validate actor access
	_, err := shared.ValidateActorAccess(stub, actorID, shared.PermissionUpdateCompliance)
	if err != nil {
		return shim.Error(fmt.Sprintf("Access denied: %v", err))
	}

	// Parse aliases
	var aliases []string
	if aliasesJSON != "" {
		err := json.Unmarshal([]byte(aliasesJSON), &aliases)
		if err != nil {
			return shim.Error(fmt.Sprintf("Failed to parse aliases JSON: %v", err))
		}
	}

	// Create sanction list entry
	now := time.Now()
	entry := SanctionListEntry{
		EntryID:       entryID,
		ListName:      listName,
		EntityName:    entityName,
		EntityType:    entityType,
		Aliases:       aliases,
		DateOfBirth:   dateOfBirth,
		Nationality:   nationality,
		SanctionType:  sanctionType,
		ListingDate:   now,
		LastUpdated:   now,
		IsActive:      true,
		Source:        source,
	}

	// Store entry
	err = shared.PutStateAsJSON(stub, "SANCTION_"+entryID, entry)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to store sanction list entry: %v", err))
	}

	// Create composite key for efficient querying by list name
	listCompositeKey, err := stub.CreateCompositeKey("SANCTION_BY_LIST", []string{listName, entryID})
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to create list composite key: %v", err))
	}
	err = stub.PutState(listCompositeKey, []byte(entryID))
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to store list composite key: %v", err))
	}

	// Emit event
	eventPayload := map[string]interface{}{
		"entryID":    entryID,
		"listName":   listName,
		"entityName": entityName,
		"actorID":    actorID,
		"action":     "ADDED",
		"timestamp":  now,
	}
	
	err = shared.EmitEvent(stub, "SanctionListEntryAdded", eventPayload)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to emit event: %v", err))
	}

	// Marshal entry to JSON for response
	entryJSON, err := json.Marshal(entry)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to marshal sanction list entry: %v", err))
	}

	return shim.Success(entryJSON)
}

// GetSanctionListEntry retrieves a sanction list entry by ID
func (t *ComplianceChaincode) GetSanctionListEntry(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 1 {
		return shim.Error("Incorrect number of arguments. Expecting 1: entryID")
	}

	entryID := args[0]
	if entryID == "" {
		return shim.Error("Entry ID cannot be empty")
	}

	// Get entry from ledger
	var entry SanctionListEntry
	err := shared.GetStateAsJSON(stub, "SANCTION_"+entryID, &entry)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get sanction list entry %s: %v", entryID, err))
	}

	// Marshal entry to JSON
	entryJSON, err := json.Marshal(entry)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to marshal sanction list entry: %v", err))
	}

	return shim.Success(entryJSON)
}

// ScreenAgainstSanctionLists performs sanction list screening for an entity
func (t *ComplianceChaincode) ScreenAgainstSanctionLists(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 4 {
		return shim.Error("Incorrect number of arguments. Expecting 4: entityID, entityType, entityDataJSON, actorID")
	}

	entityID := args[0]
	entityType := args[1]
	entityDataJSON := args[2]
	actorID := args[3]

	// Validate required fields
	requiredFields := map[string]string{
		"entityID":       entityID,
		"entityType":     entityType,
		"entityDataJSON": entityDataJSON,
		"actorID":        actorID,
	}

	if err := shared.ValidateRequired(requiredFields); err != nil {
		return shim.Error(fmt.Sprintf("Validation failed: %v", err))
	}

	// Parse entity data
	var entityData map[string]interface{}
	err := json.Unmarshal([]byte(entityDataJSON), &entityData)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to parse entity data JSON: %v", err))
	}

	// Extract entity name for screening
	entityName, ok := entityData["name"].(string)
	if !ok {
		// Try alternative field names
		if firstName, hasFirst := entityData["firstName"].(string); hasFirst {
			if lastName, hasLast := entityData["lastName"].(string); hasLast {
				entityName = firstName + " " + lastName
			} else {
				entityName = firstName
			}
		} else {
			return shim.Error("Entity name not found in data")
		}
	}

	// Generate screening ID
	screeningID := shared.GenerateID("SCREEN")
	now := time.Now()
	txID := stub.GetTxID()

	// Perform screening against hardcoded sanction list entries
	matches := t.performSanctionScreening(stub, entityName, entityData)

	// Determine screening result
	isMatch := len(matches) > 0
	status := "CLEARED"
	var maxScore float64

	if isMatch {
		// Calculate maximum match score
		for _, match := range matches {
			if match.MatchScore > maxScore {
				maxScore = match.MatchScore
			}
		}

		// Determine status based on match score
		if maxScore >= 0.9 {
			status = "FLAGGED"
		} else {
			status = "REQUIRES_REVIEW"
		}
	}

	// Create screening result
	result := SanctionScreeningResult{
		ScreeningID:   screeningID,
		EntityID:      entityID,
		EntityType:    entityType,
		EntityName:    entityName,
		ScreeningDate: now,
		IsMatch:       isMatch,
		MatchScore:    maxScore,
		Matches:       matches,
		Status:        status,
		ActorID:       actorID,
		TransactionID: txID,
	}

	// Store screening result
	err = shared.PutStateAsJSON(stub, "SCREENING_"+screeningID, result)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to store screening result: %v", err))
	}

	// Create composite key for efficient querying by entity
	entityCompositeKey, err := stub.CreateCompositeKey("SCREENING_BY_ENTITY", []string{entityID, screeningID})
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to create entity composite key: %v", err))
	}
	err = stub.PutState(entityCompositeKey, []byte(screeningID))
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to store entity composite key: %v", err))
	}

	// Record compliance event if there's a match
	if isMatch {
		eventType := "VIOLATION"
		if status == "REQUIRES_REVIEW" {
			eventType = "ALERT"
		}

		details := fmt.Sprintf("Sanction screening found %d potential matches with maximum score %.2f", len(matches), maxScore)
		t.recordAutomatedComplianceEvent(stub, "SANCTION_SCREENING", entityID, entityType, eventType, details, actorID)
	} else {
		// Record successful screening
		details := "Sanction screening completed - no matches found"
		t.recordAutomatedComplianceEvent(stub, "SANCTION_SCREENING", entityID, entityType, "COMPLIANCE_CHECK", details, actorID)
	}

	// Emit event
	eventPayload := map[string]interface{}{
		"screeningID": screeningID,
		"entityID":    entityID,
		"entityName":  entityName,
		"isMatch":     isMatch,
		"matchScore":  maxScore,
		"status":      status,
		"actorID":     actorID,
		"timestamp":   now,
	}
	
	err = shared.EmitEvent(stub, "SanctionScreeningCompleted", eventPayload)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to emit event: %v", err))
	}

	// Marshal result to JSON for response
	resultJSON, err := json.Marshal(result)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to marshal screening result: %v", err))
	}

	return shim.Success(resultJSON)
}

// performSanctionScreening performs the actual screening logic
func (t *ComplianceChaincode) performSanctionScreening(stub shim.ChaincodeStubInterface, entityName string, entityData map[string]interface{}) []SanctionMatch {
	var matches []SanctionMatch

	// Get hardcoded sanction list entries for demonstration
	sanctionEntries := t.getHardcodedSanctionEntries()

	for _, entry := range sanctionEntries {
		if !entry.IsActive {
			continue
		}

		// Check for exact name match
		if t.normalizeString(entityName) == t.normalizeString(entry.EntityName) {
			match := SanctionMatch{
				EntryID:       entry.EntryID,
				ListName:      entry.ListName,
				EntityName:    entry.EntityName,
				MatchType:     "EXACT",
				MatchScore:    1.0,
				MatchedFields: []string{"name"},
			}
			matches = append(matches, match)
			continue
		}

		// Check for alias matches
		for _, alias := range entry.Aliases {
			if t.normalizeString(entityName) == t.normalizeString(alias) {
				match := SanctionMatch{
					EntryID:       entry.EntryID,
					ListName:      entry.ListName,
					EntityName:    entry.EntityName,
					MatchType:     "ALIAS",
					MatchScore:    0.95,
					MatchedFields: []string{"alias"},
				}
				matches = append(matches, match)
				break
			}
		}

		// Check for partial name match (fuzzy matching)
		if score := t.calculateSimilarity(entityName, entry.EntityName); score >= 0.8 {
			match := SanctionMatch{
				EntryID:       entry.EntryID,
				ListName:      entry.ListName,
				EntityName:    entry.EntityName,
				MatchType:     "PARTIAL",
				MatchScore:    score,
				MatchedFields: []string{"name"},
			}
			matches = append(matches, match)
		}

		// Additional matching logic for date of birth, nationality, etc.
		if entry.DateOfBirth != "" {
			if dob, ok := entityData["dateOfBirth"].(string); ok && dob == entry.DateOfBirth {
				// Enhance existing match or create new one
				for i := range matches {
					if matches[i].EntryID == entry.EntryID {
						matches[i].MatchedFields = append(matches[i].MatchedFields, "dateOfBirth")
						matches[i].MatchScore = matches[i].MatchScore * 1.1 // Boost score
						if matches[i].MatchScore > 1.0 {
							matches[i].MatchScore = 1.0
						}
						break
					}
				}
			}
		}
	}

	return matches
}

// getHardcodedSanctionEntries returns hardcoded sanction list entries for demonstration
func (t *ComplianceChaincode) getHardcodedSanctionEntries() []SanctionListEntry {
	return []SanctionListEntry{
		{
			EntryID:      "SANCTION_001",
			ListName:     "OFAC_SDN",
			EntityName:   "John Doe Sanctioned",
			EntityType:   "Individual",
			Aliases:      []string{"J. Doe", "Johnny Doe"},
			DateOfBirth:  "1980-01-01",
			Nationality:  "Unknown",
			SanctionType: "Financial",
			ListingDate:  time.Now().AddDate(-1, 0, 0),
			LastUpdated:  time.Now().AddDate(-1, 0, 0),
			IsActive:     true,
			Source:       "OFAC",
		},
		{
			EntryID:      "SANCTION_002",
			ListName:     "UN_SANCTIONS",
			EntityName:   "Bad Company Ltd",
			EntityType:   "Organization",
			Aliases:      []string{"Bad Co", "BC Ltd"},
			SanctionType: "Trade",
			ListingDate:  time.Now().AddDate(-2, 0, 0),
			LastUpdated:  time.Now().AddDate(-2, 0, 0),
			IsActive:     true,
			Source:       "UN",
		},
		{
			EntryID:      "SANCTION_003",
			ListName:     "EU_SANCTIONS",
			EntityName:   "Jane Smith Criminal",
			EntityType:   "Individual",
			Aliases:      []string{"J. Smith", "Jane S."},
			DateOfBirth:  "1975-05-15",
			Nationality:  "Unknown",
			SanctionType: "Asset_Freeze",
			ListingDate:  time.Now().AddDate(-3, 0, 0),
			LastUpdated:  time.Now().AddDate(-3, 0, 0),
			IsActive:     true,
			Source:       "EU",
		},
	}
}

// normalizeString normalizes a string for comparison
func (t *ComplianceChaincode) normalizeString(s string) string {
	// Convert to lowercase and remove extra spaces
	normalized := strings.ToLower(strings.TrimSpace(s))
	// Remove multiple spaces
	normalized = strings.Join(strings.Fields(normalized), " ")
	return normalized
}

// calculateSimilarity calculates similarity between two strings (simple implementation)
func (t *ComplianceChaincode) calculateSimilarity(s1, s2 string) float64 {
	s1 = t.normalizeString(s1)
	s2 = t.normalizeString(s2)

	if s1 == s2 {
		return 1.0
	}

	// Simple Levenshtein distance-based similarity
	distance := t.levenshteinDistance(s1, s2)
	maxLen := len(s1)
	if len(s2) > maxLen {
		maxLen = len(s2)
	}

	if maxLen == 0 {
		return 1.0
	}

	similarity := 1.0 - float64(distance)/float64(maxLen)
	return similarity
}

// levenshteinDistance calculates the Levenshtein distance between two strings
func (t *ComplianceChaincode) levenshteinDistance(s1, s2 string) int {
	if len(s1) == 0 {
		return len(s2)
	}
	if len(s2) == 0 {
		return len(s1)
	}

	matrix := make([][]int, len(s1)+1)
	for i := range matrix {
		matrix[i] = make([]int, len(s2)+1)
		matrix[i][0] = i
	}
	for j := range matrix[0] {
		matrix[0][j] = j
	}

	for i := 1; i <= len(s1); i++ {
		for j := 1; j <= len(s2); j++ {
			cost := 0
			if s1[i-1] != s2[j-1] {
				cost = 1
			}

			matrix[i][j] = min(
				matrix[i-1][j]+1,      // deletion
				matrix[i][j-1]+1,      // insertion
				matrix[i-1][j-1]+cost, // substitution
			)
		}
	}

	return matrix[len(s1)][len(s2)]
}

// min returns the minimum of three integers
func min(a, b, c int) int {
	if a < b && a < c {
		return a
	}
	if b < c {
		return b
	}
	return c
}

// GetScreeningResult retrieves a screening result by ID
func (t *ComplianceChaincode) GetScreeningResult(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 1 {
		return shim.Error("Incorrect number of arguments. Expecting 1: screeningID")
	}

	screeningID := args[0]
	if screeningID == "" {
		return shim.Error("Screening ID cannot be empty")
	}

	// Get screening result from ledger
	var result SanctionScreeningResult
	err := shared.GetStateAsJSON(stub, "SCREENING_"+screeningID, &result)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get screening result %s: %v", screeningID, err))
	}

	// Marshal result to JSON
	resultJSON, err := json.Marshal(result)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to marshal screening result: %v", err))
	}

	return shim.Success(resultJSON)
}

// GetScreeningResultsByEntity retrieves all screening results for an entity
func (t *ComplianceChaincode) GetScreeningResultsByEntity(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 1 {
		return shim.Error("Incorrect number of arguments. Expecting 1: entityID")
	}

	entityID := args[0]
	if entityID == "" {
		return shim.Error("Entity ID cannot be empty")
	}

	// Query screening results by entity using composite key
	iterator, err := stub.GetStateByPartialCompositeKey("SCREENING_BY_ENTITY", []string{entityID})
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get screening results iterator: %v", err))
	}
	defer iterator.Close()

	var results []SanctionScreeningResult
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return shim.Error(fmt.Sprintf("Failed to iterate screening results: %v", err))
		}

		screeningID := string(response.Value)
		var result SanctionScreeningResult
		err = shared.GetStateAsJSON(stub, "SCREENING_"+screeningID, &result)
		if err != nil {
			return shim.Error(fmt.Sprintf("Failed to get screening result %s: %v", screeningID, err))
		}

		results = append(results, result)
	}

	// Marshal results to JSON
	resultsJSON, err := json.Marshal(results)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to marshal screening results: %v", err))
	}

	return shim.Success(resultsJSON)
}

func main() {
	if err := shim.Start(new(ComplianceChaincode)); err != nil {
		log.Fatalf("Error starting Compliance chaincode: %v", err)
	}
}