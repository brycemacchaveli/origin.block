package main

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/hyperledger/fabric-chaincode-go/shimtest"
	"github.com/blockchain-financial-platform/fabric-chaincode/shared"
)

func TestLoanChaincode_Init(t *testing.T) {
	cc := new(LoanChaincode)
	stub := shimtest.NewMockStub("loan", cc)

	response := cc.Init(stub)
	if response.Status != shim.OK {
		t.Errorf("Init failed with status %d and message: %s", response.Status, response.Message)
	}
}

func TestLoanChaincode_Ping(t *testing.T) {
	cc := new(LoanChaincode)
	stub := shimtest.NewMockStub("loan", cc)

	response := stub.MockInvoke("1", [][]byte{[]byte("ping")})
	if response.Status != shim.OK {
		t.Errorf("Ping failed with status %d and message: %s", response.Status, response.Message)
	}

	if string(response.Payload) != "pong" {
		t.Errorf("Expected 'pong', got '%s'", string(response.Payload))
	}
}

func setupTestEnvironment(stub *shimtest.MockStub) {
	// Create test actor with loan permissions
	testActor := shared.Actor{
		ActorID:           "test-actor-1",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test Introducer",
		Role:              shared.RoleIntroducer,
		BlockchainIdentity: "test-cert-hash",
		Permissions:       []shared.Permission{shared.PermissionCreateLoan, shared.PermissionViewLoan},
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}
	actorJSON, _ := json.Marshal(testActor)
	stub.MockTransactionStart("setup-actor")
	stub.PutState("ACTOR_test-actor-1", actorJSON)
	stub.MockTransactionEnd("setup-actor")

	// Create test underwriter actor
	underwriterActor := shared.Actor{
		ActorID:           "test-underwriter-1",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test Underwriter",
		Role:              shared.RoleUnderwriter,
		BlockchainIdentity: "test-underwriter-cert",
		Permissions:       []shared.Permission{shared.PermissionUpdateLoan, shared.PermissionViewLoan},
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}
	underwriterJSON, _ := json.Marshal(underwriterActor)
	stub.MockTransactionStart("setup-underwriter")
	stub.PutState("ACTOR_test-underwriter-1", underwriterJSON)
	stub.MockTransactionEnd("setup-underwriter")

	// Create test credit officer actor
	creditOfficerActor := shared.Actor{
		ActorID:           "test-credit-officer-1",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test Credit Officer",
		Role:              shared.RoleCreditOfficer,
		BlockchainIdentity: "test-credit-officer-cert",
		Permissions:       []shared.Permission{shared.PermissionApproveLoan, shared.PermissionViewLoan},
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}
	creditOfficerJSON, _ := json.Marshal(creditOfficerActor)
	stub.MockTransactionStart("setup-credit-officer")
	stub.PutState("ACTOR_test-credit-officer-1", creditOfficerJSON)
	stub.MockTransactionEnd("setup-credit-officer")

	// Create test customer
	testCustomer := map[string]interface{}{
		"customerID": "test-customer-1",
		"firstName":  "John",
		"lastName":   "Doe",
	}
	customerJSON, _ := json.Marshal(testCustomer)
	stub.MockTransactionStart("setup-customer")
	stub.PutState("CUSTOMER_test-customer-1", customerJSON)
	stub.MockTransactionEnd("setup-customer")
}

func TestSubmitApplication_Success(t *testing.T) {
	cc := new(LoanChaincode)
	stub := shimtest.NewMockStub("loan", cc)
	setupTestEnvironment(stub)

	// Test successful loan application submission
	args := [][]byte{
		[]byte("SubmitApplication"),
		[]byte("test-customer-1"),    // customerID
		[]byte("50000.00"),          // requestedAmount
		[]byte("Personal"),          // loanType
		[]byte("test-introducer-1"), // introducerID
		[]byte("test-actor-1"),      // actorID
	}

	response := stub.MockInvoke("1", args)
	if response.Status != shim.OK {
		t.Errorf("SubmitApplication failed with status %d and message: %s", response.Status, response.Message)
	}

	// Verify the response contains a valid loan application
	var loanApp LoanApplication
	err := json.Unmarshal(response.Payload, &loanApp)
	if err != nil {
		t.Errorf("Failed to unmarshal loan application: %v", err)
	}

	// Verify loan application fields
	if loanApp.CustomerID != "test-customer-1" {
		t.Errorf("Expected customerID 'test-customer-1', got '%s'", loanApp.CustomerID)
	}
	if loanApp.RequestedAmount != 50000.00 {
		t.Errorf("Expected requestedAmount 50000.00, got %f", loanApp.RequestedAmount)
	}
	if loanApp.LoanType != LoanTypePersonal {
		t.Errorf("Expected loanType 'Personal', got '%s'", loanApp.LoanType)
	}
	if loanApp.ApplicationStatus != StatusSubmitted {
		t.Errorf("Expected status 'Submitted', got '%s'", loanApp.ApplicationStatus)
	}
	if loanApp.Version != 1 {
		t.Errorf("Expected version 1, got %d", loanApp.Version)
	}
}

