package main

import (
	"encoding/json"
	"testing"

	"github.com/hyperledger/fabric-chaincode-go/shimtest"
)

// TestLoanHistoryIntegration demonstrates complete loan application history tracking
// from creation through approval, showing the complete immutable audit trail
func TestLoanHistoryIntegration(t *testing.T) {
	cc := new(LoanChaincode)
	stub := shimtest.NewMockStub("loan", cc)
	setupTestEnvironment(stub)

	// Step 1: Create loan application
	t.Log("Step 1: Creating loan application...")
	submitArgs := [][]byte{
		[]byte("SubmitApplication"),
		[]byte("test-customer-1"),
		[]byte("100000.00"),
		[]byte("Mortgage"),
		[]byte("test-introducer-1"),
		[]byte("test-actor-1"),
	}
	submitResponse := stub.MockInvoke("1", submitArgs)
	if submitResponse.Status != 200 {
		t.Fatalf("Failed to create loan application: %s", submitResponse.Message)
	}

	var loanApp LoanApplication
	json.Unmarshal(submitResponse.Payload, &loanApp)
	loanID := loanApp.LoanApplicationID
	t.Logf("Created loan application: %s", loanID)

	// Step 2: Progress to Underwriting
	t.Log("Step 2: Progressing to Underwriting...")
	updateArgs1 := [][]byte{
		[]byte("UpdateStatus"),
		[]byte(loanID),
		[]byte("Underwriting"),
		[]byte("test-underwriter-1"),
	}
	updateResponse1 := stub.MockInvoke("2", updateArgs1)
	if updateResponse1.Status != 200 {
		t.Fatalf("Failed to update to Underwriting: %s", updateResponse1.Message)
	}

	// Step 3: Progress to Credit Review
	t.Log("Step 3: Progressing to Credit Review...")
	updateArgs2 := [][]byte{
		[]byte("UpdateStatus"),
		[]byte(loanID),
		[]byte("Credit_Review"),
		[]byte("test-underwriter-1"),
	}
	updateResponse2 := stub.MockInvoke("3", updateArgs2)
	if updateResponse2.Status != 200 {
		t.Fatalf("Failed to update to Credit Review: %s", updateResponse2.Message)
	}

	// Step 4: Approve the loan
	t.Log("Step 4: Approving loan...")
	approveArgs := [][]byte{
		[]byte("ApproveLoan"),
		[]byte(loanID),
		[]byte("95000.00"), // Approved for less than requested
		[]byte("3.75"),     // Interest rate
		[]byte("360"),      // 30-year mortgage
		[]byte("test-credit-officer-1"),
	}
	approveResponse := stub.MockInvoke("4", approveArgs)
	if approveResponse.Status != 200 {
		t.Fatalf("Failed to approve loan: %s", approveResponse.Message)
	}

	// Step 5: Retrieve complete history
	t.Log("Step 5: Retrieving complete loan history...")
	historyArgs := [][]byte{
		[]byte("GetLoanHistory"),
		[]byte(loanID),
		[]byte("test-actor-1"),
	}
	historyResponse := stub.MockInvoke("5", historyArgs)
	if historyResponse.Status != 200 {
		t.Fatalf("Failed to get loan history: %s", historyResponse.Message)
	}

	// Parse and validate the complete history
	var historyData map[string]interface{}
	err := json.Unmarshal(historyResponse.Payload, &historyData)
	if err != nil {
		t.Fatalf("Failed to parse history response: %v", err)
	}

	// Validate response structure
	if historyData["loanApplicationID"] != loanID {
		t.Errorf("Expected loan ID %s, got %s", loanID, historyData["loanApplicationID"])
	}

	historyCount := historyData["historyCount"].(float64)
	if historyCount < 7 { // CREATE + 2 UPDATEs + 4 APPROVE entries (status, amount, rate, term)
		t.Errorf("Expected at least 7 history entries, got %f", historyCount)
	}

	// Validate current state
	currentState := historyData["currentState"].(map[string]interface{})
	if currentState["applicationStatus"] != "Approved" {
		t.Errorf("Expected current status 'Approved', got %s", currentState["applicationStatus"])
	}
	if currentState["approvedAmount"] != 95000.0 {
		t.Errorf("Expected approved amount 95000, got %f", currentState["approvedAmount"])
	}

	// Validate history entries
	history := historyData["history"].([]interface{})
	t.Logf("Found %d history entries", len(history))

	// Verify chronological order and key events
	expectedEvents := []struct {
		changeType string
		fieldName  string
		newValue   string
	}{
		{"CREATE", "status", "Submitted"},
		{"UPDATE", "status", "Underwriting"},
		{"UPDATE", "status", "Credit_Review"},
		{"APPROVE", "status", "Approved"},
		{"APPROVE", "approvedAmount", "95000.00"},
		{"APPROVE", "interestRate", "3.75"},
		{"APPROVE", "loanTerm", "360"},
	}

	for i, expectedEvent := range expectedEvents {
		if i >= len(history) {
			t.Errorf("Missing expected history entry %d: %+v", i, expectedEvent)
			continue
		}

		entry := history[i].(map[string]interface{})
		
		if entry["changeType"] != expectedEvent.changeType {
			t.Errorf("Entry %d: expected changeType %s, got %s", i, expectedEvent.changeType, entry["changeType"])
		}
		
		if entry["fieldName"] != expectedEvent.fieldName {
			t.Errorf("Entry %d: expected fieldName %s, got %s", i, expectedEvent.fieldName, entry["fieldName"])
		}
		
		if entry["newValue"] != expectedEvent.newValue {
			t.Errorf("Entry %d: expected newValue %s, got %s", i, expectedEvent.newValue, entry["newValue"])
		}

		// Verify all entries have required audit fields
		requiredFields := []string{"historyID", "timestamp", "actorID", "transactionID"}
		for _, field := range requiredFields {
			if _, exists := entry[field]; !exists {
				t.Errorf("Entry %d missing required field: %s", i, field)
			}
		}
	}

	// Verify actor attribution
	createEntry := history[0].(map[string]interface{})
	if createEntry["actorID"] != "test-actor-1" {
		t.Errorf("Expected CREATE entry by test-actor-1, got %s", createEntry["actorID"])
	}

	underwritingEntry := history[1].(map[string]interface{})
	if underwritingEntry["actorID"] != "test-underwriter-1" {
		t.Errorf("Expected Underwriting entry by test-underwriter-1, got %s", underwritingEntry["actorID"])
	}

	// Find approval entry
	var approvalEntry map[string]interface{}
	for _, entry := range history {
		entryMap := entry.(map[string]interface{})
		if entryMap["changeType"] == "APPROVE" && entryMap["fieldName"] == "status" {
			approvalEntry = entryMap
			break
		}
	}
	if approvalEntry == nil {
		t.Error("Could not find approval status entry")
	} else if approvalEntry["actorID"] != "test-credit-officer-1" {
		t.Errorf("Expected approval by test-credit-officer-1, got %s", approvalEntry["actorID"])
	}

	t.Log("✅ Complete loan history tracking integration test passed!")
	t.Logf("✅ Verified %d history entries with complete audit trail", len(history))
	t.Log("✅ Confirmed immutable record of who, what, when for all changes")
	t.Log("✅ Validated chronological ordering and data integrity")
}

