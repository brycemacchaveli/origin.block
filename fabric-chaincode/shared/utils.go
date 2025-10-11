package shared

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/shim"
)

// GenerateID creates a unique identifier using timestamp and random component
func GenerateID(prefix string) string {
	timestamp := time.Now().UnixNano()
	return fmt.Sprintf("%s_%d", prefix, timestamp)
}

// HashString creates a SHA256 hash of the input string
func HashString(input string) string {
	hash := sha256.Sum256([]byte(input))
	return hex.EncodeToString(hash[:])
}

// ValidateRequired checks if required fields are not empty
func ValidateRequired(fields map[string]string) error {
	for fieldName, value := range fields {
		if value == "" {
			return fmt.Errorf("required field '%s' is empty", fieldName)
		}
	}
	return nil
}

// GetStateAsJSON retrieves and unmarshals JSON data from the ledger
func GetStateAsJSON(stub shim.ChaincodeStubInterface, key string, result interface{}) error {
	data, err := stub.GetState(key)
	if err != nil {
		return fmt.Errorf("failed to get state for key %s: %v", key, err)
	}
	if data == nil {
		return fmt.Errorf("no data found for key %s", key)
	}
	return json.Unmarshal(data, result)
}

// PutStateAsJSON marshals and stores JSON data to the ledger
func PutStateAsJSON(stub shim.ChaincodeStubInterface, key string, value interface{}) error {
	data, err := json.Marshal(value)
	if err != nil {
		return fmt.Errorf("failed to marshal data: %v", err)
	}
	return stub.PutState(key, data)
}