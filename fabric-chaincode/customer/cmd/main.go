package main

import (
	"log"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/blockchain-financial-platform/fabric-chaincode/customer/chaincode"
)

func main() {
	customerChaincode := chaincode.NewCustomerContract()

	if err := shim.Start(customerChaincode); err != nil {
		log.Fatalf("Error starting Customer chaincode: %v", err)
	}
}