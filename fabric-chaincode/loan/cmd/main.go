package main

import (
	"log"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/blockchain-financial-platform/fabric-chaincode/loan/chaincode"
)

func main() {
	loanChaincode := chaincode.NewLoanContract()

	if err := shim.Start(loanChaincode); err != nil {
		log.Fatalf("Error starting Loan chaincode: %v", err)
	}
}