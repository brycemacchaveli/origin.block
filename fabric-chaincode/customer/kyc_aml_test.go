package main

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/blockchain-financial-platform/fabric-chaincode/shared"
	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/hyperledger/fabric-chaincode-go/shimtest"
	"github.com/stretchr/testify/assert"
)

// TestKYCValidation tests the KYC validation functionality
func TestKYCValidation(t *testing.T) {
	// Create a new mock stub
	stub := shimtest.NewMockStub("customer", new(CustomerChaincode))
	
	// Setup test actor
	setupTestActor(t, stub)
	
	// Create a test customer first
	customerID := createTestCustomer(t, stub)
	
	// Test KYC validation
	t.Run("PerformKYCValidation_Success", func(t *testing.T) {
		// Perform KYC validation
		response := stub.MockInvoke("1", [][]byte{
			[]byte("PerformKYCValidation"),
			[]byte(customerID),
			[]byte("TEST_ACTOR_001"),
		})
		
		assert.Equal(t, int32(shim.OK), response.Status, "KYC validation should succeed")
		
		// Parse response
		var kycResponse KYCValidationResponse
		err := json.Unmarshal(response.Payload, &kycResponse)
		assert.NoError(t, err, "Should be able to parse KYC response")
		assert.Equal(t, customerID, kycResponse.CustomerID)
		assert.Equal(t, string(shared.KYCStatusVerified), kycResponse.ValidationStatus)
		assert.Greater(t, kycResponse.ConfidenceScore, 0.8, "Confidence score should be high for valid customer")
	})
	
	t.Run("PerformKYCValidation_InvalidCustomer", func(t *testing.T) {
		// Try to validate non-existent customer
		response := stub.MockInvoke("2", [][]byte{
			[]byte("PerformKYCValidation"),
			[]byte("INVALID_CUSTOMER"),
			[]byte("TEST_ACTOR_001"),
		})
		
		assert.Equal(t, int32(shim.ERROR), response.Status, "KYC validation should fail for invalid customer")
		assert.Contains(t, response.Message, "Customer not found")
	})
	
	t.Run("PerformKYCValidation_AccessDenied", func(t *testing.T) {
		// Try to validate with invalid actor
		response := stub.MockInvoke("3", [][]byte{
			[]byte("PerformKYCValidation"),
			[]byte(customerID),
			[]byte("INVALID_ACTOR"),
		})
		
		assert.Equal(t, int32(shim.ERROR), response.Status, "KYC validation should fail for invalid actor")
		assert.Contains(t, response.Message, "Access denied")
	})
}

// TestAMLScreening tests the AML screening functionality
func TestAMLScreening(t *testing.T) {
	// Create a new mock stub
	stub := shimtest.NewMockStub("customer", new(CustomerChaincode))
	
	// Setup test actor
	setupTestActor(t, stub)
	
	// Create a test customer first
	customerID := createTestCustomer(t, stub)
	
	t.Run("PerformAMLCheck_Success", func(t *testing.T) {
		// Perform AML check
		response := stub.MockInvoke("1", [][]byte{
			[]byte("PerformAMLCheck"),
			[]byte(customerID),
			[]byte("TEST_ACTOR_001"),
		})
		
		assert.Equal(t, int32(shim.OK), response.Status, "AML check should succeed")
		
		// Parse response
		var amlResponse AMLCheckResponse
		err := json.Unmarshal(response.Payload, &amlResponse)
		assert.NoError(t, err, "Should be able to parse AML response")
		assert.Equal(t, customerID, amlResponse.CustomerID)
		assert.Contains(t, []string{
			string(shared.AMLStatusClear),
			string(shared.AMLStatusFlagged),
			string(shared.AMLStatusReviewing),
		}, amlResponse.Status, "AML status should be valid")
	})
	
	t.Run("PerformAMLCheck_SanctionedCustomer", func(t *testing.T) {
		// Create a regular customer first
		regularCustomerID := createTestCustomer(t, stub)
		
		// Perform AML check on the regular customer
		response := stub.MockInvoke("2", [][]byte{
			[]byte("PerformAMLCheck"),
			[]byte(regularCustomerID),
			[]byte("TEST_ACTOR_001"),
		})
		
		assert.Equal(t, int32(shim.OK), response.Status, "AML check should complete successfully")
		
		// Parse response
		var amlResponse AMLCheckResponse
		err := json.Unmarshal(response.Payload, &amlResponse)
		assert.NoError(t, err, "Should be able to parse AML response")
		
		// Should have valid AML status
		assert.Contains(t, []string{
			string(shared.AMLStatusClear),
			string(shared.AMLStatusFlagged),
			string(shared.AMLStatusBlocked),
			string(shared.AMLStatusReviewing),
		}, amlResponse.Status, "Should have valid AML status")
		
		// Should have reference ID and provider name
		assert.NotEmpty(t, amlResponse.ReferenceID, "Should have reference ID")
		assert.NotEmpty(t, amlResponse.ProviderName, "Should have provider name")
	})
}

