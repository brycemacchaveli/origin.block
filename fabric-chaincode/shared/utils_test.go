package shared

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

// ============================================================================
// BASIC UTILITY TESTS
// ============================================================================

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

// ============================================================================
// VALIDATION UTILITY TESTS
// ============================================================================

func TestValidateEmail(t *testing.T) {
	validEmails := []string{
		"test@example.com",
		"user.name@domain.co.uk",
		"user+tag@example.org",
	}
	
	for _, email := range validEmails {
		err := ValidateEmail(email)
		assert.NoError(t, err, "Valid email should pass validation: %s", email)
	}
	
	invalidEmails := []string{
		"invalid-email",
		"@example.com",
		"test@",
		"test.example.com",
	}
	
	for _, email := range invalidEmails {
		err := ValidateEmail(email)
		assert.Error(t, err, "Invalid email should fail validation: %s", email)
	}
}

func TestValidatePhone(t *testing.T) {
	validPhones := []string{
		"+1234567890",
		"1234567890",
		"+44123456789",
	}
	
	for _, phone := range validPhones {
		err := ValidatePhone(phone)
		assert.NoError(t, err, "Valid phone should pass validation: %s", phone)
	}
	
	invalidPhones := []string{
		"",
		"abc123",
		"+",
		"123",
	}
	
	for _, phone := range invalidPhones {
		err := ValidatePhone(phone)
		assert.Error(t, err, "Invalid phone should fail validation: %s", phone)
	}
}

func TestValidateAmount(t *testing.T) {
	validAmounts := []float64{0.01, 100.50, 1000000}
	
	for _, amount := range validAmounts {
		err := ValidateAmount(amount)
		assert.NoError(t, err, "Valid amount should pass validation: %f", amount)
	}
	
	invalidAmounts := []float64{0, -100, 1000000001}
	
	for _, amount := range invalidAmounts {
		err := ValidateAmount(amount)
		assert.Error(t, err, "Invalid amount should fail validation: %f", amount)
	}
}

func TestValidateStatus(t *testing.T) {
	allowedStatuses := []string{"ACTIVE", "INACTIVE", "PENDING"}
	
	err := ValidateStatus("ACTIVE", allowedStatuses)
	assert.NoError(t, err)
	
	err = ValidateStatus("INVALID", allowedStatuses)
	assert.Error(t, err)
}

func TestValidateStringLength(t *testing.T) {
	err := ValidateStringLength("test", 2, 10, "testField")
	assert.NoError(t, err)
	
	err = ValidateStringLength("a", 2, 10, "testField")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "at least 2 characters")
	
	err = ValidateStringLength("verylongstring", 2, 10, "testField")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "at most 10 characters")
}

func TestValidateFields(t *testing.T) {
	fields := map[string]string{
		"email": "test@example.com",
		"name":  "John Doe",
	}
	
	rules := map[string][]ValidationRule{
		"email": {
			{Name: "email_format", Validator: ValidateEmail},
		},
		"name": {
			{Name: "length", Validator: func(value string) error {
				return ValidateStringLength(value, 2, 50, "name")
			}},
		},
	}
	
	err := ValidateFields(fields, rules)
	assert.NoError(t, err)
	
	// Test with invalid email
	fields["email"] = "invalid-email"
	err = ValidateFields(fields, rules)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "email")
}

// ============================================================================
// ACCESS CONTROL TESTS
// ============================================================================

func TestGetRolePermissions(t *testing.T) {
	permissions := GetRolePermissions(RoleUnderwriter)
	assert.Contains(t, permissions, PermissionViewCustomer)
	assert.Contains(t, permissions, PermissionViewLoan)
	assert.NotContains(t, permissions, PermissionCreateCustomer)
	
	permissions = GetRolePermissions(RoleIntroducer)
	assert.Contains(t, permissions, PermissionCreateCustomer)
	assert.Contains(t, permissions, PermissionCreateLoan)
	assert.NotContains(t, permissions, PermissionApproveLoan)
}

