package main

import (
	"log"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/hyperledger/fabric-protos-go/peer"
)

// CustomerChaincode implements the fabric Contract interface
type CustomerChaincode struct {
}

// Init is called during chaincode instantiation to initialize any data
func (t *CustomerChaincode) Init(stub shim.ChaincodeStubInterface) peer.Response {
	return shim.Success(nil)
}

// Invoke is called per transaction on the chaincode
func (t *CustomerChaincode) Invoke(stub shim.ChaincodeStubInterface) peer.Response {
	function, args := stub.GetFunctionAndParameters()
	
	switch function {
	case "ping":
		return shim.Success([]byte("pong"))
	default:
		return shim.Error("Invalid function name: " + function)
	}
}

func main() {
	if err := shim.Start(new(CustomerChaincode)); err != nil {
		log.Fatalf("Error starting Customer chaincode: %v", err)
	}
}