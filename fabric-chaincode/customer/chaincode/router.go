package chaincode

import (
	"fmt"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/customer/handlers"
)

// Router handles function routing for the customer chaincode
type Router struct {
	handlers map[string]func(shim.ChaincodeStubInterface, []string) ([]byte, error)
}

// NewRouter creates a new router with all handler mappings
func NewRouter() *Router {
	customerHandler := handlers.NewCustomerHandler()
	kycHandler := handlers.NewKYCHandler()
	cdpHandler := handlers.NewCDPHandler()
	
	return &Router{
		handlers: map[string]func(shim.ChaincodeStubInterface, []string) ([]byte, error){
			// Customer management functions
			"RegisterCustomer":    customerHandler.RegisterCustomer,
			"UpdateCustomer":      customerHandler.UpdateCustomer,
			"GetCustomer":         customerHandler.GetCustomer,
			"GetCustomerHistory":  customerHandler.GetCustomerHistory,
			"UpdateCustomerStatus": customerHandler.UpdateCustomerStatus,
			
			// KYC/AML functions
			"InitiateKYC":         kycHandler.InitiateKYC,
			"UpdateKYCStatus":     kycHandler.UpdateKYCStatus,
			"GetKYCRecord":        kycHandler.GetKYCRecord,
			"InitiateAMLCheck":    kycHandler.InitiateAMLCheck,
			"UpdateAMLStatus":     kycHandler.UpdateAMLStatus,
			"GetAMLRecord":        kycHandler.GetAMLRecord,
			
			// CDP functions
			"GenerateCDP":          cdpHandler.GenerateCDP,
			"GetCDP":               cdpHandler.GetCDP,
			"ValidateCDP":          cdpHandler.ValidateCDP,
			"RevokeCDP":            cdpHandler.RevokeCDP,
			"GetCustomerCurrentCDP": cdpHandler.GetCustomerCurrentCDP,
			
			// Query functions
			"QueryCustomersByStatus": customerHandler.QueryCustomersByStatus,
			"QueryKYCByStatus":       kycHandler.QueryKYCByStatus,
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