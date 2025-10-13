package handlers

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/blockchain-financial-platform/fabric-chaincode/customer/domain"
	customerServices "github.com/blockchain-financial-platform/fabric-chaincode/customer/services"
	"github.com/blockchain-financial-platform/fabric-chaincode/shared/config"
	"github.com/blockchain-financial-platform/fabric-chaincode/shared/services"
	"github.com/blockchain-financial-platform/fabric-chaincode/shared/utils"
	"github.com/blockchain-financial-platform/fabric-chaincode/shared/validation"
)

// CustomerHandler handles customer-related operations
type CustomerHandler struct {
	persistenceService *services.PersistenceService
	eventService      *customerServices.EventService
}

// NewCustomerHandler creates a new customer handler
func NewCustomerHandler() *CustomerHandler {
	return &CustomerHandler{
		persistenceService: services.NewPersistenceService(),
		eventService:      customerServices.NewEventService(),
	}
}

// RegisterCustomer registers a new customer
func (h *CustomerHandler) RegisterCustomer(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	// Parse the registration request
	var req domain.CustomerRegistrationRequest
	if err := json.Unmarshal([]byte(args[0]), &req); err != nil {
		return nil, fmt.Errorf("failed to parse registration request: %v", err)
	}

	// Validate the request
	if err := domain.ValidateCustomerRegistrationRequest(&req); err != nil {
		return nil, fmt.Errorf("validation failed: %v", err)
	}

	// Check if customer with same national ID already exists
	existingCustomerKey := fmt.Sprintf("CUSTOMER_BY_NATIONAL_ID_%s", req.NationalID)
	existingData, err := stub.GetState(existingCustomerKey)
	if err != nil {
		return nil, fmt.Errorf("failed to check existing customer: %v", err)
	}
	if existingData != nil {
		return nil, fmt.Errorf("customer with national ID %s already exists", req.NationalID)
	}

	// Generate customer ID
	customerID := utils.GenerateID(config.CustomerPrefix)

	// Create customer entity
	customer := &domain.Customer{
		CustomerID:         customerID,
		FirstName:          req.FirstName,
		LastName:           req.LastName,
		Email:              req.Email,
		Phone:              req.Phone,
		DateOfBirth:        req.DateOfBirth,
		NationalID:         req.NationalID,
		Address:            req.Address,
		Status:             validation.CustomerStatusActive,
		ConsentPreferences: req.ConsentPreferences,
		CreatedDate:        time.Now(),
		LastUpdated:        time.Now(),
		CreatedBy:          req.ActorID,
		LastUpdatedBy:      req.ActorID,
	}

	// Validate the customer entity
	if err := domain.ValidateCustomer(customer); err != nil {
		return nil, fmt.Errorf("customer validation failed: %v", err)
	}

	// Store the customer
	customerKey := fmt.Sprintf("CUSTOMER_%s", customerID)
	if err := h.persistenceService.Put(stub, customerKey, customer); err != nil {
		return nil, fmt.Errorf("failed to store customer: %v", err)
	}

	// Create index by national ID
	if err := stub.PutState(existingCustomerKey, []byte(customerID)); err != nil {
		return nil, fmt.Errorf("failed to create national ID index: %v", err)
	}

	// Record history
	customerJSON, _ := utils.MarshalJSONString(customer)
	if err := h.recordCustomerHistory(stub, customerID, "CREATE", "customer", "", customerJSON, req.ActorID); err != nil {
		return nil, fmt.Errorf("failed to record history: %v", err)
	}

	// Emit event
	if err := h.eventService.EmitCustomerCreated(stub, customer, req.ActorID); err != nil {
		return nil, fmt.Errorf("failed to emit event: %v", err)
	}

	// Return the created customer
	return json.Marshal(customer)
}

