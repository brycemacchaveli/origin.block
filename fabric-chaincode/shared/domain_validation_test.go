package shared

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

// ============================================================================
// DOMAIN VALIDATION TESTS
// ============================================================================

func TestValidateLoanApplicationStatus(t *testing.T) {
	validStatuses := []string{
		string(LoanStatusSubmitted),
		string(LoanStatusUnderwriting),
		string(LoanStatusApproved),
		string(LoanStatusRejected),
	}
	
	for _, status := range validStatuses {
		err := ValidateLoanApplicationStatus(status)
		assert.NoError(t, err, "Valid loan status should pass: %s", status)
	}
	
	err := ValidateLoanApplicationStatus("INVALID_STATUS")
	assert.Error(t, err, "Invalid loan status should fail")
}

func TestValidateCustomerStatus(t *testing.T) {
	validStatuses := []string{
		string(CustomerStatusActive),
		string(CustomerStatusInactive),
		string(CustomerStatusSuspended),
	}
	
	for _, status := range validStatuses {
		err := ValidateCustomerStatus(status)
		assert.NoError(t, err, "Valid customer status should pass: %s", status)
	}
	
	err := ValidateCustomerStatus("INVALID_STATUS")
	assert.Error(t, err, "Invalid customer status should fail")
}

func TestValidateKYCStatus(t *testing.T) {
	validStatuses := []string{
		string(KYCStatusPending),
		string(KYCStatusVerified),
		string(KYCStatusFailed),
		string(KYCStatusExpired),
	}
	
	for _, status := range validStatuses {
		err := ValidateKYCStatus(status)
		assert.NoError(t, err, "Valid KYC status should pass: %s", status)
	}
	
	err := ValidateKYCStatus("INVALID_STATUS")
	assert.Error(t, err, "Invalid KYC status should fail")
}

func TestValidateAMLStatus(t *testing.T) {
	validStatuses := []string{
		string(AMLStatusClear),
		string(AMLStatusFlagged),
		string(AMLStatusReviewing),
		string(AMLStatusBlocked),
	}
	
	for _, status := range validStatuses {
		err := ValidateAMLStatus(status)
		assert.NoError(t, err, "Valid AML status should pass: %s", status)
	}
	
	err := ValidateAMLStatus("INVALID_STATUS")
	assert.Error(t, err, "Invalid AML status should fail")
}

func TestValidateLoanType(t *testing.T) {
	validTypes := []string{
		"PERSONAL",
		"MORTGAGE",
		"AUTO",
		"BUSINESS",
		"STUDENT",
		"CREDIT_CARD",
	}
	
	for _, loanType := range validTypes {
		err := ValidateLoanType(loanType)
		assert.NoError(t, err, "Valid loan type should pass: %s", loanType)
	}
	
	err := ValidateLoanType("INVALID_TYPE")
	assert.Error(t, err, "Invalid loan type should fail")
}

func TestValidateNationalID(t *testing.T) {
	validIDs := []string{
		"12345",
		"ABC123DEF",
		"1234567890123456789",
	}
	
	for _, id := range validIDs {
		err := ValidateNationalID(id)
		assert.NoError(t, err, "Valid national ID should pass: %s", id)
	}
	
	invalidIDs := []string{
		"123",           // too short
		"123456789012345678901", // too long
		"ABC-123",       // contains special characters
		"",              // empty
	}
	
	for _, id := range invalidIDs {
		err := ValidateNationalID(id)
		assert.Error(t, err, "Invalid national ID should fail: %s", id)
	}
}

func TestValidateDateOfBirth(t *testing.T) {
	now := time.Now()
	
	// Valid date of birth (30 years old)
	validDOB := now.AddDate(-30, 0, 0)
	err := ValidateDateOfBirth(validDOB)
	assert.NoError(t, err, "Valid date of birth should pass")
	
	// Future date
	futureDOB := now.AddDate(1, 0, 0)
	err = ValidateDateOfBirth(futureDOB)
	assert.Error(t, err, "Future date of birth should fail")
	assert.Contains(t, err.Error(), "future")
	
	// Too old (200 years)
	tooOldDOB := now.AddDate(-200, 0, 0)
	err = ValidateDateOfBirth(tooOldDOB)
	assert.Error(t, err, "Too old date of birth should fail")
	assert.Contains(t, err.Error(), "150 years")
	
	// Too young (10 years old)
	tooYoungDOB := now.AddDate(-10, 0, 0)
	err = ValidateDateOfBirth(tooYoungDOB)
	assert.Error(t, err, "Too young date of birth should fail")
	assert.Contains(t, err.Error(), "18 years")
}

