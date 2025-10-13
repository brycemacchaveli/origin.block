package chaincode

import (
	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/hyperledger/fabric-protos-go/peer"
	"github.com/blockchain-financial-platform/fabric-chaincode/shared/chaincode"
)

// LoanContract implements the chaincode interface
type LoanContract struct {
	chaincode.BaseContract
}

// NewLoanContract creates a new loan contract
func NewLoanContract() *LoanContract {
	return &LoanContract{
		BaseContract: chaincode.BaseContract{Name: "loan"},
	}
}

// Invoke handles chaincode invocations
func (cc *LoanContract) Invoke(stub shim.ChaincodeStubInterface) peer.Response {
	router := NewRouter()
	return cc.InvokeWithRouter(stub, router)
}