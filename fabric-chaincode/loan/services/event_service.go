package services

import (
	"fmt"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/blockchain-financial-platform/fabric-chaincode/loan/domain"
	"github.com/blockchain-financial-platform/fabric-chaincode/shared/config"
	"github.com/blockchain-financial-platform/fabric-chaincode/shared/services"
)

// EventService handles event emission for loan operations
type EventService struct {
	*services.BaseEventService
}

// NewEventService creates a new event service
func NewEventService() *EventService {
	return &EventService{
		BaseEventService: services.NewBaseEventService(),
	}
}

// EmitLoanSubmitted emits a loan submitted event
func (es *EventService) EmitLoanSubmitted(stub shim.ChaincodeStubInterface, loan *domain.LoanApplication, actorID string) error {
	metadata := map[string]string{
		"customerID":      loan.CustomerID,
		"loanType":        loan.LoanType,
		"requestedAmount": fmt.Sprintf("%.2f", loan.RequestedAmount),
		"status":          string(loan.Status),
	}
	
	payload := es.CreateEventPayloadWithMetadata(
		config.EventLoanSubmitted,
		loan.LoanID,
		"LoanApplication",
		actorID,
		loan,
		metadata,
	)
	
	return es.EmitEvent(stub, config.EventLoanSubmitted, payload)
}

// EmitLoanApproved emits a loan approved event
func (es *EventService) EmitLoanApproved(stub shim.ChaincodeStubInterface, loan *domain.LoanApplication, actorID string) error {
	metadata := map[string]string{
		"customerID":     loan.CustomerID,
		"loanType":       loan.LoanType,
		"approvedAmount": fmt.Sprintf("%.2f", *loan.ApprovedAmount),
		"interestRate":   fmt.Sprintf("%.2f", *loan.InterestRate),
		"status":         string(loan.Status),
	}
	
	payload := es.CreateEventPayloadWithMetadata(
		config.EventLoanApproved,
		loan.LoanID,
		"LoanApplication",
		actorID,
		loan,
		metadata,
	)
	
	return es.EmitEvent(stub, config.EventLoanApproved, payload)
}

// EmitLoanRejected emits a loan rejected event
func (es *EventService) EmitLoanRejected(stub shim.ChaincodeStubInterface, loan *domain.LoanApplication, actorID string) error {
	metadata := map[string]string{
		"customerID": loan.CustomerID,
		"loanType":   loan.LoanType,
		"status":     string(loan.Status),
		"reason":     loan.Notes,
	}
	
	payload := es.CreateEventPayloadWithMetadata(
		config.EventLoanRejected,
		loan.LoanID,
		"LoanApplication",
		actorID,
		loan,
		metadata,
	)
	
	return es.EmitEvent(stub, config.EventLoanRejected, payload)
}

// EmitLoanDisbursed emits a loan disbursed event
func (es *EventService) EmitLoanDisbursed(stub shim.ChaincodeStubInterface, loan *domain.LoanApplication, actorID string) error {
	metadata := map[string]string{
		"customerID":     loan.CustomerID,
		"loanType":       loan.LoanType,
		"approvedAmount": fmt.Sprintf("%.2f", *loan.ApprovedAmount),
		"status":         string(loan.Status),
	}
	
	payload := es.CreateEventPayloadWithMetadata(
		config.EventLoanDisbursed,
		loan.LoanID,
		"LoanApplication",
		actorID,
		loan,
		metadata,
	)
	
	return es.EmitEvent(stub, config.EventLoanDisbursed, payload)
}

