package main

import (
	"encoding/json"
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/blockchain-financial-platform/fabric-chaincode/shared"
	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/hyperledger/fabric-protos-go/peer"
)

// CustomerChaincode implements the fabric Contract interface
type CustomerChaincode struct {
}

// Customer represents a customer entity in the blockchain
type Customer struct {
	CustomerID        string    `json:"customerID"`
	FirstName         string    `json:"firstName"`
	LastName          string    `json:"lastName"`
	DateOfBirth       time.Time `json:"dateOfBirth"`
	NationalID        string    `json:"nationalID"` // Hashed for privacy
	Address           string    `json:"address"`
	ContactEmail      string    `json:"contactEmail"`
	ContactPhone      string    `json:"contactPhone"`
	KYCStatus         string    `json:"kycStatus"`
	AMLStatus         string    `json:"amlStatus"`
	ConsentPreferences string   `json:"consentPreferences"` // JSON string for consent data
	Status            string    `json:"status"`
	CreationDate      time.Time `json:"creationDate"`
	LastUpdated       time.Time `json:"lastUpdated"`
	UpdatedByActor    string    `json:"updatedByActor"`
	Version           int       `json:"version"`
}

// CustomerEvent represents events emitted by customer operations
type CustomerEvent struct {
	EventType    string    `json:"eventType"`
	CustomerID   string    `json:"customerID"`
	ActorID      string    `json:"actorID"`
	Timestamp    time.Time `json:"timestamp"`
	Details      string    `json:"details"`
}

// ConsentPreferences represents customer consent preferences
type ConsentPreferences struct {
	DataSharing          bool      `json:"dataSharing"`
	MarketingCommunication bool    `json:"marketingCommunication"`
	ThirdPartySharing    bool      `json:"thirdPartySharing"`
	CreditBureauSharing  bool      `json:"creditBureauSharing"`
	RegulatoryReporting  bool      `json:"regulatoryReporting"`
	ConsentDate          time.Time `json:"consentDate"`
	ExpiryDate           time.Time `json:"expiryDate"`
	ConsentVersion       string    `json:"consentVersion"`
	IPAddress            string    `json:"ipAddress"`
	UserAgent            string    `json:"userAgent"`
}

// Init is called during chaincode instantiation to initialize any data
func (t *CustomerChaincode) Init(stub shim.ChaincodeStubInterface) peer.Response {
	return shim.Success(nil)
}

// Invoke is called per transaction on the chaincode
func (t *CustomerChaincode) Invoke(stub shim.ChaincodeStubInterface) peer.Response {
	function, args := stub.GetFunctionAndParameters()
	
	switch function {
	case "CreateCustomer":
		return t.CreateCustomer(stub, args)
	case "UpdateCustomerDetails":
		return t.UpdateCustomerDetails(stub, args)
	case "GetCustomer":
		return t.GetCustomer(stub, args)
	case "GetCustomerHistory":
		return t.GetCustomerHistory(stub, args)
	case "RecordConsent":
		return t.RecordConsent(stub, args)
	case "UpdateConsent":
		return t.UpdateConsent(stub, args)
	case "GetConsent":
		return t.GetConsent(stub, args)
	case "PerformKYCValidation":
		return t.PerformKYCValidation(stub, args)
	case "PerformAMLCheck":
		return t.PerformAMLCheck(stub, args)
	case "ping":
		return shim.Success([]byte("pong"))
	default:
		return shim.Error("Invalid function name: " + function)
	}
}

