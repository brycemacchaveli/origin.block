package main

import (
	"encoding/json"
	"fmt"
	"log"
	"strconv"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/hyperledger/fabric-protos-go/peer"
	"github.com/blockchain-financial-platform/fabric-chaincode/shared"
)

// LoanApplicationStatus represents the status of a loan application
type LoanApplicationStatus string

const (
	StatusSubmitted    LoanApplicationStatus = "Submitted"
	StatusUnderwriting LoanApplicationStatus = "Underwriting"
	StatusCreditReview LoanApplicationStatus = "Credit_Review"
	StatusApproved     LoanApplicationStatus = "Approved"
	StatusRejected     LoanApplicationStatus = "Rejected"
	StatusDisbursed    LoanApplicationStatus = "Disbursed"
	StatusCancelled    LoanApplicationStatus = "Cancelled"
)

// LoanType represents the type of loan
type LoanType string

const (
	LoanTypePersonal  LoanType = "Personal"
	LoanTypeMortgage  LoanType = "Mortgage"
	LoanTypeAuto      LoanType = "Auto"
	LoanTypeBusiness  LoanType = "Business"
	LoanTypeEducation LoanType = "Education"
)

// LoanApplication represents a loan application on the blockchain
type LoanApplication struct {
	LoanApplicationID   string                `json:"loanApplicationID"`
	CustomerID          string                `json:"customerID"`
	ApplicationDate     time.Time             `json:"applicationDate"`
	RequestedAmount     float64               `json:"requestedAmount"`
	LoanType           LoanType              `json:"loanType"`
	ApplicationStatus   LoanApplicationStatus `json:"applicationStatus"`
	IntroducerID       string                `json:"introducerID"`
	CurrentOwnerActor   string                `json:"currentOwnerActor"`
	LastUpdated        time.Time             `json:"lastUpdated"`
	ApprovedAmount     float64               `json:"approvedAmount,omitempty"`
	InterestRate       float64               `json:"interestRate,omitempty"`
	LoanTerm           int                   `json:"loanTerm,omitempty"` // in months
	ApprovedBy         string                `json:"approvedBy,omitempty"`
	RejectedBy         string                `json:"rejectedBy,omitempty"`
	RejectionReason    string                `json:"rejectionReason,omitempty"`
	CreatedBy          string                `json:"createdBy"`
	Version            int                   `json:"version"`
}

// LoanChaincode implements the fabric Contract interface
type LoanChaincode struct {
}

// Init is called during chaincode instantiation to initialize any data
func (t *LoanChaincode) Init(stub shim.ChaincodeStubInterface) peer.Response {
	return shim.Success(nil)
}

// Invoke is called per transaction on the chaincode
func (t *LoanChaincode) Invoke(stub shim.ChaincodeStubInterface) peer.Response {
	function, args := stub.GetFunctionAndParameters()
	
	switch function {
	case "ping":
		return shim.Success([]byte("pong"))
	case "SubmitApplication":
		return t.SubmitApplication(stub, args)
	case "UpdateStatus":
		return t.UpdateStatus(stub, args)
	case "ApproveLoan":
		return t.ApproveLoan(stub, args)
	case "RejectLoan":
		return t.RejectLoan(stub, args)
	case "GetLoanApplication":
		return t.GetLoanApplication(stub, args)
	default:
		return shim.Error("Invalid function name: " + function)
	}
}

