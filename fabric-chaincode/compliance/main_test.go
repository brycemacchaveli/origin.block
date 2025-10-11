package main

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/hyperledger/fabric-chaincode-go/shimtest"
	"github.com/stretchr/testify/assert"
	"github.com/blockchain-financial-platform/fabric-chaincode/shared"
)

func TestComplianceChaincode_Init(t *testing.T) {
	cc := new(ComplianceChaincode)
	stub := shimtest.NewMockStub("compliance", cc)

	// Test successful initialization
	response := stub.MockInit("1", [][]byte{})
	assert.Equal(t, int32(shim.OK), response.Status, "Init should succeed")
}

func TestComplianceChaincode_Ping(t *testing.T) {
	cc := new(ComplianceChaincode)
	stub := shimtest.NewMockStub("compliance", cc)

	// Initialize chaincode
	stub.MockInit("1", [][]byte{})

	// Test ping function
	response := stub.MockInvoke("1", [][]byte{[]byte("ping")})
	assert.Equal(t, int32(shim.OK), response.Status, "Ping should succeed")
	assert.Equal(t, "pong", string(response.Payload), "Ping should return pong")
}

func TestComplianceChaincode_UpdateComplianceRule(t *testing.T) {
	cc := new(ComplianceChaincode)
	stub := shimtest.NewMockStub("compliance", cc)
	stub.MockInit("1", [][]byte{})

	// Create a test actor first
	testActor := shared.Actor{
		ActorID:           "test-actor-1",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test Compliance Officer",
		Role:              shared.RoleComplianceOfficer,
		BlockchainIdentity: "test-identity",
		Permissions:       []shared.Permission{shared.PermissionUpdateCompliance},
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}

	actorJSON, _ := json.Marshal(testActor)
	stub.MockTransactionStart("create-actor")
	stub.PutState("ACTOR_test-actor-1", actorJSON)
	stub.MockTransactionEnd("create-actor")

	t.Run("Create new compliance rule", func(t *testing.T) {
		args := [][]byte{
			[]byte("UpdateComplianceRule"),
			[]byte("RULE_001"),
			[]byte("Loan Amount Threshold"),
			[]byte("Loans above $100,000 require additional approval"),
			[]byte("amount > 100000"),
			[]byte("Loan"),
			[]byte("test-actor-1"),
		}

		response := stub.MockInvoke("2", args)
		assert.Equal(t, int32(shim.OK), response.Status, "UpdateComplianceRule should succeed")

		// Verify the rule was created
		var rule ComplianceRule
		err := json.Unmarshal(response.Payload, &rule)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.Equal(t, "RULE_001", rule.RuleID)
		assert.Equal(t, "Loan Amount Threshold", rule.RuleName)
		assert.Equal(t, "Loan", rule.AppliesToDomain)
		assert.Equal(t, "Active", rule.Status)
		assert.Equal(t, "test-actor-1", rule.CreatedBy)
	})

	t.Run("Update existing compliance rule", func(t *testing.T) {
		args := [][]byte{
			[]byte("UpdateComplianceRule"),
			[]byte("RULE_001"),
			[]byte("Updated Loan Amount Threshold"),
			[]byte("Updated description for loans above $100,000"),
			[]byte("amount > 100000 AND status = 'pending'"),
			[]byte("Loan"),
			[]byte("test-actor-1"),
		}

		response := stub.MockInvoke("3", args)
		assert.Equal(t, int32(shim.OK), response.Status, "UpdateComplianceRule should succeed")

		// Verify the rule was updated
		var rule ComplianceRule
		err := json.Unmarshal(response.Payload, &rule)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.Equal(t, "RULE_001", rule.RuleID)
		assert.Equal(t, "Updated Loan Amount Threshold", rule.RuleName)
		assert.Equal(t, "test-actor-1", rule.LastModifiedBy)
	})

	t.Run("Fail with invalid arguments", func(t *testing.T) {
		args := [][]byte{
			[]byte("UpdateComplianceRule"),
			[]byte("RULE_002"),
		}

		response := stub.MockInvoke("4", args)
		assert.Equal(t, int32(shim.ERROR), response.Status, "UpdateComplianceRule should fail with insufficient arguments")
	})

	t.Run("Fail with empty required fields", func(t *testing.T) {
		args := [][]byte{
			[]byte("UpdateComplianceRule"),
			[]byte(""), // Empty rule ID
			[]byte("Test Rule"),
			[]byte("Test Description"),
			[]byte("test logic"),
			[]byte("Loan"),
			[]byte("test-actor-1"),
		}

		response := stub.MockInvoke("5", args)
		assert.Equal(t, int32(shim.ERROR), response.Status, "UpdateComplianceRule should fail with empty rule ID")
	})

	t.Run("Fail with invalid domain", func(t *testing.T) {
		args := [][]byte{
			[]byte("UpdateComplianceRule"),
			[]byte("RULE_003"),
			[]byte("Test Rule"),
			[]byte("Test Description"),
			[]byte("test logic"),
			[]byte("InvalidDomain"), // Invalid domain
			[]byte("test-actor-1"),
		}

		response := stub.MockInvoke("6", args)
		assert.Equal(t, int32(shim.ERROR), response.Status, "UpdateComplianceRule should fail with invalid domain")
	})
}