// CreateCustomer creates a new customer record with validation and event emission
func (t *CustomerChaincode) CreateCustomer(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	// Validate arguments
	if len(args) != 8 {
		return shim.Error("Incorrect number of arguments. Expecting 8: firstName, lastName, dateOfBirth, nationalID, address, contactEmail, contactPhone, actorID")
	}

	firstName := args[0]
	lastName := args[1]
	dateOfBirthStr := args[2]
	nationalID := args[3]
	address := args[4]
	contactEmail := args[5]
	contactPhone := args[6]
	actorID := args[7]

	// Validate actor permissions
	_, err := shared.ValidateActorAccess(stub, actorID, shared.PermissionCreateCustomer)
	if err != nil {
		return shim.Error(fmt.Sprintf("Access denied: %v", err))
	}

	// Parse date of birth
	dateOfBirth, err := time.Parse("2006-01-02", dateOfBirthStr)
	if err != nil {
		return shim.Error(fmt.Sprintf("Invalid date of birth format. Use YYYY-MM-DD: %v", err))
	}

	// Validate required fields
	requiredFields := map[string]string{
		"firstName":    firstName,
		"lastName":     lastName,
		"nationalID":   nationalID,
		"address":      address,
		"contactEmail": contactEmail,
		"contactPhone": contactPhone,
	}
	if err := shared.ValidateRequired(requiredFields); err != nil {
		return shim.Error(fmt.Sprintf("Validation failed: %v", err))
	}

	// Validate field formats
	if err := shared.ValidateEmail(contactEmail); err != nil {
		return shim.Error(fmt.Sprintf("Invalid email: %v", err))
	}
	if err := shared.ValidatePhone(contactPhone); err != nil {
		return shim.Error(fmt.Sprintf("Invalid phone: %v", err))
	}
	if err := shared.ValidateNationalID(nationalID); err != nil {
		return shim.Error(fmt.Sprintf("Invalid national ID: %v", err))
	}
	if err := shared.ValidateDateOfBirth(dateOfBirth); err != nil {
		return shim.Error(fmt.Sprintf("Invalid date of birth: %v", err))
	}
	if err := shared.ValidateAddress(address); err != nil {
		return shim.Error(fmt.Sprintf("Invalid address: %v", err))
	}

	// Generate unique customer ID
	customerID := shared.GenerateID("CUST")

	// Hash the national ID for privacy
	hashedNationalID := shared.HashSensitiveData(nationalID, customerID)

	// Create customer record
	now := time.Now()
	customer := Customer{
		CustomerID:         customerID,
		FirstName:          firstName,
		LastName:           lastName,
		DateOfBirth:        dateOfBirth,
		NationalID:         hashedNationalID,
		Address:            address,
		ContactEmail:       contactEmail,
		ContactPhone:       contactPhone,
		KYCStatus:          string(shared.KYCStatusPending),
		AMLStatus:          string(shared.AMLStatusClear),
		ConsentPreferences: "{}", // Empty JSON object initially
		Status:             string(shared.CustomerStatusActive),
		CreationDate:       now,
		LastUpdated:        now,
		UpdatedByActor:     actorID,
		Version:            1,
	}

	// Perform automatic AML screening during customer creation
	amlRequest := AMLCheckRequest{
		CustomerID:  customerID,
		FirstName:   firstName,
		LastName:    lastName,
		NationalID:  hashedNationalID,
		DateOfBirth: dateOfBirth.Format("2006-01-02"),
		Country:     t.extractCountryFromAddress(address),
	}

	amlResponse, err := t.performAMLScreening(stub, amlRequest)
	if err != nil {
		return shim.Error(fmt.Sprintf("Automatic AML screening failed: %v", err))
	}

	// Update customer AML status based on screening results
	customer.AMLStatus = amlResponse.Status

	// If customer is blocked, prevent creation
	if amlResponse.Status == string(shared.AMLStatusBlocked) {
		return shim.Error(fmt.Sprintf("Customer creation blocked due to AML screening: customer appears on sanction list"))
	}

	// Store AML check record
	amlRecordKey := fmt.Sprintf("AML_RECORD_%s_%s", customerID, shared.GenerateID("AML"))
	if err := shared.PutStateAsJSON(stub, amlRecordKey, amlResponse); err != nil {
		return shim.Error(fmt.Sprintf("Failed to store AML record: %v", err))
	}

	// Create compliance event if customer is flagged
	if amlResponse.Status == string(shared.AMLStatusFlagged) {
		if err := t.createComplianceEvent(stub, customerID, "AML_FLAG_ON_CREATION", fmt.Sprintf("Customer flagged during creation AML screening: risk score %.2f", amlResponse.RiskScore), actorID); err != nil {
			// Log error but don't fail the transaction
			fmt.Printf("Warning: Failed to create compliance event: %v", err)
		}
	}

	// Store customer in ledger
	if err := shared.PutStateAsJSON(stub, customerID, customer); err != nil {
		return shim.Error(fmt.Sprintf("Failed to store customer: %v", err))
	}

	// Record history entry
	if err := shared.RecordHistoryEntry(stub, customerID, "Customer", "CREATE", "ALL", "", "Customer created", actorID); err != nil {
		return shim.Error(fmt.Sprintf("Failed to record history: %v", err))
	}

	// Emit customer created event
	event := CustomerEvent{
		EventType:  "CUSTOMER_CREATED",
		CustomerID: customerID,
		ActorID:    actorID,
		Timestamp:  now,
		Details:    fmt.Sprintf("Customer %s %s created", firstName, lastName),
	}
	if err := shared.EmitEvent(stub, "CustomerCreated", event); err != nil {
		return shim.Error(fmt.Sprintf("Failed to emit event: %v", err))
	}

	// Return customer ID
	return shim.Success([]byte(customerID))
}