func TestSubmitApplication_InvalidArguments(t *testing.T) {
	cc := new(LoanChaincode)
	stub := shimtest.NewMockStub("loan", cc)
	setupTestEnvironment(stub)

	// Test with incorrect number of arguments
	args := [][]byte{
		[]byte("SubmitApplication"),
		[]byte("test-customer-1"),
		[]byte("50000.00"),
	}

	response := stub.MockInvoke("1", args)
	if response.Status == shim.OK {
		t.Error("Expected SubmitApplication to fail with incorrect arguments")
	}
}

func TestSubmitApplication_InvalidAmount(t *testing.T) {
	cc := new(LoanChaincode)
	stub := shimtest.NewMockStub("loan", cc)
	setupTestEnvironment(stub)

	// Test with invalid amount
	args := [][]byte{
		[]byte("SubmitApplication"),
		[]byte("test-customer-1"),
		[]byte("-1000.00"), // Negative amount
		[]byte("Personal"),
		[]byte("test-introducer-1"),
		[]byte("test-actor-1"),
	}

	response := stub.MockInvoke("1", args)
	if response.Status == shim.OK {
		t.Error("Expected SubmitApplication to fail with negative amount")
	}
}

func TestSubmitApplication_InvalidLoanType(t *testing.T) {
	cc := new(LoanChaincode)
	stub := shimtest.NewMockStub("loan", cc)
	setupTestEnvironment(stub)

	// Test with invalid loan type
	args := [][]byte{
		[]byte("SubmitApplication"),
		[]byte("test-customer-1"),
		[]byte("50000.00"),
		[]byte("InvalidType"), // Invalid loan type
		[]byte("test-introducer-1"),
		[]byte("test-actor-1"),
	}

	response := stub.MockInvoke("1", args)
	if response.Status == shim.OK {
		t.Error("Expected SubmitApplication to fail with invalid loan type")
	}
}

func TestSubmitApplication_NonExistentCustomer(t *testing.T) {
	cc := new(LoanChaincode)
	stub := shimtest.NewMockStub("loan", cc)
	setupTestEnvironment(stub)

	// Test with non-existent customer
	args := [][]byte{
		[]byte("SubmitApplication"),
		[]byte("non-existent-customer"),
		[]byte("50000.00"),
		[]byte("Personal"),
		[]byte("test-introducer-1"),
		[]byte("test-actor-1"),
	}

	response := stub.MockInvoke("1", args)
	if response.Status == shim.OK {
		t.Error("Expected SubmitApplication to fail with non-existent customer")
	}
}

func TestUpdateStatus_Success(t *testing.T) {
	cc := new(LoanChaincode)
	stub := shimtest.NewMockStub("loan", cc)
	setupTestEnvironment(stub)

	// First, create a loan application
	submitArgs := [][]byte{
		[]byte("SubmitApplication"),
		[]byte("test-customer-1"),
		[]byte("50000.00"),
		[]byte("Personal"),
		[]byte("test-introducer-1"),
		[]byte("test-actor-1"),
	}
	submitResponse := stub.MockInvoke("1", submitArgs)
	if submitResponse.Status != shim.OK {
		t.Fatalf("Failed to create loan application: %s", submitResponse.Message)
	}

	var loanApp LoanApplication
	json.Unmarshal(submitResponse.Payload, &loanApp)

	// Test status update
	updateArgs := [][]byte{
		[]byte("UpdateStatus"),
		[]byte(loanApp.LoanApplicationID),
		[]byte("Underwriting"),
		[]byte("test-underwriter-1"),
	}

	response := stub.MockInvoke("2", updateArgs)
	if response.Status != shim.OK {
		t.Errorf("UpdateStatus failed with status %d and message: %s", response.Status, response.Message)
	}

	// Verify the updated loan application
	var updatedLoanApp LoanApplication
	err := json.Unmarshal(response.Payload, &updatedLoanApp)
	if err != nil {
		t.Errorf("Failed to unmarshal updated loan application: %v", err)
	}

	if updatedLoanApp.ApplicationStatus != StatusUnderwriting {
		t.Errorf("Expected status 'Underwriting', got '%s'", updatedLoanApp.ApplicationStatus)
	}
	if updatedLoanApp.Version != 2 {
		t.Errorf("Expected version 2, got %d", updatedLoanApp.Version)
	}
}

