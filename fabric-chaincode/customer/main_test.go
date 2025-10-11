package main

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/blockchain-financial-platform/fabric-chaincode/shared"
	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/hyperledger/fabric-chaincode-go/shimtest"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestCustomerChaincode_Init(t *testing.T) {
	cc := new(CustomerChaincode)
	stub := shimtest.NewMockStub("customer", cc)

	response := cc.Init(stub)
	assert.Equal(t, int32(shim.OK), response.Status)
}

func TestCustomerChaincode_CreateCustomer_Success(t *testing.T) {
	cc := new(CustomerChaincode)
	stub := shimtest.NewMockStub("customer", cc)

	// Setup test actor
	testActor := shared.Actor{
		ActorID:           "ACTOR_TEST_001",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test Customer Service Rep",
		Role:              shared.RoleCustomerService,
		BlockchainIdentity: "test-identity",
		Permissions:       []shared.Permission{shared.PermissionCreateCustomer, shared.PermissionViewCustomer},
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}
	
	// Store test actor
	actorJSON, _ := json.Marshal(testActor)
	stub.MockTransactionStart("setup")
	stub.PutState("ACTOR_ACTOR_TEST_001", actorJSON)
	stub.MockTransactionEnd("setup")

	// Test data
	args := []string{
		"John",                    // firstName
		"Doe",                     // lastName
		"1990-01-15",             // dateOfBirth
		"ID123456789",            // nationalID
		"123 Main St, City, Country", // address
		"john.doe@example.com",   // contactEmail
		"+1234567890",            // contactPhone
		"ACTOR_TEST_001",         // actorID
	}

	// Execute CreateCustomer
	stub.MockTransactionStart("create")
	response := cc.CreateCustomer(stub, args)
	stub.MockTransactionEnd("create")

	// Verify response
	assert.Equal(t, int32(shim.OK), response.Status)
	customerID := string(response.Payload)
	assert.NotEmpty(t, customerID)
	assert.Contains(t, customerID, "CUST_")

	// Verify customer was stored
	customerData, err := stub.GetState(customerID)
	require.NoError(t, err)
	require.NotNil(t, customerData)

	var customer Customer
	err = json.Unmarshal(customerData, &customer)
	require.NoError(t, err)

	// Verify customer fields
	assert.Equal(t, customerID, customer.CustomerID)
	assert.Equal(t, "John", customer.FirstName)
	assert.Equal(t, "Doe", customer.LastName)
	assert.Equal(t, "123 Main St, City, Country", customer.Address)
	assert.Equal(t, "john.doe@example.com", customer.ContactEmail)
	assert.Equal(t, "+1234567890", customer.ContactPhone)
	assert.Equal(t, string(shared.KYCStatusPending), customer.KYCStatus)
	assert.Equal(t, string(shared.AMLStatusClear), customer.AMLStatus)
	assert.Equal(t, string(shared.CustomerStatusActive), customer.Status)
	assert.Equal(t, "ACTOR_TEST_001", customer.UpdatedByActor)
	assert.Equal(t, 1, customer.Version)
	assert.NotEmpty(t, customer.NationalID) // Should be hashed
	assert.NotEqual(t, "ID123456789", customer.NationalID) // Should not be plain text
}

func TestCustomerChaincode_CreateCustomer_ValidationErrors(t *testing.T) {
	cc := new(CustomerChaincode)
	stub := shimtest.NewMockStub("customer", cc)

	// Setup test actor
	testActor := shared.Actor{
		ActorID:           "ACTOR_TEST_001",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test Customer Service Rep",
		Role:              shared.RoleCustomerService,
		Permissions:       []shared.Permission{shared.PermissionCreateCustomer},
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}
	
	actorJSON, _ := json.Marshal(testActor)
	stub.MockTransactionStart("setup")
	stub.PutState("ACTOR_ACTOR_TEST_001", actorJSON)
	stub.MockTransactionEnd("setup")

	tests := []struct {
		name string
		args []string
		expectedError string
	}{
		{
			name: "Insufficient arguments",
			args: []string{"John", "Doe"},
			expectedError: "Incorrect number of arguments",
		},
		{
			name: "Empty first name",
			args: []string{"", "Doe", "1990-01-15", "ID123456789", "123 Main St", "john@example.com", "+1234567890", "ACTOR_TEST_001"},
			expectedError: "required field 'firstName' is empty",
		},
		{
			name: "Invalid email",
			args: []string{"John", "Doe", "1990-01-15", "ID123456789", "123 Main St", "invalid-email", "+1234567890", "ACTOR_TEST_001"},
			expectedError: "Invalid email",
		},
		{
			name: "Invalid phone",
			args: []string{"John", "Doe", "1990-01-15", "ID123456789", "123 Main St", "john@example.com", "invalid-phone", "ACTOR_TEST_001"},
			expectedError: "Invalid phone",
		},
		{
			name: "Invalid date format",
			args: []string{"John", "Doe", "invalid-date", "ID123456789", "123 Main St", "john@example.com", "+1234567890", "ACTOR_TEST_001"},
			expectedError: "Invalid date of birth format",
		},
		{
			name: "Future date of birth",
			args: []string{"John", "Doe", "2030-01-15", "ID123456789", "123 Main St", "john@example.com", "+1234567890", "ACTOR_TEST_001"},
			expectedError: "date of birth cannot be in the future",
		},
		{
			name: "Too young (under 18)",
			args: []string{"John", "Doe", "2010-01-15", "ID123456789", "123 Main St", "john@example.com", "+1234567890", "ACTOR_TEST_001"},
			expectedError: "customer must be at least 18 years old",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			stub.MockTransactionStart(tt.name)
			response := cc.CreateCustomer(stub, tt.args)
			stub.MockTransactionEnd(tt.name)

			assert.Equal(t, int32(shim.ERROR), response.Status)
			assert.Contains(t, response.Message, tt.expectedError)
		})
	}
}

