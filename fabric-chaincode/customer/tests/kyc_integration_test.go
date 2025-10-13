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
	"github.com/blockchain-financial-platform/fabric-chaincode/shared/validation"
)

func TestKYCFlow(t *testing.T) {
	stub := shimtest.NewMockStub("customer", &chaincode.CustomerContract{})
	
	// First create a customer
	customer := createTestCustomer(t, stub, "KYC_TEST_001")
	
	// Initiate KYC
	kycReq := domain.KYCInitiationRequest{
		CustomerID:     customer.CustomerID,
		DocumentHashes: []string{"hash1", "hash2", "hash3"},
		ActorID:        "ACTOR_KYC_001",
	}
	
	kycBytes, err := json.Marshal(kycReq)
	assert.NoError(t, err)
	
	response := stub.MockInvoke("2", [][]byte{
		[]byte("InitiateKYC"),
		kycBytes,
	})
	
	assert.Equal(t, int32(shim.OK), response.Status)
	
	var kycRecord domain.KYCRecord
	err = json.Unmarshal(response.Payload, &kycRecord)
	assert.NoError(t, err)
	assert.Equal(t, customer.CustomerID, kycRecord.CustomerID)
	assert.Equal(t, validation.KYCStatusPending, kycRecord.Status)
	assert.Equal(t, 3, len(kycRecord.DocumentHashes))
	
	// Update KYC status to verified
	statusUpdateReq := domain.KYCStatusUpdateRequest{
		KYCID:             kycRecord.KYCID,
		NewStatus:         validation.KYCStatusVerified,
		VerificationNotes: "All documents verified successfully",
		ActorID:           "ACTOR_KYC_001",
	}
	
	statusBytes, err := json.Marshal(statusUpdateReq)
	assert.NoError(t, err)
	
	updateResponse := stub.MockInvoke("3", [][]byte{
		[]byte("UpdateKYCStatus"),
		statusBytes,
	})
	
	assert.Equal(t, int32(shim.OK), updateResponse.Status)
	
	var updatedKYCRecord domain.KYCRecord
	err = json.Unmarshal(updateResponse.Payload, &updatedKYCRecord)
	assert.NoError(t, err)
	assert.Equal(t, validation.KYCStatusVerified, updatedKYCRecord.Status)
	assert.Equal(t, "All documents verified successfully", updatedKYCRecord.VerificationNotes)
	assert.NotNil(t, updatedKYCRecord.VerificationDate)
	assert.NotNil(t, updatedKYCRecord.ExpiryDate)
	
	// Get KYC record
	getResponse := stub.MockInvoke("4", [][]byte{
		[]byte("GetKYCRecord"),
		[]byte(kycRecord.KYCID),
	})
	
	assert.Equal(t, int32(shim.OK), getResponse.Status)
	
	var retrievedKYCRecord domain.KYCRecord
	err = json.Unmarshal(getResponse.Payload, &retrievedKYCRecord)
	assert.NoError(t, err)
	assert.Equal(t, updatedKYCRecord.KYCID, retrievedKYCRecord.KYCID)
	assert.Equal(t, updatedKYCRecord.Status, retrievedKYCRecord.Status)
}