func TestUpdateStatus_InvalidTransition(t *testing.T) {
	cc := new(LoanChaincode)
	stub := shimtest.NewMockStub("loan", cc)
	setupTestEnvironment(stub)

	// First, create a loan application
	submitArgs := [][]byte{
		[]byte("SubmitApplication"),
		[]byte("test-customer-1"),
		[]byte("50000.00"),
		[]byte("Personal"),
		[]byte("test-introducer-1"),
		[]byte("test-actor-1"),
	}
	submitResponse := stub.MockInvoke("1", submitArgs)
	if submitResponse.Status != shim.OK {
		t.Fatalf("Failed to create loan application: %s", submitResponse.Message)
	}

	var loanApp LoanApplication
	json.Unmarshal(submitResponse.Payload, &loanApp)

	// Test invalid status transition (Submitted -> Approved directly)
	updateArgs := [][]byte{
		[]byte("UpdateStatus"),
		[]byte(loanApp.LoanApplicationID),
		[]byte("Approved"), // Invalid transition from Submitted
		[]byte("test-underwriter-1"),
	}

	response := stub.MockInvoke("2", updateArgs)
	if response.Status == shim.OK {
		t.Error("Expected UpdateStatus to fail with invalid transition")
	}
}

func TestApproveLoan_Success(t *testing.T) {
	cc := new(LoanChaincode)
	stub := shimtest.NewMockStub("loan", cc)
	setupTestEnvironment(stub)

	// Create and progress loan application to underwriting
	loanApp := createTestLoanApplication(t, stub, cc)
	progressToUnderwriting(t, stub, cc, loanApp.LoanApplicationID)

	// Test loan approval
	approveArgs := [][]byte{
		[]byte("ApproveLoan"),
		[]byte(loanApp.LoanApplicationID),
		[]byte("45000.00"), // approvedAmount
		[]byte("5.5"),      // interestRate
		[]byte("60"),       // loanTerm (months)
		[]byte("test-credit-officer-1"),
	}

	response := stub.MockInvoke("3", approveArgs)
	if response.Status != shim.OK {
		t.Errorf("ApproveLoan failed with status %d and message: %s", response.Status, response.Message)
	}

	// Verify the approved loan application
	var approvedLoanApp LoanApplication
	err := json.Unmarshal(response.Payload, &approvedLoanApp)
	if err != nil {
		t.Errorf("Failed to unmarshal approved loan application: %v", err)
	}

	if approvedLoanApp.ApplicationStatus != StatusApproved {
		t.Errorf("Expected status 'Approved', got '%s'", approvedLoanApp.ApplicationStatus)
	}
	if approvedLoanApp.ApprovedAmount != 45000.00 {
		t.Errorf("Expected approved amount 45000.00, got %f", approvedLoanApp.ApprovedAmount)
	}
	if approvedLoanApp.InterestRate != 5.5 {
		t.Errorf("Expected interest rate 5.5, got %f", approvedLoanApp.InterestRate)
	}
	if approvedLoanApp.LoanTerm != 60 {
		t.Errorf("Expected loan term 60, got %d", approvedLoanApp.LoanTerm)
	}
	if approvedLoanApp.ApprovedBy != "test-credit-officer-1" {
		t.Errorf("Expected approved by 'test-credit-officer-1', got '%s'", approvedLoanApp.ApprovedBy)
	}
}

func TestApproveLoan_InvalidAmount(t *testing.T) {
	cc := new(LoanChaincode)
	stub := shimtest.NewMockStub("loan", cc)
	setupTestEnvironment(stub)

	loanApp := createTestLoanApplication(t, stub, cc)
	progressToUnderwriting(t, stub, cc, loanApp.LoanApplicationID)

	// Test with invalid approved amount
	approveArgs := [][]byte{
		[]byte("ApproveLoan"),
		[]byte(loanApp.LoanApplicationID),
		[]byte("-1000.00"), // Negative amount
		[]byte("5.5"),
		[]byte("60"),
		[]byte("test-credit-officer-1"),
	}

	response := stub.MockInvoke("3", approveArgs)
	if response.Status == shim.OK {
		t.Error("Expected ApproveLoan to fail with negative amount")
	}
}

