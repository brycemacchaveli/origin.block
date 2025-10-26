package domain

import (
	"time"
)

// ============================================================================
// CDP STATUS CONSTANTS
// ============================================================================

// CDPStatus represents the status of a Canonical Data Passport
type CDPStatus string

const (
	CDPStatusValid   CDPStatus = "VALID"
	CDPStatusExpired CDPStatus = "EXPIRED"
	CDPStatusRevoked CDPStatus = "REVOKED"
)

// ============================================================================
// CDP VERIFICATION LEVEL CONSTANTS
// ============================================================================

// CDPVerificationLevel represents the level of verification for a CDP
type CDPVerificationLevel string

const (
	CDPVerificationBasic    CDPVerificationLevel = "BASIC"
	CDPVerificationStandard CDPVerificationLevel = "STANDARD"
	CDPVerificationEnhanced CDPVerificationLevel = "ENHANCED"
)

// ============================================================================
// CDP DATA STRUCTURES
// ============================================================================

// CanonicalDataPassport represents a reusable, immutable digital credential
// containing cryptographic hashes of verified customer data
type CanonicalDataPassport struct {
	CDPID                string                   `json:"cdpID"`
	CustomerID           string                   `json:"customerID"`
	KYCHash              string                   `json:"kycHash"`              // SHA-256 hash of KYC data
	IncomeHash           string                   `json:"incomeHash"`           // SHA-256 hash of income verification
	ConsentHash          string                   `json:"consentHash"`          // SHA-256 hash of consent preferences
	VerificationLevel    CDPVerificationLevel     `json:"verificationLevel"`    // BASIC, STANDARD, ENHANCED
	GeneratedDate        time.Time                `json:"generatedDate"`
	ExpirationDate       time.Time                `json:"expirationDate"`
	SourceTransactionIDs []string                 `json:"sourceTransactionIDs"` // Blockchain TxIDs of source verifications
	IssuedBy             string                   `json:"issuedBy"`
	Status               CDPStatus                `json:"status"`               // VALID, EXPIRED, REVOKED
	RevokedDate          *time.Time               `json:"revokedDate,omitempty"`
	RevocationReason     string                   `json:"revocationReason,omitempty"`
}

// ============================================================================
// CDP REQUEST STRUCTURES
// ============================================================================

// CDPGenerationRequest represents a request to generate a new CDP
type CDPGenerationRequest struct {
	CustomerID        string                   `json:"customerID"`
	VerificationLevel CDPVerificationLevel     `json:"verificationLevel"`
	ValidityDays      int                      `json:"validityDays"`
	ActorID           string                   `json:"actorID"`
}

// CDPRevocationRequest represents a request to revoke a CDP
type CDPRevocationRequest struct {
	CDPID            string `json:"cdpID"`
	RevocationReason string `json:"revocationReason"`
	ActorID          string `json:"actorID"`
}

// CDPValidationResult represents the result of a CDP validation
type CDPValidationResult struct {
	IsValid           bool                     `json:"isValid"`
	CDPID             string                   `json:"cdpID"`
	VerificationLevel CDPVerificationLevel     `json:"verificationLevel"`
	ExpirationDate    time.Time                `json:"expirationDate"`
	Status            CDPStatus                `json:"status"`
	ValidationMessage string                   `json:"validationMessage"`
}
