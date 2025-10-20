package handlers

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/customer/domain"
	customerServices "github.com/brycemacchaveli/origin.block/fabric-chaincode/customer/services"
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/shared/config"
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/shared/services"
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/shared/utils"
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/shared/validation"
)

// KYCHandler handles KYC and AML operations
type KYCHandler struct {
	persistenceService *services.PersistenceService
	eventService      *customerServices.EventService
}

// NewKYCHandler creates a new KYC handler
func NewKYCHandler() *KYCHandler {
	return &KYCHandler{
		persistenceService: services.NewPersistenceService(),
		eventService:      customerServices.NewEventService(),
	}
}

// InitiateKYC initiates KYC verification for a customer
func (h *KYCHandler) InitiateKYC(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	var req domain.KYCInitiationRequest
	if err := json.Unmarshal([]byte(args[0]), &req); err != nil {
		return nil, fmt.Errorf("failed to parse KYC initiation request: %v", err)
	}

	// Validate customer exists
	customerKey := fmt.Sprintf("CUSTOMER_%s", req.CustomerID)
	var customer domain.Customer
	if err := h.persistenceService.Get(stub, customerKey, &customer); err != nil {
		return nil, fmt.Errorf("customer not found: %v", err)
	}

	// Generate KYC ID
	kycID := utils.GenerateID(config.KYCRecordPrefix)

	// Create KYC record
	kycRecord := &domain.KYCRecord{
		KYCID:           kycID,
		CustomerID:      req.CustomerID,
		Status:          validation.KYCStatusPending,
		DocumentHashes:  req.DocumentHashes,
		VerificationNotes: "",
		VerifiedBy:      "",
		CreatedDate:     time.Now(),
		LastUpdated:     time.Now(),
	}

	// Validate KYC record
	if err := domain.ValidateKYCRecord(kycRecord); err != nil {
		return nil, fmt.Errorf("KYC record validation failed: %v", err)
	}

	// Store KYC record
	kycKey := fmt.Sprintf("KYC_%s", kycID)
	if err := h.persistenceService.Put(stub, kycKey, kycRecord); err != nil {
		return nil, fmt.Errorf("failed to store KYC record: %v", err)
	}

	// Create index by customer ID
	customerKYCKey := fmt.Sprintf("CUSTOMER_KYC_%s", req.CustomerID)
	if err := stub.PutState(customerKYCKey, []byte(kycID)); err != nil {
		return nil, fmt.Errorf("failed to create customer KYC index: %v", err)
	}

	// Record history
	kycJSON, _ := utils.MarshalJSONString(kycRecord)
	if err := h.recordKYCHistory(stub, kycID, "CREATE", "kyc_record", "", kycJSON, req.ActorID); err != nil {
		return nil, fmt.Errorf("failed to record history: %v", err)
	}

	// Emit event
	if err := h.eventService.EmitKYCInitiated(stub, kycRecord, req.ActorID); err != nil {
		return nil, fmt.Errorf("failed to emit event: %v", err)
	}

	return json.Marshal(kycRecord)
}

// UpdateKYCStatus updates the status of a KYC record
func (h *KYCHandler) UpdateKYCStatus(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	var req domain.KYCStatusUpdateRequest
	if err := json.Unmarshal([]byte(args[0]), &req); err != nil {
		return nil, fmt.Errorf("failed to parse KYC status update request: %v", err)
	}

	// Get existing KYC record
	kycKey := fmt.Sprintf("KYC_%s", req.KYCID)
	var kycRecord domain.KYCRecord
	if err := h.persistenceService.Get(stub, kycKey, &kycRecord); err != nil {
		return nil, fmt.Errorf("KYC record not found: %v", err)
	}

	// Record history for status change
	if err := h.recordKYCHistory(stub, req.KYCID, "STATUS_UPDATE", "status", string(kycRecord.Status), string(req.NewStatus), req.ActorID); err != nil {
		return nil, err
	}

	// Update KYC record
	kycRecord.Status = req.NewStatus
	kycRecord.VerificationNotes = req.VerificationNotes
	kycRecord.VerifiedBy = req.ActorID
	kycRecord.LastUpdated = time.Now()

	// Set verification and expiry dates for verified status
	if req.NewStatus == validation.KYCStatusVerified {
		now := time.Now()
		kycRecord.VerificationDate = &now
		expiryDate := now.AddDate(1, 0, 0) // 1 year from now
		kycRecord.ExpiryDate = &expiryDate
	}

	// Store updated KYC record
	if err := h.persistenceService.Put(stub, kycKey, &kycRecord); err != nil {
		return nil, fmt.Errorf("failed to update KYC record: %v", err)
	}

	// Emit appropriate event
	if req.NewStatus == validation.KYCStatusVerified {
		if err := h.eventService.EmitKYCVerified(stub, &kycRecord, req.ActorID); err != nil {
			return nil, fmt.Errorf("failed to emit KYC verified event: %v", err)
		}
	} else if req.NewStatus == validation.KYCStatusFailed {
		if err := h.eventService.EmitKYCFailed(stub, &kycRecord, req.ActorID); err != nil {
			return nil, fmt.Errorf("failed to emit KYC failed event: %v", err)
		}
	}

	return json.Marshal(&kycRecord)
}