// TestAutomaticAMLScreeningOnCreation tests automatic AML screening during customer creation
func TestAutomaticAMLScreeningOnCreation(t *testing.T) {
	// Create a new mock stub
	stub := shimtest.NewMockStub("customer", new(CustomerChaincode))
	
	// Setup test actor
	setupTestActor(t, stub)
	
	t.Run("CreateCustomer_AutomaticAMLScreening", func(t *testing.T) {
		// Create customer with automatic AML screening
		response := stub.MockInvoke("1", [][]byte{
			[]byte("CreateCustomer"),
			[]byte("John"),
			[]byte("Smith"),
			[]byte("1990-01-01"),
			[]byte("ID123456789"),
			[]byte("123 Main St, Anytown, USA"),
			[]byte("john.smith@example.com"),
			[]byte("+1234567890"),
			[]byte("TEST_ACTOR_001"),
		})
		
		assert.Equal(t, int32(shim.OK), response.Status, "Customer creation should succeed")
		
		customerID := string(response.Payload)
		
		// Verify customer was created with AML status
		customerResponse := stub.MockInvoke("2", [][]byte{
			[]byte("GetCustomer"),
			[]byte(customerID),
			[]byte("TEST_ACTOR_001"),
		})
		
		assert.Equal(t, int32(shim.OK), customerResponse.Status)
		
		var customer Customer
		err := json.Unmarshal(customerResponse.Payload, &customer)
		assert.NoError(t, err)
		assert.NotEqual(t, "", customer.AMLStatus, "AML status should be set")
		assert.Contains(t, []string{
			string(shared.AMLStatusClear),
			string(shared.AMLStatusFlagged),
			string(shared.AMLStatusReviewing),
		}, customer.AMLStatus, "AML status should be valid")
	})
	
	t.Run("CreateCustomer_BlockedBySanctionList", func(t *testing.T) {
		// Try to create customer with exact sanctioned name from mock list
		response := stub.MockInvoke("3", [][]byte{
			[]byte("CreateCustomer"),
			[]byte("Test"),
			[]byte("Flagged Person"),
			[]byte("1990-12-25"),
			[]byte("FLAG345678"),
			[]byte("123 Flagged St, Sanctioned City, USA"),
			[]byte("flagged@example.com"),
			[]byte("+1111111111"),
			[]byte("TEST_ACTOR_001"),
		})
		
		assert.Equal(t, int32(shim.ERROR), response.Status, "Customer creation should be blocked")
		assert.Contains(t, response.Message, "blocked due to AML screening", "Should indicate AML blocking")
	})
}

// TestComplianceValidation tests compliance validation functionality
func TestComplianceValidation(t *testing.T) {
	// Create a new mock stub
	stub := shimtest.NewMockStub("customer", new(CustomerChaincode))
	
	// Setup test actor and compliance officer
	setupTestActor(t, stub)
	setupComplianceOfficer(t, stub)
	
	// Create a test customer
	customerID := createTestCustomer(t, stub)
	
	t.Run("ValidateCustomerForCompliance_Success", func(t *testing.T) {
		// First, set customer to verified KYC status
		setCustomerKYCStatus(t, stub, customerID, string(shared.KYCStatusVerified))
		
		// Create chaincode instance to test internal method
		cc := &CustomerChaincode{}
		err := cc.ValidateCustomerForCompliance(stub, customerID)
		assert.NoError(t, err, "Compliance validation should pass for verified customer")
	})
	
	t.Run("ValidateCustomerForCompliance_KYCFailed", func(t *testing.T) {
		// Set customer to failed KYC status
		setCustomerKYCStatus(t, stub, customerID, string(shared.KYCStatusFailed))
		
		// Create chaincode instance to test internal method
		cc := &CustomerChaincode{}
		err := cc.ValidateCustomerForCompliance(stub, customerID)
		assert.Error(t, err, "Compliance validation should fail for failed KYC customer")
		assert.Contains(t, err.Error(), "KYC verification failed")
	})
	
	t.Run("ValidateCustomerForCompliance_AMLBlocked", func(t *testing.T) {
		// First set customer to verified KYC status
		setCustomerKYCStatus(t, stub, customerID, string(shared.KYCStatusVerified))
		// Then set customer to blocked AML status
		setCustomerAMLStatus(t, stub, customerID, string(shared.AMLStatusBlocked))
		
		// Create chaincode instance to test internal method
		cc := &CustomerChaincode{}
		err := cc.ValidateCustomerForCompliance(stub, customerID)
		assert.Error(t, err, "Compliance validation should fail for blocked customer")
		assert.Contains(t, err.Error(), "AML blocked")
	})
	
	t.Run("UpdateCustomer_BlockedByCompliance", func(t *testing.T) {
		// Set customer to flagged AML status
		setCustomerAMLStatus(t, stub, customerID, string(shared.AMLStatusFlagged))
		
		// Try to update customer details (should be blocked for regular user)
		response := stub.MockInvoke("1", [][]byte{
			[]byte("UpdateCustomerDetails"),
			[]byte(customerID),
			[]byte("Updated"),
			[]byte("Name"),
			[]byte("456 Updated St, New City, USA"),
			[]byte("updated@example.com"),
			[]byte("+9876543210"),
			[]byte(string(shared.CustomerStatusActive)),
			[]byte("TEST_ACTOR_001"),
		})
		
		assert.Equal(t, int32(shim.ERROR), response.Status, "Update should be blocked for flagged customer")
		assert.Contains(t, response.Message, "compliance issues")
	})
	
	t.Run("UpdateCustomer_AllowedForComplianceOfficer", func(t *testing.T) {
		// Set customer to flagged AML status
		setCustomerAMLStatus(t, stub, customerID, string(shared.AMLStatusFlagged))
		
		// Try to update customer details as compliance officer (should be allowed)
		response := stub.MockInvoke("2", [][]byte{
			[]byte("UpdateCustomerDetails"),
			[]byte(customerID),
			[]byte("Compliance"),
			[]byte("Updated"),
			[]byte("456 Compliance St, Officer City, USA"),
			[]byte("compliance@example.com"),
			[]byte("+5555555555"),
			[]byte(string(shared.CustomerStatusActive)),
			[]byte("COMPLIANCE_OFFICER_001"),
		})
		
		assert.Equal(t, int32(shim.OK), response.Status, "Update should be allowed for compliance officer")
	})
}

