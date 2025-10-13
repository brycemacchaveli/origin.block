package validation

import (
	"fmt"
	"regexp"
	"time"
)

// ============================================================================
// DOMAIN-SPECIFIC VALIDATION UTILITIES
// ============================================================================

// LoanApplicationStatus represents valid loan application statuses
type LoanApplicationStatus string

const (
	LoanStatusSubmitted     LoanApplicationStatus = "SUBMITTED"
	LoanStatusUnderwriting  LoanApplicationStatus = "UNDERWRITING"
	LoanStatusCreditApproval LoanApplicationStatus = "CREDIT_APPROVAL"
	LoanStatusApproved      LoanApplicationStatus = "APPROVED"
	LoanStatusRejected      LoanApplicationStatus = "REJECTED"
	LoanStatusDisbursed     LoanApplicationStatus = "DISBURSED"
)

// CustomerStatus represents valid customer statuses
type CustomerStatus string

const (
	CustomerStatusActive   CustomerStatus = "ACTIVE"
	CustomerStatusInactive CustomerStatus = "INACTIVE"
	CustomerStatusSuspended CustomerStatus = "SUSPENDED"
)

// KYCStatus represents KYC verification statuses
type KYCStatus string

const (
	KYCStatusPending   KYCStatus = "PENDING"
	KYCStatusVerified  KYCStatus = "VERIFIED"
	KYCStatusFailed    KYCStatus = "FAILED"
	KYCStatusExpired   KYCStatus = "EXPIRED"
)

// AMLStatus represents AML check statuses
type AMLStatus string

const (
	AMLStatusClear     AMLStatus = "CLEAR"
	AMLStatusFlagged   AMLStatus = "FLAGGED"
	AMLStatusReviewing AMLStatus = "REVIEWING"
	AMLStatusBlocked   AMLStatus = "BLOCKED"
)

// ValidateStatus checks if status is in allowed list
func ValidateStatus(status string, allowedStatuses []string) error {
	for _, allowed := range allowedStatuses {
		if status == allowed {
			return nil
		}
	}
	return fmt.Errorf("invalid status '%s', allowed values: %v", status, allowedStatuses)
}

// ValidateLoanApplicationStatus checks if loan application status is valid
func ValidateLoanApplicationStatus(status string) error {
	validStatuses := []string{
		string(LoanStatusSubmitted),
		string(LoanStatusUnderwriting),
		string(LoanStatusCreditApproval),
		string(LoanStatusApproved),
		string(LoanStatusRejected),
		string(LoanStatusDisbursed),
	}
	return ValidateStatus(status, validStatuses)
}

// ValidateCustomerStatus checks if customer status is valid
func ValidateCustomerStatus(status string) error {
	validStatuses := []string{
		string(CustomerStatusActive),
		string(CustomerStatusInactive),
		string(CustomerStatusSuspended),
	}
	return ValidateStatus(status, validStatuses)
}

// ValidateKYCStatus checks if KYC status is valid
func ValidateKYCStatus(status string) error {
	validStatuses := []string{
		string(KYCStatusPending),
		string(KYCStatusVerified),
		string(KYCStatusFailed),
		string(KYCStatusExpired),
	}
	return ValidateStatus(status, validStatuses)
}

// ValidateAMLStatus checks if AML status is valid
func ValidateAMLStatus(status string) error {
	validStatuses := []string{
		string(AMLStatusClear),
		string(AMLStatusFlagged),
		string(AMLStatusReviewing),
		string(AMLStatusBlocked),
	}
	return ValidateStatus(status, validStatuses)
}

// ValidateLoanType checks if loan type is valid
func ValidateLoanType(loanType string) error {
	validTypes := []string{
		"PERSONAL",
		"MORTGAGE",
		"AUTO",
		"BUSINESS",
		"STUDENT",
		"CREDIT_CARD",
	}
	return ValidateStatus(loanType, validTypes)
}

// ValidateNationalID validates national ID format (basic validation)
func ValidateNationalID(nationalID string) error {
	if len(nationalID) < 5 || len(nationalID) > 20 {
		return fmt.Errorf("national ID must be between 5 and 20 characters")
	}
	
	// Basic alphanumeric check
	alphanumericRegex := regexp.MustCompile(`^[A-Za-z0-9]+$`)
	if !alphanumericRegex.MatchString(nationalID) {
		return fmt.Errorf("national ID must contain only alphanumeric characters")
	}
	
	return nil
}