func TestCustomerChaincode_CreateCustomer_AccessDenied(t *testing.T) {
	cc := new(CustomerChaincode)
	stub := shimtest.NewMockStub("customer", cc)

	// Setup test actor without create permission
	testActor := shared.Actor{
		ActorID:           "ACTOR_TEST_001",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test User",
		Role:              shared.RoleUnderwriter,
		Permissions:       []shared.Permission{shared.PermissionViewCustomer}, // No create permission
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}
	
	actorJSON, _ := json.Marshal(testActor)
	stub.MockTransactionStart("setup")
	stub.PutState("ACTOR_ACTOR_TEST_001", actorJSON)
	stub.MockTransactionEnd("setup")

	args := []string{
		"John", "Doe", "1990-01-15", "ID123456789", "123 Main St", 
		"john.doe@example.com", "+1234567890", "ACTOR_TEST_001",
	}

	stub.MockTransactionStart("create")
	response := cc.CreateCustomer(stub, args)
	stub.MockTransactionEnd("create")

	assert.Equal(t, int32(shim.ERROR), response.Status)
	assert.Contains(t, response.Message, "Access denied")
}

func TestCustomerChaincode_UpdateCustomerDetails_Success(t *testing.T) {
	cc := new(CustomerChaincode)
	stub := shimtest.NewMockStub("customer", cc)

	// Setup test actor
	testActor := shared.Actor{
		ActorID:           "ACTOR_TEST_001",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test Customer Service Rep",
		Role:              shared.RoleCustomerService,
		Permissions:       []shared.Permission{shared.PermissionCreateCustomer, shared.PermissionUpdateCustomer, shared.PermissionViewCustomer},
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}
	
	actorJSON, _ := json.Marshal(testActor)
	stub.MockTransactionStart("setup")
	stub.PutState("ACTOR_ACTOR_TEST_001", actorJSON)
	stub.MockTransactionEnd("setup")

	// Create a customer first
	createArgs := []string{
		"John", "Doe", "1990-01-15", "ID123456789", "123 Main St", 
		"john.doe@example.com", "+1234567890", "ACTOR_TEST_001",
	}

	stub.MockTransactionStart("create")
	createResponse := cc.CreateCustomer(stub, createArgs)
	stub.MockTransactionEnd("create")
	require.Equal(t, int32(shim.OK), createResponse.Status)

	customerID := string(createResponse.Payload)

	// Update customer details
	updateArgs := []string{
		customerID,                    // customerID
		"Jane",                        // firstName (changed)
		"Smith",                       // lastName (changed)
		"456 Oak Ave, New City, Country", // address (changed)
		"jane.smith@example.com",      // contactEmail (changed)
		"+9876543210",                 // contactPhone (changed)
		"",                            // status (empty, no change)
		"ACTOR_TEST_001",              // actorID
	}

	stub.MockTransactionStart("update")
	response := cc.UpdateCustomerDetails(stub, updateArgs)
	stub.MockTransactionEnd("update")

	// Verify response
	assert.Equal(t, int32(shim.OK), response.Status)

	var updatedCustomer Customer
	err := json.Unmarshal(response.Payload, &updatedCustomer)
	require.NoError(t, err)

	// Verify updated fields
	assert.Equal(t, "Jane", updatedCustomer.FirstName)
	assert.Equal(t, "Smith", updatedCustomer.LastName)
	assert.Equal(t, "456 Oak Ave, New City, Country", updatedCustomer.Address)
	assert.Equal(t, "jane.smith@example.com", updatedCustomer.ContactEmail)
	assert.Equal(t, "+9876543210", updatedCustomer.ContactPhone)
	assert.Equal(t, 2, updatedCustomer.Version) // Version should increment
	assert.Equal(t, "ACTOR_TEST_001", updatedCustomer.UpdatedByActor)
}

func TestCustomerChaincode_UpdateCustomerDetails_NoChanges(t *testing.T) {
	cc := new(CustomerChaincode)
	stub := shimtest.NewMockStub("customer", cc)

	// Setup test actor
	testActor := shared.Actor{
		ActorID:           "ACTOR_TEST_001",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test Customer Service Rep",
		Role:              shared.RoleCustomerService,
		Permissions:       []shared.Permission{shared.PermissionCreateCustomer, shared.PermissionUpdateCustomer},
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}
	
	actorJSON, _ := json.Marshal(testActor)
	stub.MockTransactionStart("setup")
	stub.PutState("ACTOR_ACTOR_TEST_001", actorJSON)
	stub.MockTransactionEnd("setup")

	// Create a customer first
	createArgs := []string{
		"John", "Doe", "1990-01-15", "ID123456789", "123 Main St", 
		"john.doe@example.com", "+1234567890", "ACTOR_TEST_001",
	}

	stub.MockTransactionStart("create")
	createResponse := cc.CreateCustomer(stub, createArgs)
	stub.MockTransactionEnd("create")
	require.Equal(t, int32(shim.OK), createResponse.Status)

	customerID := string(createResponse.Payload)

	// Update with same values (no changes)
	updateArgs := []string{
		customerID, "", "", "", "", "", "", "ACTOR_TEST_001",
	}

	stub.MockTransactionStart("update")
	response := cc.UpdateCustomerDetails(stub, updateArgs)
	stub.MockTransactionEnd("update")

	assert.Equal(t, int32(shim.OK), response.Status)
	assert.Equal(t, "No changes detected", string(response.Payload))
}

