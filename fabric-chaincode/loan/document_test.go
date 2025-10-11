package main

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/hyperledger/fabric-chaincode-go/shimtest"
	"github.com/stretchr/testify/assert"
	"github.com/blockchain-financial-platform/fabric-chaincode/shared"
)

// TestRecordDocumentHash tests the RecordDocumentHash function
func TestRecordDocumentHash(t *testing.T) {
	// Create a new mock stub
	stub := shimtest.NewMockStub("loan", new(LoanChaincode))
	
	// Setup test data
	customerID := "CUSTOMER_123"
	loanApplicationID := "LOAN_456"
	actorID := "ACTOR_789"
	documentHash := "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3" // SHA256 of "hello"
	
	// Create test customer
	customer := map[string]interface{}{
		"customerID": customerID,
		"firstName":  "John",
		"lastName":   "Doe",
	}
	customerJSON, _ := json.Marshal(customer)
	stub.MockTransactionStart("txid1")
	stub.PutState("CUSTOMER_"+customerID, customerJSON)
	stub.MockTransactionEnd("txid1")
	
	// Create test loan application
	loanApp := LoanApplication{
		LoanApplicationID: loanApplicationID,
		CustomerID:        customerID,
		ApplicationDate:   time.Now(),
		RequestedAmount:   10000.0,
		LoanType:         LoanTypePersonal,
		ApplicationStatus: StatusSubmitted,
		IntroducerID:     "INTRO_123",
		CurrentOwnerActor: actorID,
		LastUpdated:      time.Now(),
		CreatedBy:        actorID,
		Version:          1,
	}
	loanJSON, _ := json.Marshal(loanApp)
	stub.MockTransactionStart("txid2")
	stub.PutState("LOAN_"+loanApplicationID, loanJSON)
	stub.MockTransactionEnd("txid2")
	
	// Create test actor
	actor := shared.Actor{
		ActorID:     actorID,
		ActorType:   shared.ActorTypeInternalUser,
		ActorName:   "Test Actor",
		Role:        shared.RoleIntroducer,
		Permissions: []shared.Permission{shared.PermissionCreateLoan},
		IsActive:    true,
		CreatedDate: time.Now(),
		LastUpdated: time.Now(),
	}
	actorJSON, _ := json.Marshal(actor)
	stub.MockTransactionStart("txid3")
	stub.PutState("ACTOR_"+actorID, actorJSON)
	stub.MockTransactionEnd("txid3")

	t.Run("Successful document hash recording", func(t *testing.T) {
		// Test successful document hash recording
		args := []string{
			loanApplicationID,
			customerID,
			string(DocumentTypeIdentity),
			"passport.pdf",
			documentHash,
			actorID,
		}
		
		stub.MockTransactionStart("txid4")
		response := stub.MockInvoke("1", [][]byte{
			[]byte("RecordDocumentHash"),
			[]byte(args[0]),
			[]byte(args[1]),
			[]byte(args[2]),
			[]byte(args[3]),
			[]byte(args[4]),
			[]byte(args[5]),
		})
		stub.MockTransactionEnd("txid4")
		
		assert.Equal(t, int32(shim.OK), response.Status, "Expected OK status")
		
		// Verify the response contains the document record
		var document LoanDocument
		err := json.Unmarshal(response.Payload, &document)
		assert.NoError(t, err, "Should unmarshal document successfully")
		assert.Equal(t, loanApplicationID, document.LoanApplicationID)
		assert.Equal(t, customerID, document.CustomerID)
		assert.Equal(t, DocumentTypeIdentity, document.DocumentType)
		assert.Equal(t, "passport.pdf", document.DocumentName)
		assert.Equal(t, documentHash, document.DocumentHash)
		assert.Equal(t, "SHA256", document.HashAlgorithm)
		assert.Equal(t, DocumentStatusUploaded, document.DocumentStatus)
		assert.Equal(t, actorID, document.UploadedBy)
		assert.Equal(t, 1, document.Version)
	})

	t.Run("Invalid number of arguments", func(t *testing.T) {
		args := []string{loanApplicationID, customerID} // Too few arguments
		
		stub.MockTransactionStart("txid5")
		response := stub.MockInvoke("2", [][]byte{
			[]byte("RecordDocumentHash"),
			[]byte(args[0]),
			[]byte(args[1]),
		})
		stub.MockTransactionEnd("txid5")
		
		assert.Equal(t, int32(shim.ERROR), response.Status)
		assert.Contains(t, response.Message, "Incorrect number of arguments")
	})

	t.Run("Invalid document type", func(t *testing.T) {
		args := []string{
			loanApplicationID,
			customerID,
			"InvalidType",
			"document.pdf",
			documentHash,
			actorID,
		}
		
		stub.MockTransactionStart("txid6")
		response := stub.MockInvoke("3", [][]byte{
			[]byte("RecordDocumentHash"),
			[]byte(args[0]),
			[]byte(args[1]),
			[]byte(args[2]),
			[]byte(args[3]),
			[]byte(args[4]),
			[]byte(args[5]),
		})
		stub.MockTransactionEnd("txid6")
		
		assert.Equal(t, int32(shim.ERROR), response.Status)
		assert.Contains(t, response.Message, "Invalid document type")
	})

	t.Run("Invalid document hash length", func(t *testing.T) {
		args := []string{
			loanApplicationID,
			customerID,
			string(DocumentTypeIdentity),
			"document.pdf",
			"invalidhash", // Too short
			actorID,
		}
		
		stub.MockTransactionStart("txid7")
		response := stub.MockInvoke("4", [][]byte{
			[]byte("RecordDocumentHash"),
			[]byte(args[0]),
			[]byte(args[1]),
			[]byte(args[2]),
			[]byte(args[3]),
			[]byte(args[4]),
			[]byte(args[5]),
		})
		stub.MockTransactionEnd("txid7")
		
		assert.Equal(t, int32(shim.ERROR), response.Status)
		assert.Contains(t, response.Message, "Document hash must be 64 characters")
	})

	t.Run("Invalid document hash format", func(t *testing.T) {
		args := []string{
			loanApplicationID,
			customerID,
			string(DocumentTypeIdentity),
			"document.pdf",
			"gggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggg", // Invalid hex
			actorID,
		}
		
		stub.MockTransactionStart("txid8")
		response := stub.MockInvoke("5", [][]byte{
			[]byte("RecordDocumentHash"),
			[]byte(args[0]),
			[]byte(args[1]),
			[]byte(args[2]),
			[]byte(args[3]),
			[]byte(args[4]),
			[]byte(args[5]),
		})
		stub.MockTransactionEnd("txid8")
		
		assert.Equal(t, int32(shim.ERROR), response.Status)
		assert.Contains(t, response.Message, "Document hash must be valid hexadecimal")
	})

	t.Run("Customer ID mismatch", func(t *testing.T) {
		args := []string{
			loanApplicationID,
			"WRONG_CUSTOMER", // Wrong customer ID
			string(DocumentTypeIdentity),
			"document.pdf",
			documentHash,
			actorID,
		}
		
		stub.MockTransactionStart("txid9")
		response := stub.MockInvoke("6", [][]byte{
			[]byte("RecordDocumentHash"),
			[]byte(args[0]),
			[]byte(args[1]),
			[]byte(args[2]),
			[]byte(args[3]),
			[]byte(args[4]),
			[]byte(args[5]),
		})
		stub.MockTransactionEnd("txid9")
		
		assert.Equal(t, int32(shim.ERROR), response.Status)
		assert.Contains(t, response.Message, "Customer ID")
		assert.Contains(t, response.Message, "does not match")
	})
}