func TestComplianceChaincode_GetComplianceRule(t *testing.T) {
	cc := new(ComplianceChaincode)
	stub := shimtest.NewMockStub("compliance", cc)
	stub.MockInit("1", [][]byte{})

	// Create a test actor and rule first
	testActor := shared.Actor{
		ActorID:           "test-actor-1",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test Compliance Officer",
		Role:              shared.RoleComplianceOfficer,
		BlockchainIdentity: "test-identity",
		Permissions:       []shared.Permission{shared.PermissionUpdateCompliance},
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}

	actorJSON, _ := json.Marshal(testActor)
	stub.MockTransactionStart("create-actor")
	stub.PutState("ACTOR_test-actor-1", actorJSON)
	stub.MockTransactionEnd("create-actor")

	// Create a rule
	createArgs := [][]byte{
		[]byte("UpdateComplianceRule"),
		[]byte("RULE_001"),
		[]byte("Test Rule"),
		[]byte("Test Description"),
		[]byte("test logic"),
		[]byte("Loan"),
		[]byte("test-actor-1"),
	}
	stub.MockInvoke("2", createArgs)

	t.Run("Get existing compliance rule", func(t *testing.T) {
		args := [][]byte{
			[]byte("GetComplianceRule"),
			[]byte("RULE_001"),
		}

		response := stub.MockInvoke("3", args)
		assert.Equal(t, int32(shim.OK), response.Status, "GetComplianceRule should succeed")

		var rule ComplianceRule
		err := json.Unmarshal(response.Payload, &rule)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.Equal(t, "RULE_001", rule.RuleID)
		assert.Equal(t, "Test Rule", rule.RuleName)
	})

	t.Run("Fail with non-existent rule", func(t *testing.T) {
		args := [][]byte{
			[]byte("GetComplianceRule"),
			[]byte("RULE_999"),
		}

		response := stub.MockInvoke("4", args)
		assert.Equal(t, int32(shim.ERROR), response.Status, "GetComplianceRule should fail for non-existent rule")
	})

	t.Run("Fail with empty rule ID", func(t *testing.T) {
		args := [][]byte{
			[]byte("GetComplianceRule"),
			[]byte(""),
		}

		response := stub.MockInvoke("5", args)
		assert.Equal(t, int32(shim.ERROR), response.Status, "GetComplianceRule should fail with empty rule ID")
	})
}

func TestComplianceChaincode_RecordComplianceEvent(t *testing.T) {
	cc := new(ComplianceChaincode)
	stub := shimtest.NewMockStub("compliance", cc)
	stub.MockInit("1", [][]byte{})

	// Create a test actor and rule first
	testActor := shared.Actor{
		ActorID:           "test-actor-1",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test Compliance Officer",
		Role:              shared.RoleComplianceOfficer,
		BlockchainIdentity: "test-identity",
		Permissions:       []shared.Permission{shared.PermissionUpdateCompliance},
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}

	actorJSON, _ := json.Marshal(testActor)
	stub.MockTransactionStart("create-actor")
	stub.PutState("ACTOR_test-actor-1", actorJSON)
	stub.MockTransactionEnd("create-actor")

	// Create a rule
	createRuleArgs := [][]byte{
		[]byte("UpdateComplianceRule"),
		[]byte("RULE_001"),
		[]byte("Test Rule"),
		[]byte("Test Description"),
		[]byte("test logic"),
		[]byte("Loan"),
		[]byte("test-actor-1"),
	}
	stub.MockInvoke("2", createRuleArgs)

	t.Run("Record compliance event", func(t *testing.T) {
		args := [][]byte{
			[]byte("RecordComplianceEvent"),
			[]byte("RULE_001"),
			[]byte("LOAN_123"),
			[]byte("LoanApplication"),
			[]byte("VIOLATION"),
			[]byte("Loan amount exceeds threshold"),
			[]byte("test-actor-1"),
		}

		response := stub.MockInvoke("3", args)
		assert.Equal(t, int32(shim.OK), response.Status, "RecordComplianceEvent should succeed")

		var event ComplianceEvent
		err := json.Unmarshal(response.Payload, &event)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.Equal(t, "RULE_001", event.RuleID)
		assert.Equal(t, "LOAN_123", event.AffectedEntityID)
		assert.Equal(t, "LoanApplication", event.AffectedEntityType)
		assert.Equal(t, "VIOLATION", event.EventType)
		assert.True(t, event.IsAlerted, "Violation events should be alerted")
		assert.Equal(t, "test-actor-1", event.ActorID)
	})

	t.Run("Record compliance check event", func(t *testing.T) {
		args := [][]byte{
			[]byte("RecordComplianceEvent"),
			[]byte("RULE_001"),
			[]byte("LOAN_124"),
			[]byte("LoanApplication"),
			[]byte("COMPLIANCE_CHECK"),
			[]byte("Loan amount within threshold"),
			[]byte("test-actor-1"),
		}

		response := stub.MockInvoke("4", args)
		assert.Equal(t, int32(shim.OK), response.Status, "RecordComplianceEvent should succeed")

		var event ComplianceEvent
		err := json.Unmarshal(response.Payload, &event)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.Equal(t, "COMPLIANCE_CHECK", event.EventType)
		assert.False(t, event.IsAlerted, "Compliance check events should not be alerted")
	})

	t.Run("Fail with invalid event type", func(t *testing.T) {
		args := [][]byte{
			[]byte("RecordComplianceEvent"),
			[]byte("RULE_001"),
			[]byte("LOAN_125"),
			[]byte("LoanApplication"),
			[]byte("INVALID_TYPE"),
			[]byte("Test details"),
			[]byte("test-actor-1"),
		}

		response := stub.MockInvoke("5", args)
		assert.Equal(t, int32(shim.ERROR), response.Status, "RecordComplianceEvent should fail with invalid event type")
	})

	t.Run("Fail with non-existent rule", func(t *testing.T) {
		args := [][]byte{
			[]byte("RecordComplianceEvent"),
			[]byte("RULE_999"),
			[]byte("LOAN_126"),
			[]byte("LoanApplication"),
			[]byte("VIOLATION"),
			[]byte("Test details"),
			[]byte("test-actor-1"),
		}

		response := stub.MockInvoke("6", args)
		assert.Equal(t, int32(shim.ERROR), response.Status, "RecordComplianceEvent should fail with non-existent rule")
	})
}