// TestHistoryAccessControl verifies that history access is properly controlled
func TestHistoryAccessControl(t *testing.T) {
	cc := new(LoanChaincode)
	stub := shimtest.NewMockStub("loan", cc)
	setupTestEnvironment(stub)

	// Create a loan application
	loanApp := createTestLoanApplication(t, stub, cc)

	// Test 1: Valid access with proper permissions
	historyArgs := [][]byte{
		[]byte("GetLoanHistory"),
		[]byte(loanApp.LoanApplicationID),
		[]byte("test-actor-1"), // Has VIEW_LOAN permission
	}
	response := stub.MockInvoke("2", historyArgs)
	if response.Status != 200 {
		t.Errorf("Expected authorized access to succeed, got error: %s", response.Message)
	}

	// Test 2: Invalid access without proper permissions
	// Create actor without VIEW_LOAN permission
	restrictedActor := `{
		"actorID": "restricted-actor",
		"actorType": "Internal_User",
		"actorName": "Restricted User",
		"role": "Customer_Service",
		"blockchainIdentity": "restricted-cert",
		"permissions": [],
		"isActive": true,
		"createdDate": "2024-01-01T00:00:00Z",
		"lastUpdated": "2024-01-01T00:00:00Z"
	}`
	stub.MockTransactionStart("setup-restricted")
	stub.PutState("ACTOR_restricted-actor", []byte(restrictedActor))
	stub.MockTransactionEnd("setup-restricted")

	restrictedHistoryArgs := [][]byte{
		[]byte("GetLoanHistory"),
		[]byte(loanApp.LoanApplicationID),
		[]byte("restricted-actor"), // No VIEW_LOAN permission
	}
	restrictedResponse := stub.MockInvoke("3", restrictedHistoryArgs)
	if restrictedResponse.Status == 200 {
		t.Error("Expected unauthorized access to fail")
	}

	t.Log("✅ History access control test passed!")
}