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