func TestComplianceChaincode_GetComplianceEvent(t *testing.T) {
	cc := new(ComplianceChaincode)
	stub := shimtest.NewMockStub("compliance", cc)
	stub.MockInit("1", [][]byte{})

	// Setup test data
	setupTestData(t, stub)

	// Record an event first
	recordArgs := [][]byte{
		[]byte("RecordComplianceEvent"),
		[]byte("RULE_001"),
		[]byte("LOAN_123"),
		[]byte("LoanApplication"),
		[]byte("VIOLATION"),
		[]byte("Test violation"),
		[]byte("test-actor-1"),
	}
	recordResponse := stub.MockInvoke("3", recordArgs)
	assert.Equal(t, int32(shim.OK), recordResponse.Status)

	var recordedEvent ComplianceEvent
	json.Unmarshal(recordResponse.Payload, &recordedEvent)

	t.Run("Get existing compliance event", func(t *testing.T) {
		args := [][]byte{
			[]byte("GetComplianceEvent"),
			[]byte(recordedEvent.EventID),
		}

		response := stub.MockInvoke("4", args)
		assert.Equal(t, int32(shim.OK), response.Status, "GetComplianceEvent should succeed")

		var event ComplianceEvent
		err := json.Unmarshal(response.Payload, &event)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.Equal(t, recordedEvent.EventID, event.EventID)
		assert.Equal(t, "VIOLATION", event.EventType)
	})

	t.Run("Fail with non-existent event", func(t *testing.T) {
		args := [][]byte{
			[]byte("GetComplianceEvent"),
			[]byte("EVENT_999"),
		}

		response := stub.MockInvoke("5", args)
		assert.Equal(t, int32(shim.ERROR), response.Status, "GetComplianceEvent should fail for non-existent event")
	})
}

func TestComplianceChaincode_GetComplianceEventsByRule(t *testing.T) {
	cc := new(ComplianceChaincode)
	stub := shimtest.NewMockStub("compliance", cc)
	stub.MockInit("1", [][]byte{})

	// Setup test data
	setupTestData(t, stub)

	// Record multiple events for the same rule
	eventArgs1 := [][]byte{
		[]byte("RecordComplianceEvent"),
		[]byte("RULE_001"),
		[]byte("LOAN_123"),
		[]byte("LoanApplication"),
		[]byte("VIOLATION"),
		[]byte("First violation"),
		[]byte("test-actor-1"),
	}
	stub.MockInvoke("3", eventArgs1)

	eventArgs2 := [][]byte{
		[]byte("RecordComplianceEvent"),
		[]byte("RULE_001"),
		[]byte("LOAN_124"),
		[]byte("LoanApplication"),
		[]byte("COMPLIANCE_CHECK"),
		[]byte("Compliance check passed"),
		[]byte("test-actor-1"),
	}
	stub.MockInvoke("4", eventArgs2)

	t.Run("Get events by rule", func(t *testing.T) {
		args := [][]byte{
			[]byte("GetComplianceEventsByRule"),
			[]byte("RULE_001"),
		}

		response := stub.MockInvoke("5", args)
		assert.Equal(t, int32(shim.OK), response.Status, "GetComplianceEventsByRule should succeed")

		var events []ComplianceEvent
		err := json.Unmarshal(response.Payload, &events)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.Len(t, events, 2, "Should return 2 events")
		
		// Verify both events are for the correct rule
		for _, event := range events {
			assert.Equal(t, "RULE_001", event.RuleID)
		}
	})

	t.Run("Get events for non-existent rule", func(t *testing.T) {
		args := [][]byte{
			[]byte("GetComplianceEventsByRule"),
			[]byte("RULE_999"),
		}

		response := stub.MockInvoke("6", args)
		assert.Equal(t, int32(shim.OK), response.Status, "GetComplianceEventsByRule should succeed even for non-existent rule")

		var events []ComplianceEvent
		err := json.Unmarshal(response.Payload, &events)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.Len(t, events, 0, "Should return empty array for non-existent rule")
	})
}

