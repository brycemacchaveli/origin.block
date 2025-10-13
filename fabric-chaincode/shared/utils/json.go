package utils

import (
	"encoding/json"
	"fmt"
)

// MarshalJSON safely marshals an object to JSON
func MarshalJSON(obj interface{}) ([]byte, error) {
	data, err := json.Marshal(obj)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal JSON: %v", err)
	}
	return data, nil
}

// UnmarshalJSON safely unmarshals JSON to an object
func UnmarshalJSON(data []byte, obj interface{}) error {
	if err := json.Unmarshal(data, obj); err != nil {
		return fmt.Errorf("failed to unmarshal JSON: %v", err)
	}
	return nil
}

// MarshalJSONString marshals an object to JSON string
func MarshalJSONString(obj interface{}) (string, error) {
	data, err := MarshalJSON(obj)
	if err != nil {
		return "", err
	}
	return string(data), nil
}

// UnmarshalJSONString unmarshals JSON string to an object
func UnmarshalJSONString(jsonStr string, obj interface{}) error {
	return UnmarshalJSON([]byte(jsonStr), obj)
}

// PrettyPrintJSON returns a pretty-printed JSON string
func PrettyPrintJSON(obj interface{}) (string, error) {
	data, err := json.MarshalIndent(obj, "", "  ")
	if err != nil {
		return "", fmt.Errorf("failed to pretty print JSON: %v", err)
	}
	return string(data), nil
}