// TestVerifyDocumentHash tests the VerifyDocumentHash function
func TestVerifyDocumentHash(t *testing.T) {
	// Create a new mock stub
	stub := shimtest.NewMockStub("loan", new(LoanChaincode))
	
	// Setup test data
	documentID := "DOC_123"
	actorID := "ACTOR_789"
	correctHash := "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3"
	wrongHash := "b665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3"
	
	// Create test actor
	actor := shared.Actor{
		ActorID:     actorID,
		ActorType:   shared.ActorTypeInternalUser,
		ActorName:   "Test Actor",
		Role:        shared.RoleUnderwriter,
		Permissions: []shared.Permission{shared.PermissionViewLoan},
		IsActive:    true,
		CreatedDate: time.Now(),
		LastUpdated: time.Now(),
	}
	actorJSON, _ := json.Marshal(actor)
	stub.MockTransactionStart("txid1")
	stub.PutState("ACTOR_"+actorID, actorJSON)
	stub.MockTransactionEnd("txid1")
	
	// Create test document
	document := LoanDocument{
		DocumentID:        documentID,
		LoanApplicationID: "LOAN_456",
		CustomerID:        "CUSTOMER_123",
		DocumentType:      DocumentTypeIdentity,
		DocumentName:      "passport.pdf",
		DocumentHash:      correctHash,
		HashAlgorithm:     "SHA256",
		DocumentStatus:    DocumentStatusUploaded,
		UploadedBy:        actorID,
		UploadedDate:      time.Now(),
		LastUpdated:       time.Now(),
		Version:           1,
	}
	documentJSON, _ := json.Marshal(document)
	stub.MockTransactionStart("txid2")
	stub.PutState("DOCUMENT_"+documentID, documentJSON)
	stub.MockTransactionEnd("txid2")

	t.Run("Successful hash verification - valid", func(t *testing.T) {
		args := []string{documentID, correctHash, actorID}
		
		stub.MockTransactionStart("txid3")
		response := stub.MockInvoke("1", [][]byte{
			[]byte("VerifyDocumentHash"),
			[]byte(args[0]),
			[]byte(args[1]),
			[]byte(args[2]),
		})
		stub.MockTransactionEnd("txid3")
		
		assert.Equal(t, int32(shim.OK), response.Status, "Expected OK status")
		
		// Verify the response
		var result map[string]interface{}
		err := json.Unmarshal(response.Payload, &result)
		assert.NoError(t, err, "Should unmarshal result successfully")
		assert.Equal(t, documentID, result["documentID"])
		assert.Equal(t, true, result["isValid"])
		assert.Equal(t, correctHash, result["storedHash"])
		assert.Equal(t, correctHash, result["providedHash"])
		assert.Equal(t, "SHA256", result["hashAlgorithm"])
		assert.Equal(t, actorID, result["verifiedBy"])
	})

	t.Run("Successful hash verification - invalid", func(t *testing.T) {
		args := []string{documentID, wrongHash, actorID}
		
		stub.MockTransactionStart("txid4")
		response := stub.MockInvoke("2", [][]byte{
			[]byte("VerifyDocumentHash"),
			[]byte(args[0]),
			[]byte(args[1]),
			[]byte(args[2]),
		})
		stub.MockTransactionEnd("txid4")
		
		assert.Equal(t, int32(shim.OK), response.Status, "Expected OK status")
		
		// Verify the response
		var result map[string]interface{}
		err := json.Unmarshal(response.Payload, &result)
		assert.NoError(t, err, "Should unmarshal result successfully")
		assert.Equal(t, documentID, result["documentID"])
		assert.Equal(t, false, result["isValid"])
		assert.Equal(t, correctHash, result["storedHash"])
		assert.Equal(t, wrongHash, result["providedHash"])
	})

	t.Run("Invalid hash length", func(t *testing.T) {
		args := []string{documentID, "short", actorID}
		
		stub.MockTransactionStart("txid5")
		response := stub.MockInvoke("3", [][]byte{
			[]byte("VerifyDocumentHash"),
			[]byte(args[0]),
			[]byte(args[1]),
			[]byte(args[2]),
		})
		stub.MockTransactionEnd("txid5")
		
		assert.Equal(t, int32(shim.ERROR), response.Status)
		assert.Contains(t, response.Message, "Provided hash must be 64 characters")
	})

	t.Run("Document not found", func(t *testing.T) {
		args := []string{"NONEXISTENT_DOC", correctHash, actorID}
		
		stub.MockTransactionStart("txid6")
		response := stub.MockInvoke("4", [][]byte{
			[]byte("VerifyDocumentHash"),
			[]byte(args[0]),
			[]byte(args[1]),
			[]byte(args[2]),
		})
		stub.MockTransactionEnd("txid6")
		
		assert.Equal(t, int32(shim.ERROR), response.Status)
		assert.Contains(t, response.Message, "Failed to get document record")
	})
}

