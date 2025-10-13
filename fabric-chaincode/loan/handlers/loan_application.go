package handlers

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/blockchain-financial-platform/fabric-chaincode/loan/domain"
	loanServices "github.com/blockchain-financial-platform/fabric-chaincode/loan/services"
	"github.com/blockchain-financial-platform/fabric-chaincode/shared/config"
	"github.com/blockchain-financial-platform/fabric-chaincode/shared/services"
	"github.com/blockchain-financial-platform/fabric-chaincode/shared/utils"
	"github.com/blockchain-financial-platform/fabric-chaincode/shared/validation"
)

// LoanApplicationHandler handles loan application operations
type LoanApplicationHandler struct {
	persistenceService *services.PersistenceService
	eventService      *loanServices.EventService
}

// NewLoanApplicationHandler creates a new loan application handler
func NewLoanApplicationHandler() *LoanApplicationHandler {
	return &LoanApplicationHandler{
		persistenceService: services.NewPersistenceService(),
		eventService:      loanServices.NewEventService(),
	}
}

// SubmitLoanApplication submits a new loan application
func (h *LoanApplicationHandler) SubmitLoanApplication(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	var req domain.LoanApplicationRequest
	if err := json.Unmarshal([]byte(args[0]), &req); err != nil {
		return nil, fmt.Errorf("failed to parse loan application request: %v", err)
	}

	// Validate loan type
	if err := validation.ValidateLoanType(req.LoanType); err != nil {
		return nil, fmt.Errorf("invalid loan type: %v", err)
	}

	// Validate loan amount
	if err := validation.ValidateLoanAmount(req.RequestedAmount, req.LoanType); err != nil {
		return nil, fmt.Errorf("invalid loan amount: %v", err)
	}

	// Generate loan ID
	loanID := utils.GenerateID(config.LoanApplicationPrefix)

	// Create loan application
	loanApp := &domain.LoanApplication{
		LoanID:          loanID,
		CustomerID:      req.CustomerID,
		LoanType:        req.LoanType,
		RequestedAmount: req.RequestedAmount,
		TermMonths:      req.TermMonths,
		Purpose:         req.Purpose,
		Status:          validation.LoanStatusSubmitted,
		ApplicationDate: time.Now(),
		Notes:           "",
		CreatedDate:     time.Now(),
		LastUpdated:     time.Now(),
		CreatedBy:       req.ActorID,
		LastUpdatedBy:   req.ActorID,
	}

	// Store the loan application
	loanKey := fmt.Sprintf("LOAN_%s", loanID)
	if err := h.persistenceService.Put(stub, loanKey, loanApp); err != nil {
		return nil, fmt.Errorf("failed to store loan application: %v", err)
	}

	// Create index by customer ID
	customerLoanKey := fmt.Sprintf("CUSTOMER_LOAN_%s_%s", req.CustomerID, loanID)
	if err := stub.PutState(customerLoanKey, []byte(loanID)); err != nil {
		return nil, fmt.Errorf("failed to create customer loan index: %v", err)
	}

	// Record history
	loanJSON, _ := utils.MarshalJSONString(loanApp)
	if err := h.recordLoanHistory(stub, loanID, "CREATE", "loan_application", "", loanJSON, req.ActorID); err != nil {
		return nil, fmt.Errorf("failed to record history: %v", err)
	}

	// Emit event
	if err := h.eventService.EmitLoanSubmitted(stub, loanApp, req.ActorID); err != nil {
		return nil, fmt.Errorf("failed to emit event: %v", err)
	}

	return json.Marshal(loanApp)
}

