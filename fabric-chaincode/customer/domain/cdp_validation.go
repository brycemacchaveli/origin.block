package domain

import (
	"fmt"
	"regexp"
	"strings"
	"time"
	
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/shared/validation"
)

// ValidateCanonicalDataPassport validates a CDP entity
func ValidateCanonicalDataPassport(cdp *CanonicalDataPassport) error {
	var errors []string
	
	// Validate required fields
	if strings.TrimSpace(cdp.CDPID) == "" {
		errors = append(errors, "cdpID is required")
	}
	if strings.TrimSpace(cdp.CustomerID) == "" {
		errors = append(errors, "customerID is required")
	}
	if strings.TrimSpace(cdp.IssuedBy) == "" {
		errors = append(errors, "issuedBy is required")
	}
	
	// Validate hashes (SHA-256 format: 64 hex characters)
	hashRegex := regexp.MustCompile(`^[a-fA-F0-9]{64}$`)
	
	if cdp.KYCHash != "" && !hashRegex.MatchString(cdp.KYCHash) {
		errors = append(errors, "kycHash must be a valid SHA-256 hash (64 hex characters)")
	}
	if cdp.IncomeHash != "" && !hashRegex.MatchString(cdp.IncomeHash) {
		errors = append(errors, "incomeHash must be a valid SHA-256 hash (64 hex characters)")
	}
	if cdp.ConsentHash != "" && !hashRegex.MatchString(cdp.ConsentHash) {
		errors = append(errors, "consentHash must be a valid SHA-256 hash (64 hex characters)")
	}
	
	// Validate verification level
	if err := validation.ValidateCDPVerificationLevel(string(cdp.VerificationLevel)); err != nil {
		errors = append(errors, fmt.Sprintf("verificationLevel: %v", err))
	}
	
	// Validate status
	if err := validation.ValidateCDPStatus(string(cdp.Status)); err != nil {
		errors = append(errors, fmt.Sprintf("status: %v", err))
	}
	
	// Validate dates
	if cdp.GeneratedDate.IsZero() {
		errors = append(errors, "generatedDate is required")
	}
	if cdp.ExpirationDate.IsZero() {
		errors = append(errors, "expirationDate is required")
	}
	if !cdp.ExpirationDate.IsZero() && !cdp.GeneratedDate.IsZero() {
		if cdp.ExpirationDate.Before(cdp.GeneratedDate) {
			errors = append(errors, "expirationDate must be after generatedDate")
		}
	}
	
	// Validate revocation fields consistency
	if cdp.Status == CDPStatusRevoked {
		if cdp.RevokedDate == nil {
			errors = append(errors, "revokedDate is required when status is REVOKED")
		}
		if strings.TrimSpace(cdp.RevocationReason) == "" {
			errors = append(errors, "revocationReason is required when status is REVOKED")
		}
	}
	
	if len(errors) > 0 {
		return fmt.Errorf("validation errors: %s", strings.Join(errors, ", "))
	}
	
	return nil
}

// ValidateCDPGenerationRequest validates a CDP generation request
func ValidateCDPGenerationRequest(req *CDPGenerationRequest) error {
	var errors []string
	
	// Validate required fields
	if strings.TrimSpace(req.CustomerID) == "" {
		errors = append(errors, "customerID is required")
	}
	if strings.TrimSpace(req.ActorID) == "" {
		errors = append(errors, "actorID is required")
	}
	
	// Validate verification level
	if err := validation.ValidateCDPVerificationLevel(string(req.VerificationLevel)); err != nil {
		errors = append(errors, fmt.Sprintf("verificationLevel: %v", err))
	}
	
	// Validate validity days
	if req.ValidityDays <= 0 {
		errors = append(errors, "validityDays must be positive")
	}
	if req.ValidityDays > 365 {
		errors = append(errors, "validityDays cannot exceed 365 days")
	}
	
	if len(errors) > 0 {
		return fmt.Errorf("validation errors: %s", strings.Join(errors, ", "))
	}
	
	return nil
}

// ValidateCDPRevocationRequest validates a CDP revocation request
func ValidateCDPRevocationRequest(req *CDPRevocationRequest) error {
	var errors []string
	
	// Validate required fields
	if strings.TrimSpace(req.CDPID) == "" {
		errors = append(errors, "cdpID is required")
	}
	if strings.TrimSpace(req.ActorID) == "" {
		errors = append(errors, "actorID is required")
	}
	if strings.TrimSpace(req.RevocationReason) == "" {
		errors = append(errors, "revocationReason is required")
	}
	
	if len(errors) > 0 {
		return fmt.Errorf("validation errors: %s", strings.Join(errors, ", "))
	}
	
	return nil
}

// IsCDPExpired checks if a CDP has expired
func IsCDPExpired(cdp *CanonicalDataPassport) bool {
	return time.Now().After(cdp.ExpirationDate)
}

// IsCDPValid checks if a CDP is valid (not expired and status is VALID)
func IsCDPValid(cdp *CanonicalDataPassport) bool {
	return cdp.Status == CDPStatusValid && !IsCDPExpired(cdp)
}