// SubmitApplication creates a new loan application
func (t *LoanChaincode) SubmitApplication(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	// Expected args: [customerID, requestedAmount, loanType, introducerID, actorID]
	if len(args) != 5 {
		return shim.Error("Incorrect number of arguments. Expecting 5: customerID, requestedAmount, loanType, introducerID, actorID")
	}

	customerID := args[0]
	requestedAmountStr := args[1]
	loanTypeStr := args[2]
	introducerID := args[3]
	actorID := args[4]

	// Validate actor permissions
	_, err := shared.ValidateActorAccess(stub, actorID, shared.PermissionCreateLoan)
	if err != nil {
		return shim.Error(fmt.Sprintf("Access denied: %v", err))
	}

	// Validate and parse requested amount
	requestedAmount, err := strconv.ParseFloat(requestedAmountStr, 64)
	if err != nil {
		return shim.Error(fmt.Sprintf("Invalid requested amount: %v", err))
	}

	// Validate amount
	if err := shared.ValidateAmount(requestedAmount); err != nil {
		return shim.Error(fmt.Sprintf("Invalid amount: %v", err))
	}

	// Validate loan type
	loanType := LoanType(loanTypeStr)
	if !isValidLoanType(loanType) {
		return shim.Error(fmt.Sprintf("Invalid loan type: %s", loanTypeStr))
	}

	// Validate required fields
	requiredFields := map[string]string{
		"customerID":    customerID,
		"introducerID":  introducerID,
		"actorID":       actorID,
	}
	if err := shared.ValidateRequired(requiredFields); err != nil {
		return shim.Error(fmt.Sprintf("Validation failed: %v", err))
	}

	// Verify customer exists (basic check)
	customerKey := "CUSTOMER_" + customerID
	customerData, err := stub.GetState(customerKey)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to check customer existence: %v", err))
	}
	if customerData == nil {
		return shim.Error(fmt.Sprintf("Customer %s does not exist", customerID))
	}

	// Generate unique loan application ID
	loanApplicationID := shared.GenerateID("LOAN")

	// Create loan application
	loanApplication := LoanApplication{
		LoanApplicationID: loanApplicationID,
		CustomerID:        customerID,
		ApplicationDate:   time.Now(),
		RequestedAmount:   requestedAmount,
		LoanType:         loanType,
		ApplicationStatus: StatusSubmitted,
		IntroducerID:     introducerID,
		CurrentOwnerActor: actorID,
		LastUpdated:      time.Now(),
		CreatedBy:        actorID,
		Version:          1,
	}

	// Store loan application
	loanKey := "LOAN_" + loanApplicationID
	err = shared.PutStateAsJSON(stub, loanKey, loanApplication)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to store loan application: %v", err))
	}

	// Record history entry
	err = shared.RecordHistoryEntry(stub, loanApplicationID, "LoanApplication", "CREATE", "status", "", string(StatusSubmitted), actorID)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to record history: %v", err))
	}

	// Emit event
	eventPayload := map[string]interface{}{
		"loanApplicationID": loanApplicationID,
		"customerID":        customerID,
		"status":           StatusSubmitted,
		"requestedAmount":   requestedAmount,
		"actorID":          actorID,
	}
	err = shared.EmitEvent(stub, "LoanApplicationSubmitted", eventPayload)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to emit event: %v", err))
	}

	// Return the loan application
	loanJSON, err := json.Marshal(loanApplication)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to marshal loan application: %v", err))
	}

	return shim.Success(loanJSON)
}