// UpdateLoanStatus updates the status of a loan application
func (h *LoanApplicationHandler) UpdateLoanStatus(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	var req domain.LoanStatusUpdateRequest
	if err := json.Unmarshal([]byte(args[0]), &req); err != nil {
		return nil, fmt.Errorf("failed to parse status update request: %v", err)
	}

	// Get existing loan application
	loanKey := fmt.Sprintf("LOAN_%s", req.LoanID)
	var loanApp domain.LoanApplication
	if err := h.persistenceService.Get(stub, loanKey, &loanApp); err != nil {
		return nil, fmt.Errorf("loan application not found: %v", err)
	}

	// Validate status transition
	if err := validation.ValidateStatusTransition(string(loanApp.Status), string(req.NewStatus), "LoanApplication"); err != nil {
		return nil, fmt.Errorf("invalid status transition: %v", err)
	}

	// Record history
	if err := h.recordLoanHistory(stub, req.LoanID, "STATUS_UPDATE", "status", string(loanApp.Status), string(req.NewStatus), req.ActorID); err != nil {
		return nil, err
	}

	// Update loan application
	loanApp.Status = req.NewStatus
	loanApp.Notes = req.Notes
	loanApp.LastUpdated = time.Now()
	loanApp.LastUpdatedBy = req.ActorID

	// Store updated loan application
	if err := h.persistenceService.Put(stub, loanKey, &loanApp); err != nil {
		return nil, fmt.Errorf("failed to update loan application: %v", err)
	}

	// Emit appropriate event based on status
	switch req.NewStatus {
	case validation.LoanStatusApproved:
		if err := h.eventService.EmitLoanApproved(stub, &loanApp, req.ActorID); err != nil {
			return nil, fmt.Errorf("failed to emit approved event: %v", err)
		}
	case validation.LoanStatusRejected:
		if err := h.eventService.EmitLoanRejected(stub, &loanApp, req.ActorID); err != nil {
			return nil, fmt.Errorf("failed to emit rejected event: %v", err)
		}
	case validation.LoanStatusDisbursed:
		if err := h.eventService.EmitLoanDisbursed(stub, &loanApp, req.ActorID); err != nil {
			return nil, fmt.Errorf("failed to emit disbursed event: %v", err)
		}
	}

	return json.Marshal(&loanApp)
}

// GetLoanApplication retrieves a loan application by ID
func (h *LoanApplicationHandler) GetLoanApplication(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	loanID := args[0]
	loanKey := fmt.Sprintf("LOAN_%s", loanID)

	var loanApp domain.LoanApplication
	if err := h.persistenceService.Get(stub, loanKey, &loanApp); err != nil {
		return nil, fmt.Errorf("loan application not found: %v", err)
	}

	return json.Marshal(&loanApp)
}

// GetLoanHistory retrieves the history of a loan application
func (h *LoanApplicationHandler) GetLoanHistory(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	loanID := args[0]
	history, err := h.getEntityHistory(stub, loanID)
	if err != nil {
		return nil, fmt.Errorf("failed to get loan history: %v", err)
	}

	return json.Marshal(history)
}

// ApproveLoan approves a loan application
func (h *LoanApplicationHandler) ApproveLoan(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	var req domain.LoanApprovalRequest
	if err := json.Unmarshal([]byte(args[0]), &req); err != nil {
		return nil, fmt.Errorf("failed to parse approval request: %v", err)
	}

	// Get existing loan application
	loanKey := fmt.Sprintf("LOAN_%s", req.LoanID)
	var loanApp domain.LoanApplication
	if err := h.persistenceService.Get(stub, loanKey, &loanApp); err != nil {
		return nil, fmt.Errorf("loan application not found: %v", err)
	}

	// Validate current status allows approval
	if loanApp.Status != validation.LoanStatusCreditApproval {
		return nil, fmt.Errorf("loan cannot be approved from current status: %s", loanApp.Status)
	}

	// Update loan application with approval details
	now := time.Now()
	loanApp.Status = validation.LoanStatusApproved
	loanApp.ApprovedAmount = &req.ApprovedAmount
	loanApp.InterestRate = &req.InterestRate
	loanApp.RiskScore = &req.RiskScore
	loanApp.DecisionDate = &now
	loanApp.Notes = req.Notes
	loanApp.LastUpdated = now
	loanApp.LastUpdatedBy = req.ActorID

	// Store updated loan application
	if err := h.persistenceService.Put(stub, loanKey, &loanApp); err != nil {
		return nil, fmt.Errorf("failed to update loan application: %v", err)
	}

	// Record history
	if err := h.recordLoanHistory(stub, req.LoanID, "APPROVAL", "status", string(validation.LoanStatusCreditApproval), string(validation.LoanStatusApproved), req.ActorID); err != nil {
		return nil, err
	}

	// Emit event
	if err := h.eventService.EmitLoanApproved(stub, &loanApp, req.ActorID); err != nil {
		return nil, fmt.Errorf("failed to emit event: %v", err)
	}

	return json.Marshal(&loanApp)
}