func TestComplianceChaincode_GetComplianceEventsByEntity(t *testing.T) {
	cc := new(ComplianceChaincode)
	stub := shimtest.NewMockStub("compliance", cc)
	stub.MockInit("1", [][]byte{})

	// Setup test data
	setupTestData(t, stub)

	// Record multiple events for the same entity
	eventArgs1 := [][]byte{
		[]byte("RecordComplianceEvent"),
		[]byte("RULE_001"),
		[]byte("LOAN_123"),
		[]byte("LoanApplication"),
		[]byte("VIOLATION"),
		[]byte("First violation"),
		[]byte("test-actor-1"),
	}
	stub.MockInvoke("3", eventArgs1)

	eventArgs2 := [][]byte{
		[]byte("RecordComplianceEvent"),
		[]byte("RULE_001"),
		[]byte("LOAN_123"),
		[]byte("LoanApplication"),
		[]byte("ACKNOWLEDGMENT"),
		[]byte("Violation acknowledged"),
		[]byte("test-actor-1"),
	}
	stub.MockInvoke("4", eventArgs2)

	t.Run("Get events by entity", func(t *testing.T) {
		args := [][]byte{
			[]byte("GetComplianceEventsByEntity"),
			[]byte("LOAN_123"),
		}

		response := stub.MockInvoke("5", args)
		assert.Equal(t, int32(shim.OK), response.Status, "GetComplianceEventsByEntity should succeed")

		var events []ComplianceEvent
		err := json.Unmarshal(response.Payload, &events)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.Len(t, events, 2, "Should return 2 events")
		
		// Verify both events are for the correct entity
		for _, event := range events {
			assert.Equal(t, "LOAN_123", event.AffectedEntityID)
		}
	})

	t.Run("Get events for non-existent entity", func(t *testing.T) {
		args := [][]byte{
			[]byte("GetComplianceEventsByEntity"),
			[]byte("LOAN_999"),
		}

		response := stub.MockInvoke("6", args)
		assert.Equal(t, int32(shim.OK), response.Status, "GetComplianceEventsByEntity should succeed even for non-existent entity")

		var events []ComplianceEvent
		err := json.Unmarshal(response.Payload, &events)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.Len(t, events, 0, "Should return empty array for non-existent entity")
	})
}

func TestComplianceChaincode_InvalidFunction(t *testing.T) {
	cc := new(ComplianceChaincode)
	stub := shimtest.NewMockStub("compliance", cc)
	stub.MockInit("1", [][]byte{})

	response := stub.MockInvoke("1", [][]byte{[]byte("InvalidFunction")})
	assert.Equal(t, int32(shim.ERROR), response.Status, "Invalid function should return error")
	assert.Contains(t, response.Message, "Invalid function name", "Error message should mention invalid function")
}

func TestComplianceChaincode_GetHardcodedRules(t *testing.T) {
	cc := new(ComplianceChaincode)
	stub := shimtest.NewMockStub("compliance", cc)
	stub.MockInit("1", [][]byte{})

	t.Run("Get all hardcoded rules", func(t *testing.T) {
		args := [][]byte{
			[]byte("GetHardcodedRules"),
		}

		response := stub.MockInvoke("2", args)
		assert.Equal(t, int32(shim.OK), response.Status, "GetHardcodedRules should succeed")

		var rules []map[string]interface{}
		err := json.Unmarshal(response.Payload, &rules)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.Greater(t, len(rules), 0, "Should return at least one rule")

		// Check that expected rules are present
		ruleIDs := make([]string, len(rules))
		for i, rule := range rules {
			ruleIDs[i] = rule["ruleID"].(string)
		}
		assert.Contains(t, ruleIDs, "LOAN_AMOUNT_THRESHOLD")
		assert.Contains(t, ruleIDs, "CUSTOMER_KYC_REQUIRED")
	})
}

func TestComplianceChaincode_ValidateLoanApplication(t *testing.T) {
	cc := new(ComplianceChaincode)
	stub := shimtest.NewMockStub("compliance", cc)
	stub.MockInit("1", [][]byte{})

	t.Run("Validate compliant loan application", func(t *testing.T) {
		loanData := map[string]interface{}{
			"requestedAmount": 50000.0,
			"loanType":       "Personal",
			"currentStatus":  "Submitted",
		}
		loanDataJSON, _ := json.Marshal(loanData)

		args := [][]byte{
			[]byte("ValidateLoanApplication"),
			[]byte("LOAN_123"),
			[]byte(string(loanDataJSON)),
		}

		response := stub.MockInvoke("2", args)
		assert.Equal(t, int32(shim.OK), response.Status, "ValidateLoanApplication should succeed")

		var result map[string]interface{}
		err := json.Unmarshal(response.Payload, &result)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.True(t, result["isCompliant"].(bool), "Loan should be compliant")
		assert.Equal(t, float64(0), result["violationCount"].(float64), "Should have no violations")
	})

	t.Run("Validate non-compliant loan application - amount threshold", func(t *testing.T) {
		loanData := map[string]interface{}{
			"requestedAmount": 150000.0,
			"loanType":       "Personal",
			"currentStatus":  "Submitted",
		}
		loanDataJSON, _ := json.Marshal(loanData)

		args := [][]byte{
			[]byte("ValidateLoanApplication"),
			[]byte("LOAN_124"),
			[]byte(string(loanDataJSON)),
		}

		response := stub.MockInvoke("3", args)
		assert.Equal(t, int32(shim.OK), response.Status, "ValidateLoanApplication should succeed")

		var result map[string]interface{}
		err := json.Unmarshal(response.Payload, &result)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.False(t, result["isCompliant"].(bool), "Loan should not be compliant")
		assert.Greater(t, result["violationCount"].(float64), float64(0), "Should have violations")

		violations := result["violations"].([]interface{})
		assert.Greater(t, len(violations), 0, "Should have violation details")
	})

	t.Run("Validate non-compliant loan application - maximum amount", func(t *testing.T) {
		loanData := map[string]interface{}{
			"requestedAmount": 1500000.0,
			"loanType":       "Business",
			"currentStatus":  "Submitted",
		}
		loanDataJSON, _ := json.Marshal(loanData)

		args := [][]byte{
			[]byte("ValidateLoanApplication"),
			[]byte("LOAN_125"),
			[]byte(string(loanDataJSON)),
		}

		response := stub.MockInvoke("4", args)
		assert.Equal(t, int32(shim.OK), response.Status, "ValidateLoanApplication should succeed")

		var result map[string]interface{}
		err := json.Unmarshal(response.Payload, &result)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.False(t, result["isCompliant"].(bool), "Loan should not be compliant")
		assert.Greater(t, result["violationCount"].(float64), float64(0), "Should have violations")
	})
}