// TestGetLoanDocuments tests the GetLoanDocuments function
func TestGetLoanDocuments(t *testing.T) {
	// Create a new mock stub
	stub := shimtest.NewMockStub("loan", new(LoanChaincode))
	
	// Setup test data
	loanApplicationID := "LOAN_456"
	actorID := "ACTOR_789"
	documentID1 := "DOC_123"
	documentID2 := "DOC_124"
	
	// Create test actor
	actor := shared.Actor{
		ActorID:     actorID,
		ActorType:   shared.ActorTypeInternalUser,
		ActorName:   "Test Actor",
		Role:        shared.RoleUnderwriter,
		Permissions: []shared.Permission{shared.PermissionViewLoan},
		IsActive:    true,
		CreatedDate: time.Now(),
		LastUpdated: time.Now(),
	}
	actorJSON, _ := json.Marshal(actor)
	stub.MockTransactionStart("txid1")
	stub.PutState("ACTOR_"+actorID, actorJSON)
	stub.MockTransactionEnd("txid1")
	
	// Create test loan application
	loanApp := LoanApplication{
		LoanApplicationID: loanApplicationID,
		CustomerID:        "CUSTOMER_123",
		ApplicationDate:   time.Now(),
		RequestedAmount:   10000.0,
		LoanType:         LoanTypePersonal,
		ApplicationStatus: StatusSubmitted,
		IntroducerID:     "INTRO_123",
		CurrentOwnerActor: actorID,
		LastUpdated:      time.Now(),
		CreatedBy:        actorID,
		Version:          1,
	}
	loanJSON, _ := json.Marshal(loanApp)
	stub.MockTransactionStart("txid2")
	stub.PutState("LOAN_"+loanApplicationID, loanJSON)
	stub.MockTransactionEnd("txid2")
	
	// Create test documents
	document1 := LoanDocument{
		DocumentID:        documentID1,
		LoanApplicationID: loanApplicationID,
		CustomerID:        "CUSTOMER_123",
		DocumentType:      DocumentTypeIdentity,
		DocumentName:      "passport.pdf",
		DocumentHash:      "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
		HashAlgorithm:     "SHA256",
		DocumentStatus:    DocumentStatusUploaded,
		UploadedBy:        actorID,
		UploadedDate:      time.Now(),
		LastUpdated:       time.Now(),
		Version:           1,
	}
	
	document2 := LoanDocument{
		DocumentID:        documentID2,
		LoanApplicationID: loanApplicationID,
		CustomerID:        "CUSTOMER_123",
		DocumentType:      DocumentTypeIncome,
		DocumentName:      "salary_slip.pdf",
		DocumentHash:      "b665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
		HashAlgorithm:     "SHA256",
		DocumentStatus:    DocumentStatusVerified,
		UploadedBy:        actorID,
		UploadedDate:      time.Now(),
		VerifiedBy:        actorID,
		VerifiedDate:      time.Now(),
		LastUpdated:       time.Now(),
		Version:           2,
	}
	
	// Store documents
	doc1JSON, _ := json.Marshal(document1)
	doc2JSON, _ := json.Marshal(document2)
	stub.MockTransactionStart("txid3")
	stub.PutState("DOCUMENT_"+documentID1, doc1JSON)
	stub.PutState("DOCUMENT_"+documentID2, doc2JSON)
	stub.MockTransactionEnd("txid3")
	
	// Create composite keys for document references
	stub.MockTransactionStart("txid4")
	compositeKey1, _ := stub.CreateCompositeKey("LOAN_DOCUMENTS", []string{loanApplicationID, documentID1})
	compositeKey2, _ := stub.CreateCompositeKey("LOAN_DOCUMENTS", []string{loanApplicationID, documentID2})
	stub.PutState(compositeKey1, []byte(documentID1))
	stub.PutState(compositeKey2, []byte(documentID2))
	stub.MockTransactionEnd("txid4")

	t.Run("Successful document retrieval", func(t *testing.T) {
		args := []string{loanApplicationID, actorID}
		
		stub.MockTransactionStart("txid5")
		response := stub.MockInvoke("1", [][]byte{
			[]byte("GetLoanDocuments"),
			[]byte(args[0]),
			[]byte(args[1]),
		})
		stub.MockTransactionEnd("txid5")
		
		assert.Equal(t, int32(shim.OK), response.Status, "Expected OK status")
		
		// Verify the response
		var result map[string]interface{}
		err := json.Unmarshal(response.Payload, &result)
		assert.NoError(t, err, "Should unmarshal result successfully")
		assert.Equal(t, loanApplicationID, result["loanApplicationID"])
		assert.Equal(t, float64(2), result["documentCount"]) // JSON numbers are float64
		assert.Equal(t, actorID, result["retrievedBy"])
		
		// Verify documents array
		documents, ok := result["documents"].([]interface{})
		assert.True(t, ok, "Documents should be an array")
		assert.Len(t, documents, 2, "Should have 2 documents")
	})

	t.Run("Loan application not found", func(t *testing.T) {
		args := []string{"NONEXISTENT_LOAN", actorID}
		
		stub.MockTransactionStart("txid6")
		response := stub.MockInvoke("2", [][]byte{
			[]byte("GetLoanDocuments"),
			[]byte(args[0]),
			[]byte(args[1]),
		})
		stub.MockTransactionEnd("txid6")
		
		assert.Equal(t, int32(shim.ERROR), response.Status)
		assert.Contains(t, response.Message, "Failed to get loan application")
	})
}

