package tests

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/hyperledger/fabric-chaincode-go/shimtest"
	"github.com/stretchr/testify/assert"
	"github.com/blockchain-financial-platform/fabric-chaincode/customer/chaincode"
	"github.com/blockchain-financial-platform/fabric-chaincode/customer/domain"
)

func TestCustomerRegistrationFlow(t *testing.T) {
	// Create a new mock stub
	stub := shimtest.NewMockStub("customer", &chaincode.CustomerContract{})
	
	// Test customer registration
	registrationReq := domain.CustomerRegistrationRequest{
		FirstName:          "John",
		LastName:           "Doe",
		Email:              "john.doe@example.com",
		Phone:              "+1234567890",
		DateOfBirth:        time.Date(1990, 1, 1, 0, 0, 0, 0, time.UTC),
		NationalID:         "ID123456789",
		Address:            "123 Main Street, City, Country",
		ConsentPreferences: `{"marketing": true, "analytics": false}`,
		ActorID:            "ACTOR_001",
	}
	
	reqBytes, err := json.Marshal(registrationReq)
	assert.NoError(t, err)
	
	// Invoke RegisterCustomer
	response := stub.MockInvoke("1", [][]byte{
		[]byte("RegisterCustomer"),
		reqBytes,
	})
	
	assert.Equal(t, int32(shim.OK), response.Status)
	assert.NotEmpty(t, response.Payload)
	
	// Parse the response
	var customer domain.Customer
	err = json.Unmarshal(response.Payload, &customer)
	assert.NoError(t, err)
	assert.Equal(t, "John", customer.FirstName)
	assert.Equal(t, "Doe", customer.LastName)
	assert.Equal(t, "john.doe@example.com", customer.Email)
	assert.NotEmpty(t, customer.CustomerID)
	
	// Test getting the customer
	getResponse := stub.MockInvoke("2", [][]byte{
		[]byte("GetCustomer"),
		[]byte(customer.CustomerID),
	})
	
	assert.Equal(t, int32(shim.OK), getResponse.Status)
	
	var retrievedCustomer domain.Customer
	err = json.Unmarshal(getResponse.Payload, &retrievedCustomer)
	assert.NoError(t, err)
	assert.Equal(t, customer.CustomerID, retrievedCustomer.CustomerID)
	assert.Equal(t, customer.Email, retrievedCustomer.Email)
}

func TestCustomerUpdateFlow(t *testing.T) {
	stub := shimtest.NewMockStub("customer", &chaincode.CustomerContract{})
	
	// First register a customer
	registrationReq := domain.CustomerRegistrationRequest{
		FirstName:          "Jane",
		LastName:           "Smith",
		Email:              "jane.smith@example.com",
		Phone:              "+1987654321",
		DateOfBirth:        time.Date(1985, 5, 15, 0, 0, 0, 0, time.UTC),
		NationalID:         "ID987654321",
		Address:            "456 Oak Avenue, City, Country",
		ConsentPreferences: `{"marketing": false, "analytics": true}`,
		ActorID:            "ACTOR_002",
	}
	
	reqBytes, err := json.Marshal(registrationReq)
	assert.NoError(t, err)
	
	response := stub.MockInvoke("1", [][]byte{
		[]byte("RegisterCustomer"),
		reqBytes,
	})
	
	assert.Equal(t, int32(shim.OK), response.Status)
	
	var customer domain.Customer
	err = json.Unmarshal(response.Payload, &customer)
	assert.NoError(t, err)
	
	// Now update the customer
	newEmail := "jane.smith.updated@example.com"
	newPhone := "+1555666777"
	
	updateReq := domain.CustomerUpdateRequest{
		CustomerID: customer.CustomerID,
		Email:      &newEmail,
		Phone:      &newPhone,
		ActorID:    "ACTOR_002",
	}
	
	updateBytes, err := json.Marshal(updateReq)
	assert.NoError(t, err)
	
	updateResponse := stub.MockInvoke("2", [][]byte{
		[]byte("UpdateCustomer"),
		updateBytes,
	})
	
	assert.Equal(t, int32(shim.OK), updateResponse.Status)
	
	var updatedCustomer domain.Customer
	err = json.Unmarshal(updateResponse.Payload, &updatedCustomer)
	assert.NoError(t, err)
	assert.Equal(t, newEmail, updatedCustomer.Email)
	assert.Equal(t, newPhone, updatedCustomer.Phone)
	assert.Equal(t, customer.FirstName, updatedCustomer.FirstName) // Should remain unchanged
}

func TestCustomerValidation(t *testing.T) {
	stub := shimtest.NewMockStub("customer", &chaincode.CustomerContract{})
	
	// Test registration with invalid email
	registrationReq := domain.CustomerRegistrationRequest{
		FirstName:          "Invalid",
		LastName:           "Email",
		Email:              "invalid-email",
		Phone:              "+1234567890",
		DateOfBirth:        time.Date(1990, 1, 1, 0, 0, 0, 0, time.UTC),
		NationalID:         "ID123456789",
		Address:            "123 Main Street, City, Country",
		ConsentPreferences: `{"marketing": true}`,
		ActorID:            "ACTOR_003",
	}
	
	reqBytes, err := json.Marshal(registrationReq)
	assert.NoError(t, err)
	
	response := stub.MockInvoke("1", [][]byte{
		[]byte("RegisterCustomer"),
		reqBytes,
	})
	
	// Should fail due to invalid email
	assert.Equal(t, int32(shim.ERROR), response.Status)
	assert.Contains(t, response.Message, "validation failed")
}

func TestDuplicateCustomerRegistration(t *testing.T) {
	stub := shimtest.NewMockStub("customer", &chaincode.CustomerContract{})
	
	registrationReq := domain.CustomerRegistrationRequest{
		FirstName:          "Duplicate",
		LastName:           "Test",
		Email:              "duplicate@example.com",
		Phone:              "+1234567890",
		DateOfBirth:        time.Date(1990, 1, 1, 0, 0, 0, 0, time.UTC),
		NationalID:         "DUPLICATE123",
		Address:            "123 Main Street, City, Country",
		ConsentPreferences: `{"marketing": true}`,
		ActorID:            "ACTOR_004",
	}
	
	reqBytes, err := json.Marshal(registrationReq)
	assert.NoError(t, err)
	
	// First registration should succeed
	response1 := stub.MockInvoke("1", [][]byte{
		[]byte("RegisterCustomer"),
		reqBytes,
	})
	assert.Equal(t, int32(shim.OK), response1.Status)
	
	// Second registration with same national ID should fail
	response2 := stub.MockInvoke("2", [][]byte{
		[]byte("RegisterCustomer"),
		reqBytes,
	})
	assert.Equal(t, int32(shim.ERROR), response2.Status)
	assert.Contains(t, response2.Message, "already exists")
}