func TestRejectLoan_Success(t *testing.T) {
	cc := new(LoanChaincode)
	stub := shimtest.NewMockStub("loan", cc)
	setupTestEnvironment(stub)

	loanApp := createTestLoanApplication(t, stub, cc)
	progressToUnderwriting(t, stub, cc, loanApp.LoanApplicationID)

	// Test loan rejection
	rejectArgs := [][]byte{
		[]byte("RejectLoan"),
		[]byte(loanApp.LoanApplicationID),
		[]byte("Insufficient credit score"),
		[]byte("test-credit-officer-1"),
	}

	response := stub.MockInvoke("3", rejectArgs)
	if response.Status != shim.OK {
		t.Errorf("RejectLoan failed with status %d and message: %s", response.Status, response.Message)
	}

	// Verify the rejected loan application
	var rejectedLoanApp LoanApplication
	err := json.Unmarshal(response.Payload, &rejectedLoanApp)
	if err != nil {
		t.Errorf("Failed to unmarshal rejected loan application: %v", err)
	}

	if rejectedLoanApp.ApplicationStatus != StatusRejected {
		t.Errorf("Expected status 'Rejected', got '%s'", rejectedLoanApp.ApplicationStatus)
	}
	if rejectedLoanApp.RejectionReason != "Insufficient credit score" {
		t.Errorf("Expected rejection reason 'Insufficient credit score', got '%s'", rejectedLoanApp.RejectionReason)
	}
	if rejectedLoanApp.RejectedBy != "test-credit-officer-1" {
		t.Errorf("Expected rejected by 'test-credit-officer-1', got '%s'", rejectedLoanApp.RejectedBy)
	}
}

func TestRejectLoan_EmptyReason(t *testing.T) {
	cc := new(LoanChaincode)
	stub := shimtest.NewMockStub("loan", cc)
	setupTestEnvironment(stub)

	loanApp := createTestLoanApplication(t, stub, cc)

	// Test with empty rejection reason
	rejectArgs := [][]byte{
		[]byte("RejectLoan"),
		[]byte(loanApp.LoanApplicationID),
		[]byte(""), // Empty reason
		[]byte("test-credit-officer-1"),
	}

	response := stub.MockInvoke("2", rejectArgs)
	if response.Status == shim.OK {
		t.Error("Expected RejectLoan to fail with empty rejection reason")
	}
}

func TestGetLoanApplication_Success(t *testing.T) {
	cc := new(LoanChaincode)
	stub := shimtest.NewMockStub("loan", cc)
	setupTestEnvironment(stub)

	loanApp := createTestLoanApplication(t, stub, cc)

	// Test getting loan application
	getArgs := [][]byte{
		[]byte("GetLoanApplication"),
		[]byte(loanApp.LoanApplicationID),
		[]byte("test-actor-1"),
	}

	response := stub.MockInvoke("2", getArgs)
	if response.Status != shim.OK {
		t.Errorf("GetLoanApplication failed with status %d and message: %s", response.Status, response.Message)
	}

	// Verify the retrieved loan application
	var retrievedLoanApp LoanApplication
	err := json.Unmarshal(response.Payload, &retrievedLoanApp)
	if err != nil {
		t.Errorf("Failed to unmarshal retrieved loan application: %v", err)
	}

	if retrievedLoanApp.LoanApplicationID != loanApp.LoanApplicationID {
		t.Errorf("Expected loan ID '%s', got '%s'", loanApp.LoanApplicationID, retrievedLoanApp.LoanApplicationID)
	}
}

func TestGetLoanApplication_NonExistent(t *testing.T) {
	cc := new(LoanChaincode)
	stub := shimtest.NewMockStub("loan", cc)
	setupTestEnvironment(stub)

	// Test getting non-existent loan application
	getArgs := [][]byte{
		[]byte("GetLoanApplication"),
		[]byte("non-existent-loan"),
		[]byte("test-actor-1"),
	}

	response := stub.MockInvoke("1", getArgs)
	if response.Status == shim.OK {
		t.Error("Expected GetLoanApplication to fail with non-existent loan")
	}
}

// Helper functions for tests

func createTestLoanApplication(t *testing.T, stub *shimtest.MockStub, cc *LoanChaincode) LoanApplication {
	args := [][]byte{
		[]byte("SubmitApplication"),
		[]byte("test-customer-1"),
		[]byte("50000.00"),
		[]byte("Personal"),
		[]byte("test-introducer-1"),
		[]byte("test-actor-1"),
	}

	response := stub.MockInvoke("1", args)
	if response.Status != shim.OK {
		t.Fatalf("Failed to create test loan application: %s", response.Message)
	}

	var loanApp LoanApplication
	err := json.Unmarshal(response.Payload, &loanApp)
	if err != nil {
		t.Fatalf("Failed to unmarshal loan application: %v", err)
	}

	return loanApp
}

func progressToUnderwriting(t *testing.T, stub *shimtest.MockStub, cc *LoanChaincode, loanID string) {
	args := [][]byte{
		[]byte("UpdateStatus"),
		[]byte(loanID),
		[]byte("Underwriting"),
		[]byte("test-underwriter-1"),
	}

	response := stub.MockInvoke("2", args)
	if response.Status != shim.OK {
		t.Fatalf("Failed to progress loan to underwriting: %s", response.Message)
	}
}

