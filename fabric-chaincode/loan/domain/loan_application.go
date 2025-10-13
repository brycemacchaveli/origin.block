package domain

import (
	"time"
	
	"github.com/blockchain-financial-platform/fabric-chaincode/shared/validation"
)

// LoanApplication represents a loan application entity
type LoanApplication struct {
	LoanID              string                            `json:"loanID"`
	CustomerID          string                            `json:"customerID"`
	LoanType            string                            `json:"loanType"`
	RequestedAmount     float64                           `json:"requestedAmount"`
	ApprovedAmount      *float64                          `json:"approvedAmount,omitempty"`
	InterestRate        *float64                          `json:"interestRate,omitempty"`
	TermMonths          int                               `json:"termMonths"`
	Purpose             string                            `json:"purpose"`
	Status              validation.LoanApplicationStatus `json:"status"`
	ApplicationDate     time.Time                         `json:"applicationDate"`
	DecisionDate        *time.Time                        `json:"decisionDate,omitempty"`
	DisbursementDate    *time.Time                        `json:"disbursementDate,omitempty"`
	UnderwriterID       string                            `json:"underwriterID,omitempty"`
	CreditOfficerID     string                            `json:"creditOfficerID,omitempty"`
	RiskScore           *float64                          `json:"riskScore,omitempty"`
	Notes               string                            `json:"notes"`
	CreatedDate         time.Time                         `json:"createdDate"`
	LastUpdated         time.Time                         `json:"lastUpdated"`
	CreatedBy           string                            `json:"createdBy"`
	LastUpdatedBy       string                            `json:"lastUpdatedBy"`
}

// LoanApplicationRequest represents a loan application submission request
type LoanApplicationRequest struct {
	CustomerID      string  `json:"customerID"`
	LoanType        string  `json:"loanType"`
	RequestedAmount float64 `json:"requestedAmount"`
	TermMonths      int     `json:"termMonths"`
	Purpose         string  `json:"purpose"`
	ActorID         string  `json:"actorID"`
}

// LoanStatusUpdateRequest represents a loan status update request
type LoanStatusUpdateRequest struct {
	LoanID    string                            `json:"loanID"`
	NewStatus validation.LoanApplicationStatus `json:"newStatus"`
	Notes     string                            `json:"notes"`
	ActorID   string                            `json:"actorID"`
}

// LoanApprovalRequest represents a loan approval request
type LoanApprovalRequest struct {
	LoanID         string  `json:"loanID"`
	ApprovedAmount float64 `json:"approvedAmount"`
	InterestRate   float64 `json:"interestRate"`
	RiskScore      float64 `json:"riskScore"`
	Notes          string  `json:"notes"`
	ActorID        string  `json:"actorID"`
}

// LoanRejectionRequest represents a loan rejection request
type LoanRejectionRequest struct {
	LoanID  string `json:"loanID"`
	Reason  string `json:"reason"`
	ActorID string `json:"actorID"`
}