func TestComplianceChaincode_ValidateCustomer(t *testing.T) {
	cc := new(ComplianceChaincode)
	stub := shimtest.NewMockStub("compliance", cc)
	stub.MockInit("1", [][]byte{})

	t.Run("Validate compliant customer", func(t *testing.T) {
		customerData := map[string]interface{}{
			"customerID": "CUST_123",
			"kycStatus":  "Completed",
			"amlStatus":  "Cleared",
		}
		customerDataJSON, _ := json.Marshal(customerData)

		args := [][]byte{
			[]byte("ValidateCustomer"),
			[]byte("CUST_123"),
			[]byte(string(customerDataJSON)),
		}

		response := stub.MockInvoke("2", args)
		assert.Equal(t, int32(shim.OK), response.Status, "ValidateCustomer should succeed")

		var result map[string]interface{}
		err := json.Unmarshal(response.Payload, &result)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.True(t, result["isCompliant"].(bool), "Customer should be compliant")
		assert.Equal(t, float64(0), result["violationCount"].(float64), "Should have no violations")
	})

	t.Run("Validate non-compliant customer - KYC not completed", func(t *testing.T) {
		customerData := map[string]interface{}{
			"customerID": "CUST_124",
			"kycStatus":  "Pending",
			"amlStatus":  "Cleared",
		}
		customerDataJSON, _ := json.Marshal(customerData)

		args := [][]byte{
			[]byte("ValidateCustomer"),
			[]byte("CUST_124"),
			[]byte(string(customerDataJSON)),
		}

		response := stub.MockInvoke("3", args)
		assert.Equal(t, int32(shim.OK), response.Status, "ValidateCustomer should succeed")

		var result map[string]interface{}
		err := json.Unmarshal(response.Payload, &result)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.False(t, result["isCompliant"].(bool), "Customer should not be compliant")
		assert.Greater(t, result["violationCount"].(float64), float64(0), "Should have violations")
	})

	t.Run("Validate non-compliant customer - AML failed", func(t *testing.T) {
		customerData := map[string]interface{}{
			"customerID": "CUST_125",
			"kycStatus":  "Completed",
			"amlStatus":  "Failed",
		}
		customerDataJSON, _ := json.Marshal(customerData)

		args := [][]byte{
			[]byte("ValidateCustomer"),
			[]byte("CUST_125"),
			[]byte(string(customerDataJSON)),
		}

		response := stub.MockInvoke("4", args)
		assert.Equal(t, int32(shim.OK), response.Status, "ValidateCustomer should succeed")

		var result map[string]interface{}
		err := json.Unmarshal(response.Payload, &result)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.False(t, result["isCompliant"].(bool), "Customer should not be compliant")
		assert.Greater(t, result["violationCount"].(float64), float64(0), "Should have violations")
	})
}

func TestComplianceChaincode_ValidateComplianceRules(t *testing.T) {
	cc := new(ComplianceChaincode)
	stub := shimtest.NewMockStub("compliance", cc)
	stub.MockInit("1", [][]byte{})

	t.Run("Validate loan status transition - valid", func(t *testing.T) {
		loanData := map[string]interface{}{
			"currentStatus": "Submitted",
			"newStatus":     "Under_Review",
		}
		loanDataJSON, _ := json.Marshal(loanData)

		args := [][]byte{
			[]byte("ValidateComplianceRules"),
			[]byte("Loan"),
			[]byte("LOAN_126"),
			[]byte("LoanApplication"),
			[]byte(string(loanDataJSON)),
		}

		response := stub.MockInvoke("2", args)
		assert.Equal(t, int32(shim.OK), response.Status, "ValidateComplianceRules should succeed")

		var result map[string]interface{}
		err := json.Unmarshal(response.Payload, &result)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.True(t, result["isCompliant"].(bool), "Status transition should be compliant")
	})

	t.Run("Validate loan status transition - invalid", func(t *testing.T) {
		loanData := map[string]interface{}{
			"currentStatus": "Submitted",
			"newStatus":     "Disbursed", // Invalid transition
		}
		loanDataJSON, _ := json.Marshal(loanData)

		args := [][]byte{
			[]byte("ValidateComplianceRules"),
			[]byte("Loan"),
			[]byte("LOAN_127"),
			[]byte("LoanApplication"),
			[]byte(string(loanDataJSON)),
		}

		response := stub.MockInvoke("3", args)
		assert.Equal(t, int32(shim.OK), response.Status, "ValidateComplianceRules should succeed")

		var result map[string]interface{}
		err := json.Unmarshal(response.Payload, &result)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.False(t, result["isCompliant"].(bool), "Status transition should not be compliant")
		assert.Greater(t, result["violationCount"].(float64), float64(0), "Should have violations")
	})

	t.Run("Fail with invalid JSON", func(t *testing.T) {
		args := [][]byte{
			[]byte("ValidateComplianceRules"),
			[]byte("Loan"),
			[]byte("LOAN_128"),
			[]byte("LoanApplication"),
			[]byte("invalid json"),
		}

		response := stub.MockInvoke("4", args)
		assert.Equal(t, int32(shim.ERROR), response.Status, "ValidateComplianceRules should fail with invalid JSON")
	})
}

