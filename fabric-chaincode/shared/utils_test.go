package shared

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestGenerateID(t *testing.T) {
	id1 := GenerateID("test")
	id2 := GenerateID("test")
	
	assert.NotEqual(t, id1, id2, "Generated IDs should be unique")
	assert.Contains(t, id1, "test_", "ID should contain prefix")
}

func TestHashString(t *testing.T) {
	input := "test string"
	hash1 := HashString(input)
	hash2 := HashString(input)
	
	assert.Equal(t, hash1, hash2, "Same input should produce same hash")
	assert.Len(t, hash1, 64, "SHA256 hash should be 64 characters")
}

func TestValidateRequired(t *testing.T) {
	// Test with all fields present
	fields := map[string]string{
		"field1": "value1",
		"field2": "value2",
	}
	err := ValidateRequired(fields)
	assert.NoError(t, err)
	
	// Test with missing field
	fields["field3"] = ""
	err = ValidateRequired(fields)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "field3")
}