// GetKYCRecord retrieves a KYC record by ID
func (h *KYCHandler) GetKYCRecord(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	kycID := args[0]
	kycKey := fmt.Sprintf("KYC_%s", kycID)

	var kycRecord domain.KYCRecord
	if err := h.persistenceService.Get(stub, kycKey, &kycRecord); err != nil {
		return nil, fmt.Errorf("KYC record not found: %v", err)
	}

	return json.Marshal(&kycRecord)
}

// InitiateAMLCheck initiates an AML check for a customer
func (h *KYCHandler) InitiateAMLCheck(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	var req domain.AMLCheckRequest
	if err := json.Unmarshal([]byte(args[0]), &req); err != nil {
		return nil, fmt.Errorf("failed to parse AML check request: %v", err)
	}

	// Validate customer exists
	customerKey := fmt.Sprintf("CUSTOMER_%s", req.CustomerID)
	var customer domain.Customer
	if err := h.persistenceService.Get(stub, customerKey, &customer); err != nil {
		return nil, fmt.Errorf("customer not found: %v", err)
	}

	// Generate AML ID
	amlID := utils.GenerateID(config.AMLCheckPrefix)

	// Create AML record
	amlRecord := &domain.AMLRecord{
		AMLID:       amlID,
		CustomerID:  req.CustomerID,
		Status:      validation.AMLStatusClear, // Default to clear, will be updated by compliance checks
		CheckDate:   time.Now(),
		RiskScore:   0.0,
		Flags:       []string{},
		CheckedBy:   req.ActorID,
		Notes:       "AML check initiated",
		CreatedDate: time.Now(),
		LastUpdated: time.Now(),
	}

	// Validate AML record
	if err := domain.ValidateAMLRecord(amlRecord); err != nil {
		return nil, fmt.Errorf("AML record validation failed: %v", err)
	}

	// Store AML record
	amlKey := fmt.Sprintf("AML_%s", amlID)
	if err := h.persistenceService.Put(stub, amlKey, amlRecord); err != nil {
		return nil, fmt.Errorf("failed to store AML record: %v", err)
	}

	// Create index by customer ID
	customerAMLKey := fmt.Sprintf("CUSTOMER_AML_%s", req.CustomerID)
	if err := stub.PutState(customerAMLKey, []byte(amlID)); err != nil {
		return nil, fmt.Errorf("failed to create customer AML index: %v", err)
	}

	// Record history
	amlJSON, _ := utils.MarshalJSONString(amlRecord)
	if err := h.recordAMLHistory(stub, amlID, "CREATE", "aml_record", "", amlJSON, req.ActorID); err != nil {
		return nil, fmt.Errorf("failed to record history: %v", err)
	}

	// Emit event
	if err := h.eventService.EmitAMLCheckInitiated(stub, amlRecord, req.ActorID); err != nil {
		return nil, fmt.Errorf("failed to emit event: %v", err)
	}

	return json.Marshal(amlRecord)
}