func TestActorHasPermission(t *testing.T) {
	actor := Actor{
		ActorID:     "test-actor",
		ActorType:   ActorTypeInternalUser,
		Role:        RoleUnderwriter,
		Permissions: GetRolePermissions(RoleUnderwriter),
		IsActive:    true,
	}
	
	assert.True(t, actor.HasPermission(PermissionViewCustomer))
	assert.False(t, actor.HasPermission(PermissionCreateCustomer))
	
	// Test inactive actor
	actor.IsActive = false
	assert.False(t, actor.HasPermission(PermissionViewCustomer))
}

// ============================================================================
// CRYPTOGRAPHIC UTILITY TESTS
// ============================================================================

func TestHashDocument(t *testing.T) {
	content := []byte("test document content")
	hash1 := HashDocument(content)
	hash2 := HashDocument(content)
	
	assert.Equal(t, hash1, hash2, "Same content should produce same hash")
	assert.Len(t, hash1, 64, "SHA256 hash should be 64 characters")
	
	// Different content should produce different hash
	differentContent := []byte("different content")
	hash3 := HashDocument(differentContent)
	assert.NotEqual(t, hash1, hash3, "Different content should produce different hash")
}

func TestEncryptDecryptSensitiveData(t *testing.T) {
	plaintext := "sensitive data"
	key := "test-encryption-key"
	
	encrypted, err := EncryptSensitiveData(plaintext, key)
	assert.NoError(t, err)
	assert.NotEqual(t, plaintext, encrypted)
	
	decrypted, err := DecryptSensitiveData(encrypted, key)
	assert.NoError(t, err)
	assert.Equal(t, plaintext, decrypted)
	
	// Test with wrong key
	wrongKey := "wrong-key"
	_, err = DecryptSensitiveData(encrypted, wrongKey)
	assert.Error(t, err)
}

func TestHashSensitiveData(t *testing.T) {
	data := "123456789"
	salt := "random-salt"
	
	hash1 := HashSensitiveData(data, salt)
	hash2 := HashSensitiveData(data, salt)
	
	assert.Equal(t, hash1, hash2, "Same data and salt should produce same hash")
	assert.Len(t, hash1, 64, "SHA256 hash should be 64 characters")
	
	// Different salt should produce different hash
	differentSalt := "different-salt"
	hash3 := HashSensitiveData(data, differentSalt)
	assert.NotEqual(t, hash1, hash3, "Different salt should produce different hash")
}

// ============================================================================
// HISTORY TRACKING TESTS
// ============================================================================

func TestHistoryEntry(t *testing.T) {
	entry := HistoryEntry{
		HistoryID:     "HIST_123",
		EntityID:      "CUSTOMER_456",
		EntityType:    "Customer",
		Timestamp:     time.Now(),
		ChangeType:    "UPDATE",
		FieldName:     "email",
		PreviousValue: "old@example.com",
		NewValue:      "new@example.com",
		ActorID:       "ACTOR_789",
		TransactionID: "TX_ABC",
	}
	
	assert.Equal(t, "HIST_123", entry.HistoryID)
	assert.Equal(t, "CUSTOMER_456", entry.EntityID)
	assert.Equal(t, "Customer", entry.EntityType)
	assert.Equal(t, "UPDATE", entry.ChangeType)
}

// ============================================================================
// UNIT TESTS FOR UTILITY FUNCTIONS (NO STUB REQUIRED)
// ============================================================================

func TestCreateCompositeKeyLogic(t *testing.T) {
	// Test the logic that would be used with CreateCompositeKey
	objectType := "CUSTOMER"
	attributes := []string{"123", "active"}
	
	// Simulate composite key creation
	expectedKey := objectType + "_" + attributes[0] + "_" + attributes[1]
	assert.Contains(t, expectedKey, "CUSTOMER")
	assert.Contains(t, expectedKey, "123")
	assert.Contains(t, expectedKey, "active")
}

func TestEmitEventPayload(t *testing.T) {
	// Test event payload marshaling
	payload := map[string]interface{}{
		"eventType": "CustomerCreated",
		"customerID": "CUST_123",
	}
	
	payloadBytes, err := json.Marshal(payload)
	assert.NoError(t, err)
	assert.Contains(t, string(payloadBytes), "CustomerCreated")
	assert.Contains(t, string(payloadBytes), "CUST_123")
}