func TestCustomerChaincode_GetCustomer_Success(t *testing.T) {
	cc := new(CustomerChaincode)
	stub := shimtest.NewMockStub("customer", cc)

	// Setup test actor
	testActor := shared.Actor{
		ActorID:           "ACTOR_TEST_001",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test Customer Service Rep",
		Role:              shared.RoleCustomerService,
		Permissions:       []shared.Permission{shared.PermissionCreateCustomer, shared.PermissionViewCustomer},
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}
	
	actorJSON, _ := json.Marshal(testActor)
	stub.MockTransactionStart("setup")
	stub.PutState("ACTOR_ACTOR_TEST_001", actorJSON)
	stub.MockTransactionEnd("setup")

	// Create a customer first
	createArgs := []string{
		"John", "Doe", "1990-01-15", "ID123456789", "123 Main St", 
		"john.doe@example.com", "+1234567890", "ACTOR_TEST_001",
	}

	stub.MockTransactionStart("create")
	createResponse := cc.CreateCustomer(stub, createArgs)
	stub.MockTransactionEnd("create")
	require.Equal(t, int32(shim.OK), createResponse.Status)

	customerID := string(createResponse.Payload)

	// Get customer
	getArgs := []string{customerID, "ACTOR_TEST_001"}

	stub.MockTransactionStart("get")
	response := cc.GetCustomer(stub, getArgs)
	stub.MockTransactionEnd("get")

	// Verify response
	assert.Equal(t, int32(shim.OK), response.Status)

	var customer Customer
	err := json.Unmarshal(response.Payload, &customer)
	require.NoError(t, err)

	assert.Equal(t, customerID, customer.CustomerID)
	assert.Equal(t, "John", customer.FirstName)
	assert.Equal(t, "Doe", customer.LastName)
}

func TestCustomerChaincode_GetCustomer_NotFound(t *testing.T) {
	cc := new(CustomerChaincode)
	stub := shimtest.NewMockStub("customer", cc)

	// Setup test actor
	testActor := shared.Actor{
		ActorID:           "ACTOR_TEST_001",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test User",
		Role:              shared.RoleCustomerService,
		Permissions:       []shared.Permission{shared.PermissionViewCustomer},
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}
	
	actorJSON, _ := json.Marshal(testActor)
	stub.MockTransactionStart("setup")
	stub.PutState("ACTOR_ACTOR_TEST_001", actorJSON)
	stub.MockTransactionEnd("setup")

	// Try to get non-existent customer
	getArgs := []string{"NONEXISTENT_ID", "ACTOR_TEST_001"}

	stub.MockTransactionStart("get")
	response := cc.GetCustomer(stub, getArgs)
	stub.MockTransactionEnd("get")

	assert.Equal(t, int32(shim.ERROR), response.Status)
	assert.Contains(t, response.Message, "Customer not found")
}

func TestCustomerChaincode_GetCustomerHistory_Success(t *testing.T) {
	cc := new(CustomerChaincode)
	stub := shimtest.NewMockStub("customer", cc)

	// Setup test actor
	testActor := shared.Actor{
		ActorID:           "ACTOR_TEST_001",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test Customer Service Rep",
		Role:              shared.RoleCustomerService,
		Permissions:       []shared.Permission{shared.PermissionCreateCustomer, shared.PermissionUpdateCustomer, shared.PermissionViewCustomer},
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}
	
	actorJSON, _ := json.Marshal(testActor)
	stub.MockTransactionStart("setup")
	stub.PutState("ACTOR_ACTOR_TEST_001", actorJSON)
	stub.MockTransactionEnd("setup")

	// Create a customer first
	createArgs := []string{
		"John", "Doe", "1990-01-15", "ID123456789", "123 Main St", 
		"john.doe@example.com", "+1234567890", "ACTOR_TEST_001",
	}

	stub.MockTransactionStart("create")
	createResponse := cc.CreateCustomer(stub, createArgs)
	stub.MockTransactionEnd("create")
	require.Equal(t, int32(shim.OK), createResponse.Status)

	customerID := string(createResponse.Payload)

	// Update customer to create history
	updateArgs := []string{
		customerID, "Jane", "", "", "", "", "", "ACTOR_TEST_001",
	}

	stub.MockTransactionStart("update")
	updateResponse := cc.UpdateCustomerDetails(stub, updateArgs)
	stub.MockTransactionEnd("update")
	require.Equal(t, int32(shim.OK), updateResponse.Status)

	// Get customer history
	historyArgs := []string{customerID, "ACTOR_TEST_001"}

	stub.MockTransactionStart("history")
	response := cc.GetCustomerHistory(stub, historyArgs)
	stub.MockTransactionEnd("history")

	// Verify response
	assert.Equal(t, int32(shim.OK), response.Status)

	var history []shared.HistoryEntry
	err := json.Unmarshal(response.Payload, &history)
	require.NoError(t, err)

	// Should have at least 2 history entries (create + update)
	assert.GreaterOrEqual(t, len(history), 2)
}

