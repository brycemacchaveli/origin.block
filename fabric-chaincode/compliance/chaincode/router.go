package chaincode

import (
	"fmt"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/compliance/handlers"
)

// Router handles function routing for the compliance chaincode
type Router struct {
	handlers map[string]func(shim.ChaincodeStubInterface, []string) ([]byte, error)
}

// NewRouter creates a new router with all handler mappings
func NewRouter() *Router {
	amlHandler := handlers.NewAMLCheckHandler()
	kycHandler := handlers.NewKYCVerificationHandler()
	reportHandler := handlers.NewReportGenerationHandler()
	
	return &Router{
		handlers: map[string]func(shim.ChaincodeStubInterface, []string) ([]byte, error){
			// AML functions
			"PerformAMLCheck":         amlHandler.PerformAMLCheck,
			"UpdateAMLStatus":         amlHandler.UpdateAMLStatus,
			"GetAMLReport":            amlHandler.GetAMLReport,
			
			// KYC functions
			"VerifyKYCDocuments":      kycHandler.VerifyKYCDocuments,
			"UpdateKYCStatus":         kycHandler.UpdateKYCStatus,
			"GetKYCReport":            kycHandler.GetKYCReport,
			
			// Report functions
			"GenerateComplianceReport": reportHandler.GenerateComplianceReport,
			"GetComplianceReport":      reportHandler.GetComplianceReport,
			"QueryReportsByType":       reportHandler.QueryReportsByType,
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