// UpdateCustomerDetails updates customer details with automatic versioning and history tracking
func (t *CustomerChaincode) UpdateCustomerDetails(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	// Validate arguments
	if len(args) != 8 {
		return shim.Error("Incorrect number of arguments. Expecting 8: customerID, firstName, lastName, address, contactEmail, contactPhone, status, actorID")
	}

	customerID := args[0]
	firstName := args[1]
	lastName := args[2]
	address := args[3]
	contactEmail := args[4]
	contactPhone := args[5]
	status := args[6]
	actorID := args[7]

	// Validate actor permissions
	_, err := shared.ValidateActorAccess(stub, actorID, shared.PermissionUpdateCustomer)
	if err != nil {
		return shim.Error(fmt.Sprintf("Access denied: %v", err))
	}

	// Get existing customer
	var existingCustomer Customer
	if err := shared.GetStateAsJSON(stub, customerID, &existingCustomer); err != nil {
		return shim.Error(fmt.Sprintf("Customer not found: %v", err))
	}

	// Validate customer compliance status before allowing updates
	if err := t.ValidateCustomerForCompliance(stub, customerID); err != nil {
		// Allow updates for compliance officers even if customer is flagged
		actor, actorErr := shared.ValidateActorAccess(stub, actorID, shared.PermissionUpdateCompliance)
		if actorErr != nil || actor.Role != shared.RoleComplianceOfficer {
			return shim.Error(fmt.Sprintf("Customer update blocked due to compliance issues: %v", err))
		}
	}

	// Validate field formats
	if firstName != "" {
		if err := shared.ValidateStringLength(firstName, 1, 100, "firstName"); err != nil {
			return shim.Error(fmt.Sprintf("Invalid first name: %v", err))
		}
	}
	if lastName != "" {
		if err := shared.ValidateStringLength(lastName, 1, 100, "lastName"); err != nil {
			return shim.Error(fmt.Sprintf("Invalid last name: %v", err))
		}
	}
	if address != "" {
		if err := shared.ValidateAddress(address); err != nil {
			return shim.Error(fmt.Sprintf("Invalid address: %v", err))
		}
	}
	if contactEmail != "" {
		if err := shared.ValidateEmail(contactEmail); err != nil {
			return shim.Error(fmt.Sprintf("Invalid email: %v", err))
		}
	}
	if contactPhone != "" {
		if err := shared.ValidatePhone(contactPhone); err != nil {
			return shim.Error(fmt.Sprintf("Invalid phone: %v", err))
		}
	}
	if status != "" {
		if err := shared.ValidateCustomerStatus(status); err != nil {
			return shim.Error(fmt.Sprintf("Invalid status: %v", err))
		}
		// Validate status transition only if status is different
		if status != existingCustomer.Status {
			if err := shared.ValidateStatusTransition(existingCustomer.Status, status, "Customer"); err != nil {
				return shim.Error(fmt.Sprintf("Invalid status transition: %v", err))
			}
		}
	}

	// Track changes and update fields
	now := time.Now()
	changes := []string{}

	if firstName != "" && firstName != existingCustomer.FirstName {
		if err := shared.RecordHistoryEntry(stub, customerID, "Customer", "UPDATE", "firstName", existingCustomer.FirstName, firstName, actorID); err != nil {
			return shim.Error(fmt.Sprintf("Failed to record history: %v", err))
		}
		existingCustomer.FirstName = firstName
		changes = append(changes, "firstName")
	}

	if lastName != "" && lastName != existingCustomer.LastName {
		if err := shared.RecordHistoryEntry(stub, customerID, "Customer", "UPDATE", "lastName", existingCustomer.LastName, lastName, actorID); err != nil {
			return shim.Error(fmt.Sprintf("Failed to record history: %v", err))
		}
		existingCustomer.LastName = lastName
		changes = append(changes, "lastName")
	}

	if address != "" && address != existingCustomer.Address {
		if err := shared.RecordHistoryEntry(stub, customerID, "Customer", "UPDATE", "address", existingCustomer.Address, address, actorID); err != nil {
			return shim.Error(fmt.Sprintf("Failed to record history: %v", err))
		}
		existingCustomer.Address = address
		changes = append(changes, "address")
	}

	if contactEmail != "" && contactEmail != existingCustomer.ContactEmail {
		if err := shared.RecordHistoryEntry(stub, customerID, "Customer", "UPDATE", "contactEmail", existingCustomer.ContactEmail, contactEmail, actorID); err != nil {
			return shim.Error(fmt.Sprintf("Failed to record history: %v", err))
		}
		existingCustomer.ContactEmail = contactEmail
		changes = append(changes, "contactEmail")
	}

	if contactPhone != "" && contactPhone != existingCustomer.ContactPhone {
		if err := shared.RecordHistoryEntry(stub, customerID, "Customer", "UPDATE", "contactPhone", existingCustomer.ContactPhone, contactPhone, actorID); err != nil {
			return shim.Error(fmt.Sprintf("Failed to record history: %v", err))
		}
		existingCustomer.ContactPhone = contactPhone
		changes = append(changes, "contactPhone")
	}

	if status != "" && status != existingCustomer.Status {
		if err := shared.RecordHistoryEntry(stub, customerID, "Customer", "UPDATE", "status", existingCustomer.Status, status, actorID); err != nil {
			return shim.Error(fmt.Sprintf("Failed to record history: %v", err))
		}
		existingCustomer.Status = status
		changes = append(changes, "status")
	}

	// If no changes, return success without updating
	if len(changes) == 0 {
		return shim.Success([]byte("No changes detected"))
	}

	// Update metadata
	existingCustomer.LastUpdated = now
	existingCustomer.UpdatedByActor = actorID
	existingCustomer.Version++

	// Store updated customer
	if err := shared.PutStateAsJSON(stub, customerID, existingCustomer); err != nil {
		return shim.Error(fmt.Sprintf("Failed to update customer: %v", err))
	}

	// Emit customer updated event
	event := CustomerEvent{
		EventType:  "CUSTOMER_UPDATED",
		CustomerID: customerID,
		ActorID:    actorID,
		Timestamp:  now,
		Details:    fmt.Sprintf("Customer updated. Changed fields: %v", changes),
	}
	if err := shared.EmitEvent(stub, "CustomerUpdated", event); err != nil {
		return shim.Error(fmt.Sprintf("Failed to emit event: %v", err))
	}

	// Return success
	customerJSON, _ := json.Marshal(existingCustomer)
	return shim.Success(customerJSON)
}

// GetCustomer retrieves a customer record with consent validation
func (t *CustomerChaincode) GetCustomer(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	// Validate arguments - now accepts optional third parameter for consent validation
	if len(args) < 2 || len(args) > 3 {
		return shim.Error("Incorrect number of arguments. Expecting 2-3: customerID, actorID, [validateConsent]")
	}

	customerID := args[0]
	actorID := args[1]
	validateConsent := len(args) == 3 && args[2] == "true"

	// Validate actor permissions
	actor, err := shared.ValidateActorAccess(stub, actorID, shared.PermissionViewCustomer)
	if err != nil {
		return shim.Error(fmt.Sprintf("Access denied: %v", err))
	}

	// Get customer from ledger
	var customer Customer
	if err := shared.GetStateAsJSON(stub, customerID, &customer); err != nil {
		return shim.Error(fmt.Sprintf("Customer not found: %v", err))
	}

	// Validate consent for data sharing if requested and actor is external
	if validateConsent && actor.ActorType == shared.ActorTypeExternalPartner {
		if err := t.ValidateConsentForDataSharing(stub, customerID, "DATA_SHARING"); err != nil {
			return shim.Error(fmt.Sprintf("Consent validation failed: %v", err))
		}
	}

	// Return customer data
	customerJSON, err := json.Marshal(customer)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to marshal customer: %v", err))
	}

	return shim.Success(customerJSON)
}

// GetCustomerHistory retrieves the complete history of a customer
func (t *CustomerChaincode) GetCustomerHistory(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	// Validate arguments
	if len(args) != 2 {
		return shim.Error("Incorrect number of arguments. Expecting 2: customerID, actorID")
	}

	customerID := args[0]
	actorID := args[1]

	// Validate actor permissions
	_, err := shared.ValidateActorAccess(stub, actorID, shared.PermissionViewCustomer)
	if err != nil {
		return shim.Error(fmt.Sprintf("Access denied: %v", err))
	}

	// Verify customer exists
	var customer Customer
	if err := shared.GetStateAsJSON(stub, customerID, &customer); err != nil {
		return shim.Error(fmt.Sprintf("Customer not found: %v", err))
	}

	// Get customer history
	history, err := shared.GetEntityHistory(stub, customerID)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to get customer history: %v", err))
	}

	// Return history data
	historyJSON, err := json.Marshal(history)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to marshal history: %v", err))
	}

	return shim.Success(historyJSON)
}