func TestCustomerChaincode_InvalidFunction(t *testing.T) {
	cc := new(CustomerChaincode)
	stub := shimtest.NewMockStub("customer", cc)

	stub.MockTransactionStart("invalid")
	response := stub.MockInvoke("1", [][]byte{[]byte("InvalidFunction")})
	stub.MockTransactionEnd("invalid")

	assert.Equal(t, int32(shim.ERROR), response.Status)
	assert.Contains(t, response.Message, "Invalid function name")
}

func TestCustomerChaincode_Ping(t *testing.T) {
	cc := new(CustomerChaincode)
	stub := shimtest.NewMockStub("customer", cc)

	stub.MockTransactionStart("ping")
	response := stub.MockInvoke("1", [][]byte{[]byte("ping")})
	stub.MockTransactionEnd("ping")

	assert.Equal(t, int32(shim.OK), response.Status)
	assert.Equal(t, "pong", string(response.Payload))
}

// ============================================================================
// CONSENT MANAGEMENT TESTS
// ============================================================================

func TestCustomerChaincode_RecordConsent_Success(t *testing.T) {
	cc := new(CustomerChaincode)
	stub := shimtest.NewMockStub("customer", cc)

	// Setup test actor
	testActor := shared.Actor{
		ActorID:           "ACTOR_TEST_001",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test Customer Service Rep",
		Role:              shared.RoleCustomerService,
		Permissions:       []shared.Permission{shared.PermissionCreateCustomer, shared.PermissionUpdateCustomer, shared.PermissionViewCustomer},
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}
	
	actorJSON, _ := json.Marshal(testActor)
	stub.MockTransactionStart("setup")
	stub.PutState("ACTOR_ACTOR_TEST_001", actorJSON)
	stub.MockTransactionEnd("setup")

	// Create a customer first
	createArgs := []string{
		"John", "Doe", "1990-01-15", "ID123456789", "123 Main St", 
		"john.doe@example.com", "+1234567890", "ACTOR_TEST_001",
	}

	stub.MockTransactionStart("create")
	createResponse := cc.CreateCustomer(stub, createArgs)
	stub.MockTransactionEnd("create")
	require.Equal(t, int32(shim.OK), createResponse.Status)

	customerID := string(createResponse.Payload)

	// Record consent
	consentArgs := []string{
		customerID,        // customerID
		"true",           // dataSharing
		"false",          // marketingCommunication
		"true",           // thirdPartySharing
		"true",           // creditBureauSharing
		"true",           // regulatoryReporting
		"v1.0",           // consentVersion
		"192.168.1.1",    // ipAddress
		"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", // userAgent
		"ACTOR_TEST_001", // actorID
	}

	stub.MockTransactionStart("consent")
	response := cc.RecordConsent(stub, consentArgs)
	stub.MockTransactionEnd("consent")

	// Verify response
	assert.Equal(t, int32(shim.OK), response.Status)

	var consentPrefs ConsentPreferences
	err := json.Unmarshal(response.Payload, &consentPrefs)
	require.NoError(t, err)

	// Verify consent preferences
	assert.True(t, consentPrefs.DataSharing)
	assert.False(t, consentPrefs.MarketingCommunication)
	assert.True(t, consentPrefs.ThirdPartySharing)
	assert.True(t, consentPrefs.CreditBureauSharing)
	assert.True(t, consentPrefs.RegulatoryReporting)
	assert.Equal(t, "v1.0", consentPrefs.ConsentVersion)
	assert.Equal(t, "192.168.1.1", consentPrefs.IPAddress)
	assert.NotEmpty(t, consentPrefs.UserAgent)
	assert.False(t, consentPrefs.ConsentDate.IsZero())
	assert.False(t, consentPrefs.ExpiryDate.IsZero())
	assert.True(t, consentPrefs.ExpiryDate.After(consentPrefs.ConsentDate))

	// Verify customer was updated
	customerData, err := stub.GetState(customerID)
	require.NoError(t, err)

	var customer Customer
	err = json.Unmarshal(customerData, &customer)
	require.NoError(t, err)

	assert.NotEqual(t, "{}", customer.ConsentPreferences)
	assert.Equal(t, 2, customer.Version) // Should increment
}