func TestAMLFlow(t *testing.T) {
	stub := shimtest.NewMockStub("customer", &chaincode.CustomerContract{})
	
	// First create a customer
	customer := createTestCustomer(t, stub, "AML_TEST_001")
	
	// Initiate AML check
	amlReq := domain.AMLCheckRequest{
		CustomerID: customer.CustomerID,
		ActorID:    "ACTOR_AML_001",
	}
	
	amlBytes, err := json.Marshal(amlReq)
	assert.NoError(t, err)
	
	response := stub.MockInvoke("2", [][]byte{
		[]byte("InitiateAMLCheck"),
		amlBytes,
	})
	
	assert.Equal(t, int32(shim.OK), response.Status)
	
	var amlRecord domain.AMLRecord
	err = json.Unmarshal(response.Payload, &amlRecord)
	assert.NoError(t, err)
	assert.Equal(t, customer.CustomerID, amlRecord.CustomerID)
	assert.Equal(t, validation.AMLStatusClear, amlRecord.Status)
	assert.Equal(t, 0.0, amlRecord.RiskScore)
	
	// Update AML status to flagged
	statusUpdateReq := domain.AMLStatusUpdateRequest{
		AMLID:     amlRecord.AMLID,
		NewStatus: validation.AMLStatusFlagged,
		RiskScore: 75.5,
		Flags:     []string{"HIGH_RISK_COUNTRY", "SUSPICIOUS_TRANSACTION_PATTERN"},
		Notes:     "Customer flagged for manual review",
		ActorID:   "ACTOR_AML_001",
	}
	
	statusBytes, err := json.Marshal(statusUpdateReq)
	assert.NoError(t, err)
	
	updateResponse := stub.MockInvoke("3", [][]byte{
		[]byte("UpdateAMLStatus"),
		statusBytes,
	})
	
	assert.Equal(t, int32(shim.OK), updateResponse.Status)
	
	var updatedAMLRecord domain.AMLRecord
	err = json.Unmarshal(updateResponse.Payload, &updatedAMLRecord)
	assert.NoError(t, err)
	assert.Equal(t, validation.AMLStatusFlagged, updatedAMLRecord.Status)
	assert.Equal(t, 75.5, updatedAMLRecord.RiskScore)
	assert.Equal(t, 2, len(updatedAMLRecord.Flags))
	assert.Contains(t, updatedAMLRecord.Flags, "HIGH_RISK_COUNTRY")
	assert.Contains(t, updatedAMLRecord.Flags, "SUSPICIOUS_TRANSACTION_PATTERN")
	
	// Get AML record
	getResponse := stub.MockInvoke("4", [][]byte{
		[]byte("GetAMLRecord"),
		[]byte(amlRecord.AMLID),
	})
	
	assert.Equal(t, int32(shim.OK), getResponse.Status)
	
	var retrievedAMLRecord domain.AMLRecord
	err = json.Unmarshal(getResponse.Payload, &retrievedAMLRecord)
	assert.NoError(t, err)
	assert.Equal(t, updatedAMLRecord.AMLID, retrievedAMLRecord.AMLID)
	assert.Equal(t, updatedAMLRecord.Status, retrievedAMLRecord.Status)
	assert.Equal(t, updatedAMLRecord.RiskScore, retrievedAMLRecord.RiskScore)
}

func TestKYCValidation(t *testing.T) {
	stub := shimtest.NewMockStub("customer", &chaincode.CustomerContract{})
	
	// Try to initiate KYC for non-existent customer
	kycReq := domain.KYCInitiationRequest{
		CustomerID:     "NON_EXISTENT_CUSTOMER",
		DocumentHashes: []string{"hash1"},
		ActorID:        "ACTOR_KYC_002",
	}
	
	kycBytes, err := json.Marshal(kycReq)
	assert.NoError(t, err)
	
	response := stub.MockInvoke("1", [][]byte{
		[]byte("InitiateKYC"),
		kycBytes,
	})
	
	assert.Equal(t, int32(shim.ERROR), response.Status)
	assert.Contains(t, response.Message, "customer not found")
}

func TestAMLValidation(t *testing.T) {
	stub := shimtest.NewMockStub("customer", &chaincode.CustomerContract{})
	
	// Try to initiate AML check for non-existent customer
	amlReq := domain.AMLCheckRequest{
		CustomerID: "NON_EXISTENT_CUSTOMER",
		ActorID:    "ACTOR_AML_002",
	}
	
	amlBytes, err := json.Marshal(amlReq)
	assert.NoError(t, err)
	
	response := stub.MockInvoke("1", [][]byte{
		[]byte("InitiateAMLCheck"),
		amlBytes,
	})
	
	assert.Equal(t, int32(shim.ERROR), response.Status)
	assert.Contains(t, response.Message, "customer not found")
}

// Helper function to create a test customer
func createTestCustomer(t *testing.T, stub *shimtest.MockStub, nationalID string) domain.Customer {
	registrationReq := domain.CustomerRegistrationRequest{
		FirstName:          "Test",
		LastName:           "Customer",
		Email:              "test@example.com",
		Phone:              "+1234567890",
		DateOfBirth:        time.Date(1990, 1, 1, 0, 0, 0, 0, time.UTC),
		NationalID:         nationalID,
		Address:            "123 Test Street, Test City, Test Country",
		ConsentPreferences: `{"marketing": true}`,
		ActorID:            "ACTOR_TEST",
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
	
	return customer
}