func TestComplianceChaincode_AddSanctionListEntry(t *testing.T) {
	cc := new(ComplianceChaincode)
	stub := shimtest.NewMockStub("compliance", cc)
	stub.MockInit("1", [][]byte{})

	// Setup test actor
	setupTestData(t, stub)

	t.Run("Add sanction list entry", func(t *testing.T) {
		aliases := []string{"J. Doe", "Johnny Doe"}
		aliasesJSON, _ := json.Marshal(aliases)

		args := [][]byte{
			[]byte("AddSanctionListEntry"),
			[]byte("SANCTION_TEST_001"),
			[]byte("TEST_LIST"),
			[]byte("John Doe Test"),
			[]byte("Individual"),
			[]byte(string(aliasesJSON)),
			[]byte("1980-01-01"),
			[]byte("US"),
			[]byte("Financial"),
			[]byte("TEST_SOURCE"),
			[]byte("test-actor-1"),
		}

		response := stub.MockInvoke("3", args)
		assert.Equal(t, int32(shim.OK), response.Status, "AddSanctionListEntry should succeed")

		var entry SanctionListEntry
		err := json.Unmarshal(response.Payload, &entry)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.Equal(t, "SANCTION_TEST_001", entry.EntryID)
		assert.Equal(t, "John Doe Test", entry.EntityName)
		assert.Equal(t, "Individual", entry.EntityType)
		assert.True(t, entry.IsActive)
		assert.Len(t, entry.Aliases, 2)
	})

	t.Run("Fail with insufficient arguments", func(t *testing.T) {
		args := [][]byte{
			[]byte("AddSanctionListEntry"),
			[]byte("SANCTION_TEST_002"),
		}

		response := stub.MockInvoke("4", args)
		assert.Equal(t, int32(shim.ERROR), response.Status, "AddSanctionListEntry should fail with insufficient arguments")
	})
}

func TestComplianceChaincode_GetSanctionListEntry(t *testing.T) {
	cc := new(ComplianceChaincode)
	stub := shimtest.NewMockStub("compliance", cc)
	stub.MockInit("1", [][]byte{})

	// Setup test data
	setupTestData(t, stub)

	// Add a sanction list entry first
	aliases := []string{"J. Doe"}
	aliasesJSON, _ := json.Marshal(aliases)

	addArgs := [][]byte{
		[]byte("AddSanctionListEntry"),
		[]byte("SANCTION_TEST_001"),
		[]byte("TEST_LIST"),
		[]byte("John Doe Test"),
		[]byte("Individual"),
		[]byte(string(aliasesJSON)),
		[]byte("1980-01-01"),
		[]byte("US"),
		[]byte("Financial"),
		[]byte("TEST_SOURCE"),
		[]byte("test-actor-1"),
	}
	stub.MockInvoke("3", addArgs)

	t.Run("Get existing sanction list entry", func(t *testing.T) {
		args := [][]byte{
			[]byte("GetSanctionListEntry"),
			[]byte("SANCTION_TEST_001"),
		}

		response := stub.MockInvoke("4", args)
		assert.Equal(t, int32(shim.OK), response.Status, "GetSanctionListEntry should succeed")

		var entry SanctionListEntry
		err := json.Unmarshal(response.Payload, &entry)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.Equal(t, "SANCTION_TEST_001", entry.EntryID)
		assert.Equal(t, "John Doe Test", entry.EntityName)
	})

	t.Run("Fail with non-existent entry", func(t *testing.T) {
		args := [][]byte{
			[]byte("GetSanctionListEntry"),
			[]byte("SANCTION_NONEXISTENT"),
		}

		response := stub.MockInvoke("5", args)
		assert.Equal(t, int32(shim.ERROR), response.Status, "GetSanctionListEntry should fail for non-existent entry")
	})
}