// RecordConsent records initial consent preferences for a customer
func (t *CustomerChaincode) RecordConsent(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	// Validate arguments
	if len(args) != 10 {
		return shim.Error("Incorrect number of arguments. Expecting 10: customerID, dataSharing, marketingCommunication, thirdPartySharing, creditBureauSharing, regulatoryReporting, consentVersion, ipAddress, userAgent, actorID")
	}

	customerID := args[0]
	dataSharing := args[1] == "true"
	marketingCommunication := args[2] == "true"
	thirdPartySharing := args[3] == "true"
	creditBureauSharing := args[4] == "true"
	regulatoryReporting := args[5] == "true"
	consentVersion := args[6]
	ipAddress := args[7]
	userAgent := args[8]
	actorID := args[9]

	// Validate actor permissions
	_, err := shared.ValidateActorAccess(stub, actorID, shared.PermissionUpdateCustomer)
	if err != nil {
		return shim.Error(fmt.Sprintf("Access denied: %v", err))
	}

	// Get existing customer
	var existingCustomer Customer
	if err := shared.GetStateAsJSON(stub, customerID, &existingCustomer); err != nil {
		return shim.Error(fmt.Sprintf("Customer not found: %v", err))
	}

	// Validate required fields
	requiredFields := map[string]string{
		"consentVersion": consentVersion,
		"ipAddress":      ipAddress,
		"userAgent":      userAgent,
	}
	if err := shared.ValidateRequired(requiredFields); err != nil {
		return shim.Error(fmt.Sprintf("Validation failed: %v", err))
	}

	// Validate IP address format (basic validation)
	if err := shared.ValidateStringLength(ipAddress, 7, 45, "ipAddress"); err != nil {
		return shim.Error(fmt.Sprintf("Invalid IP address: %v", err))
	}

	// Validate user agent
	if err := shared.ValidateStringLength(userAgent, 10, 500, "userAgent"); err != nil {
		return shim.Error(fmt.Sprintf("Invalid user agent: %v", err))
	}

	// Create consent preferences
	now := time.Now()
	consentPrefs := ConsentPreferences{
		DataSharing:            dataSharing,
		MarketingCommunication: marketingCommunication,
		ThirdPartySharing:      thirdPartySharing,
		CreditBureauSharing:    creditBureauSharing,
		RegulatoryReporting:    regulatoryReporting,
		ConsentDate:            now,
		ExpiryDate:             now.AddDate(1, 0, 0), // 1 year expiry
		ConsentVersion:         consentVersion,
		IPAddress:              ipAddress,
		UserAgent:              userAgent,
	}

	// Convert consent preferences to JSON
	consentJSON, err := json.Marshal(consentPrefs)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to marshal consent preferences: %v", err))
	}

	// Record history entry for previous consent
	if err := shared.RecordHistoryEntry(stub, customerID, "Customer", "UPDATE", "consentPreferences", existingCustomer.ConsentPreferences, string(consentJSON), actorID); err != nil {
		return shim.Error(fmt.Sprintf("Failed to record history: %v", err))
	}

	// Update customer with new consent preferences
	existingCustomer.ConsentPreferences = string(consentJSON)
	existingCustomer.LastUpdated = now
	existingCustomer.UpdatedByActor = actorID
	existingCustomer.Version++

	// Store updated customer
	if err := shared.PutStateAsJSON(stub, customerID, existingCustomer); err != nil {
		return shim.Error(fmt.Sprintf("Failed to update customer: %v", err))
	}

	// Emit consent recorded event
	event := CustomerEvent{
		EventType:  "CONSENT_RECORDED",
		CustomerID: customerID,
		ActorID:    actorID,
		Timestamp:  now,
		Details:    fmt.Sprintf("Consent preferences recorded for customer %s", customerID),
	}
	if err := shared.EmitEvent(stub, "ConsentRecorded", event); err != nil {
		return shim.Error(fmt.Sprintf("Failed to emit event: %v", err))
	}

	// Return success with consent preferences
	return shim.Success(consentJSON)
}

