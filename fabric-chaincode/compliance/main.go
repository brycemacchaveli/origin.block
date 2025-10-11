package main

import (
	"log"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/hyperledger/fabric-protos-go/peer"
)

// ComplianceChaincode implements the fabric Contract interface
type ComplianceChaincode struct {
}

// Init is called during chaincode instantiation to initialize any data
func (t *ComplianceChaincode) Init(stub shim.ChaincodeStubInterface) peer.Response {
	return shim.Success(nil)
}

// Invoke is called per transaction on the chaincode
func (t *ComplianceChaincode) Invoke(stub shim.ChaincodeStubInterface) peer.Response {
	function, args := stub.GetFunctionAndParameters()
	
	switch function {
	case "ping":
		return shim.Success([]byte("pong"))
	default:
		return shim.Error("Invalid function name: " + function)
	}
}

func main() {
	if err := shim.Start(new(ComplianceChaincode)); err != nil {
		log.Fatalf("Error starting Compliance chaincode: %v", err)
	}
}