// RejectLoan rejects a loan application
func (h *LoanApplicationHandler) RejectLoan(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	var req domain.LoanRejectionRequest
	if err := json.Unmarshal([]byte(args[0]), &req); err != nil {
		return nil, fmt.Errorf("failed to parse rejection request: %v", err)
	}

	// Get existing loan application
	loanKey := fmt.Sprintf("LOAN_%s", req.LoanID)
	var loanApp domain.LoanApplication
	if err := h.persistenceService.Get(stub, loanKey, &loanApp); err != nil {
		return nil, fmt.Errorf("loan application not found: %v", err)
	}

	// Update loan application with rejection details
	now := time.Now()
	loanApp.Status = validation.LoanStatusRejected
	loanApp.DecisionDate = &now
	loanApp.Notes = req.Reason
	loanApp.LastUpdated = now
	loanApp.LastUpdatedBy = req.ActorID

	// Store updated loan application
	if err := h.persistenceService.Put(stub, loanKey, &loanApp); err != nil {
		return nil, fmt.Errorf("failed to update loan application: %v", err)
	}

	// Record history
	if err := h.recordLoanHistory(stub, req.LoanID, "REJECTION", "status", string(loanApp.Status), string(validation.LoanStatusRejected), req.ActorID); err != nil {
		return nil, err
	}

	// Emit event
	if err := h.eventService.EmitLoanRejected(stub, &loanApp, req.ActorID); err != nil {
		return nil, fmt.Errorf("failed to emit event: %v", err)
	}

	return json.Marshal(&loanApp)
}

// QueryLoansByStatus queries loans by status
func (h *LoanApplicationHandler) QueryLoansByStatus(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	status := args[0]
	
	// Validate status
	if err := validation.ValidateLoanApplicationStatus(status); err != nil {
		return nil, fmt.Errorf("invalid loan status: %v", err)
	}

	// Query loans by status using composite key
	iterator, err := stub.GetStateByPartialCompositeKey("LOAN_STATUS", []string{status})
	if err != nil {
		return nil, fmt.Errorf("failed to get loans by status: %v", err)
	}
	defer iterator.Close()

	var loans []domain.LoanApplication
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate loans: %v", err)
		}

		var loan domain.LoanApplication
		if err := json.Unmarshal(response.Value, &loan); err != nil {
			return nil, fmt.Errorf("failed to unmarshal loan: %v", err)
		}

		loans = append(loans, loan)
	}

	return json.Marshal(loans)
}

// QueryLoansByCustomer queries loans by customer ID
func (h *LoanApplicationHandler) QueryLoansByCustomer(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	customerID := args[0]

	// Query loans by customer using partial composite key
	iterator, err := stub.GetStateByPartialCompositeKey("CUSTOMER_LOAN", []string{customerID})
	if err != nil {
		return nil, fmt.Errorf("failed to get loans by customer: %v", err)
	}
	defer iterator.Close()

	var loans []domain.LoanApplication
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate customer loans: %v", err)
		}

		// Get the loan ID from the index
		loanID := string(response.Value)
		
		// Get the actual loan application
		loanKey := fmt.Sprintf("LOAN_%s", loanID)
		var loan domain.LoanApplication
		if err := h.persistenceService.Get(stub, loanKey, &loan); err != nil {
			continue // Skip if loan not found
		}

		loans = append(loans, loan)
	}

	return json.Marshal(loans)
}

// Helper methods

func (h *LoanApplicationHandler) recordLoanHistory(stub shim.ChaincodeStubInterface, loanID, changeType, fieldName, previousValue, newValue, actorID string) error {
	historyID := utils.GenerateID(config.HistoryPrefix)
	txID := stub.GetTxID()

	historyEntry := map[string]interface{}{
		"historyID":     historyID,
		"entityID":      loanID,
		"entityType":    "LoanApplication",
		"timestamp":     utils.GetCurrentTimeString(),
		"changeType":    changeType,
		"fieldName":     fieldName,
		"previousValue": previousValue,
		"newValue":      newValue,
		"actorID":       actorID,
		"transactionID": txID,
	}

	compositeKey, err := stub.CreateCompositeKey("HISTORY", []string{loanID, historyID})
	if err != nil {
		return fmt.Errorf("failed to create composite key: %v", err)
	}

	return h.persistenceService.Put(stub, compositeKey, historyEntry)
}

func (h *LoanApplicationHandler) getEntityHistory(stub shim.ChaincodeStubInterface, entityID string) ([]interface{}, error) {
	iterator, err := stub.GetStateByPartialCompositeKey("HISTORY", []string{entityID})
	if err != nil {
		return nil, fmt.Errorf("failed to get history iterator: %v", err)
	}
	defer iterator.Close()

	var history []interface{}
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate history: %v", err)
		}

		var entry interface{}
		if err := json.Unmarshal(response.Value, &entry); err != nil {
			return nil, fmt.Errorf("failed to unmarshal history entry: %v", err)
		}

		history = append(history, entry)
	}

	return history, nil
}