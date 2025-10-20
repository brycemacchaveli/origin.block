package utils

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"time"
)

// GenerateID creates a unique identifier with the given prefix
func GenerateID(prefix string) string {
	timestamp := time.Now().UnixNano()
	
	// Add random component for uniqueness
	randomBytes := make([]byte, 4)
	rand.Read(randomBytes)
	
	// Create hash for shorter, consistent length
	hash := sha256.Sum256([]byte(fmt.Sprintf("%d_%s", timestamp, hex.EncodeToString(randomBytes))))
	hashStr := hex.EncodeToString(hash[:4]) // Use first 4 bytes
	
	return fmt.Sprintf("%s_%d_%s", prefix, timestamp, hashStr)
}

// GenerateShortID creates a shorter unique identifier
func GenerateShortID(prefix string) string {
	timestamp := time.Now().Unix()
	randomBytes := make([]byte, 2)
	rand.Read(randomBytes)
	
	return fmt.Sprintf("%s_%d_%s", prefix, timestamp, hex.EncodeToString(randomBytes))
}

// GenerateUUID creates a UUID-like identifier
func GenerateUUID() string {
	randomBytes := make([]byte, 16)
	rand.Read(randomBytes)
	
	// Set version (4) and variant bits
	randomBytes[6] = (randomBytes[6] & 0x0f) | 0x40
	randomBytes[8] = (randomBytes[8] & 0x3f) | 0x80
	
	return fmt.Sprintf("%x-%x-%x-%x-%x",
		randomBytes[0:4],
		randomBytes[4:6],
		randomBytes[6:8],
		randomBytes[8:10],
		randomBytes[10:16])
}

// ValidateID checks if an ID has the expected format
func ValidateID(id, expectedPrefix string) error {
	if len(id) < len(expectedPrefix)+1 {
		return fmt.Errorf("ID too short: %s", id)
	}
	
	if id[:len(expectedPrefix)] != expectedPrefix {
		return fmt.Errorf("ID does not have expected prefix %s: %s", expectedPrefix, id)
	}
	
	return nil
}