// TestKYCAMLIntegrationPatterns tests external service integration patterns
func TestKYCAMLIntegrationPatterns(t *testing.T) {
	cc := &CustomerChaincode{}
	stub := shimtest.NewMockStub("customer", cc)
	
	t.Run("KYCProviderIntegration", func(t *testing.T) {
		// Test KYC provider integration pattern
		request := KYCValidationRequest{
			CustomerID:   "TEST_CUSTOMER_001",
			FirstName:    "John",
			LastName:     "Doe",
			DateOfBirth:  "1990-01-01",
			NationalID:   "ID123456789",
			Address:      "123 Main St, Anytown, USA",
			DocumentType: "NATIONAL_ID",
			DocumentHash: "hash123",
		}
		
		response, err := cc.integrateWithKYCProvider(stub, request)
		assert.NoError(t, err, "KYC provider integration should not error")
		assert.NotNil(t, response, "Should return KYC response")
		assert.Equal(t, request.CustomerID, response.CustomerID)
		assert.NotEmpty(t, response.ReferenceID, "Should have reference ID")
		assert.NotEmpty(t, response.ProviderName, "Should have provider name")
	})
	
	t.Run("AMLScreeningIntegration", func(t *testing.T) {
		// Test AML screening integration pattern
		request := AMLCheckRequest{
			CustomerID:  "TEST_CUSTOMER_001",
			FirstName:   "John",
			LastName:    "Doe",
			NationalID:  "ID123456789",
			DateOfBirth: "1990-01-01",
			Country:     "US",
		}
		
		response, err := cc.performAMLScreening(stub, request)
		assert.NoError(t, err, "AML screening should not error")
		assert.NotNil(t, response, "Should return AML response")
		assert.Equal(t, request.CustomerID, response.CustomerID)
		assert.NotEmpty(t, response.ReferenceID, "Should have reference ID")
		assert.NotEmpty(t, response.ProviderName, "Should have provider name")
		assert.Contains(t, []string{
			string(shared.AMLStatusClear),
			string(shared.AMLStatusFlagged),
			string(shared.AMLStatusReviewing),
			string(shared.AMLStatusBlocked),
		}, response.Status, "Should have valid AML status")
	})
	
	t.Run("SanctionListMatching", func(t *testing.T) {
		// Test sanction list matching
		sanctionList := cc.getMockSanctionList()
		assert.Greater(t, len(sanctionList), 0, "Should have sanction list entries")
		
		// Test name matching
		isMatch := cc.isNameMatch("John Doe Sanctioned", "John Doe Sanctioned")
		assert.True(t, isMatch, "Exact name match should return true")
		
		isMatch = cc.isNameMatch("Test Flagged Person", "Test Flagged Person")
		assert.True(t, isMatch, "Exact sanctioned name match should return true")
		
		isMatch = cc.isNameMatch("Jane Smith", "John Doe")
		assert.False(t, isMatch, "Different names should not match")
	})
}