func TestCustomerChaincode_RecordConsent_ValidationErrors(t *testing.T) {
	cc := new(CustomerChaincode)
	stub := shimtest.NewMockStub("customer", cc)

	// Setup test actor
	testActor := shared.Actor{
		ActorID:           "ACTOR_TEST_001",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test Customer Service Rep",
		Role:              shared.RoleCustomerService,
		Permissions:       []shared.Permission{shared.PermissionCreateCustomer, shared.PermissionUpdateCustomer},
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}
	
	actorJSON, _ := json.Marshal(testActor)
	stub.MockTransactionStart("setup")
	stub.PutState("ACTOR_ACTOR_TEST_001", actorJSON)
	stub.MockTransactionEnd("setup")

	// Create a customer first
	createArgs := []string{
		"John", "Doe", "1990-01-15", "ID123456789", "123 Main St", 
		"john.doe@example.com", "+1234567890", "ACTOR_TEST_001",
	}

	stub.MockTransactionStart("create")
	createResponse := cc.CreateCustomer(stub, createArgs)
	stub.MockTransactionEnd("create")
	require.Equal(t, int32(shim.OK), createResponse.Status)

	customerID := string(createResponse.Payload)

	tests := []struct {
		name string
		args []string
		expectedError string
	}{
		{
			name: "Insufficient arguments",
			args: []string{customerID, "true", "false"},
			expectedError: "Incorrect number of arguments",
		},
		{
			name: "Empty consent version",
			args: []string{customerID, "true", "false", "true", "true", "true", "", "192.168.1.1", "Mozilla/5.0", "ACTOR_TEST_001"},
			expectedError: "required field 'consentVersion' is empty",
		},
		{
			name: "Empty IP address",
			args: []string{customerID, "true", "false", "true", "true", "true", "v1.0", "", "Mozilla/5.0", "ACTOR_TEST_001"},
			expectedError: "required field 'ipAddress' is empty",
		},
		{
			name: "Empty user agent",
			args: []string{customerID, "true", "false", "true", "true", "true", "v1.0", "192.168.1.1", "", "ACTOR_TEST_001"},
			expectedError: "required field 'userAgent' is empty",
		},
		{
			name: "Invalid IP address (too short)",
			args: []string{customerID, "true", "false", "true", "true", "true", "v1.0", "1.1", "Mozilla/5.0", "ACTOR_TEST_001"},
			expectedError: "Invalid IP address",
		},
		{
			name: "Invalid user agent (too short)",
			args: []string{customerID, "true", "false", "true", "true", "true", "v1.0", "192.168.1.1", "short", "ACTOR_TEST_001"},
			expectedError: "Invalid user agent",
		},
		{
			name: "Non-existent customer",
			args: []string{"NONEXISTENT_ID", "true", "false", "true", "true", "true", "v1.0", "192.168.1.1", "Mozilla/5.0", "ACTOR_TEST_001"},
			expectedError: "Customer not found",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			stub.MockTransactionStart(tt.name)
			response := cc.RecordConsent(stub, tt.args)
			stub.MockTransactionEnd(tt.name)

			assert.Equal(t, int32(shim.ERROR), response.Status)
			assert.Contains(t, response.Message, tt.expectedError)
		})
	}
}

func TestCustomerChaincode_UpdateConsent_Success(t *testing.T) {
	cc := new(CustomerChaincode)
	stub := shimtest.NewMockStub("customer", cc)

	// Setup test actor
	testActor := shared.Actor{
		ActorID:           "ACTOR_TEST_001",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test Customer Service Rep",
		Role:              shared.RoleCustomerService,
		Permissions:       []shared.Permission{shared.PermissionCreateCustomer, shared.PermissionUpdateCustomer, shared.PermissionViewCustomer},
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}
	
	actorJSON, _ := json.Marshal(testActor)
	stub.MockTransactionStart("setup")
	stub.PutState("ACTOR_ACTOR_TEST_001", actorJSON)
	stub.MockTransactionEnd("setup")

	// Create a customer first
	createArgs := []string{
		"John", "Doe", "1990-01-15", "ID123456789", "123 Main St", 
		"john.doe@example.com", "+1234567890", "ACTOR_TEST_001",
	}

	stub.MockTransactionStart("create")
	createResponse := cc.CreateCustomer(stub, createArgs)
	stub.MockTransactionEnd("create")
	require.Equal(t, int32(shim.OK), createResponse.Status)

	customerID := string(createResponse.Payload)

	// Record initial consent
	initialConsentArgs := []string{
		customerID, "true", "false", "true", "true", "true", "v1.0", 
		"192.168.1.1", "Mozilla/5.0", "ACTOR_TEST_001",
	}

	stub.MockTransactionStart("initial_consent")
	initialResponse := cc.RecordConsent(stub, initialConsentArgs)
	stub.MockTransactionEnd("initial_consent")
	require.Equal(t, int32(shim.OK), initialResponse.Status)

	// Update consent with different preferences
	updateConsentArgs := []string{
		customerID,        // customerID
		"false",          // dataSharing (changed)
		"true",           // marketingCommunication (changed)
		"false",          // thirdPartySharing (changed)
		"true",           // creditBureauSharing
		"true",           // regulatoryReporting
		"v1.1",           // consentVersion (updated)
		"192.168.1.2",    // ipAddress (changed)
		"Mozilla/5.0 (Updated)", // userAgent (changed)
		"ACTOR_TEST_001", // actorID
	}

	stub.MockTransactionStart("update_consent")
	response := cc.UpdateConsent(stub, updateConsentArgs)
	stub.MockTransactionEnd("update_consent")

	// Verify response
	assert.Equal(t, int32(shim.OK), response.Status)

	var updatedConsentPrefs ConsentPreferences
	err := json.Unmarshal(response.Payload, &updatedConsentPrefs)
	require.NoError(t, err)

	// Verify updated consent preferences
	assert.False(t, updatedConsentPrefs.DataSharing) // Changed
	assert.True(t, updatedConsentPrefs.MarketingCommunication) // Changed
	assert.False(t, updatedConsentPrefs.ThirdPartySharing) // Changed
	assert.True(t, updatedConsentPrefs.CreditBureauSharing) // Same
	assert.True(t, updatedConsentPrefs.RegulatoryReporting) // Same
	assert.Equal(t, "v1.1", updatedConsentPrefs.ConsentVersion)
	assert.Equal(t, "192.168.1.2", updatedConsentPrefs.IPAddress)
	assert.Contains(t, updatedConsentPrefs.UserAgent, "Updated")

	// Verify customer was updated
	customerData, err := stub.GetState(customerID)
	require.NoError(t, err)

	var customer Customer
	err = json.Unmarshal(customerData, &customer)
	require.NoError(t, err)

	assert.Equal(t, 3, customer.Version) // Should increment again
}

