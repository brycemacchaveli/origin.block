package chaincode

import (
	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/hyperledger/fabric-protos-go/peer"
	"github.com/blockchain-financial-platform/fabric-chaincode/shared/chaincode"
)

// ComplianceContract implements the chaincode interface
type ComplianceContract struct {
	chaincode.BaseContract
}

// NewComplianceContract creates a new compliance contract
func NewComplianceContract() *ComplianceContract {
	return &ComplianceContract{
		BaseContract: chaincode.BaseContract{Name: "compliance"},
	}
}

// Invoke handles chaincode invocations
func (cc *ComplianceContract) Invoke(stub shim.ChaincodeStubInterface) peer.Response {
	router := NewRouter()
	return cc.InvokeWithRouter(stub, router)
}