// Test helper functions

func TestIsValidLoanType(t *testing.T) {
	validTypes := []LoanType{LoanTypePersonal, LoanTypeMortgage, LoanTypeAuto, LoanTypeBusiness, LoanTypeEducation}
	
	for _, loanType := range validTypes {
		if !isValidLoanType(loanType) {
			t.Errorf("Expected %s to be valid loan type", loanType)
		}
	}

	if isValidLoanType("InvalidType") {
		t.Error("Expected 'InvalidType' to be invalid loan type")
	}
}

func TestIsValidStatus(t *testing.T) {
	validStatuses := []LoanApplicationStatus{
		StatusSubmitted, StatusUnderwriting, StatusCreditReview,
		StatusApproved, StatusRejected, StatusDisbursed, StatusCancelled,
	}
	
	for _, status := range validStatuses {
		if !isValidStatus(status) {
			t.Errorf("Expected %s to be valid status", status)
		}
	}

	if isValidStatus("InvalidStatus") {
		t.Error("Expected 'InvalidStatus' to be invalid status")
	}
}

func TestIsValidStatusTransition(t *testing.T) {
	// Test valid transitions
	validTransitions := map[LoanApplicationStatus][]LoanApplicationStatus{
		StatusSubmitted:    {StatusUnderwriting, StatusCancelled},
		StatusUnderwriting: {StatusCreditReview, StatusRejected, StatusCancelled},
		StatusCreditReview: {StatusApproved, StatusRejected, StatusUnderwriting, StatusCancelled},
		StatusApproved:     {StatusDisbursed, StatusCancelled},
	}

	for currentStatus, allowedStatuses := range validTransitions {
		for _, newStatus := range allowedStatuses {
			if !isValidStatusTransition(currentStatus, newStatus) {
				t.Errorf("Expected transition from %s to %s to be valid", currentStatus, newStatus)
			}
		}
	}

	// Test invalid transitions
	if isValidStatusTransition(StatusSubmitted, StatusApproved) {
		t.Error("Expected transition from Submitted to Approved to be invalid")
	}

	if isValidStatusTransition(StatusRejected, StatusApproved) {
		t.Error("Expected transition from Rejected to Approved to be invalid")
	}

	if isValidStatusTransition(StatusDisbursed, StatusRejected) {
		t.Error("Expected transition from Disbursed to Rejected to be invalid")
	}
}

// ============================================================================
// HISTORY TRACKING TESTS
// ============================================================================

func TestGetLoanHistory_Success(t *testing.T) {
	cc := new(LoanChaincode)
	stub := shimtest.NewMockStub("loan", cc)
	setupTestEnvironment(stub)

	// Create a loan application and perform several operations to generate history
	loanApp := createTestLoanApplication(t, stub, cc)
	
	// Progress through multiple status changes
	progressToUnderwriting(t, stub, cc, loanApp.LoanApplicationID)
	
	// Progress to credit review
	updateArgs := [][]byte{
		[]byte("UpdateStatus"),
		[]byte(loanApp.LoanApplicationID),
		[]byte("Credit_Review"),
		[]byte("test-underwriter-1"),
	}
	stub.MockInvoke("3", updateArgs)

	// Approve the loan
	approveArgs := [][]byte{
		[]byte("ApproveLoan"),
		[]byte(loanApp.LoanApplicationID),
		[]byte("45000.00"),
		[]byte("5.5"),
		[]byte("60"),
		[]byte("test-credit-officer-1"),
	}
	stub.MockInvoke("4", approveArgs)

	// Test getting loan history
	historyArgs := [][]byte{
		[]byte("GetLoanHistory"),
		[]byte(loanApp.LoanApplicationID),
		[]byte("test-actor-1"),
	}

	response := stub.MockInvoke("5", historyArgs)
	if response.Status != shim.OK {
		t.Errorf("GetLoanHistory failed with status %d and message: %s", response.Status, response.Message)
	}

	// Parse the history response
	var historyResponse map[string]interface{}
	err := json.Unmarshal(response.Payload, &historyResponse)
	if err != nil {
		t.Errorf("Failed to unmarshal history response: %v", err)
	}

	// Verify response structure
	if historyResponse["loanApplicationID"] != loanApp.LoanApplicationID {
		t.Errorf("Expected loan ID '%s', got '%s'", loanApp.LoanApplicationID, historyResponse["loanApplicationID"])
	}

	// Verify history count (should have multiple entries from all the operations)
	historyCount, ok := historyResponse["historyCount"].(float64)
	if !ok {
		t.Error("History count should be a number")
	}
	if historyCount < 4 { // At least CREATE, UPDATE to Underwriting, UPDATE to Credit_Review, APPROVE
		t.Errorf("Expected at least 4 history entries, got %f", historyCount)
	}

	// Verify current state is included
	currentState, ok := historyResponse["currentState"]
	if !ok {
		t.Error("Current state should be included in history response")
	}
	currentStateMap := currentState.(map[string]interface{})
	if currentStateMap["applicationStatus"] != "Approved" {
		t.Errorf("Expected current status 'Approved', got '%s'", currentStateMap["applicationStatus"])
	}

	// Verify history entries structure
	history, ok := historyResponse["history"].([]interface{})
	if !ok {
		t.Error("History should be an array")
	}
	if len(history) == 0 {
		t.Error("History should not be empty")
	}

	// Verify first history entry (creation)
	firstEntry := history[0].(map[string]interface{})
	if firstEntry["changeType"] != "CREATE" {
		t.Errorf("Expected first entry to be CREATE, got '%s'", firstEntry["changeType"])
	}
	if firstEntry["fieldName"] != "status" {
		t.Errorf("Expected first entry field to be 'status', got '%s'", firstEntry["fieldName"])
	}
	if firstEntry["newValue"] != "Submitted" {
		t.Errorf("Expected first entry new value to be 'Submitted', got '%s'", firstEntry["newValue"])
	}
}