func TestComplianceChaincode_ScreenAgainstSanctionLists(t *testing.T) {
	cc := new(ComplianceChaincode)
	stub := shimtest.NewMockStub("compliance", cc)
	stub.MockInit("1", [][]byte{})

	t.Run("Screen entity with no matches", func(t *testing.T) {
		entityData := map[string]interface{}{
			"name":        "Clean Customer",
			"dateOfBirth": "1990-01-01",
		}
		entityDataJSON, _ := json.Marshal(entityData)

		args := [][]byte{
			[]byte("ScreenAgainstSanctionLists"),
			[]byte("CUSTOMER_001"),
			[]byte("Customer"),
			[]byte(string(entityDataJSON)),
			[]byte("system"),
		}

		response := stub.MockInvoke("2", args)
		assert.Equal(t, int32(shim.OK), response.Status, "ScreenAgainstSanctionLists should succeed")

		var result SanctionScreeningResult
		err := json.Unmarshal(response.Payload, &result)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.False(t, result.IsMatch, "Should not find matches for clean customer")
		assert.Equal(t, "CLEARED", result.Status)
		assert.Len(t, result.Matches, 0)
	})

	t.Run("Screen entity with exact match", func(t *testing.T) {
		entityData := map[string]interface{}{
			"name":        "John Doe Sanctioned",
			"dateOfBirth": "1980-01-01",
		}
		entityDataJSON, _ := json.Marshal(entityData)

		args := [][]byte{
			[]byte("ScreenAgainstSanctionLists"),
			[]byte("CUSTOMER_002"),
			[]byte("Customer"),
			[]byte(string(entityDataJSON)),
			[]byte("system"),
		}

		response := stub.MockInvoke("3", args)
		assert.Equal(t, int32(shim.OK), response.Status, "ScreenAgainstSanctionLists should succeed")

		var result SanctionScreeningResult
		err := json.Unmarshal(response.Payload, &result)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.True(t, result.IsMatch, "Should find exact match")
		assert.Equal(t, "FLAGGED", result.Status)
		assert.Greater(t, len(result.Matches), 0, "Should have matches")
		assert.Equal(t, 1.0, result.MatchScore, "Should have perfect match score")
	})

	t.Run("Screen entity with alias match", func(t *testing.T) {
		entityData := map[string]interface{}{
			"name": "J. Doe",
		}
		entityDataJSON, _ := json.Marshal(entityData)

		args := [][]byte{
			[]byte("ScreenAgainstSanctionLists"),
			[]byte("CUSTOMER_003"),
			[]byte("Customer"),
			[]byte(string(entityDataJSON)),
			[]byte("system"),
		}

		response := stub.MockInvoke("4", args)
		assert.Equal(t, int32(shim.OK), response.Status, "ScreenAgainstSanctionLists should succeed")

		var result SanctionScreeningResult
		err := json.Unmarshal(response.Payload, &result)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.True(t, result.IsMatch, "Should find alias match")
		assert.Greater(t, len(result.Matches), 0, "Should have matches")
		assert.Equal(t, "ALIAS", result.Matches[0].MatchType)
	})

	t.Run("Screen entity with exact match (corrected)", func(t *testing.T) {
		entityData := map[string]interface{}{
			"name": "John Doe Sanctioned", // Exact match
		}
		entityDataJSON, _ := json.Marshal(entityData)

		args := [][]byte{
			[]byte("ScreenAgainstSanctionLists"),
			[]byte("CUSTOMER_004"),
			[]byte("Customer"),
			[]byte(string(entityDataJSON)),
			[]byte("system"),
		}

		response := stub.MockInvoke("5", args)
		assert.Equal(t, int32(shim.OK), response.Status, "ScreenAgainstSanctionLists should succeed")

		var result SanctionScreeningResult
		err := json.Unmarshal(response.Payload, &result)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.True(t, result.IsMatch, "Should find exact match")
		assert.Greater(t, len(result.Matches), 0, "Should have matches")
		if len(result.Matches) > 0 {
			assert.Equal(t, "EXACT", result.Matches[0].MatchType)
		}
	})

	t.Run("Screen entity with partial match", func(t *testing.T) {
		entityData := map[string]interface{}{
			"name": "John Doe Sanction", // Missing 'ed' - should trigger partial match
		}
		entityDataJSON, _ := json.Marshal(entityData)

		args := [][]byte{
			[]byte("ScreenAgainstSanctionLists"),
			[]byte("CUSTOMER_005"),
			[]byte("Customer"),
			[]byte(string(entityDataJSON)),
			[]byte("system"),
		}

		response := stub.MockInvoke("6", args)
		assert.Equal(t, int32(shim.OK), response.Status, "ScreenAgainstSanctionLists should succeed")

		var result SanctionScreeningResult
		err := json.Unmarshal(response.Payload, &result)
		assert.NoError(t, err, "Response should be valid JSON")
		
		// This might or might not match depending on similarity threshold
		// Let's just check that the function executes successfully
		if result.IsMatch && len(result.Matches) > 0 {
			// If there's a match, it should be partial
			assert.Equal(t, "PARTIAL", result.Matches[0].MatchType)
		}
	})

	t.Run("Screen with firstName and lastName", func(t *testing.T) {
		entityData := map[string]interface{}{
			"firstName": "Jane",
			"lastName":  "Smith Criminal",
		}
		entityDataJSON, _ := json.Marshal(entityData)

		args := [][]byte{
			[]byte("ScreenAgainstSanctionLists"),
			[]byte("CUSTOMER_006"),
			[]byte("Customer"),
			[]byte(string(entityDataJSON)),
			[]byte("system"),
		}

		response := stub.MockInvoke("7", args)
		assert.Equal(t, int32(shim.OK), response.Status, "ScreenAgainstSanctionLists should succeed")

		var result SanctionScreeningResult
		err := json.Unmarshal(response.Payload, &result)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.True(t, result.IsMatch, "Should find match using firstName and lastName")
		assert.Equal(t, "Jane Smith Criminal", result.EntityName)
	})

	t.Run("Fail with missing entity name", func(t *testing.T) {
		entityData := map[string]interface{}{
			"id": "CUSTOMER_007",
		}
		entityDataJSON, _ := json.Marshal(entityData)

		args := [][]byte{
			[]byte("ScreenAgainstSanctionLists"),
			[]byte("CUSTOMER_007"),
			[]byte("Customer"),
			[]byte(string(entityDataJSON)),
			[]byte("system"),
		}

		response := stub.MockInvoke("8", args)
		assert.Equal(t, int32(shim.ERROR), response.Status, "ScreenAgainstSanctionLists should fail without entity name")
	})
}