func TestValidateAddress(t *testing.T) {
	validAddresses := []string{
		"123 Main Street, City, State 12345",
		"456 Oak Avenue, Apartment 2B, Another City, State 67890",
	}
	
	for _, address := range validAddresses {
		err := ValidateAddress(address)
		assert.NoError(t, err, "Valid address should pass: %s", address)
	}
	
	invalidAddresses := []string{
		"123",           // too short
		"",              // empty
	}
	
	for _, address := range invalidAddresses {
		err := ValidateAddress(address)
		assert.Error(t, err, "Invalid address should fail: %s", address)
	}
}

func TestValidateLoanAmount(t *testing.T) {
	// Test valid amounts for different loan types
	testCases := []struct {
		amount   float64
		loanType string
		valid    bool
	}{
		{5000, "PERSONAL", true},
		{500, "PERSONAL", false},    // below minimum
		{150000, "PERSONAL", false}, // above maximum
		{100000, "MORTGAGE", true},
		{30000, "MORTGAGE", false},  // below minimum
		{15000, "AUTO", true},
		{2000, "AUTO", false},       // below minimum
		{25000, "BUSINESS", true},
		{5000, "BUSINESS", false},   // below minimum
		{10000, "STUDENT", true},
		{500, "STUDENT", false},     // below minimum
		{5000, "CREDIT_CARD", true},
		{200, "CREDIT_CARD", false}, // below minimum
	}
	
	for _, tc := range testCases {
		err := ValidateLoanAmount(tc.amount, tc.loanType)
		if tc.valid {
			assert.NoError(t, err, "Valid loan amount should pass: %.2f for %s", tc.amount, tc.loanType)
		} else {
			assert.Error(t, err, "Invalid loan amount should fail: %.2f for %s", tc.amount, tc.loanType)
		}
	}
}

func TestValidateStatusTransition(t *testing.T) {
	// Test valid loan application transitions
	validTransitions := []struct {
		current, new, entityType string
	}{
		{string(LoanStatusSubmitted), string(LoanStatusUnderwriting), "LoanApplication"},
		{string(LoanStatusUnderwriting), string(LoanStatusCreditApproval), "LoanApplication"},
		{string(LoanStatusCreditApproval), string(LoanStatusApproved), "LoanApplication"},
		{string(LoanStatusApproved), string(LoanStatusDisbursed), "LoanApplication"},
		{string(CustomerStatusActive), string(CustomerStatusInactive), "Customer"},
		{string(CustomerStatusInactive), string(CustomerStatusActive), "Customer"},
	}
	
	for _, transition := range validTransitions {
		err := ValidateStatusTransition(transition.current, transition.new, transition.entityType)
		assert.NoError(t, err, "Valid transition should pass: %s -> %s for %s", 
			transition.current, transition.new, transition.entityType)
	}
	
	// Test invalid transitions
	invalidTransitions := []struct {
		current, new, entityType string
	}{
		{string(LoanStatusDisbursed), string(LoanStatusSubmitted), "LoanApplication"}, // terminal state
		{string(LoanStatusRejected), string(LoanStatusApproved), "LoanApplication"},   // terminal state
		{string(LoanStatusSubmitted), string(LoanStatusDisbursed), "LoanApplication"}, // skip states
	}
	
	for _, transition := range invalidTransitions {
		err := ValidateStatusTransition(transition.current, transition.new, transition.entityType)
		assert.Error(t, err, "Invalid transition should fail: %s -> %s for %s", 
			transition.current, transition.new, transition.entityType)
	}
}

func TestValidateConsentPreferences(t *testing.T) {
	validConsent := `{"marketing": true, "dataSharing": false, "analytics": true}`
	err := ValidateConsentPreferences(validConsent)
	assert.NoError(t, err, "Valid consent preferences should pass")
	
	invalidConsent := []string{
		"",        // empty
		"short",   // too short
	}
	
	for _, consent := range invalidConsent {
		err := ValidateConsentPreferences(consent)
		assert.Error(t, err, "Invalid consent preferences should fail: %s", consent)
	}
}

func TestValidateComplianceRuleLogic(t *testing.T) {
	validLogic := "IF amount > 10000 THEN require_additional_approval = true"
	err := ValidateComplianceRuleLogic(validLogic)
	assert.NoError(t, err, "Valid rule logic should pass")
	
	invalidLogic := []string{
		"",        // empty
		"short",   // too short
	}
	
	for _, logic := range invalidLogic {
		err := ValidateComplianceRuleLogic(logic)
		assert.Error(t, err, "Invalid rule logic should fail: %s", logic)
	}
}