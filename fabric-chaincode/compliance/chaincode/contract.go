package chaincode

import (
	"encoding/json"
	"fmt"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/hyperledger/fabric-protos-go/peer"
)

// ComplianceContract implements the chaincode interface
type ComplianceContract struct {
}

// NewComplianceContract creates a new compliance contract
func NewComplianceContract() *ComplianceContract {
	return &ComplianceContract{}
}

// Init is called during chaincode instantiation
func (c *ComplianceContract) Init(stub shim.ChaincodeStubInterface) peer.Response {
	return shim.Success(nil)
}

// Invoke is called per transaction on the chaincode
func (c *ComplianceContract) Invoke(stub shim.ChaincodeStubInterface) peer.Response {
	function, args := stub.GetFunctionAndParameters()

	switch function {
	case "CreateComplianceRule":
		return c.CreateComplianceRule(stub, args)
	case "GetComplianceRule":
		return c.GetComplianceRule(stub, args)
	case "InitLedger":
		return c.InitLedger(stub)
	default:
		return shim.Error(fmt.Sprintf("Unknown function: %s", function))
	}
}

// ComplianceRule represents a compliance rule
type ComplianceRule struct {
	ID          string `json:"id"`
	Type        string `json:"type"`
	Description string `json:"description"`
	Status      string `json:"status"`
}

// InitLedger initializes the ledger with sample data
func (c *ComplianceContract) InitLedger(stub shim.ChaincodeStubInterface) peer.Response {
	rules := []ComplianceRule{
		{ID: "RULE001", Type: "KYC_VERIFICATION", Description: "All customers must complete KYC verification", Status: "ACTIVE"},
		{ID: "RULE002", Type: "AML_CHECK", Description: "Anti-money laundering checks required", Status: "ACTIVE"},
	}

	for _, rule := range rules {
		ruleJSON, err := json.Marshal(rule)
		if err != nil {
			return shim.Error(err.Error())
		}

		err = stub.PutState(rule.ID, ruleJSON)
		if err != nil {
			return shim.Error(err.Error())
		}
	}

	return shim.Success(nil)
}

// CreateComplianceRule creates a new compliance rule
func (c *ComplianceContract) CreateComplianceRule(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 4 {
		return shim.Error("Incorrect number of arguments. Expecting 4")
	}

	rule := ComplianceRule{
		ID:          args[0],
		Type:        args[1],
		Description: args[2],
		Status:      args[3],
	}

	ruleJSON, err := json.Marshal(rule)
	if err != nil {
		return shim.Error(err.Error())
	}

	err = stub.PutState(rule.ID, ruleJSON)
	if err != nil {
		return shim.Error(err.Error())
	}

	return shim.Success(nil)
}

// GetComplianceRule retrieves a compliance rule
func (c *ComplianceContract) GetComplianceRule(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	if len(args) != 1 {
		return shim.Error("Incorrect number of arguments. Expecting 1")
	}

	ruleJSON, err := stub.GetState(args[0])
	if err != nil {
		return shim.Error(err.Error())
	}

	if ruleJSON == nil {
		return shim.Error("Rule not found")
	}

	return shim.Success(ruleJSON)
}

