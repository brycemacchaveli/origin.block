package main

import (
	"log"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/blockchain-financial-platform/fabric-chaincode/compliance/chaincode"
)

func main() {
	complianceChaincode := chaincode.NewComplianceContract()

	if err := shim.Start(complianceChaincode); err != nil {
		log.Fatalf("Error starting Compliance chaincode: %v", err)
	}
}