// TestUpdateDocumentStatus tests the UpdateDocumentStatus function
func TestUpdateDocumentStatus(t *testing.T) {
	// Create a new mock stub
	stub := shimtest.NewMockStub("loan", new(LoanChaincode))
	
	// Setup test data
	documentID := "DOC_123"
	actorID := "ACTOR_789"
	
	// Create test actor
	actor := shared.Actor{
		ActorID:     actorID,
		ActorType:   shared.ActorTypeInternalUser,
		ActorName:   "Test Actor",
		Role:        shared.RoleUnderwriter,
		Permissions: []shared.Permission{shared.PermissionUpdateLoan},
		IsActive:    true,
		CreatedDate: time.Now(),
		LastUpdated: time.Now(),
	}
	actorJSON, _ := json.Marshal(actor)
	stub.MockTransactionStart("txid1")
	stub.PutState("ACTOR_"+actorID, actorJSON)
	stub.MockTransactionEnd("txid1")
	
	// Create test document
	document := LoanDocument{
		DocumentID:        documentID,
		LoanApplicationID: "LOAN_456",
		CustomerID:        "CUSTOMER_123",
		DocumentType:      DocumentTypeIdentity,
		DocumentName:      "passport.pdf",
		DocumentHash:      "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
		HashAlgorithm:     "SHA256",
		DocumentStatus:    DocumentStatusUploaded,
		UploadedBy:        actorID,
		UploadedDate:      time.Now(),
		LastUpdated:       time.Now(),
		Version:           1,
	}
	documentJSON, _ := json.Marshal(document)
	stub.MockTransactionStart("txid2")
	stub.PutState("DOCUMENT_"+documentID, documentJSON)
	stub.MockTransactionEnd("txid2")

	t.Run("Successful status update to verified", func(t *testing.T) {
		args := []string{documentID, string(DocumentStatusVerified), actorID, "Document verified successfully"}
		
		stub.MockTransactionStart("txid3")
		response := stub.MockInvoke("1", [][]byte{
			[]byte("UpdateDocumentStatus"),
			[]byte(args[0]),
			[]byte(args[1]),
			[]byte(args[2]),
			[]byte(args[3]),
		})
		stub.MockTransactionEnd("txid3")
		
		assert.Equal(t, int32(shim.OK), response.Status, "Expected OK status")
		
		// Verify the response
		var updatedDoc LoanDocument
		err := json.Unmarshal(response.Payload, &updatedDoc)
		assert.NoError(t, err, "Should unmarshal document successfully")
		assert.Equal(t, DocumentStatusVerified, updatedDoc.DocumentStatus)
		assert.Equal(t, actorID, updatedDoc.VerifiedBy)
		assert.Equal(t, 2, updatedDoc.Version)
		assert.False(t, updatedDoc.VerifiedDate.IsZero())
	})

	t.Run("Invalid status", func(t *testing.T) {
		args := []string{documentID, "InvalidStatus", actorID, "Notes"}
		
		stub.MockTransactionStart("txid4")
		response := stub.MockInvoke("2", [][]byte{
			[]byte("UpdateDocumentStatus"),
			[]byte(args[0]),
			[]byte(args[1]),
			[]byte(args[2]),
			[]byte(args[3]),
		})
		stub.MockTransactionEnd("txid4")
		
		assert.Equal(t, int32(shim.ERROR), response.Status)
		assert.Contains(t, response.Message, "Invalid document status")
	})

	t.Run("Document not found", func(t *testing.T) {
		args := []string{"NONEXISTENT_DOC", string(DocumentStatusVerified), actorID, "Notes"}
		
		stub.MockTransactionStart("txid5")
		response := stub.MockInvoke("3", [][]byte{
			[]byte("UpdateDocumentStatus"),
			[]byte(args[0]),
			[]byte(args[1]),
			[]byte(args[2]),
			[]byte(args[3]),
		})
		stub.MockTransactionEnd("txid5")
		
		assert.Equal(t, int32(shim.ERROR), response.Status)
		assert.Contains(t, response.Message, "Failed to get document")
	})
}

