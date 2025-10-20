package services

import (
	"encoding/json"
	"fmt"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/shared/interfaces"
)

// PersistenceService provides data persistence operations
type PersistenceService struct{}

// NewPersistenceService creates a new persistence service
func NewPersistenceService() *PersistenceService {
	return &PersistenceService{}
}

// Get retrieves and unmarshals data from the ledger
func (ps *PersistenceService) Get(stub shim.ChaincodeStubInterface, key string, result interface{}) error {
	data, err := stub.GetState(key)
	if err != nil {
		return fmt.Errorf("failed to get state for key %s: %v", key, err)
	}
	if data == nil {
		return fmt.Errorf("no data found for key %s", key)
	}
	
	if err := json.Unmarshal(data, result); err != nil {
		return fmt.Errorf("failed to unmarshal data for key %s: %v", key, err)
	}
	
	return nil
}

// Put marshals and stores data to the ledger
func (ps *PersistenceService) Put(stub shim.ChaincodeStubInterface, key string, value interface{}) error {
	data, err := json.Marshal(value)
	if err != nil {
		return fmt.Errorf("failed to marshal data for key %s: %v", key, err)
	}
	
	if err := stub.PutState(key, data); err != nil {
		return fmt.Errorf("failed to put state for key %s: %v", key, err)
	}
	
	return nil
}

// Delete removes data from the ledger
func (ps *PersistenceService) Delete(stub shim.ChaincodeStubInterface, key string) error {
	if err := stub.DelState(key); err != nil {
		return fmt.Errorf("failed to delete state for key %s: %v", key, err)
	}
	return nil
}

// Exists checks if a key exists in the ledger
func (ps *PersistenceService) Exists(stub shim.ChaincodeStubInterface, key string) (bool, error) {
	data, err := stub.GetState(key)
	if err != nil {
		return false, fmt.Errorf("failed to check existence for key %s: %v", key, err)
	}
	return data != nil, nil
}

// GetByCompositeKey retrieves data using a composite key
func (ps *PersistenceService) GetByCompositeKey(stub shim.ChaincodeStubInterface, objectType string, attributes []string) ([]interface{}, error) {
	iterator, err := stub.GetStateByCompositeKey(objectType, attributes)
	if err != nil {
		return nil, fmt.Errorf("failed to get state by composite key: %v", err)
	}
	defer iterator.Close()
	
	var results []interface{}
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate composite key results: %v", err)
		}
		
		var result interface{}
		if err := json.Unmarshal(response.Value, &result); err != nil {
			return nil, fmt.Errorf("failed to unmarshal composite key result: %v", err)
		}
		
		results = append(results, result)
	}
	
	return results, nil
}

// GetByPartialCompositeKey retrieves data using a partial composite key
func (ps *PersistenceService) GetByPartialCompositeKey(stub shim.ChaincodeStubInterface, objectType string, attributes []string) ([]interface{}, error) {
	iterator, err := stub.GetStateByPartialCompositeKey(objectType, attributes)
	if err != nil {
		return nil, fmt.Errorf("failed to get state by partial composite key: %v", err)
	}
	defer iterator.Close()
	
	var results []interface{}
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate partial composite key results: %v", err)
		}
		
		var result interface{}
		if err := json.Unmarshal(response.Value, &result); err != nil {
			return nil, fmt.Errorf("failed to unmarshal partial composite key result: %v", err)
		}
		
		results = append(results, result)
	}
	
	return results, nil
}

// CreateCompositeKey creates a composite key
func (ps *PersistenceService) CreateCompositeKey(stub shim.ChaincodeStubInterface, objectType string, attributes []string) (string, error) {
	return stub.CreateCompositeKey(objectType, attributes)
}

// SplitCompositeKey splits a composite key into its components
func (ps *PersistenceService) SplitCompositeKey(stub shim.ChaincodeStubInterface, compositeKey string) (string, []string, error) {
	return stub.SplitCompositeKey(compositeKey)
}

// GetHistory retrieves the history of a key
func (ps *PersistenceService) GetHistory(stub shim.ChaincodeStubInterface, key string) ([]interfaces.HistoryEntry, error) {
	iterator, err := stub.GetHistoryForKey(key)
	if err != nil {
		return nil, fmt.Errorf("failed to get history for key %s: %v", key, err)
	}
	defer iterator.Close()
	
	var history []interfaces.HistoryEntry
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate history: %v", err)
		}
		
		entry := interfaces.HistoryEntry{
			TxID:      response.TxId,
			Timestamp: response.Timestamp,
			IsDelete:  response.IsDelete,
			Value:     response.Value,
		}
		
		history = append(history, entry)
	}
	
	return history, nil
}