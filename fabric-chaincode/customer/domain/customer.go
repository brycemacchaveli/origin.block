package domain

import (
	"time"
	
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/shared/validation"
)

// Customer represents a customer entity
type Customer struct {
	CustomerID      string                     `json:"customerID"`
	FirstName       string                     `json:"firstName"`
	LastName        string                     `json:"lastName"`
	Email           string                     `json:"email"`
	Phone           string                     `json:"phone"`
	DateOfBirth     time.Time                  `json:"dateOfBirth"`
	NationalID      string                     `json:"nationalID"`
	Address         string                     `json:"address"`
	Status          validation.CustomerStatus `json:"status"`
	ConsentPreferences string                  `json:"consentPreferences"`
	CreatedDate     time.Time                  `json:"createdDate"`
	LastUpdated     time.Time                  `json:"lastUpdated"`
	CreatedBy       string                     `json:"createdBy"`
	LastUpdatedBy   string                     `json:"lastUpdatedBy"`
}

// CustomerRegistrationRequest represents a customer registration request
type CustomerRegistrationRequest struct {
	FirstName          string    `json:"firstName"`
	LastName           string    `json:"lastName"`
	Email              string    `json:"email"`
	Phone              string    `json:"phone"`
	DateOfBirth        time.Time `json:"dateOfBirth"`
	NationalID         string    `json:"nationalID"`
	Address            string    `json:"address"`
	ConsentPreferences string    `json:"consentPreferences"`
	ActorID            string    `json:"actorID"`
}

// CustomerUpdateRequest represents a customer update request
type CustomerUpdateRequest struct {
	CustomerID         string    `json:"customerID"`
	FirstName          *string   `json:"firstName,omitempty"`
	LastName           *string   `json:"lastName,omitempty"`
	Email              *string   `json:"email,omitempty"`
	Phone              *string   `json:"phone,omitempty"`
	Address            *string   `json:"address,omitempty"`
	ConsentPreferences *string   `json:"consentPreferences,omitempty"`
	ActorID            string    `json:"actorID"`
}

// CustomerStatusUpdateRequest represents a customer status update request
type CustomerStatusUpdateRequest struct {
	CustomerID string                     `json:"customerID"`
	NewStatus  validation.CustomerStatus `json:"newStatus"`
	Reason     string                     `json:"reason"`
	ActorID    string                     `json:"actorID"`
}