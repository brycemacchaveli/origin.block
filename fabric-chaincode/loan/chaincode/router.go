package chaincode

import (
	"fmt"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/blockchain-financial-platform/fabric-chaincode/loan/handlers"
)

// Router handles function routing for the loan chaincode
type Router struct {
	handlers map[string]func(shim.ChaincodeStubInterface, []string) ([]byte, error)
}

// NewRouter creates a new router with all handler mappings
func NewRouter() *Router {
	loanHandler := handlers.NewLoanApplicationHandler()
	documentHandler := handlers.NewDocumentHandler()
	
	return &Router{
		handlers: map[string]func(shim.ChaincodeStubInterface, []string) ([]byte, error){
			// Loan application functions
			"SubmitLoanApplication":    loanHandler.SubmitLoanApplication,
			"UpdateLoanStatus":         loanHandler.UpdateLoanStatus,
			"GetLoanApplication":       loanHandler.GetLoanApplication,
			"GetLoanHistory":           loanHandler.GetLoanHistory,
			"ApproveLoan":              loanHandler.ApproveLoan,
			"RejectLoan":               loanHandler.RejectLoan,
			
			// Document functions
			"UploadDocument":           documentHandler.UploadDocument,
			"VerifyDocument":           documentHandler.VerifyDocument,
			"GetDocument":              documentHandler.GetDocument,
			"GetLoanDocuments":         documentHandler.GetLoanDocuments,
			
			// Query functions
			"QueryLoansByStatus":       loanHandler.QueryLoansByStatus,
			"QueryLoansByCustomer":     loanHandler.QueryLoansByCustomer,
		},
	}
}

// Route routes the function call to the appropriate handler
func (r *Router) Route(stub shim.ChaincodeStubInterface, function string, args []string) ([]byte, error) {
	handler, exists := r.handlers[function]
	if !exists {
		return nil, fmt.Errorf("function %s not found", function)
	}
	
	return handler(stub, args)
}