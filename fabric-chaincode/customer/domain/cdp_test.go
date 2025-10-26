package domain

import (
	"testing"
	"time"
)

func TestCDPStatusConstants(t *testing.T) {
	// Test that CDP status constants are defined correctly
	if CDPStatusValid != "VALID" {
		t.Errorf("Expected CDPStatusValid to be 'VALID', got '%s'", CDPStatusValid)
	}
	if CDPStatusExpired != "EXPIRED" {
		t.Errorf("Expected CDPStatusExpired to be 'EXPIRED', got '%s'", CDPStatusExpired)
	}
	if CDPStatusRevoked != "REVOKED" {
		t.Errorf("Expected CDPStatusRevoked to be 'REVOKED', got '%s'", CDPStatusRevoked)
	}
}

func TestCDPVerificationLevelConstants(t *testing.T) {
	// Test that CDP verification level constants are defined correctly
	if CDPVerificationBasic != "BASIC" {
		t.Errorf("Expected CDPVerificationBasic to be 'BASIC', got '%s'", CDPVerificationBasic)
	}
	if CDPVerificationStandard != "STANDARD" {
		t.Errorf("Expected CDPVerificationStandard to be 'STANDARD', got '%s'", CDPVerificationStandard)
	}
	if CDPVerificationEnhanced != "ENHANCED" {
		t.Errorf("Expected CDPVerificationEnhanced to be 'ENHANCED', got '%s'", CDPVerificationEnhanced)
	}
}

func TestCanonicalDataPassportStructure(t *testing.T) {
	// Test that CanonicalDataPassport struct can be created with all fields
	now := time.Now()
	expiration := now.Add(90 * 24 * time.Hour)
	
	// Create valid SHA-256 hashes (64 hex characters)
	kycHash := "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
	incomeHash := "b1c2d3e4f5a6b1c2d3e4f5a6b1c2d3e4f5a6b1c2d3e4f5a6b1c2d3e4f5a6b1c2"
	consentHash := "c1d2e3f4a5b6c1d2e3f4a5b6c1d2e3f4a5b6c1d2e3f4a5b6c1d2e3f4a5b6c1d2"
	
	cdp := CanonicalDataPassport{
		CDPID:                "CDP-001",
		CustomerID:           "CUST-001",
		KYCHash:              kycHash,
		IncomeHash:           incomeHash,
		ConsentHash:          consentHash,
		VerificationLevel:    CDPVerificationStandard,
		GeneratedDate:        now,
		ExpirationDate:       expiration,
		SourceTransactionIDs: []string{"TX-001", "TX-002"},
		IssuedBy:             "SYSTEM",
		Status:               CDPStatusValid,
	}
	
	// Verify fields are set correctly
	if cdp.CDPID != "CDP-001" {
		t.Errorf("Expected CDPID to be 'CDP-001', got '%s'", cdp.CDPID)
	}
	if cdp.Status != CDPStatusValid {
		t.Errorf("Expected Status to be 'VALID', got '%s'", cdp.Status)
	}
	if cdp.VerificationLevel != CDPVerificationStandard {
		t.Errorf("Expected VerificationLevel to be 'STANDARD', got '%s'", cdp.VerificationLevel)
	}
}

func TestCustomerCDPFields(t *testing.T) {
	// Test that Customer struct has CDP fields
	customer := Customer{
		CustomerID:   "CUST-001",
		FirstName:    "John",
		LastName:     "Doe",
		CurrentCDPID: "CDP-001",
		CDPHistory:   []string{"CDP-000", "CDP-001"},
	}
	
	if customer.CurrentCDPID != "CDP-001" {
		t.Errorf("Expected CurrentCDPID to be 'CDP-001', got '%s'", customer.CurrentCDPID)
	}
	if len(customer.CDPHistory) != 2 {
		t.Errorf("Expected CDPHistory length to be 2, got %d", len(customer.CDPHistory))
	}
}

func TestIsCDPExpired(t *testing.T) {
	now := time.Now()
	
	// Test expired CDP
	expiredCDP := &CanonicalDataPassport{
		ExpirationDate: now.Add(-24 * time.Hour), // Expired yesterday
		Status:         CDPStatusValid,
	}
	if !IsCDPExpired(expiredCDP) {
		t.Error("Expected CDP to be expired")
	}
	
	// Test valid CDP
	validCDP := &CanonicalDataPassport{
		ExpirationDate: now.Add(24 * time.Hour), // Expires tomorrow
		Status:         CDPStatusValid,
	}
	if IsCDPExpired(validCDP) {
		t.Error("Expected CDP to not be expired")
	}
}

func TestIsCDPValid(t *testing.T) {
	now := time.Now()
	
	// Test valid CDP
	validCDP := &CanonicalDataPassport{
		ExpirationDate: now.Add(24 * time.Hour),
		Status:         CDPStatusValid,
	}
	if !IsCDPValid(validCDP) {
		t.Error("Expected CDP to be valid")
	}
	
	// Test expired CDP
	expiredCDP := &CanonicalDataPassport{
		ExpirationDate: now.Add(-24 * time.Hour),
		Status:         CDPStatusValid,
	}
	if IsCDPValid(expiredCDP) {
		t.Error("Expected CDP to be invalid (expired)")
	}
	
	// Test revoked CDP
	revokedCDP := &CanonicalDataPassport{
		ExpirationDate: now.Add(24 * time.Hour),
		Status:         CDPStatusRevoked,
	}
	if IsCDPValid(revokedCDP) {
		t.Error("Expected CDP to be invalid (revoked)")
	}
}