// UpdateStatus updates the status of a loan application
func (t *LoanChaincode) UpdateStatus(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	// Expected args: [loanApplicationID, newStatus, actorID]
	if len(args) != 3 {
		return shim.Error("Incorrect number of arguments. Expecting 3: loanApplicationID, newStatus, actorID")
	}

	loanApplicationID := args[0]
	newStatusStr := args[1]
	actorID := args[2]

	// Validate actor permissions
	_, err := shared.ValidateActorAccess(stub, actorID, shared.PermissionUpdateLoan)
	if err != nil {
		return shim.Error(fmt.Sprintf("Access denied: %v", err))
	}

	// Validate new status
	newStatus := LoanApplicationStatus(newStatusStr)
	if !isValidStatus(newStatus) {
		return shim.Error(fmt.Sprintf("Invalid status: %s", newStatusStr))
	}

	// Get existing loan application
	loanKey := "LOAN_" + loanApplicationID
	var loanApplication LoanApplication
	err = shared.GetStateAsJSON(stub, loanKey, &loanApplication)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get loan application: %v", err))
	}

	// Validate status transition
	if !isValidStatusTransition(loanApplication.ApplicationStatus, newStatus) {
		return shim.Error(fmt.Sprintf("Invalid status transition from %s to %s", loanApplication.ApplicationStatus, newStatus))
	}

	// Store previous status for history
	previousStatus := loanApplication.ApplicationStatus

	// Update loan application
	loanApplication.ApplicationStatus = newStatus
	loanApplication.CurrentOwnerActor = actorID
	loanApplication.LastUpdated = time.Now()
	loanApplication.Version++

	// Store updated loan application
	err = shared.PutStateAsJSON(stub, loanKey, loanApplication)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to update loan application: %v", err))
	}

	// Record history entry
	err = shared.RecordHistoryEntry(stub, loanApplicationID, "LoanApplication", "UPDATE", "status", string(previousStatus), string(newStatus), actorID)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to record history: %v", err))
	}

	// Emit event
	eventPayload := map[string]interface{}{
		"loanApplicationID": loanApplicationID,
		"previousStatus":    previousStatus,
		"newStatus":        newStatus,
		"actorID":          actorID,
	}
	err = shared.EmitEvent(stub, "LoanApplicationStatusUpdated", eventPayload)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to emit event: %v", err))
	}

	// Return the updated loan application
	loanJSON, err := json.Marshal(loanApplication)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to marshal loan application: %v", err))
	}

	return shim.Success(loanJSON)
}

// ApproveLoan approves a loan application with specific terms
func (t *LoanChaincode) ApproveLoan(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	// Expected args: [loanApplicationID, approvedAmount, interestRate, loanTerm, actorID]
	if len(args) != 5 {
		return shim.Error("Incorrect number of arguments. Expecting 5: loanApplicationID, approvedAmount, interestRate, loanTerm, actorID")
	}

	loanApplicationID := args[0]
	approvedAmountStr := args[1]
	interestRateStr := args[2]
	loanTermStr := args[3]
	actorID := args[4]

	// Validate actor permissions
	_, err := shared.ValidateActorAccess(stub, actorID, shared.PermissionApproveLoan)
	if err != nil {
		return shim.Error(fmt.Sprintf("Access denied: %v", err))
	}

	// Parse and validate approved amount
	approvedAmount, err := strconv.ParseFloat(approvedAmountStr, 64)
	if err != nil {
		return shim.Error(fmt.Sprintf("Invalid approved amount: %v", err))
	}
	if err := shared.ValidateAmount(approvedAmount); err != nil {
		return shim.Error(fmt.Sprintf("Invalid approved amount: %v", err))
	}

	// Parse and validate interest rate
	interestRate, err := strconv.ParseFloat(interestRateStr, 64)
	if err != nil {
		return shim.Error(fmt.Sprintf("Invalid interest rate: %v", err))
	}
	if interestRate < 0 || interestRate > 100 {
		return shim.Error("Interest rate must be between 0 and 100")
	}

	// Parse and validate loan term
	loanTerm, err := strconv.Atoi(loanTermStr)
	if err != nil {
		return shim.Error(fmt.Sprintf("Invalid loan term: %v", err))
	}
	if loanTerm <= 0 || loanTerm > 360 { // Max 30 years
		return shim.Error("Loan term must be between 1 and 360 months")
	}

	// Get existing loan application
	loanKey := "LOAN_" + loanApplicationID
	var loanApplication LoanApplication
	err = shared.GetStateAsJSON(stub, loanKey, &loanApplication)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get loan application: %v", err))
	}

	// Validate that loan can be approved (must be in underwriting or credit review)
	if loanApplication.ApplicationStatus != StatusUnderwriting && loanApplication.ApplicationStatus != StatusCreditReview {
		return shim.Error(fmt.Sprintf("Cannot approve loan in status %s", loanApplication.ApplicationStatus))
	}

	// Store previous status for history
	previousStatus := loanApplication.ApplicationStatus

	// Update loan application with approval details
	loanApplication.ApplicationStatus = StatusApproved
	loanApplication.ApprovedAmount = approvedAmount
	loanApplication.InterestRate = interestRate
	loanApplication.LoanTerm = loanTerm
	loanApplication.ApprovedBy = actorID
	loanApplication.CurrentOwnerActor = actorID
	loanApplication.LastUpdated = time.Now()
	loanApplication.Version++

	// Store updated loan application
	err = shared.PutStateAsJSON(stub, loanKey, loanApplication)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to update loan application: %v", err))
	}

	// Record history entries for all changes
	err = shared.RecordHistoryEntry(stub, loanApplicationID, "LoanApplication", "APPROVE", "status", string(previousStatus), string(StatusApproved), actorID)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to record status history: %v", err))
	}

	err = shared.RecordHistoryEntry(stub, loanApplicationID, "LoanApplication", "APPROVE", "approvedAmount", "0", approvedAmountStr, actorID)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to record amount history: %v", err))
	}

	err = shared.RecordHistoryEntry(stub, loanApplicationID, "LoanApplication", "APPROVE", "interestRate", "0", interestRateStr, actorID)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to record rate history: %v", err))
	}

	// Emit event
	eventPayload := map[string]interface{}{
		"loanApplicationID": loanApplicationID,
		"previousStatus":    previousStatus,
		"approvedAmount":    approvedAmount,
		"interestRate":      interestRate,
		"loanTerm":         loanTerm,
		"approvedBy":       actorID,
	}
	err = shared.EmitEvent(stub, "LoanApplicationApproved", eventPayload)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to emit event: %v", err))
	}

	// Return the updated loan application
	loanJSON, err := json.Marshal(loanApplication)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to marshal loan application: %v", err))
	}

	return shim.Success(loanJSON)
}