func TestCustomerChaincode_GetConsent_Success(t *testing.T) {
	cc := new(CustomerChaincode)
	stub := shimtest.NewMockStub("customer", cc)

	// Setup test actor
	testActor := shared.Actor{
		ActorID:           "ACTOR_TEST_001",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test Customer Service Rep",
		Role:              shared.RoleCustomerService,
		Permissions:       []shared.Permission{shared.PermissionCreateCustomer, shared.PermissionUpdateCustomer, shared.PermissionViewCustomer},
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}
	
	actorJSON, _ := json.Marshal(testActor)
	stub.MockTransactionStart("setup")
	stub.PutState("ACTOR_ACTOR_TEST_001", actorJSON)
	stub.MockTransactionEnd("setup")

	// Create a customer first
	createArgs := []string{
		"John", "Doe", "1990-01-15", "ID123456789", "123 Main St", 
		"john.doe@example.com", "+1234567890", "ACTOR_TEST_001",
	}

	stub.MockTransactionStart("create")
	createResponse := cc.CreateCustomer(stub, createArgs)
	stub.MockTransactionEnd("create")
	require.Equal(t, int32(shim.OK), createResponse.Status)

	customerID := string(createResponse.Payload)

	// Record consent
	consentArgs := []string{
		customerID, "true", "false", "true", "true", "true", "v1.0", 
		"192.168.1.1", "Mozilla/5.0", "ACTOR_TEST_001",
	}

	stub.MockTransactionStart("consent")
	consentResponse := cc.RecordConsent(stub, consentArgs)
	stub.MockTransactionEnd("consent")
	require.Equal(t, int32(shim.OK), consentResponse.Status)

	// Get consent
	getConsentArgs := []string{customerID, "ACTOR_TEST_001"}

	stub.MockTransactionStart("get_consent")
	response := cc.GetConsent(stub, getConsentArgs)
	stub.MockTransactionEnd("get_consent")

	// Verify response
	assert.Equal(t, int32(shim.OK), response.Status)

	var consentPrefs ConsentPreferences
	err := json.Unmarshal(response.Payload, &consentPrefs)
	require.NoError(t, err)

	// Verify consent preferences match what was recorded
	assert.True(t, consentPrefs.DataSharing)
	assert.False(t, consentPrefs.MarketingCommunication)
	assert.True(t, consentPrefs.ThirdPartySharing)
	assert.True(t, consentPrefs.CreditBureauSharing)
	assert.True(t, consentPrefs.RegulatoryReporting)
	assert.Equal(t, "v1.0", consentPrefs.ConsentVersion)
	assert.Equal(t, "192.168.1.1", consentPrefs.IPAddress)
}

func TestCustomerChaincode_GetConsent_EmptyConsent(t *testing.T) {
	cc := new(CustomerChaincode)
	stub := shimtest.NewMockStub("customer", cc)

	// Setup test actor
	testActor := shared.Actor{
		ActorID:           "ACTOR_TEST_001",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test Customer Service Rep",
		Role:              shared.RoleCustomerService,
		Permissions:       []shared.Permission{shared.PermissionCreateCustomer, shared.PermissionViewCustomer},
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}
	
	actorJSON, _ := json.Marshal(testActor)
	stub.MockTransactionStart("setup")
	stub.PutState("ACTOR_ACTOR_TEST_001", actorJSON)
	stub.MockTransactionEnd("setup")

	// Create a customer without recording consent
	createArgs := []string{
		"John", "Doe", "1990-01-15", "ID123456789", "123 Main St", 
		"john.doe@example.com", "+1234567890", "ACTOR_TEST_001",
	}

	stub.MockTransactionStart("create")
	createResponse := cc.CreateCustomer(stub, createArgs)
	stub.MockTransactionEnd("create")
	require.Equal(t, int32(shim.OK), createResponse.Status)

	customerID := string(createResponse.Payload)

	// Get consent (should return empty consent)
	getConsentArgs := []string{customerID, "ACTOR_TEST_001"}

	stub.MockTransactionStart("get_consent")
	response := cc.GetConsent(stub, getConsentArgs)
	stub.MockTransactionEnd("get_consent")

	// Verify response
	assert.Equal(t, int32(shim.OK), response.Status)

	var consentPrefs ConsentPreferences
	err := json.Unmarshal(response.Payload, &consentPrefs)
	require.NoError(t, err)

	// Verify empty consent preferences
	assert.False(t, consentPrefs.DataSharing)
	assert.False(t, consentPrefs.MarketingCommunication)
	assert.False(t, consentPrefs.ThirdPartySharing)
	assert.False(t, consentPrefs.CreditBureauSharing)
	assert.False(t, consentPrefs.RegulatoryReporting)
	assert.Empty(t, consentPrefs.ConsentVersion)
	assert.Empty(t, consentPrefs.IPAddress)
}

