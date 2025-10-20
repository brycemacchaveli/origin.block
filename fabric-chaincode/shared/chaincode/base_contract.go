package chaincode

import (
	"fmt"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/hyperledger/fabric-protos-go/peer"
)

// BaseContract provides common chaincode functionality
type BaseContract struct {
	Name string
}

// Init initializes the chaincode - common implementation
func (bc *BaseContract) Init(stub shim.ChaincodeStubInterface) peer.Response {
	return shim.Success(nil)
}

// Router interface that all chaincodes must implement
type Router interface {
	Route(stub shim.ChaincodeStubInterface, function string, args []string) ([]byte, error)
}

// InvokeWithRouter handles chaincode invocations using a router
func (bc *BaseContract) InvokeWithRouter(stub shim.ChaincodeStubInterface, router Router) peer.Response {
	function, args := stub.GetFunctionAndParameters()
	
	response, err := router.Route(stub, function, args)
	if err != nil {
		return shim.Error(fmt.Sprintf("Error invoking function %s: %v", function, err))
	}
	
	return shim.Success(response)
}