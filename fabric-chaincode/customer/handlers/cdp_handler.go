package handlers

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/customer/domain"
	customerServices "github.com/brycemacchaveli/origin.block/fabric-chaincode/customer/services"
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/shared/config"
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/shared/services"
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/shared/utils"
)

// CDPHandler handles Canonical Data Passport operations
type CDPHandler struct {
	persistenceService *services.PersistenceService
	eventService       *customerServices.EventService
}

// NewCDPHandler creates a new CDP handler
func NewCDPHandler() *CDPHandler {
	return &CDPHandler{
		persistenceService: services.NewPersistenceService(),
		eventService:       customerServices.NewEventService(),
	}
}

// GenerateCDP creates a new Canonical Data Passport for a customer
// Requirements: 1.1, 1.2, 1.10
func (h *CDPHandler) GenerateCDP(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	// Parse the CDP generation request
	var req domain.CDPGenerationRequest
	if err := json.Unmarshal([]byte(args[0]), &req); err != nil {
		return nil, fmt.Errorf("failed to parse CDP generation request: %v", err)
	}

	// Validate request
	if req.CustomerID == "" {
		return nil, fmt.Errorf("customer ID is required")
	}
	if req.ValidityDays <= 0 {
		return nil, fmt.Errorf("validity days must be positive")
	}
	if req.ActorID == "" {
		return nil, fmt.Errorf("actor ID is required")
	}

	// Get the customer to verify existence and get data for hashing
	customerKey := fmt.Sprintf("CUSTOMER_%s", req.CustomerID)
	var customer domain.Customer
	if err := h.persistenceService.Get(stub, customerKey, &customer); err != nil {
		return nil, fmt.Errorf("customer not found: %v", err)
	}

	// Get KYC record for hashing
	kycKey := fmt.Sprintf("KYC_%s", req.CustomerID)
	var kycRecord interface{}
	kycData := []byte{}
	if err := h.persistenceService.Get(stub, kycKey, &kycRecord); err == nil {
		kycData, _ = json.Marshal(kycRecord)
	}

	// Generate unique CDP ID
	cdpID := utils.GenerateID(config.CDPPrefix)

	// Get transaction ID for source tracking
	txID := stub.GetTxID()

	// Create cryptographic hashes (SHA-256)
	kycHash := h.generateHash(kycData)
	incomeHash := h.generateHash([]byte(customer.NationalID)) // Placeholder for income data
	consentHash := h.generateHash([]byte(customer.ConsentPreferences))

	// Set dates
	generatedDate := time.Now()
	expirationDate := generatedDate.AddDate(0, 0, req.ValidityDays)

	// Create CDP
	cdp := &domain.CanonicalDataPassport{
		CDPID:                cdpID,
		CustomerID:           req.CustomerID,
		KYCHash:              kycHash,
		IncomeHash:           incomeHash,
		ConsentHash:          consentHash,
		VerificationLevel:    req.VerificationLevel,
		GeneratedDate:        generatedDate,
		ExpirationDate:       expirationDate,
		SourceTransactionIDs: []string{txID},
		IssuedBy:             req.ActorID,
		Status:               domain.CDPStatusValid,
	}

	// Store CDP in ledger
	cdpKey := fmt.Sprintf("CDP_%s", cdpID)
	if err := h.persistenceService.Put(stub, cdpKey, cdp); err != nil {
		return nil, fmt.Errorf("failed to store CDP: %v", err)
	}

	// Store CDP in Private Data Collection
	if err := h.storeCDPInPrivateData(stub, cdp); err != nil {
		return nil, fmt.Errorf("failed to store CDP in private data: %v", err)
	}

	// Update customer record with current CDP ID
	customer.CurrentCDPID = cdpID
	if customer.CDPHistory == nil {
		customer.CDPHistory = []string{}
	}
	customer.CDPHistory = append(customer.CDPHistory, cdpID)
	customer.LastUpdated = time.Now()
	customer.LastUpdatedBy = req.ActorID

	if err := h.persistenceService.Put(stub, customerKey, &customer); err != nil {
		return nil, fmt.Errorf("failed to update customer with CDP ID: %v", err)
	}

	// Create index for customer to CDP lookup
	customerCDPKey := fmt.Sprintf("CUSTOMER_CDP_%s", req.CustomerID)
	if err := stub.PutState(customerCDPKey, []byte(cdpID)); err != nil {
		return nil, fmt.Errorf("failed to create customer CDP index: %v", err)
	}

	return json.Marshal(cdp)
}