// UpdateConsent updates existing consent preferences for a customer
func (t *CustomerChaincode) UpdateConsent(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	// Validate arguments
	if len(args) != 10 {
		return shim.Error("Incorrect number of arguments. Expecting 10: customerID, dataSharing, marketingCommunication, thirdPartySharing, creditBureauSharing, regulatoryReporting, consentVersion, ipAddress, userAgent, actorID")
	}

	customerID := args[0]
	dataSharing := args[1] == "true"
	marketingCommunication := args[2] == "true"
	thirdPartySharing := args[3] == "true"
	creditBureauSharing := args[4] == "true"
	regulatoryReporting := args[5] == "true"
	consentVersion := args[6]
	ipAddress := args[7]
	userAgent := args[8]
	actorID := args[9]

	// Validate actor permissions
	_, err := shared.ValidateActorAccess(stub, actorID, shared.PermissionUpdateCustomer)
	if err != nil {
		return shim.Error(fmt.Sprintf("Access denied: %v", err))
	}

	// Get existing customer
	var existingCustomer Customer
	if err := shared.GetStateAsJSON(stub, customerID, &existingCustomer); err != nil {
		return shim.Error(fmt.Sprintf("Customer not found: %v", err))
	}

	// Parse existing consent preferences
	var existingConsent ConsentPreferences
	if existingCustomer.ConsentPreferences != "" && existingCustomer.ConsentPreferences != "{}" {
		if err := json.Unmarshal([]byte(existingCustomer.ConsentPreferences), &existingConsent); err != nil {
			return shim.Error(fmt.Sprintf("Failed to parse existing consent: %v", err))
		}
	}

	// Validate required fields
	requiredFields := map[string]string{
		"consentVersion": consentVersion,
		"ipAddress":      ipAddress,
		"userAgent":      userAgent,
	}
	if err := shared.ValidateRequired(requiredFields); err != nil {
		return shim.Error(fmt.Sprintf("Validation failed: %v", err))
	}

	// Validate IP address format (basic validation)
	if err := shared.ValidateStringLength(ipAddress, 7, 45, "ipAddress"); err != nil {
		return shim.Error(fmt.Sprintf("Invalid IP address: %v", err))
	}

	// Validate user agent
	if err := shared.ValidateStringLength(userAgent, 10, 500, "userAgent"); err != nil {
		return shim.Error(fmt.Sprintf("Invalid user agent: %v", err))
	}

	// Create updated consent preferences
	now := time.Now()
	updatedConsent := ConsentPreferences{
		DataSharing:            dataSharing,
		MarketingCommunication: marketingCommunication,
		ThirdPartySharing:      thirdPartySharing,
		CreditBureauSharing:    creditBureauSharing,
		RegulatoryReporting:    regulatoryReporting,
		ConsentDate:            now,
		ExpiryDate:             now.AddDate(1, 0, 0), // 1 year expiry
		ConsentVersion:         consentVersion,
		IPAddress:              ipAddress,
		UserAgent:              userAgent,
	}

	// Convert consent preferences to JSON
	consentJSON, err := json.Marshal(updatedConsent)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to marshal consent preferences: %v", err))
	}

	// Record history entry for consent update
	if err := shared.RecordHistoryEntry(stub, customerID, "Customer", "UPDATE", "consentPreferences", existingCustomer.ConsentPreferences, string(consentJSON), actorID); err != nil {
		return shim.Error(fmt.Sprintf("Failed to record history: %v", err))
	}

	// Update customer with new consent preferences
	existingCustomer.ConsentPreferences = string(consentJSON)
	existingCustomer.LastUpdated = now
	existingCustomer.UpdatedByActor = actorID
	existingCustomer.Version++

	// Store updated customer
	if err := shared.PutStateAsJSON(stub, customerID, existingCustomer); err != nil {
		return shim.Error(fmt.Sprintf("Failed to update customer: %v", err))
	}

	// Emit consent updated event
	event := CustomerEvent{
		EventType:  "CONSENT_UPDATED",
		CustomerID: customerID,
		ActorID:    actorID,
		Timestamp:  now,
		Details:    fmt.Sprintf("Consent preferences updated for customer %s", customerID),
	}
	if err := shared.EmitEvent(stub, "ConsentUpdated", event); err != nil {
		return shim.Error(fmt.Sprintf("Failed to emit event: %v", err))
	}

	// Return success with updated consent preferences
	return shim.Success(consentJSON)
}

// GetConsent retrieves consent preferences for a customer with proper access controls
func (t *CustomerChaincode) GetConsent(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	// Validate arguments
	if len(args) != 2 {
		return shim.Error("Incorrect number of arguments. Expecting 2: customerID, actorID")
	}

	customerID := args[0]
	actorID := args[1]

	// Validate actor permissions - consent data requires customer view permission
	_, err := shared.ValidateActorAccess(stub, actorID, shared.PermissionViewCustomer)
	if err != nil {
		return shim.Error(fmt.Sprintf("Access denied: %v", err))
	}

	// Get customer from ledger
	var customer Customer
	if err := shared.GetStateAsJSON(stub, customerID, &customer); err != nil {
		return shim.Error(fmt.Sprintf("Customer not found: %v", err))
	}

	// Parse consent preferences
	var consentPrefs ConsentPreferences
	if customer.ConsentPreferences != "" && customer.ConsentPreferences != "{}" {
		if err := json.Unmarshal([]byte(customer.ConsentPreferences), &consentPrefs); err != nil {
			return shim.Error(fmt.Sprintf("Failed to parse consent preferences: %v", err))
		}
	} else {
		// Return empty consent if none exists
		consentPrefs = ConsentPreferences{}
	}

	// Return consent data
	consentJSON, err := json.Marshal(consentPrefs)
	if err != nil {
		return shim.Error(fmt.Sprintf("Failed to marshal consent preferences: %v", err))
	}

	return shim.Success(consentJSON)
}

// ============================================================================
// KYC/AML VALIDATION FUNCTIONS
// ============================================================================

// SanctionListEntry represents an entry in the sanction list
type SanctionListEntry struct {
	Name        string `json:"name"`
	NationalID  string `json:"nationalID"`
	DateOfBirth string `json:"dateOfBirth"`
	Country     string `json:"country"`
	ListType    string `json:"listType"` // "OFAC", "UN", "EU", etc.
}

// KYCValidationRequest represents a request for KYC validation
type KYCValidationRequest struct {
	CustomerID   string `json:"customerID"`
	FirstName    string `json:"firstName"`
	LastName     string `json:"lastName"`
	DateOfBirth  string `json:"dateOfBirth"`
	NationalID   string `json:"nationalID"`
	Address      string `json:"address"`
	DocumentType string `json:"documentType"`
	DocumentHash string `json:"documentHash"`
}

// KYCValidationResponse represents the response from KYC validation
type KYCValidationResponse struct {
	CustomerID       string    `json:"customerID"`
	ValidationStatus string    `json:"validationStatus"` // "VERIFIED", "FAILED", "PENDING"
	ProviderName     string    `json:"providerName"`
	ValidationDate   time.Time `json:"validationDate"`
	ConfidenceScore  float64   `json:"confidenceScore"`
	FailureReasons   []string  `json:"failureReasons"`
	ReferenceID      string    `json:"referenceID"`
}