// RejectLoan rejects a loan application with a reason
func (t *LoanChaincode) RejectLoan(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	// Expected args: [loanApplicationID, rejectionReason, actorID]
	if len(args) != 3 {
		return shim.Error("Incorrect number of arguments. Expecting 3: loanApplicationID, rejectionReason, actorID")
	}

	loanApplicationID := args[0]
	rejectionReason := args[1]
	actorID := args[2]

	// Validate actor permissions
	_, err := shared.ValidateActorAccess(stub, actorID, shared.PermissionApproveLoan)
	if err != nil {
		return shim.Error(fmt.Sprintf("Access denied: %v", err))
	}

	// Validate rejection reason
	if len(rejectionReason) == 0 {
		return shim.Error("Rejection reason is required")
	}
	if len(rejectionReason) > 500 {
		return shim.Error("Rejection reason must be less than 500 characters")
	}

	// Get existing loan application
	loanKey := "LOAN_" + loanApplicationID
	var loanApplication LoanApplication
	err = shared.GetStateAsJSON(stub, loanKey, &loanApplication)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get loan application: %v", err))
	}

	// Validate that loan can be rejected (cannot reject already approved or disbursed loans)
	if loanApplication.ApplicationStatus == StatusApproved || loanApplication.ApplicationStatus == StatusDisbursed {
		return shim.Error(fmt.Sprintf("Cannot reject loan in status %s", loanApplication.ApplicationStatus))
	}

	if loanApplication.ApplicationStatus == StatusRejected {
		return shim.Error("Loan application is already rejected")
	}

	// Store previous status for history
	previousStatus := loanApplication.ApplicationStatus

	// Update loan application with rejection details
	loanApplication.ApplicationStatus = StatusRejected
	loanApplication.RejectedBy = actorID
	loanApplication.RejectionReason = rejectionReason
	loanApplication.CurrentOwnerActor = actorID
	loanApplication.LastUpdated = time.Now()
	loanApplication.Version++

	// Store updated loan application
	err = shared.PutStateAsJSON(stub, loanKey, loanApplication)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to update loan application: %v", err))
	}

	// Record history entries
	err = shared.RecordHistoryEntry(stub, loanApplicationID, "LoanApplication", "REJECT", "status", string(previousStatus), string(StatusRejected), actorID)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to record status history: %v", err))
	}

	err = shared.RecordHistoryEntry(stub, loanApplicationID, "LoanApplication", "REJECT", "rejectionReason", "", rejectionReason, actorID)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to record reason history: %v", err))
	}

	// Emit event
	eventPayload := map[string]interface{}{
		"loanApplicationID": loanApplicationID,
		"previousStatus":    previousStatus,
		"rejectionReason":   rejectionReason,
		"rejectedBy":       actorID,
	}
	err = shared.EmitEvent(stub, "LoanApplicationRejected", eventPayload)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to emit event: %v", err))
	}

	// Return the updated loan application
	loanJSON, err := json.Marshal(loanApplication)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to marshal loan application: %v", err))
	}

	return shim.Success(loanJSON)
}