// TestDocumentValidationHelpers tests the helper functions
func TestDocumentValidationHelpers(t *testing.T) {
	t.Run("isValidDocumentType", func(t *testing.T) {
		assert.True(t, isValidDocumentType(DocumentTypeIdentity))
		assert.True(t, isValidDocumentType(DocumentTypeIncome))
		assert.True(t, isValidDocumentType(DocumentTypeBankStatement))
		assert.True(t, isValidDocumentType(DocumentTypeCollateral))
		assert.True(t, isValidDocumentType(DocumentTypeOther))
		assert.False(t, isValidDocumentType(DocumentType("Invalid")))
	})

	t.Run("isValidDocumentStatus", func(t *testing.T) {
		assert.True(t, isValidDocumentStatus(DocumentStatusUploaded))
		assert.True(t, isValidDocumentStatus(DocumentStatusVerified))
		assert.True(t, isValidDocumentStatus(DocumentStatusRejected))
		assert.True(t, isValidDocumentStatus(DocumentStatusExpired))
		assert.False(t, isValidDocumentStatus(DocumentStatus("Invalid")))
	})

	t.Run("isValidDocumentStatusTransition", func(t *testing.T) {
		// Valid transitions from Uploaded
		assert.True(t, isValidDocumentStatusTransition(DocumentStatusUploaded, DocumentStatusVerified))
		assert.True(t, isValidDocumentStatusTransition(DocumentStatusUploaded, DocumentStatusRejected))
		assert.True(t, isValidDocumentStatusTransition(DocumentStatusUploaded, DocumentStatusExpired))
		
		// Valid transitions from Verified
		assert.True(t, isValidDocumentStatusTransition(DocumentStatusVerified, DocumentStatusExpired))
		
		// Valid transitions from Rejected
		assert.True(t, isValidDocumentStatusTransition(DocumentStatusRejected, DocumentStatusUploaded))
		
		// Valid transitions from Expired
		assert.True(t, isValidDocumentStatusTransition(DocumentStatusExpired, DocumentStatusUploaded))
		
		// Invalid transitions
		assert.False(t, isValidDocumentStatusTransition(DocumentStatusVerified, DocumentStatusUploaded))
		assert.False(t, isValidDocumentStatusTransition(DocumentStatusVerified, DocumentStatusRejected))
		assert.False(t, isValidDocumentStatusTransition(DocumentStatusRejected, DocumentStatusVerified))
	})
}