// AMLCheckRequest represents a request for AML screening
type AMLCheckRequest struct {
	CustomerID  string `json:"customerID"`
	FirstName   string `json:"firstName"`
	LastName    string `json:"lastName"`
	NationalID  string `json:"nationalID"`
	DateOfBirth string `json:"dateOfBirth"`
	Country     string `json:"country"`
}

// AMLCheckResponse represents the response from AML screening
type AMLCheckResponse struct {
	CustomerID     string                `json:"customerID"`
	Status         string                `json:"status"` // "CLEAR", "FLAGGED", "BLOCKED"
	CheckDate      time.Time             `json:"checkDate"`
	Matches        []SanctionListEntry   `json:"matches"`
	RiskScore      float64               `json:"riskScore"`
	ProviderName   string                `json:"providerName"`
	ReferenceID    string                `json:"referenceID"`
}

// PerformKYCValidation performs KYC validation for a customer
func (t *CustomerChaincode) PerformKYCValidation(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	// Validate arguments
	if len(args) != 2 {
		return shim.Error("Incorrect number of arguments. Expecting 2: customerID, actorID")
	}

	customerID := args[0]
	actorID := args[1]

	// Validate actor permissions
	_, err := shared.ValidateActorAccess(stub, actorID, shared.PermissionUpdateCustomer)
	if err != nil {
		return shim.Error(fmt.Sprintf("Access denied: %v", err))
	}

	// Get existing customer
	var customer Customer
	if err := shared.GetStateAsJSON(stub, customerID, &customer); err != nil {
		return shim.Error(fmt.Sprintf("Customer not found: %v", err))
	}

	// Create KYC validation request
	kycRequest := KYCValidationRequest{
		CustomerID:   customerID,
		FirstName:    customer.FirstName,
		LastName:     customer.LastName,
		DateOfBirth:  customer.DateOfBirth.Format("2006-01-02"),
		NationalID:   customer.NationalID, // This is already hashed
		Address:      customer.Address,
		DocumentType: "NATIONAL_ID",
		DocumentHash: shared.HashString(customer.NationalID),
	}

	// Simulate external KYC provider integration
	kycResponse, err := t.integrateWithKYCProvider(stub, kycRequest)
	if err != nil {
		return shim.Error(fmt.Sprintf("KYC validation failed: %v", err))
	}

	// Update customer KYC status based on response
	previousKYCStatus := customer.KYCStatus
	customer.KYCStatus = kycResponse.ValidationStatus
	customer.LastUpdated = time.Now()
	customer.UpdatedByActor = actorID
	customer.Version++

	// Record history entry
	if err := shared.RecordHistoryEntry(stub, customerID, "Customer", "UPDATE", "kycStatus", previousKYCStatus, customer.KYCStatus, actorID); err != nil {
		return shim.Error(fmt.Sprintf("Failed to record history: %v", err))
	}

	// Store updated customer
	if err := shared.PutStateAsJSON(stub, customerID, customer); err != nil {
		return shim.Error(fmt.Sprintf("Failed to update customer: %v", err))
	}

	// Store KYC validation record
	kycRecordKey := fmt.Sprintf("KYC_RECORD_%s_%s", customerID, shared.GenerateID("KYC"))
	if err := shared.PutStateAsJSON(stub, kycRecordKey, kycResponse); err != nil {
		return shim.Error(fmt.Sprintf("Failed to store KYC record: %v", err))
	}

	// Emit KYC validation event
	event := CustomerEvent{
		EventType:  "KYC_VALIDATION_COMPLETED",
		CustomerID: customerID,
		ActorID:    actorID,
		Timestamp:  time.Now(),
		Details:    fmt.Sprintf("KYC validation completed with status: %s", kycResponse.ValidationStatus),
	}
	if err := shared.EmitEvent(stub, "KYCValidationCompleted", event); err != nil {
		return shim.Error(fmt.Sprintf("Failed to emit event: %v", err))
	}

	// Return KYC response
	responseJSON, _ := json.Marshal(kycResponse)
	return shim.Success(responseJSON)
}

// PerformAMLCheck performs AML screening for a customer
func (t *CustomerChaincode) PerformAMLCheck(stub shim.ChaincodeStubInterface, args []string) peer.Response {
	// Validate arguments
	if len(args) != 2 {
		return shim.Error("Incorrect number of arguments. Expecting 2: customerID, actorID")
	}

	customerID := args[0]
	actorID := args[1]

	// Validate actor permissions
	_, err := shared.ValidateActorAccess(stub, actorID, shared.PermissionUpdateCustomer)
	if err != nil {
		return shim.Error(fmt.Sprintf("Access denied: %v", err))
	}

	// Get existing customer
	var customer Customer
	if err := shared.GetStateAsJSON(stub, customerID, &customer); err != nil {
		return shim.Error(fmt.Sprintf("Customer not found: %v", err))
	}

	// Create AML check request
	amlRequest := AMLCheckRequest{
		CustomerID:  customerID,
		FirstName:   customer.FirstName,
		LastName:    customer.LastName,
		NationalID:  customer.NationalID, // This is already hashed
		DateOfBirth: customer.DateOfBirth.Format("2006-01-02"),
		Country:     t.extractCountryFromAddress(customer.Address),
	}

	// Perform AML screening
	amlResponse, err := t.performAMLScreening(stub, amlRequest)
	if err != nil {
		return shim.Error(fmt.Sprintf("AML screening failed: %v", err))
	}

	// Update customer AML status based on response
	previousAMLStatus := customer.AMLStatus
	customer.AMLStatus = amlResponse.Status
	customer.LastUpdated = time.Now()
	customer.UpdatedByActor = actorID
	customer.Version++

	// Record history entry
	if err := shared.RecordHistoryEntry(stub, customerID, "Customer", "UPDATE", "amlStatus", previousAMLStatus, customer.AMLStatus, actorID); err != nil {
		return shim.Error(fmt.Sprintf("Failed to record history: %v", err))
	}

	// Store updated customer
	if err := shared.PutStateAsJSON(stub, customerID, customer); err != nil {
		return shim.Error(fmt.Sprintf("Failed to update customer: %v", err))
	}

	// Store AML check record
	amlRecordKey := fmt.Sprintf("AML_RECORD_%s_%s", customerID, shared.GenerateID("AML"))
	if err := shared.PutStateAsJSON(stub, amlRecordKey, amlResponse); err != nil {
		return shim.Error(fmt.Sprintf("Failed to store AML record: %v", err))
	}

	// If customer is flagged or blocked, create compliance event
	if amlResponse.Status == string(shared.AMLStatusFlagged) || amlResponse.Status == string(shared.AMLStatusBlocked) {
		if err := t.createComplianceEvent(stub, customerID, "AML_VIOLATION", fmt.Sprintf("Customer flagged during AML screening: %s", amlResponse.Status), actorID); err != nil {
			// Log error but don't fail the transaction
			fmt.Printf("Warning: Failed to create compliance event: %v", err)
		}
	}

	// Emit AML check event
	event := CustomerEvent{
		EventType:  "AML_CHECK_COMPLETED",
		CustomerID: customerID,
		ActorID:    actorID,
		Timestamp:  time.Now(),
		Details:    fmt.Sprintf("AML check completed with status: %s", amlResponse.Status),
	}
	if err := shared.EmitEvent(stub, "AMLCheckCompleted", event); err != nil {
		return shim.Error(fmt.Sprintf("Failed to emit event: %v", err))
	}

	// Return AML response
	responseJSON, _ := json.Marshal(amlResponse)
	return shim.Success(responseJSON)
}