func TestGetLoanHistory_NonExistentLoan(t *testing.T) {
	cc := new(LoanChaincode)
	stub := shimtest.NewMockStub("loan", cc)
	setupTestEnvironment(stub)

	// Test getting history for non-existent loan
	historyArgs := [][]byte{
		[]byte("GetLoanHistory"),
		[]byte("non-existent-loan"),
		[]byte("test-actor-1"),
	}

	response := stub.MockInvoke("1", historyArgs)
	if response.Status == shim.OK {
		t.Error("Expected GetLoanHistory to fail with non-existent loan")
	}
}

func TestGetLoanHistory_AccessControl(t *testing.T) {
	cc := new(LoanChaincode)
	stub := shimtest.NewMockStub("loan", cc)
	setupTestEnvironment(stub)

	loanApp := createTestLoanApplication(t, stub, cc)

	// Test with actor that doesn't have view permissions
	unauthorizedActor := shared.Actor{
		ActorID:           "unauthorized-actor",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Unauthorized User",
		Role:              shared.RoleCustomerService,
		BlockchainIdentity: "unauthorized-cert",
		Permissions:       []shared.Permission{}, // No permissions
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}
	actorJSON, _ := json.Marshal(unauthorizedActor)
	stub.MockTransactionStart("setup-unauthorized")
	stub.PutState("ACTOR_unauthorized-actor", actorJSON)
	stub.MockTransactionEnd("setup-unauthorized")

	historyArgs := [][]byte{
		[]byte("GetLoanHistory"),
		[]byte(loanApp.LoanApplicationID),
		[]byte("unauthorized-actor"),
	}

	response := stub.MockInvoke("2", historyArgs)
	if response.Status == shim.OK {
		t.Error("Expected GetLoanHistory to fail with unauthorized actor")
	}
}

func TestRecordLoanHistoryEntry_Success(t *testing.T) {
	cc := new(LoanChaincode)
	stub := shimtest.NewMockStub("loan", cc)
	setupTestEnvironment(stub)

	// Test recording a history entry within a transaction
	loanID := "test-loan-123"
	
	stub.MockTransactionStart("test-history")
	err := cc.recordLoanHistoryEntry(stub, loanID, "TEST", "testField", "oldValue", "newValue", "test-actor-1", 1, "Test context")
	stub.MockTransactionEnd("test-history")
	
	if err != nil {
		t.Errorf("Failed to record loan history entry: %v", err)
	}

	// Verify the history entry was stored
	historyEntries, err := shared.GetEntityHistory(stub, loanID)
	if err != nil {
		t.Errorf("Failed to retrieve history entries: %v", err)
	}

	if len(historyEntries) == 0 {
		t.Error("Expected at least one history entry")
		return
	}

	// Verify the entry details
	entry := historyEntries[0]
	if entry.EntityID != loanID {
		t.Errorf("Expected entity ID '%s', got '%s'", loanID, entry.EntityID)
	}
	if entry.ChangeType != "TEST" {
		t.Errorf("Expected change type 'TEST', got '%s'", entry.ChangeType)
	}
	if entry.FieldName != "testField" {
		t.Errorf("Expected field name 'testField', got '%s'", entry.FieldName)
	}
	if entry.PreviousValue != "oldValue" {
		t.Errorf("Expected previous value 'oldValue', got '%s'", entry.PreviousValue)
	}
	if entry.NewValue != "newValue" {
		t.Errorf("Expected new value 'newValue', got '%s'", entry.NewValue)
	}
	if entry.ActorID != "test-actor-1" {
		t.Errorf("Expected actor ID 'test-actor-1', got '%s'", entry.ActorID)
	}
}