// GetCDP retrieves a CDP by ID from ledger
// Requirements: 1.8
func (h *CDPHandler) GetCDP(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	cdpID := args[0]
	if cdpID == "" {
		return nil, fmt.Errorf("CDP ID is required")
	}

	// Retrieve CDP from ledger
	cdpKey := fmt.Sprintf("CDP_%s", cdpID)
	var cdp domain.CanonicalDataPassport
	if err := h.persistenceService.Get(stub, cdpKey, &cdp); err != nil {
		return nil, fmt.Errorf("CDP not found: %v", err)
	}

	// Validate access permissions (basic check - can be enhanced)
	// In a production system, this would check the caller's MSP ID and permissions
	callerMSPID, err := stub.GetCreator()
	if err != nil {
		return nil, fmt.Errorf("failed to get caller identity: %v", err)
	}
	if len(callerMSPID) == 0 {
		return nil, fmt.Errorf("unauthorized access to CDP")
	}

	return json.Marshal(&cdp)
}

// ValidateCDP checks if a CDP is valid and not expired
// Requirements: 1.5, 1.7
func (h *CDPHandler) ValidateCDP(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	cdpID := args[0]
	if cdpID == "" {
		return nil, fmt.Errorf("CDP ID is required")
	}

	// Retrieve CDP
	cdpKey := fmt.Sprintf("CDP_%s", cdpID)
	var cdp domain.CanonicalDataPassport
	if err := h.persistenceService.Get(stub, cdpKey, &cdp); err != nil {
		result := &domain.CDPValidationResult{
			IsValid:           false,
			CDPID:             cdpID,
			ValidationMessage: fmt.Sprintf("CDP not found: %v", err),
		}
		resultBytes, _ := json.Marshal(result)
		return resultBytes, nil
	}

	// Check CDP status
	currentTime := time.Now()
	isValid := true
	validationMessage := "CDP is valid"

	// Check if revoked
	if cdp.Status == domain.CDPStatusRevoked {
		isValid = false
		validationMessage = fmt.Sprintf("CDP has been revoked: %s", cdp.RevocationReason)
	} else if cdp.Status == domain.CDPStatusExpired {
		isValid = false
		validationMessage = "CDP status is marked as expired"
	} else if currentTime.After(cdp.ExpirationDate) {
		// Check expiration date
		isValid = false
		validationMessage = fmt.Sprintf("CDP expired on %s", utils.FormatTime(cdp.ExpirationDate))
		
		// Update status to expired if not already
		if cdp.Status == domain.CDPStatusValid {
			cdp.Status = domain.CDPStatusExpired
			if err := h.persistenceService.Put(stub, cdpKey, &cdp); err != nil {
				// Log error but don't fail validation
				validationMessage += fmt.Sprintf(" (failed to update status: %v)", err)
			}
		}
	}

	result := &domain.CDPValidationResult{
		IsValid:           isValid,
		CDPID:             cdp.CDPID,
		VerificationLevel: cdp.VerificationLevel,
		ExpirationDate:    cdp.ExpirationDate,
		Status:            cdp.Status,
		ValidationMessage: validationMessage,
	}

	return json.Marshal(result)
}