// integrateWithKYCProvider simulates integration with external KYC provider
func (t *CustomerChaincode) integrateWithKYCProvider(stub shim.ChaincodeStubInterface, request KYCValidationRequest) (*KYCValidationResponse, error) {
	// In a real implementation, this would make an API call to an external KYC provider
	// For this simulation, we'll implement basic validation logic
	
	now := time.Now()
	response := &KYCValidationResponse{
		CustomerID:       request.CustomerID,
		ValidationStatus: string(shared.KYCStatusPending),
		ProviderName:     "MockKYCProvider",
		ValidationDate:   now,
		ConfidenceScore:  0.0,
		FailureReasons:   []string{},
		ReferenceID:      shared.GenerateID("KYC_REF"),
	}

	// Basic validation checks
	validationPassed := true
	
	// Check required fields
	if request.FirstName == "" || request.LastName == "" || request.NationalID == "" {
		response.FailureReasons = append(response.FailureReasons, "Missing required fields")
		validationPassed = false
	}

	// Check name format (basic validation)
	if len(request.FirstName) < 2 || len(request.LastName) < 2 {
		response.FailureReasons = append(response.FailureReasons, "Invalid name format")
		validationPassed = false
	}

	// Check date of birth format
	if _, err := time.Parse("2006-01-02", request.DateOfBirth); err != nil {
		response.FailureReasons = append(response.FailureReasons, "Invalid date of birth format")
		validationPassed = false
	}

	// Simulate document verification (in real implementation, this would verify against government databases)
	if request.DocumentHash == "" {
		response.FailureReasons = append(response.FailureReasons, "Document hash missing")
		validationPassed = false
	}

	// Set validation status and confidence score
	if validationPassed {
		response.ValidationStatus = string(shared.KYCStatusVerified)
		response.ConfidenceScore = 0.95 // High confidence for passed validation
	} else {
		response.ValidationStatus = string(shared.KYCStatusFailed)
		response.ConfidenceScore = 0.1 // Low confidence for failed validation
	}

	return response, nil
}

// performAMLScreening performs AML screening against sanction lists
func (t *CustomerChaincode) performAMLScreening(stub shim.ChaincodeStubInterface, request AMLCheckRequest) (*AMLCheckResponse, error) {
	now := time.Now()
	response := &AMLCheckResponse{
		CustomerID:   request.CustomerID,
		Status:       string(shared.AMLStatusClear),
		CheckDate:    now,
		Matches:      []SanctionListEntry{},
		RiskScore:    0.0,
		ProviderName: "MockAMLProvider",
		ReferenceID:  shared.GenerateID("AML_REF"),
	}

	// Get sanction list entries (in real implementation, this would query external sanction databases)
	sanctionEntries := t.getMockSanctionList()

	// Perform name matching
	customerFullName := fmt.Sprintf("%s %s", request.FirstName, request.LastName)
	
	for _, entry := range sanctionEntries {
		// Simple name matching (in real implementation, this would use fuzzy matching algorithms)
		if t.isNameMatch(customerFullName, entry.Name) {
			response.Matches = append(response.Matches, entry)
			response.RiskScore += 0.8 // High risk for name match
		}
		
		// Check national ID match (if available in sanction list)
		if entry.NationalID != "" && entry.NationalID == request.NationalID {
			response.Matches = append(response.Matches, entry)
			response.RiskScore += 0.9 // Very high risk for ID match
		}
		
		// Check date of birth match
		if entry.DateOfBirth != "" && entry.DateOfBirth == request.DateOfBirth {
			response.RiskScore += 0.3 // Medium risk for DOB match
		}
	}

	// Determine final status based on matches and risk score
	if len(response.Matches) > 0 {
		if response.RiskScore >= 0.8 {
			response.Status = string(shared.AMLStatusBlocked)
		} else {
			response.Status = string(shared.AMLStatusFlagged)
		}
	} else if response.RiskScore > 0.5 {
		response.Status = string(shared.AMLStatusReviewing)
	} else {
		response.Status = string(shared.AMLStatusClear)
	}

	return response, nil
}

