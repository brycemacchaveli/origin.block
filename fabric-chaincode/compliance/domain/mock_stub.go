package domain

import (
	"fmt"
	"sort"
	"strings"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/hyperledger/fabric-chaincode-go/shimtest"
	"github.com/hyperledger/fabric-protos-go/ledger/queryresult"
)

// EnhancedMockStub extends shimtest.MockStub to support composite key operations
type EnhancedMockStub struct {
	*shimtest.MockStub
	compositeKeys map[string][]byte
}

// NewEnhancedMockStub creates a new enhanced mock stub with composite key support
func NewEnhancedMockStub(name string, cc shim.Chaincode) *EnhancedMockStub {
	mockStub := shimtest.NewMockStub(name, cc)
	mockStub.MockTransactionStart("txid")
	
	return &EnhancedMockStub{
		MockStub:      mockStub,
		compositeKeys: make(map[string][]byte),
	}
}

// CreateCompositeKey creates a composite key from the given attributes
func (stub *EnhancedMockStub) CreateCompositeKey(objectType string, attributes []string) (string, error) {
	if objectType == "" {
		return "", fmt.Errorf("object type must not be empty")
	}
	
	// Create composite key by joining object type and attributes with a delimiter
	parts := append([]string{objectType}, attributes...)
	compositeKey := strings.Join(parts, "~")
	
	return compositeKey, nil
}

// SplitCompositeKey splits a composite key into its object type and attributes
func (stub *EnhancedMockStub) SplitCompositeKey(compositeKey string) (string, []string, error) {
	parts := strings.Split(compositeKey, "~")
	if len(parts) < 1 {
		return "", nil, fmt.Errorf("invalid composite key format")
	}
	
	objectType := parts[0]
	attributes := parts[1:]
	
	return objectType, attributes, nil
}

// PutState stores the key-value pair and also handles composite key indexing
func (stub *EnhancedMockStub) PutState(key string, value []byte) error {
	// Store in the regular state
	err := stub.MockStub.PutState(key, value)
	if err != nil {
		return err
	}
	
	// If this is a composite key, also store it in our composite key map
	if strings.Contains(key, "~") {
		stub.compositeKeys[key] = value
	}
	
	return nil
}

// GetStateByPartialCompositeKey returns an iterator for keys matching the partial composite key
func (stub *EnhancedMockStub) GetStateByPartialCompositeKey(objectType string, attributes []string) (shim.StateQueryIteratorInterface, error) {
	// Create the partial key prefix
	prefix := objectType
	for _, attr := range attributes {
		prefix += "~" + attr
	}
	
	// Find all keys that start with this prefix
	var matchingKeys []string
	for key := range stub.compositeKeys {
		if strings.HasPrefix(key, prefix) {
			matchingKeys = append(matchingKeys, key)
		}
	}
	
	// Sort keys for consistent ordering
	sort.Strings(matchingKeys)
	
	// Create and return a mock iterator
	return &MockStateQueryIterator{
		keys:    matchingKeys,
		values:  stub.compositeKeys,
		current: -1,
	}, nil
}

// MockStateQueryIterator implements shim.StateQueryIteratorInterface for testing
type MockStateQueryIterator struct {
	keys    []string
	values  map[string][]byte
	current int
}

// HasNext returns true if there are more items to iterate
func (iter *MockStateQueryIterator) HasNext() bool {
	return iter.current+1 < len(iter.keys)
}

// Next returns the next key-value pair
func (iter *MockStateQueryIterator) Next() (*queryresult.KV, error) {
	if !iter.HasNext() {
		return nil, fmt.Errorf("no more items")
	}
	
	iter.current++
	key := iter.keys[iter.current]
	value := iter.values[key]
	
	return &queryresult.KV{
		Key:   key,
		Value: value,
	}, nil
}

// Close closes the iterator
func (iter *MockStateQueryIterator) Close() error {
	return nil
}