// RevokeCDP invalidates a CDP
// Requirements: 1.10
func (h *CDPHandler) RevokeCDP(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	// Parse the revocation request
	var req domain.CDPRevocationRequest
	if err := json.Unmarshal([]byte(args[0]), &req); err != nil {
		return nil, fmt.Errorf("failed to parse CDP revocation request: %v", err)
	}

	// Validate request
	if req.CDPID == "" {
		return nil, fmt.Errorf("CDP ID is required")
	}
	if req.RevocationReason == "" {
		return nil, fmt.Errorf("revocation reason is required")
	}
	if req.ActorID == "" {
		return nil, fmt.Errorf("actor ID is required")
	}

	// Retrieve CDP
	cdpKey := fmt.Sprintf("CDP_%s", req.CDPID)
	var cdp domain.CanonicalDataPassport
	if err := h.persistenceService.Get(stub, cdpKey, &cdp); err != nil {
		return nil, fmt.Errorf("CDP not found: %v", err)
	}

	// Check if already revoked
	if cdp.Status == domain.CDPStatusRevoked {
		return nil, fmt.Errorf("CDP is already revoked")
	}

	// Update CDP status to REVOKED
	revokedTime := time.Now()
	cdp.Status = domain.CDPStatusRevoked
	cdp.RevokedDate = &revokedTime
	cdp.RevocationReason = req.RevocationReason

	// Store updated CDP
	if err := h.persistenceService.Put(stub, cdpKey, &cdp); err != nil {
		return nil, fmt.Errorf("failed to update CDP status: %v", err)
	}

	// Update CDP in Private Data Collection
	if err := h.storeCDPInPrivateData(stub, &cdp); err != nil {
		return nil, fmt.Errorf("failed to update CDP in private data: %v", err)
	}

	// Update customer record to clear current CDP ID
	customerKey := fmt.Sprintf("CUSTOMER_%s", cdp.CustomerID)
	var customer domain.Customer
	if err := h.persistenceService.Get(stub, customerKey, &customer); err == nil {
		if customer.CurrentCDPID == req.CDPID {
			customer.CurrentCDPID = ""
			customer.LastUpdated = time.Now()
			customer.LastUpdatedBy = req.ActorID
			if err := h.persistenceService.Put(stub, customerKey, &customer); err != nil {
				// Log error but don't fail revocation
				return nil, fmt.Errorf("CDP revoked but failed to update customer record: %v", err)
			}
		}
	}

	return json.Marshal(&cdp)
}

// Helper methods

// generateHash creates a SHA-256 hash of the input data
func (h *CDPHandler) generateHash(data []byte) string {
	hash := sha256.Sum256(data)
	return hex.EncodeToString(hash[:])
}

// storeCDPInPrivateData stores CDP in Private Data Collection
func (h *CDPHandler) storeCDPInPrivateData(stub shim.ChaincodeStubInterface, cdp *domain.CanonicalDataPassport) error {
	cdpJSON, err := json.Marshal(cdp)
	if err != nil {
		return fmt.Errorf("failed to marshal CDP: %v", err)
	}

	// Store in private data collection named "cdpPrivateData"
	cdpKey := fmt.Sprintf("CDP_%s", cdp.CDPID)
	if err := stub.PutPrivateData("cdpPrivateData", cdpKey, cdpJSON); err != nil {
		return fmt.Errorf("failed to store in private data collection: %v", err)
	}

	return nil
}

// GetCustomerCurrentCDP retrieves the current CDP for a customer
func (h *CDPHandler) GetCustomerCurrentCDP(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	customerID := args[0]
	if customerID == "" {
		return nil, fmt.Errorf("customer ID is required")
	}

	// Get customer to find current CDP ID
	customerKey := fmt.Sprintf("CUSTOMER_%s", customerID)
	var customer domain.Customer
	if err := h.persistenceService.Get(stub, customerKey, &customer); err != nil {
		return nil, fmt.Errorf("customer not found: %v", err)
	}

	if customer.CurrentCDPID == "" {
		return nil, fmt.Errorf("customer has no current CDP")
	}

	// Get the CDP
	cdpKey := fmt.Sprintf("CDP_%s", customer.CurrentCDPID)
	var cdp domain.CanonicalDataPassport
	if err := h.persistenceService.Get(stub, cdpKey, &cdp); err != nil {
		return nil, fmt.Errorf("CDP not found: %v", err)
	}

	return json.Marshal(&cdp)
}