// getMockSanctionList returns a mock sanction list for testing
func (t *CustomerChaincode) getMockSanctionList() []SanctionListEntry {
	// In a real implementation, this would fetch from external sanction databases
	return []SanctionListEntry{
		{
			Name:        "John Doe Sanctioned",
			NationalID:  "SANCT123456",
			DateOfBirth: "1980-01-01",
			Country:     "Unknown",
			ListType:    "OFAC",
		},
		{
			Name:        "Jane Smith Blocked",
			NationalID:  "BLOCK789012",
			DateOfBirth: "1975-05-15",
			Country:     "Unknown",
			ListType:    "UN",
		},
		{
			Name:        "Test Flagged Person",
			NationalID:  "FLAG345678",
			DateOfBirth: "1990-12-25",
			Country:     "Unknown",
			ListType:    "EU",
		},
	}
}

// isNameMatch performs basic name matching
func (t *CustomerChaincode) isNameMatch(customerName, sanctionName string) bool {
	// Simple case-insensitive comparison
	// In real implementation, this would use sophisticated fuzzy matching algorithms
	customerNameLower := strings.ToLower(customerName)
	sanctionNameLower := strings.ToLower(sanctionName)
	
	// Check for exact match
	if customerNameLower == sanctionNameLower {
		return true
	}
	
	// Only match if the sanctioned name is contained in customer name (not vice versa)
	// This prevents false positives like "John Doe" matching "John Doe Sanctioned"
	if strings.Contains(sanctionNameLower, customerNameLower) && len(customerNameLower) >= len(sanctionNameLower)-10 {
		return true
	}
	
	return false
}

// extractCountryFromAddress extracts country from address (basic implementation)
func (t *CustomerChaincode) extractCountryFromAddress(address string) string {
	// In real implementation, this would use address parsing libraries
	// For now, return a default country
	return "US" // Default country
}

// createComplianceEvent creates a compliance event (cross-chaincode call simulation)
func (t *CustomerChaincode) createComplianceEvent(stub shim.ChaincodeStubInterface, entityID, eventType, details, actorID string) error {
	// In a real implementation, this would invoke the Compliance chaincode
	// For now, we'll just log the event
	fmt.Printf("Compliance Event: EntityID=%s, Type=%s, Details=%s, Actor=%s", entityID, eventType, details, actorID)
	return nil
}

// ValidateCustomerForCompliance validates customer data against compliance rules
func (t *CustomerChaincode) ValidateCustomerForCompliance(stub shim.ChaincodeStubInterface, customerID string) error {
	// Get customer data
	var customer Customer
	if err := shared.GetStateAsJSON(stub, customerID, &customer); err != nil {
		return fmt.Errorf("customer not found: %v", err)
	}

	// Check AML status first (most critical)
	if customer.AMLStatus == string(shared.AMLStatusBlocked) {
		return fmt.Errorf("customer is AML blocked: %s", customer.AMLStatus)
	}

	if customer.AMLStatus == string(shared.AMLStatusFlagged) {
		return fmt.Errorf("customer is AML flagged and requires review: %s", customer.AMLStatus)
	}

	// Check KYC status - allow PENDING for basic operations, but require VERIFIED for high-risk operations
	if customer.KYCStatus == string(shared.KYCStatusFailed) {
		return fmt.Errorf("customer KYC verification failed: %s", customer.KYCStatus)
	}

	if customer.KYCStatus == string(shared.KYCStatusExpired) {
		return fmt.Errorf("customer KYC verification expired: %s", customer.KYCStatus)
	}

	// Check customer status
	if customer.Status != string(shared.CustomerStatusActive) {
		return fmt.Errorf("customer is not active: %s", customer.Status)
	}

	// Check if customer is of legal age (already validated during creation, but double-check)
	age := time.Now().Year() - customer.DateOfBirth.Year()
	if age < 18 {
		return fmt.Errorf("customer is under legal age: %d years", age)
	}

	return nil
}

// ValidateConsentForDataSharing validates if customer has given consent for specific data sharing operation
func (t *CustomerChaincode) ValidateConsentForDataSharing(stub shim.ChaincodeStubInterface, customerID string, operationType string) error {
	// Get customer from ledger
	var customer Customer
	if err := shared.GetStateAsJSON(stub, customerID, &customer); err != nil {
		return fmt.Errorf("customer not found: %v", err)
	}

	// Parse consent preferences
	var consentPrefs ConsentPreferences
	if customer.ConsentPreferences != "" && customer.ConsentPreferences != "{}" {
		if err := json.Unmarshal([]byte(customer.ConsentPreferences), &consentPrefs); err != nil {
			return fmt.Errorf("failed to parse consent preferences: %v", err)
		}
	} else {
		return fmt.Errorf("no consent preferences found for customer %s", customerID)
	}

	// Check if consent has expired
	if time.Now().After(consentPrefs.ExpiryDate) {
		return fmt.Errorf("consent has expired for customer %s", customerID)
	}

	// Validate consent based on operation type
	switch operationType {
	case "DATA_SHARING":
		if !consentPrefs.DataSharing {
			return fmt.Errorf("customer %s has not consented to data sharing", customerID)
		}
	case "MARKETING_COMMUNICATION":
		if !consentPrefs.MarketingCommunication {
			return fmt.Errorf("customer %s has not consented to marketing communication", customerID)
		}
	case "THIRD_PARTY_SHARING":
		if !consentPrefs.ThirdPartySharing {
			return fmt.Errorf("customer %s has not consented to third party sharing", customerID)
		}
	case "CREDIT_BUREAU_SHARING":
		if !consentPrefs.CreditBureauSharing {
			return fmt.Errorf("customer %s has not consented to credit bureau sharing", customerID)
		}
	case "REGULATORY_REPORTING":
		if !consentPrefs.RegulatoryReporting {
			return fmt.Errorf("customer %s has not consented to regulatory reporting", customerID)
		}
	default:
		return fmt.Errorf("unknown operation type: %s", operationType)
	}

	return nil
}

func main() {
	if err := shim.Start(new(CustomerChaincode)); err != nil {
		log.Fatalf("Error starting Customer chaincode: %v", err)
	}
}