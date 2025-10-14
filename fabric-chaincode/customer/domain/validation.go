package domain

import (
	"fmt"
	"strings"
	
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/shared/validation"
)

// ValidateCustomer validates a customer entity
func ValidateCustomer(customer *Customer) error {
	var errors []string
	
	// Validate required fields
	if strings.TrimSpace(customer.FirstName) == "" {
		errors = append(errors, "firstName is required")
	}
	if strings.TrimSpace(customer.LastName) == "" {
		errors = append(errors, "lastName is required")
	}
	if strings.TrimSpace(customer.Email) == "" {
		errors = append(errors, "email is required")
	}
	if strings.TrimSpace(customer.NationalID) == "" {
		errors = append(errors, "nationalID is required")
	}
	
	// Validate email format
	if customer.Email != "" {
		if err := validation.ValidateEmail(customer.Email); err != nil {
			errors = append(errors, fmt.Sprintf("email: %v", err))
		}
	}
	
	// Validate phone format
	if customer.Phone != "" {
		if err := validation.ValidatePhone(customer.Phone); err != nil {
			errors = append(errors, fmt.Sprintf("phone: %v", err))
		}
	}
	
	// Validate national ID
	if customer.NationalID != "" {
		if err := validation.ValidateNationalID(customer.NationalID); err != nil {
			errors = append(errors, fmt.Sprintf("nationalID: %v", err))
		}
	}
	
	// Validate date of birth
	if !customer.DateOfBirth.IsZero() {
		if err := validation.ValidateDateOfBirth(customer.DateOfBirth); err != nil {
			errors = append(errors, fmt.Sprintf("dateOfBirth: %v", err))
		}
	}
	
	// Validate address
	if customer.Address != "" {
		if err := validation.ValidateAddress(customer.Address); err != nil {
			errors = append(errors, fmt.Sprintf("address: %v", err))
		}
	}
	
	// Validate customer status
	if err := validation.ValidateCustomerStatus(string(customer.Status)); err != nil {
		errors = append(errors, fmt.Sprintf("status: %v", err))
	}
	
	// Validate consent preferences
	if customer.ConsentPreferences != "" {
		if err := validation.ValidateConsentPreferences(customer.ConsentPreferences); err != nil {
			errors = append(errors, fmt.Sprintf("consentPreferences: %v", err))
		}
	}
	
	if len(errors) > 0 {
		return fmt.Errorf("validation errors: %s", strings.Join(errors, ", "))
	}
	
	return nil
}

// ValidateCustomerRegistrationRequest validates a customer registration request
func ValidateCustomerRegistrationRequest(req *CustomerRegistrationRequest) error {
	var errors []string
	
	// Validate required fields
	if strings.TrimSpace(req.FirstName) == "" {
		errors = append(errors, "firstName is required")
	}
	if strings.TrimSpace(req.LastName) == "" {
		errors = append(errors, "lastName is required")
	}
	if strings.TrimSpace(req.Email) == "" {
		errors = append(errors, "email is required")
	}
	if strings.TrimSpace(req.NationalID) == "" {
		errors = append(errors, "nationalID is required")
	}
	if strings.TrimSpace(req.ActorID) == "" {
		errors = append(errors, "actorID is required")
	}
	
	// Validate formats
	if req.Email != "" {
		if err := validation.ValidateEmail(req.Email); err != nil {
			errors = append(errors, fmt.Sprintf("email: %v", err))
		}
	}
	
	if req.Phone != "" {
		if err := validation.ValidatePhone(req.Phone); err != nil {
			errors = append(errors, fmt.Sprintf("phone: %v", err))
		}
	}
	
	if req.NationalID != "" {
		if err := validation.ValidateNationalID(req.NationalID); err != nil {
			errors = append(errors, fmt.Sprintf("nationalID: %v", err))
		}
	}
	
	if !req.DateOfBirth.IsZero() {
		if err := validation.ValidateDateOfBirth(req.DateOfBirth); err != nil {
			errors = append(errors, fmt.Sprintf("dateOfBirth: %v", err))
		}
	}
	
	if req.Address != "" {
		if err := validation.ValidateAddress(req.Address); err != nil {
			errors = append(errors, fmt.Sprintf("address: %v", err))
		}
	}
	
	if len(errors) > 0 {
		return fmt.Errorf("validation errors: %s", strings.Join(errors, ", "))
	}
	
	return nil
}

// ValidateKYCRecord validates a KYC record
func ValidateKYCRecord(record *KYCRecord) error {
	var errors []string
	
	// Validate required fields
	if strings.TrimSpace(record.CustomerID) == "" {
		errors = append(errors, "customerID is required")
	}
	
	// Validate KYC status
	if err := validation.ValidateKYCStatus(string(record.Status)); err != nil {
		errors = append(errors, fmt.Sprintf("status: %v", err))
	}
	
	if len(errors) > 0 {
		return fmt.Errorf("validation errors: %s", strings.Join(errors, ", "))
	}
	
	return nil
}

// ValidateAMLRecord validates an AML record
func ValidateAMLRecord(record *AMLRecord) error {
	var errors []string
	
	// Validate required fields
	if strings.TrimSpace(record.CustomerID) == "" {
		errors = append(errors, "customerID is required")
	}
	
	// Validate AML status
	if err := validation.ValidateAMLStatus(string(record.Status)); err != nil {
		errors = append(errors, fmt.Sprintf("status: %v", err))
	}
	
	// Validate risk score
	if record.RiskScore < 0 || record.RiskScore > 100 {
		errors = append(errors, "riskScore must be between 0 and 100")
	}
	
	if len(errors) > 0 {
		return fmt.Errorf("validation errors: %s", strings.Join(errors, ", "))
	}
	
	return nil
}