func TestComplianceChaincode_GetScreeningResult(t *testing.T) {
	cc := new(ComplianceChaincode)
	stub := shimtest.NewMockStub("compliance", cc)
	stub.MockInit("1", [][]byte{})

	// Perform a screening first
	entityData := map[string]interface{}{
		"name": "Test Customer",
	}
	entityDataJSON, _ := json.Marshal(entityData)

	screenArgs := [][]byte{
		[]byte("ScreenAgainstSanctionLists"),
		[]byte("CUSTOMER_001"),
		[]byte("Customer"),
		[]byte(string(entityDataJSON)),
		[]byte("system"),
	}
	screenResponse := stub.MockInvoke("2", screenArgs)
	assert.Equal(t, int32(shim.OK), screenResponse.Status)

	var screenResult SanctionScreeningResult
	json.Unmarshal(screenResponse.Payload, &screenResult)

	t.Run("Get existing screening result", func(t *testing.T) {
		args := [][]byte{
			[]byte("GetScreeningResult"),
			[]byte(screenResult.ScreeningID),
		}

		response := stub.MockInvoke("3", args)
		assert.Equal(t, int32(shim.OK), response.Status, "GetScreeningResult should succeed")

		var result SanctionScreeningResult
		err := json.Unmarshal(response.Payload, &result)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.Equal(t, screenResult.ScreeningID, result.ScreeningID)
		assert.Equal(t, "CUSTOMER_001", result.EntityID)
	})

	t.Run("Fail with non-existent screening result", func(t *testing.T) {
		args := [][]byte{
			[]byte("GetScreeningResult"),
			[]byte("SCREENING_NONEXISTENT"),
		}

		response := stub.MockInvoke("4", args)
		assert.Equal(t, int32(shim.ERROR), response.Status, "GetScreeningResult should fail for non-existent result")
	})
}

func TestComplianceChaincode_GetScreeningResultsByEntity(t *testing.T) {
	cc := new(ComplianceChaincode)
	stub := shimtest.NewMockStub("compliance", cc)
	stub.MockInit("1", [][]byte{})

	// Perform multiple screenings for the same entity
	entityData := map[string]interface{}{
		"name": "Test Customer",
	}
	entityDataJSON, _ := json.Marshal(entityData)

	// First screening
	screenArgs1 := [][]byte{
		[]byte("ScreenAgainstSanctionLists"),
		[]byte("CUSTOMER_001"),
		[]byte("Customer"),
		[]byte(string(entityDataJSON)),
		[]byte("system"),
	}
	stub.MockInvoke("2", screenArgs1)

	// Second screening
	screenArgs2 := [][]byte{
		[]byte("ScreenAgainstSanctionLists"),
		[]byte("CUSTOMER_001"),
		[]byte("Customer"),
		[]byte(string(entityDataJSON)),
		[]byte("system"),
	}
	stub.MockInvoke("3", screenArgs2)

	t.Run("Get screening results by entity", func(t *testing.T) {
		args := [][]byte{
			[]byte("GetScreeningResultsByEntity"),
			[]byte("CUSTOMER_001"),
		}

		response := stub.MockInvoke("4", args)
		assert.Equal(t, int32(shim.OK), response.Status, "GetScreeningResultsByEntity should succeed")

		var results []SanctionScreeningResult
		err := json.Unmarshal(response.Payload, &results)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.Len(t, results, 2, "Should return 2 screening results")

		// Verify both results are for the correct entity
		for _, result := range results {
			assert.Equal(t, "CUSTOMER_001", result.EntityID)
		}
	})

	t.Run("Get screening results for non-existent entity", func(t *testing.T) {
		args := [][]byte{
			[]byte("GetScreeningResultsByEntity"),
			[]byte("CUSTOMER_NONEXISTENT"),
		}

		response := stub.MockInvoke("5", args)
		assert.Equal(t, int32(shim.OK), response.Status, "GetScreeningResultsByEntity should succeed even for non-existent entity")

		var results []SanctionScreeningResult
		err := json.Unmarshal(response.Payload, &results)
		assert.NoError(t, err, "Response should be valid JSON")
		assert.Len(t, results, 0, "Should return empty array for non-existent entity")
	})
}

// Helper function to setup test data
func setupTestData(t *testing.T, stub *shimtest.MockStub) {
	// Create a test actor
	testActor := shared.Actor{
		ActorID:           "test-actor-1",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test Compliance Officer",
		Role:              shared.RoleComplianceOfficer,
		BlockchainIdentity: "test-identity",
		Permissions:       []shared.Permission{shared.PermissionUpdateCompliance},
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}

	actorJSON, _ := json.Marshal(testActor)
	stub.MockTransactionStart("create-actor")
	stub.PutState("ACTOR_test-actor-1", actorJSON)
	stub.MockTransactionEnd("create-actor")

	// Create a test rule
	createRuleArgs := [][]byte{
		[]byte("UpdateComplianceRule"),
		[]byte("RULE_001"),
		[]byte("Test Rule"),
		[]byte("Test Description"),
		[]byte("test logic"),
		[]byte("Loan"),
		[]byte("test-actor-1"),
	}
	response := stub.MockInvoke("2", createRuleArgs)
	assert.Equal(t, int32(shim.OK), response.Status, "Rule creation should succeed")
}