func TestValidateHistoryEntry_Success(t *testing.T) {
	// Test valid history entry
	entry := shared.HistoryEntry{
		HistoryID:     "HIST_123",
		EntityID:      "test-loan-123",
		EntityType:    "LoanApplication",
		Timestamp:     time.Now(),
		ChangeType:    "CREATE",
		FieldName:     "status",
		PreviousValue: "",
		NewValue:      "Submitted",
		ActorID:       "test-actor-1",
		TransactionID: "tx-123",
	}

	err := validateHistoryEntry(entry, "test-loan-123")
	if err != nil {
		t.Errorf("Expected valid history entry to pass validation, got error: %v", err)
	}
}

func TestValidateHistoryEntry_InvalidEntityID(t *testing.T) {
	entry := shared.HistoryEntry{
		HistoryID:     "HIST_123",
		EntityID:      "wrong-loan-id",
		EntityType:    "LoanApplication",
		Timestamp:     time.Now(),
		ChangeType:    "CREATE",
		FieldName:     "status",
		PreviousValue: "",
		NewValue:      "Submitted",
		ActorID:       "test-actor-1",
		TransactionID: "tx-123",
	}

	err := validateHistoryEntry(entry, "test-loan-123")
	if err == nil {
		t.Error("Expected validation to fail with mismatched entity ID")
	}
}

func TestValidateHistoryEntry_InvalidEntityType(t *testing.T) {
	entry := shared.HistoryEntry{
		HistoryID:     "HIST_123",
		EntityID:      "test-loan-123",
		EntityType:    "Customer", // Wrong entity type
		Timestamp:     time.Now(),
		ChangeType:    "CREATE",
		FieldName:     "status",
		PreviousValue: "",
		NewValue:      "Submitted",
		ActorID:       "test-actor-1",
		TransactionID: "tx-123",
	}

	err := validateHistoryEntry(entry, "test-loan-123")
	if err == nil {
		t.Error("Expected validation to fail with wrong entity type")
	}
}

func TestValidateHistoryEntry_MissingRequiredFields(t *testing.T) {
	// Test missing HistoryID
	entry := shared.HistoryEntry{
		HistoryID:     "", // Missing
		EntityID:      "test-loan-123",
		EntityType:    "LoanApplication",
		Timestamp:     time.Now(),
		ChangeType:    "CREATE",
		FieldName:     "status",
		PreviousValue: "",
		NewValue:      "Submitted",
		ActorID:       "test-actor-1",
		TransactionID: "tx-123",
	}

	err := validateHistoryEntry(entry, "test-loan-123")
	if err == nil {
		t.Error("Expected validation to fail with missing HistoryID")
	}

	// Test missing ActorID
	entry.HistoryID = "HIST_123"
	entry.ActorID = "" // Missing
	err = validateHistoryEntry(entry, "test-loan-123")
	if err == nil {
		t.Error("Expected validation to fail with missing ActorID")
	}

	// Test missing TransactionID
	entry.ActorID = "test-actor-1"
	entry.TransactionID = "" // Missing
	err = validateHistoryEntry(entry, "test-loan-123")
	if err == nil {
		t.Error("Expected validation to fail with missing TransactionID")
	}
}

func TestValidateHistoryEntry_InvalidChangeType(t *testing.T) {
	entry := shared.HistoryEntry{
		HistoryID:     "HIST_123",
		EntityID:      "test-loan-123",
		EntityType:    "LoanApplication",
		Timestamp:     time.Now(),
		ChangeType:    "INVALID_TYPE", // Invalid change type
		FieldName:     "status",
		PreviousValue: "",
		NewValue:      "Submitted",
		ActorID:       "test-actor-1",
		TransactionID: "tx-123",
	}

	err := validateHistoryEntry(entry, "test-loan-123")
	if err == nil {
		t.Error("Expected validation to fail with invalid change type")
	}
}