func TestCustomerChaincode_GetConsent_AccessDenied(t *testing.T) {
	cc := new(CustomerChaincode)
	stub := shimtest.NewMockStub("customer", cc)

	// Setup test actor without view permission
	testActor := shared.Actor{
		ActorID:           "ACTOR_TEST_001",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test User",
		Role:              shared.RoleUnderwriter,
		Permissions:       []shared.Permission{}, // No view permission
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}
	
	actorJSON, _ := json.Marshal(testActor)
	stub.MockTransactionStart("setup")
	stub.PutState("ACTOR_ACTOR_TEST_001", actorJSON)
	stub.MockTransactionEnd("setup")

	// Try to get consent without permission
	getConsentArgs := []string{"SOME_CUSTOMER_ID", "ACTOR_TEST_001"}

	stub.MockTransactionStart("get_consent")
	response := cc.GetConsent(stub, getConsentArgs)
	stub.MockTransactionEnd("get_consent")

	assert.Equal(t, int32(shim.ERROR), response.Status)
	assert.Contains(t, response.Message, "Access denied")
}

func TestCustomerChaincode_ValidateConsentForDataSharing_Success(t *testing.T) {
	cc := new(CustomerChaincode)
	stub := shimtest.NewMockStub("customer", cc)

	// Setup test actor
	testActor := shared.Actor{
		ActorID:           "ACTOR_TEST_001",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test Customer Service Rep",
		Role:              shared.RoleCustomerService,
		Permissions:       []shared.Permission{shared.PermissionCreateCustomer, shared.PermissionUpdateCustomer},
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}
	
	actorJSON, _ := json.Marshal(testActor)
	stub.MockTransactionStart("setup")
	stub.PutState("ACTOR_ACTOR_TEST_001", actorJSON)
	stub.MockTransactionEnd("setup")

	// Create a customer first
	createArgs := []string{
		"John", "Doe", "1990-01-15", "ID123456789", "123 Main St", 
		"john.doe@example.com", "+1234567890", "ACTOR_TEST_001",
	}

	stub.MockTransactionStart("create")
	createResponse := cc.CreateCustomer(stub, createArgs)
	stub.MockTransactionEnd("create")
	require.Equal(t, int32(shim.OK), createResponse.Status)

	customerID := string(createResponse.Payload)

	// Record consent with data sharing enabled
	consentArgs := []string{
		customerID, "true", "false", "true", "true", "true", "v1.0", 
		"192.168.1.1", "Mozilla/5.0", "ACTOR_TEST_001",
	}

	stub.MockTransactionStart("consent")
	consentResponse := cc.RecordConsent(stub, consentArgs)
	stub.MockTransactionEnd("consent")
	require.Equal(t, int32(shim.OK), consentResponse.Status)

	// Test various operation types
	operationTypes := []string{
		"DATA_SHARING",
		"THIRD_PARTY_SHARING",
		"CREDIT_BUREAU_SHARING",
		"REGULATORY_REPORTING",
	}

	for _, opType := range operationTypes {
		t.Run("ValidateConsent_"+opType, func(t *testing.T) {
			err := cc.ValidateConsentForDataSharing(stub, customerID, opType)
			assert.NoError(t, err)
		})
	}

	// Test operation type that should fail (marketing communication was set to false)
	t.Run("ValidateConsent_MARKETING_COMMUNICATION_Denied", func(t *testing.T) {
		err := cc.ValidateConsentForDataSharing(stub, customerID, "MARKETING_COMMUNICATION")
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "has not consented to marketing communication")
	})
}

func TestCustomerChaincode_ValidateConsentForDataSharing_Failures(t *testing.T) {
	cc := new(CustomerChaincode)
	stub := shimtest.NewMockStub("customer", cc)

	// Setup test actor
	testActor := shared.Actor{
		ActorID:           "ACTOR_TEST_001",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test Customer Service Rep",
		Role:              shared.RoleCustomerService,
		Permissions:       []shared.Permission{shared.PermissionCreateCustomer, shared.PermissionUpdateCustomer},
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}
	
	actorJSON, _ := json.Marshal(testActor)
	stub.MockTransactionStart("setup")
	stub.PutState("ACTOR_ACTOR_TEST_001", actorJSON)
	stub.MockTransactionEnd("setup")

	// Create a customer first
	createArgs := []string{
		"John", "Doe", "1990-01-15", "ID123456789", "123 Main St", 
		"john.doe@example.com", "+1234567890", "ACTOR_TEST_001",
	}

	stub.MockTransactionStart("create")
	createResponse := cc.CreateCustomer(stub, createArgs)
	stub.MockTransactionEnd("create")
	require.Equal(t, int32(shim.OK), createResponse.Status)

	customerID := string(createResponse.Payload)

	tests := []struct {
		name string
		setupConsent bool
		consentArgs []string
		operationType string
		expectedError string
	}{
		{
			name: "No consent preferences",
			setupConsent: false,
			operationType: "DATA_SHARING",
			expectedError: "no consent preferences found",
		},
		{
			name: "Data sharing denied",
			setupConsent: true,
			consentArgs: []string{customerID, "false", "false", "false", "false", "false", "v1.0", "192.168.1.1", "Mozilla/5.0", "ACTOR_TEST_001"},
			operationType: "DATA_SHARING",
			expectedError: "has not consented to data sharing",
		},
		{
			name: "Unknown operation type",
			setupConsent: true,
			consentArgs: []string{customerID, "true", "true", "true", "true", "true", "v1.0", "192.168.1.1", "Mozilla/5.0", "ACTOR_TEST_001"},
			operationType: "UNKNOWN_OPERATION",
			expectedError: "unknown operation type",
		},
		{
			name: "Non-existent customer",
			setupConsent: false,
			operationType: "DATA_SHARING",
			expectedError: "customer not found",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			testCustomerID := customerID
			if tt.name == "Non-existent customer" {
				testCustomerID = "NONEXISTENT_ID"
			}

			if tt.setupConsent {
				stub.MockTransactionStart("setup_consent_"+tt.name)
				consentResponse := cc.RecordConsent(stub, tt.consentArgs)
				stub.MockTransactionEnd("setup_consent_"+tt.name)
				require.Equal(t, int32(shim.OK), consentResponse.Status)
			}

			err := cc.ValidateConsentForDataSharing(stub, testCustomerID, tt.operationType)
			assert.Error(t, err)
			assert.Contains(t, err.Error(), tt.expectedError)
		})
	}
}