// GetLoanApplication retrieves a loan application by ID
func (t *LoanChaincode) GetLoanApplication(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	// Expected args: [loanApplicationID, actorID]
	if len(args) != 2 {
		return shim.Error("Incorrect number of arguments. Expecting 2: loanApplicationID, actorID")
	}

	loanApplicationID := args[0]
	actorID := args[1]

	// Validate actor permissions
	_, err := shared.ValidateActorAccess(stub, actorID, shared.PermissionViewLoan)
	if err != nil {
		return shim.Error(fmt.Sprintf("Access denied: %v", err))
	}

	// Get loan application
	loanKey := "LOAN_" + loanApplicationID
	var loanApplication LoanApplication
	err = shared.GetStateAsJSON(stub, loanKey, &loanApplication)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get loan application: %v", err))
	}

	// Return the loan application
	loanJSON, err := json.Marshal(loanApplication)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to marshal loan application: %v", err))
	}

	return shim.Success(loanJSON)
}

// Helper functions

// isValidLoanType checks if the loan type is valid
func isValidLoanType(loanType LoanType) bool {
	validTypes := []LoanType{LoanTypePersonal, LoanTypeMortgage, LoanTypeAuto, LoanTypeBusiness, LoanTypeEducation}
	for _, validType := range validTypes {
		if loanType == validType {
			return true
		}
	}
	return false
}

// isValidStatus checks if the status is valid
func isValidStatus(status LoanApplicationStatus) bool {
	validStatuses := []LoanApplicationStatus{
		StatusSubmitted, StatusUnderwriting, StatusCreditReview,
		StatusApproved, StatusRejected, StatusDisbursed, StatusCancelled,
	}
	for _, validStatus := range validStatuses {
		if status == validStatus {
			return true
		}
	}
	return false
}

// isValidStatusTransition checks if a status transition is valid
func isValidStatusTransition(currentStatus, newStatus LoanApplicationStatus) bool {
	// Define valid transitions
	validTransitions := map[LoanApplicationStatus][]LoanApplicationStatus{
		StatusSubmitted: {StatusUnderwriting, StatusCancelled},
		StatusUnderwriting: {StatusCreditReview, StatusRejected, StatusCancelled},
		StatusCreditReview: {StatusApproved, StatusRejected, StatusUnderwriting, StatusCancelled},
		StatusApproved: {StatusDisbursed, StatusCancelled},
		StatusRejected: {}, // Terminal state
		StatusDisbursed: {}, // Terminal state
		StatusCancelled: {}, // Terminal state
	}

	allowedTransitions, exists := validTransitions[currentStatus]
	if !exists {
		return false
	}

	for _, allowedStatus := range allowedTransitions {
		if newStatus == allowedStatus {
			return true
		}
	}
	return false
}

func main() {
	if err := shim.Start(new(LoanChaincode)); err != nil {
		log.Fatalf("Error starting Loan chaincode: %v", err)
	}
}