// UpdateCustomer updates an existing customer
func (h *CustomerHandler) UpdateCustomer(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	// Parse the update request
	var req domain.CustomerUpdateRequest
	if err := json.Unmarshal([]byte(args[0]), &req); err != nil {
		return nil, fmt.Errorf("failed to parse update request: %v", err)
	}

	// Get existing customer
	customerKey := fmt.Sprintf("CUSTOMER_%s", req.CustomerID)
	var existingCustomer domain.Customer
	if err := h.persistenceService.Get(stub, customerKey, &existingCustomer); err != nil {
		return nil, fmt.Errorf("customer not found: %v", err)
	}

	// Create updated customer
	updatedCustomer := existingCustomer
	updatedCustomer.LastUpdated = time.Now()
	updatedCustomer.LastUpdatedBy = req.ActorID

	// Apply updates
	if req.FirstName != nil {
		if err := h.recordCustomerHistory(stub, req.CustomerID, "UPDATE", "firstName", updatedCustomer.FirstName, *req.FirstName, req.ActorID); err != nil {
			return nil, err
		}
		updatedCustomer.FirstName = *req.FirstName
	}
	if req.LastName != nil {
		if err := h.recordCustomerHistory(stub, req.CustomerID, "UPDATE", "lastName", updatedCustomer.LastName, *req.LastName, req.ActorID); err != nil {
			return nil, err
		}
		updatedCustomer.LastName = *req.LastName
	}
	if req.Email != nil {
		if err := h.recordCustomerHistory(stub, req.CustomerID, "UPDATE", "email", updatedCustomer.Email, *req.Email, req.ActorID); err != nil {
			return nil, err
		}
		updatedCustomer.Email = *req.Email
	}
	if req.Phone != nil {
		if err := h.recordCustomerHistory(stub, req.CustomerID, "UPDATE", "phone", updatedCustomer.Phone, *req.Phone, req.ActorID); err != nil {
			return nil, err
		}
		updatedCustomer.Phone = *req.Phone
	}
	if req.Address != nil {
		if err := h.recordCustomerHistory(stub, req.CustomerID, "UPDATE", "address", updatedCustomer.Address, *req.Address, req.ActorID); err != nil {
			return nil, err
		}
		updatedCustomer.Address = *req.Address
	}
	if req.ConsentPreferences != nil {
		if err := h.recordCustomerHistory(stub, req.CustomerID, "UPDATE", "consentPreferences", updatedCustomer.ConsentPreferences, *req.ConsentPreferences, req.ActorID); err != nil {
			return nil, err
		}
		updatedCustomer.ConsentPreferences = *req.ConsentPreferences
	}

	// Validate the updated customer
	if err := domain.ValidateCustomer(&updatedCustomer); err != nil {
		return nil, fmt.Errorf("updated customer validation failed: %v", err)
	}

	// Store the updated customer
	if err := h.persistenceService.Put(stub, customerKey, &updatedCustomer); err != nil {
		return nil, fmt.Errorf("failed to update customer: %v", err)
	}

	// Emit event
	if err := h.eventService.EmitCustomerUpdated(stub, &updatedCustomer, req.ActorID); err != nil {
		return nil, fmt.Errorf("failed to emit event: %v", err)
	}

	return json.Marshal(&updatedCustomer)
}

// GetCustomer retrieves a customer by ID
func (h *CustomerHandler) GetCustomer(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	customerID := args[0]
	customerKey := fmt.Sprintf("CUSTOMER_%s", customerID)

	var customer domain.Customer
	if err := h.persistenceService.Get(stub, customerKey, &customer); err != nil {
		return nil, fmt.Errorf("customer not found: %v", err)
	}

	return json.Marshal(&customer)
}

// GetCustomerHistory retrieves the history of a customer
func (h *CustomerHandler) GetCustomerHistory(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	customerID := args[0]
	history, err := h.getEntityHistory(stub, customerID)
	if err != nil {
		return nil, fmt.Errorf("failed to get customer history: %v", err)
	}

	return json.Marshal(history)
}

