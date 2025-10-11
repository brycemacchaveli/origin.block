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