// UpdateAMLStatus updates the status of an AML record
func (h *KYCHandler) UpdateAMLStatus(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	var req domain.AMLStatusUpdateRequest
	if err := json.Unmarshal([]byte(args[0]), &req); err != nil {
		return nil, fmt.Errorf("failed to parse AML status update request: %v", err)
	}

	// Get existing AML record
	amlKey := fmt.Sprintf("AML_%s", req.AMLID)
	var amlRecord domain.AMLRecord
	if err := h.persistenceService.Get(stub, amlKey, &amlRecord); err != nil {
		return nil, fmt.Errorf("AML record not found: %v", err)
	}

	// Record history for status change
	if err := h.recordAMLHistory(stub, req.AMLID, "STATUS_UPDATE", "status", string(amlRecord.Status), string(req.NewStatus), req.ActorID); err != nil {
		return nil, err
	}

	// Update AML record
	amlRecord.Status = req.NewStatus
	amlRecord.RiskScore = req.RiskScore
	amlRecord.Flags = req.Flags
	amlRecord.Notes = req.Notes
	amlRecord.CheckedBy = req.ActorID
	amlRecord.LastUpdated = time.Now()

	// Validate updated record
	if err := domain.ValidateAMLRecord(&amlRecord); err != nil {
		return nil, fmt.Errorf("updated AML record validation failed: %v", err)
	}

	// Store updated AML record
	if err := h.persistenceService.Put(stub, amlKey, &amlRecord); err != nil {
		return nil, fmt.Errorf("failed to update AML record: %v", err)
	}

	// Emit appropriate event
	if req.NewStatus == validation.AMLStatusFlagged {
		if err := h.eventService.EmitAMLFlagged(stub, &amlRecord, req.ActorID); err != nil {
			return nil, fmt.Errorf("failed to emit AML flagged event: %v", err)
		}
	} else {
		if err := h.eventService.EmitAMLCheckCompleted(stub, &amlRecord, req.ActorID); err != nil {
			return nil, fmt.Errorf("failed to emit AML completed event: %v", err)
		}
	}

	return json.Marshal(&amlRecord)
}

// GetAMLRecord retrieves an AML record by ID
func (h *KYCHandler) GetAMLRecord(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	amlID := args[0]
	amlKey := fmt.Sprintf("AML_%s", amlID)

	var amlRecord domain.AMLRecord
	if err := h.persistenceService.Get(stub, amlKey, &amlRecord); err != nil {
		return nil, fmt.Errorf("AML record not found: %v", err)
	}

	return json.Marshal(&amlRecord)
}

// QueryKYCByStatus queries KYC records by status
func (h *KYCHandler) QueryKYCByStatus(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	status := args[0]
	
	// Validate status
	if err := validation.ValidateKYCStatus(status); err != nil {
		return nil, fmt.Errorf("invalid KYC status: %v", err)
	}

	// Query KYC records by status using composite key
	iterator, err := stub.GetStateByPartialCompositeKey("KYC_STATUS", []string{status})
	if err != nil {
		return nil, fmt.Errorf("failed to get KYC records by status: %v", err)
	}
	defer iterator.Close()

	var kycRecords []domain.KYCRecord
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate KYC records: %v", err)
		}

		var kycRecord domain.KYCRecord
		if err := json.Unmarshal(response.Value, &kycRecord); err != nil {
			return nil, fmt.Errorf("failed to unmarshal KYC record: %v", err)
		}

		kycRecords = append(kycRecords, kycRecord)
	}

	return json.Marshal(kycRecords)
}

// Helper methods

func (h *KYCHandler) recordKYCHistory(stub shim.ChaincodeStubInterface, kycID, changeType, fieldName, previousValue, newValue, actorID string) error {
	historyID := utils.GenerateID(config.HistoryPrefix)
	txID := stub.GetTxID()

	historyEntry := map[string]interface{}{
		"historyID":     historyID,
		"entityID":      kycID,
		"entityType":    "KYCRecord",
		"timestamp":     utils.GetCurrentTimeString(),
		"changeType":    changeType,
		"fieldName":     fieldName,
		"previousValue": previousValue,
		"newValue":      newValue,
		"actorID":       actorID,
		"transactionID": txID,
	}

	compositeKey, err := stub.CreateCompositeKey("HISTORY", []string{kycID, historyID})
	if err != nil {
		return fmt.Errorf("failed to create composite key: %v", err)
	}

	return h.persistenceService.Put(stub, compositeKey, historyEntry)
}

func (h *KYCHandler) recordAMLHistory(stub shim.ChaincodeStubInterface, amlID, changeType, fieldName, previousValue, newValue, actorID string) error {
	historyID := utils.GenerateID(config.HistoryPrefix)
	txID := stub.GetTxID()

	historyEntry := map[string]interface{}{
		"historyID":     historyID,
		"entityID":      amlID,
		"entityType":    "AMLRecord",
		"timestamp":     utils.GetCurrentTimeString(),
		"changeType":    changeType,
		"fieldName":     fieldName,
		"previousValue": previousValue,
		"newValue":      newValue,
		"actorID":       actorID,
		"transactionID": txID,
	}

	compositeKey, err := stub.CreateCompositeKey("HISTORY", []string{amlID, historyID})
	if err != nil {
		return fmt.Errorf("failed to create composite key: %v", err)
	}

	return h.persistenceService.Put(stub, compositeKey, historyEntry)
}