// UpdateCustomerStatus updates a customer's status
func (h *CustomerHandler) UpdateCustomerStatus(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	var req domain.CustomerStatusUpdateRequest
	if err := json.Unmarshal([]byte(args[0]), &req); err != nil {
		return nil, fmt.Errorf("failed to parse status update request: %v", err)
	}

	// Get existing customer
	customerKey := fmt.Sprintf("CUSTOMER_%s", req.CustomerID)
	var customer domain.Customer
	if err := h.persistenceService.Get(stub, customerKey, &customer); err != nil {
		return nil, fmt.Errorf("customer not found: %v", err)
	}

	// Validate status transition
	if err := validation.ValidateStatusTransition(string(customer.Status), string(req.NewStatus), "Customer"); err != nil {
		return nil, fmt.Errorf("invalid status transition: %v", err)
	}

	// Record history
	if err := h.recordCustomerHistory(stub, req.CustomerID, "STATUS_UPDATE", "status", string(customer.Status), string(req.NewStatus), req.ActorID); err != nil {
		return nil, err
	}

	// Update status
	customer.Status = req.NewStatus
	customer.LastUpdated = time.Now()
	customer.LastUpdatedBy = req.ActorID

	// Store updated customer
	if err := h.persistenceService.Put(stub, customerKey, &customer); err != nil {
		return nil, fmt.Errorf("failed to update customer status: %v", err)
	}

	// Emit event
	if err := h.eventService.EmitCustomerUpdated(stub, &customer, req.ActorID); err != nil {
		return nil, fmt.Errorf("failed to emit event: %v", err)
	}

	return json.Marshal(&customer)
}

// QueryCustomersByStatus queries customers by status
func (h *CustomerHandler) QueryCustomersByStatus(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	status := args[0]
	
	// Validate status
	if err := validation.ValidateCustomerStatus(status); err != nil {
		return nil, fmt.Errorf("invalid status: %v", err)
	}

	// Query customers by status using composite key
	iterator, err := stub.GetStateByPartialCompositeKey("CUSTOMER_STATUS", []string{status})
	if err != nil {
		return nil, fmt.Errorf("failed to get customers by status: %v", err)
	}
	defer iterator.Close()

	var customers []domain.Customer
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate customers: %v", err)
		}

		var customer domain.Customer
		if err := json.Unmarshal(response.Value, &customer); err != nil {
			return nil, fmt.Errorf("failed to unmarshal customer: %v", err)
		}

		customers = append(customers, customer)
	}

	return json.Marshal(customers)
}

// Helper methods

func (h *CustomerHandler) recordCustomerHistory(stub shim.ChaincodeStubInterface, customerID, changeType, fieldName, previousValue, newValue, actorID string) error {
	historyID := utils.GenerateID(config.HistoryPrefix)
	txID := stub.GetTxID()

	historyEntry := map[string]interface{}{
		"historyID":     historyID,
		"entityID":      customerID,
		"entityType":    "Customer",
		"timestamp":     utils.GetCurrentTimeString(),
		"changeType":    changeType,
		"fieldName":     fieldName,
		"previousValue": previousValue,
		"newValue":      newValue,
		"actorID":       actorID,
		"transactionID": txID,
	}

	compositeKey, err := stub.CreateCompositeKey("HISTORY", []string{customerID, historyID})
	if err != nil {
		return fmt.Errorf("failed to create composite key: %v", err)
	}

	return h.persistenceService.Put(stub, compositeKey, historyEntry)
}

func (h *CustomerHandler) getEntityHistory(stub shim.ChaincodeStubInterface, entityID string) ([]interface{}, error) {
	iterator, err := stub.GetStateByPartialCompositeKey("HISTORY", []string{entityID})
	if err != nil {
		return nil, fmt.Errorf("failed to get history iterator: %v", err)
	}
	defer iterator.Close()

	var history []interface{}
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate history: %v", err)
		}

		var entry interface{}
		if err := json.Unmarshal(response.Value, &entry); err != nil {
			return nil, fmt.Errorf("failed to unmarshal history entry: %v", err)
		}

		history = append(history, entry)
	}

	return history, nil
}