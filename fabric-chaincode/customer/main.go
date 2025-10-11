package main

import (
	"encoding/json"
	"fmt"
	"log"
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

// GetCustomer retrieves a customer record
func (t *CustomerChaincode) GetCustomer(stub shim.ChaincodeStubInterface, args []string) peer.Response {
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

	// Get customer from ledger
	var customer Customer
	if err := shared.GetStateAsJSON(stub, customerID, &customer); err != nil {
		return shim.Error(fmt.Sprintf("Customer not found: %v", err))
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

func main() {
	if err := shim.Start(new(CustomerChaincode)); err != nil {
		log.Fatalf("Error starting Customer chaincode: %v", err)
	}
}