func TestCustomerChaincode_GetCustomer_WithConsentValidation(t *testing.T) {
	cc := new(CustomerChaincode)
	stub := shimtest.NewMockStub("customer", cc)

	// Setup internal actor
	internalActor := shared.Actor{
		ActorID:           "ACTOR_INTERNAL_001",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Internal User",
		Role:              shared.RoleCustomerService,
		Permissions:       []shared.Permission{shared.PermissionCreateCustomer, shared.PermissionUpdateCustomer, shared.PermissionViewCustomer},
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}

	// Setup external actor
	externalActor := shared.Actor{
		ActorID:           "ACTOR_EXTERNAL_001",
		ActorType:         shared.ActorTypeExternalPartner,
		ActorName:         "External Partner",
		Role:              shared.RoleIntroducer,
		Permissions:       []shared.Permission{shared.PermissionViewCustomer},
		IsActive:          true,
		CreatedDate:       time.Now(),
		LastUpdated:       time.Now(),
	}
	
	internalActorJSON, _ := json.Marshal(internalActor)
	externalActorJSON, _ := json.Marshal(externalActor)
	stub.MockTransactionStart("setup")
	stub.PutState("ACTOR_ACTOR_INTERNAL_001", internalActorJSON)
	stub.PutState("ACTOR_ACTOR_EXTERNAL_001", externalActorJSON)
	stub.MockTransactionEnd("setup")

	// Create a customer
	createArgs := []string{
		"John", "Doe", "1990-01-15", "ID123456789", "123 Main St", 
		"john.doe@example.com", "+1234567890", "ACTOR_INTERNAL_001",
	}

	stub.MockTransactionStart("create")
	createResponse := cc.CreateCustomer(stub, createArgs)
	stub.MockTransactionEnd("create")
	require.Equal(t, int32(shim.OK), createResponse.Status)

	customerID := string(createResponse.Payload)

	// Record consent with data sharing enabled
	consentArgs := []string{
		customerID, "true", "false", "true", "true", "true", "v1.0", 
		"192.168.1.1", "Mozilla/5.0", "ACTOR_INTERNAL_001",
	}

	stub.MockTransactionStart("consent")
	consentResponse := cc.RecordConsent(stub, consentArgs)
	stub.MockTransactionEnd("consent")
	require.Equal(t, int32(shim.OK), consentResponse.Status)

	// Test internal actor access (should work without consent validation)
	t.Run("Internal_Actor_No_Consent_Validation", func(t *testing.T) {
		getArgs := []string{customerID, "ACTOR_INTERNAL_001", "true"}

		stub.MockTransactionStart("get_internal")
		response := cc.GetCustomer(stub, getArgs)
		stub.MockTransactionEnd("get_internal")

		assert.Equal(t, int32(shim.OK), response.Status)
	})

	// Test external actor access with consent validation (should work)
	t.Run("External_Actor_With_Consent", func(t *testing.T) {
		getArgs := []string{customerID, "ACTOR_EXTERNAL_001", "true"}

		stub.MockTransactionStart("get_external_with_consent")
		response := cc.GetCustomer(stub, getArgs)
		stub.MockTransactionEnd("get_external_with_consent")

		assert.Equal(t, int32(shim.OK), response.Status)
	})

	// Test external actor access without consent validation (should work)
	t.Run("External_Actor_Without_Consent_Validation", func(t *testing.T) {
		getArgs := []string{customerID, "ACTOR_EXTERNAL_001", "false"}

		stub.MockTransactionStart("get_external_no_validation")
		response := cc.GetCustomer(stub, getArgs)
		stub.MockTransactionEnd("get_external_no_validation")

		assert.Equal(t, int32(shim.OK), response.Status)
	})

	// Update consent to deny data sharing
	updateConsentArgs := []string{
		customerID, "false", "false", "false", "false", "false", "v1.1", 
		"192.168.1.1", "Mozilla/5.0", "ACTOR_INTERNAL_001",
	}

	stub.MockTransactionStart("update_consent")
	updateResponse := cc.UpdateConsent(stub, updateConsentArgs)
	stub.MockTransactionEnd("update_consent")
	require.Equal(t, int32(shim.OK), updateResponse.Status)

	// Test external actor access with consent validation (should fail now)
	t.Run("External_Actor_Consent_Denied", func(t *testing.T) {
		getArgs := []string{customerID, "ACTOR_EXTERNAL_001", "true"}

		stub.MockTransactionStart("get_external_denied")
		response := cc.GetCustomer(stub, getArgs)
		stub.MockTransactionEnd("get_external_denied")

		assert.Equal(t, int32(shim.ERROR), response.Status)
		assert.Contains(t, response.Message, "Consent validation failed")
	})
}