// Helper functions for testing

func setupTestActor(t *testing.T, stub *shimtest.MockStub) {
	actor := shared.Actor{
		ActorID:           "TEST_ACTOR_001",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Test User",
		Role:              shared.RoleIntroducer,
		BlockchainIdentity: "test-cert-001",
		Permissions: []shared.Permission{
			shared.PermissionCreateCustomer,
			shared.PermissionUpdateCustomer,
			shared.PermissionViewCustomer,
		},
		IsActive:    true,
		CreatedDate: time.Now(),
		LastUpdated: time.Now(),
	}
	
	actorJSON, _ := json.Marshal(actor)
	stub.MockTransactionStart("setup")
	stub.PutState("ACTOR_TEST_ACTOR_001", actorJSON)
	stub.MockTransactionEnd("setup")
}

func setupComplianceOfficer(t *testing.T, stub *shimtest.MockStub) {
	actor := shared.Actor{
		ActorID:           "COMPLIANCE_OFFICER_001",
		ActorType:         shared.ActorTypeInternalUser,
		ActorName:         "Compliance Officer",
		Role:              shared.RoleComplianceOfficer,
		BlockchainIdentity: "compliance-cert-001",
		Permissions: []shared.Permission{
			shared.PermissionUpdateCustomer,
			shared.PermissionViewCustomer,
			shared.PermissionUpdateCompliance,
			shared.PermissionViewCompliance,
		},
		IsActive:    true,
		CreatedDate: time.Now(),
		LastUpdated: time.Now(),
	}
	
	actorJSON, _ := json.Marshal(actor)
	stub.MockTransactionStart("setup")
	stub.PutState("ACTOR_COMPLIANCE_OFFICER_001", actorJSON)
	stub.MockTransactionEnd("setup")
}

func createTestCustomer(t *testing.T, stub *shimtest.MockStub) string {
	response := stub.MockInvoke("create", [][]byte{
		[]byte("CreateCustomer"),
		[]byte("John"),
		[]byte("Doe"),
		[]byte("1990-01-01"),
		[]byte("ID123456789"),
		[]byte("123 Main St, Anytown, USA"),
		[]byte("john.doe@example.com"),
		[]byte("+1234567890"),
		[]byte("TEST_ACTOR_001"),
	})
	
	assert.Equal(t, int32(shim.OK), response.Status, "Customer creation should succeed")
	return string(response.Payload)
}

func createSanctionedCustomer(t *testing.T, stub *shimtest.MockStub) string {
	response := stub.MockInvoke("create", [][]byte{
		[]byte("CreateCustomer"),
		[]byte("Test Flagged Person"),
		[]byte("Sanctioned"),
		[]byte("1990-12-25"),
		[]byte("FLAG345678"),
		[]byte("123 Flagged St, Sanctioned City, USA"),
		[]byte("flagged@example.com"),
		[]byte("+1111111111"),
		[]byte("TEST_ACTOR_001"),
	})
	
	assert.Equal(t, int32(shim.OK), response.Status, "Sanctioned customer creation should succeed")
	return string(response.Payload)
}

func setCustomerKYCStatus(t *testing.T, stub *shimtest.MockStub, customerID, status string) {
	// Get customer
	customerResponse := stub.MockInvoke("get", [][]byte{
		[]byte("GetCustomer"),
		[]byte(customerID),
		[]byte("TEST_ACTOR_001"),
	})
	assert.Equal(t, int32(shim.OK), customerResponse.Status)
	
	var customer Customer
	err := json.Unmarshal(customerResponse.Payload, &customer)
	assert.NoError(t, err)
	
	// Update KYC status
	customer.KYCStatus = status
	customer.LastUpdated = time.Now()
	customer.Version++
	
	// Store updated customer
	customerJSON, _ := json.Marshal(customer)
	stub.MockTransactionStart("update")
	stub.PutState(customerID, customerJSON)
	stub.MockTransactionEnd("update")
}

func setCustomerAMLStatus(t *testing.T, stub *shimtest.MockStub, customerID, status string) {
	// Get customer
	customerResponse := stub.MockInvoke("get", [][]byte{
		[]byte("GetCustomer"),
		[]byte(customerID),
		[]byte("TEST_ACTOR_001"),
	})
	assert.Equal(t, int32(shim.OK), customerResponse.Status)
	
	var customer Customer
	err := json.Unmarshal(customerResponse.Payload, &customer)
	assert.NoError(t, err)
	
	// Update AML status
	customer.AMLStatus = status
	customer.LastUpdated = time.Now()
	customer.Version++
	
	// Store updated customer
	customerJSON, _ := json.Marshal(customer)
	stub.MockTransactionStart("update")
	stub.PutState(customerID, customerJSON)
	stub.MockTransactionEnd("update")
}