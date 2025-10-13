package chaincode

import (
	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/hyperledger/fabric-protos-go/peer"
	"github.com/blockchain-financial-platform/fabric-chaincode/shared/chaincode"
)

// CustomerContract implements the chaincode interface
type CustomerContract struct {
	chaincode.BaseContract
}

// NewCustomerContract creates a new customer contract
func NewCustomerContract() *CustomerContract {
	return &CustomerContract{
		BaseContract: chaincode.BaseContract{Name: "customer"},
	}
}

// Invoke handles chaincode invocations
func (cc *CustomerContract) Invoke(stub shim.ChaincodeStubInterface) peer.Response {
	router := NewRouter()
	return cc.InvokeWithRouter(stub, router)
}