// ValidateDateOfBirth validates date of birth
func ValidateDateOfBirth(dob time.Time) error {
	now := time.Now()
	
	// Check if date is in the future
	if dob.After(now) {
		return fmt.Errorf("date of birth cannot be in the future")
	}
	
	// Check if person is too old (more than 150 years)
	maxAge := now.AddDate(-150, 0, 0)
	if dob.Before(maxAge) {
		return fmt.Errorf("date of birth indicates age over 150 years")
	}
	
	// Check if person is too young (less than 18 years for financial services)
	minAge := now.AddDate(-18, 0, 0)
	if dob.After(minAge) {
		return fmt.Errorf("customer must be at least 18 years old")
	}
	
	return nil
}

// ValidateAddress performs basic address validation
func ValidateAddress(address string) error {
	if len(address) < 10 || len(address) > 500 {
		return fmt.Errorf("address must be between 10 and 500 characters")
	}
	
	// Check for minimum required components (basic check)
	if len(address) < 10 {
		return fmt.Errorf("address appears to be too short")
	}
	
	return nil
}

// ValidateAmount checks if the amount is positive and within reasonable limits
func ValidateAmount(amount float64) error {
	if amount <= 0 {
		return fmt.Errorf("amount must be positive: %f", amount)
	}
	if amount > 1000000000 { // 1 billion limit
		return fmt.Errorf("amount exceeds maximum limit: %f", amount)
	}
	return nil
}

// ValidateLoanAmount validates loan amount based on type and limits
func ValidateLoanAmount(amount float64, loanType string) error {
	if err := ValidateAmount(amount); err != nil {
		return err
	}
	
	// Type-specific limits
	limits := map[string]struct {
		min, max float64
	}{
		"PERSONAL":    {1000, 100000},
		"MORTGAGE":    {50000, 10000000},
		"AUTO":        {5000, 500000},
		"BUSINESS":    {10000, 5000000},
		"STUDENT":     {1000, 200000},
		"CREDIT_CARD": {500, 50000},
	}
	
	if limit, exists := limits[loanType]; exists {
		if amount < limit.min {
			return fmt.Errorf("loan amount %.2f is below minimum %.2f for %s loans", amount, limit.min, loanType)
		}
		if amount > limit.max {
			return fmt.Errorf("loan amount %.2f exceeds maximum %.2f for %s loans", amount, limit.max, loanType)
		}
	}
	
	return nil
}

// ValidateStatusTransition checks if a status transition is valid
func ValidateStatusTransition(currentStatus, newStatus string, entityType string) error {
	var validTransitions map[string][]string
	
	switch entityType {
	case "LoanApplication":
		validTransitions = map[string][]string{
			string(LoanStatusSubmitted):     {string(LoanStatusUnderwriting), string(LoanStatusRejected)},
			string(LoanStatusUnderwriting):  {string(LoanStatusCreditApproval), string(LoanStatusRejected)},
			string(LoanStatusCreditApproval): {string(LoanStatusApproved), string(LoanStatusRejected)},
			string(LoanStatusApproved):      {string(LoanStatusDisbursed)},
			string(LoanStatusRejected):      {}, // Terminal state
			string(LoanStatusDisbursed):     {}, // Terminal state
		}
	case "Customer":
		validTransitions = map[string][]string{
			string(CustomerStatusActive):   {string(CustomerStatusInactive), string(CustomerStatusSuspended)},
			string(CustomerStatusInactive): {string(CustomerStatusActive)},
			string(CustomerStatusSuspended): {string(CustomerStatusActive), string(CustomerStatusInactive)},
		}
	default:
		return fmt.Errorf("unknown entity type for status transition: %s", entityType)
	}
	
	allowedTransitions, exists := validTransitions[currentStatus]
	if !exists {
		return fmt.Errorf("unknown current status: %s", currentStatus)
	}
	
	for _, allowed := range allowedTransitions {
		if newStatus == allowed {
			return nil
		}
	}
	
	return fmt.Errorf("invalid status transition from %s to %s for %s", currentStatus, newStatus, entityType)
}

// ValidateConsentPreferences validates consent preferences JSON structure
func ValidateConsentPreferences(consentJSON string) error {
	if consentJSON == "" {
		return fmt.Errorf("consent preferences cannot be empty")
	}
	
	// Basic JSON validation - in a real implementation, you'd validate against a schema
	if len(consentJSON) < 10 || len(consentJSON) > 5000 {
		return fmt.Errorf("consent preferences JSON must be between 10 and 5000 characters")
	}
	
	return nil
}

// ValidateComplianceRuleLogic validates compliance rule logic format
func ValidateComplianceRuleLogic(ruleLogic string) error {
	if len(ruleLogic) < 10 || len(ruleLogic) > 10000 {
		return fmt.Errorf("rule logic must be between 10 and 10000 characters")
	}
	
	// Basic validation - in a real implementation, you'd parse and validate the rule syntax
	if ruleLogic == "" {
		return fmt.Errorf("rule logic cannot be empty")
	}
	
	return nil
}