func TestGenerateAdditionalContext(t *testing.T) {
	// Test CREATE context
	createEntry := shared.HistoryEntry{
		ChangeType: "CREATE",
		FieldName:  "status",
	}
	context := generateAdditionalContext(createEntry)
	if context != "Initial loan application submission" {
		t.Errorf("Expected CREATE context, got '%s'", context)
	}

	// Test UPDATE context
	updateEntry := shared.HistoryEntry{
		ChangeType:    "UPDATE",
		FieldName:     "status",
		PreviousValue: "Submitted",
		NewValue:      "Underwriting",
	}
	context = generateAdditionalContext(updateEntry)
	expected := "Status transition from Submitted to Underwriting"
	if context != expected {
		t.Errorf("Expected '%s', got '%s'", expected, context)
	}

	// Test APPROVE context
	approveEntry := shared.HistoryEntry{
		ChangeType: "APPROVE",
	}
	context = generateAdditionalContext(approveEntry)
	if context != "Loan application approved with terms" {
		t.Errorf("Expected APPROVE context, got '%s'", context)
	}

	// Test REJECT context
	rejectEntry := shared.HistoryEntry{
		ChangeType: "REJECT",
	}
	context = generateAdditionalContext(rejectEntry)
	if context != "Loan application rejected" {
		t.Errorf("Expected REJECT context, got '%s'", context)
	}
}

func TestSortHistoryByTimestamp(t *testing.T) {
	now := time.Now()
	
	// Create history entries with different timestamps
	history := []LoanApplicationHistory{
		{
			HistoryID: "HIST_3",
			Timestamp: now.Add(2 * time.Hour), // Latest
		},
		{
			HistoryID: "HIST_1",
			Timestamp: now, // Earliest
		},
		{
			HistoryID: "HIST_2",
			Timestamp: now.Add(1 * time.Hour), // Middle
		},
	}

	// Sort the history
	sortHistoryByTimestamp(history)

	// Verify chronological order (oldest first)
	if history[0].HistoryID != "HIST_1" {
		t.Errorf("Expected first entry to be HIST_1, got %s", history[0].HistoryID)
	}
	if history[1].HistoryID != "HIST_2" {
		t.Errorf("Expected second entry to be HIST_2, got %s", history[1].HistoryID)
	}
	if history[2].HistoryID != "HIST_3" {
		t.Errorf("Expected third entry to be HIST_3, got %s", history[2].HistoryID)
	}
}

func TestHistoryIntegrityThroughWorkflow(t *testing.T) {
	cc := new(LoanChaincode)
	stub := shimtest.NewMockStub("loan", cc)
	setupTestEnvironment(stub)

	// Create loan application
	loanApp := createTestLoanApplication(t, stub, cc)

	// Progress through complete workflow
	progressToUnderwriting(t, stub, cc, loanApp.LoanApplicationID)
	
	// Progress to credit review
	updateArgs := [][]byte{
		[]byte("UpdateStatus"),
		[]byte(loanApp.LoanApplicationID),
		[]byte("Credit_Review"),
		[]byte("test-underwriter-1"),
	}
	stub.MockInvoke("3", updateArgs)

	// Approve the loan
	approveArgs := [][]byte{
		[]byte("ApproveLoan"),
		[]byte(loanApp.LoanApplicationID),
		[]byte("45000.00"),
		[]byte("5.5"),
		[]byte("60"),
		[]byte("test-credit-officer-1"),
	}
	stub.MockInvoke("4", approveArgs)

	// Get complete history
	historyArgs := [][]byte{
		[]byte("GetLoanHistory"),
		[]byte(loanApp.LoanApplicationID),
		[]byte("test-actor-1"),
	}
	response := stub.MockInvoke("5", historyArgs)

	if response.Status != shim.OK {
		t.Fatalf("Failed to get loan history: %s", response.Message)
	}

	var historyResponse map[string]interface{}
	json.Unmarshal(response.Payload, &historyResponse)

	history := historyResponse["history"].([]interface{})
	
	// Verify complete audit trail
	expectedChangeTypes := []string{"CREATE", "UPDATE", "UPDATE", "APPROVE"}
	if len(history) < len(expectedChangeTypes) {
		t.Errorf("Expected at least %d history entries, got %d", len(expectedChangeTypes), len(history))
	}

	// Verify chronological order and change types
	for i, expectedType := range expectedChangeTypes {
		if i >= len(history) {
			break
		}
		entry := history[i].(map[string]interface{})
		if entry["changeType"] != expectedType {
			t.Errorf("Expected change type '%s' at position %d, got '%s'", expectedType, i, entry["changeType"])
		}
	}

	// Verify all entries have required fields
	for i, historyEntry := range history {
		entry := historyEntry.(map[string]interface{})
		requiredFields := []string{"historyID", "loanApplicationID", "timestamp", "changeType", "actorID", "transactionID"}
		for _, field := range requiredFields {
			if _, exists := entry[field]; !exists {
				t.Errorf("History entry %d missing required field '%s'", i, field)
			}
		}
	}
}