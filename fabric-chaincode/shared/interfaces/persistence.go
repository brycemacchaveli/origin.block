package interfaces

import "github.com/hyperledger/fabric-chaincode-go/shim"

// PersistenceService defines common persistence operations
type PersistenceService interface {
	// Basic CRUD operations
	Get(stub shim.ChaincodeStubInterface, key string, result interface{}) error
	Put(stub shim.ChaincodeStubInterface, key string, value interface{}) error
	Delete(stub shim.ChaincodeStubInterface, key string) error
	Exists(stub shim.ChaincodeStubInterface, key string) (bool, error)
	
	// Query operations
	GetByCompositeKey(stub shim.ChaincodeStubInterface, objectType string, attributes []string) ([]interface{}, error)
	GetByPartialCompositeKey(stub shim.ChaincodeStubInterface, objectType string, attributes []string) ([]interface{}, error)
	
	// History operations
	GetHistory(stub shim.ChaincodeStubInterface, key string) ([]interface{}, error)
}

// StateManager provides higher-level state management
type StateManager interface {
	PersistenceService
	
	// Transactional operations
	BeginTransaction(stub shim.ChaincodeStubInterface) error
	CommitTransaction(stub shim.ChaincodeStubInterface) error
	RollbackTransaction(stub shim.ChaincodeStubInterface) error
	
	// Validation
	ValidateState(stub shim.ChaincodeStubInterface, key string, value interface{}) error
}