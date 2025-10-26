package domain

import (
	"strings"
	"testing"
	"time"
)

func TestValidateCanonicalDataPassport(t *testing.T) {
	now := time.Now()
	expiration := now.Add(90 * 24 * time.Hour)
	validHash := "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
	
	tests := []struct {
		name    string
		cdp     *CanonicalDataPassport
		wantErr bool
		errMsg  string
	}{
		{
			name: "Valid CDP",
			cdp: &CanonicalDataPassport{
				CDPID:             "CDP-001",
				CustomerID:        "CUST-001",
				KYCHash:           validHash,
				IncomeHash:        validHash,
				ConsentHash:       validHash,
				VerificationLevel: CDPVerificationStandard,
				GeneratedDate:     now,
				ExpirationDate:    expiration,
				IssuedBy:          "SYSTEM",
				Status:            CDPStatusValid,
			},
			wantErr: false,
		},
		{
			name: "Missing CDPID",
			cdp: &CanonicalDataPassport{
				CustomerID:        "CUST-001",
				VerificationLevel: CDPVerificationStandard,
				GeneratedDate:     now,
				ExpirationDate:    expiration,
				IssuedBy:          "SYSTEM",
				Status:            CDPStatusValid,
			},
			wantErr: true,
			errMsg:  "cdpID is required",
		},
		{
			name: "Invalid KYC Hash",
			cdp: &CanonicalDataPassport{
				CDPID:             "CDP-001",
				CustomerID:        "CUST-001",
				KYCHash:           "invalid-hash",
				VerificationLevel: CDPVerificationStandard,
				GeneratedDate:     now,
				ExpirationDate:    expiration,
				IssuedBy:          "SYSTEM",
				Status:            CDPStatusValid,
			},
			wantErr: true,
			errMsg:  "kycHash must be a valid SHA-256 hash",
		},
		{
			name: "Invalid Verification Level",
			cdp: &CanonicalDataPassport{
				CDPID:             "CDP-001",
				CustomerID:        "CUST-001",
				KYCHash:           validHash,
				VerificationLevel: "INVALID",
				GeneratedDate:     now,
				ExpirationDate:    expiration,
				IssuedBy:          "SYSTEM",
				Status:            CDPStatusValid,
			},
			wantErr: true,
			errMsg:  "verificationLevel",
		},
		{
			name: "Expiration before Generation",
			cdp: &CanonicalDataPassport{
				CDPID:             "CDP-001",
				CustomerID:        "CUST-001",
				KYCHash:           validHash,
				VerificationLevel: CDPVerificationStandard,
				GeneratedDate:     expiration,
				ExpirationDate:    now,
				IssuedBy:          "SYSTEM",
				Status:            CDPStatusValid,
			},
			wantErr: true,
			errMsg:  "expirationDate must be after generatedDate",
		},
		{
			name: "Revoked without RevokedDate",
			cdp: &CanonicalDataPassport{
				CDPID:             "CDP-001",
				CustomerID:        "CUST-001",
				KYCHash:           validHash,
				VerificationLevel: CDPVerificationStandard,
				GeneratedDate:     now,
				ExpirationDate:    expiration,
				IssuedBy:          "SYSTEM",
				Status:            CDPStatusRevoked,
			},
			wantErr: true,
			errMsg:  "revokedDate is required when status is REVOKED",
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateCanonicalDataPassport(tt.cdp)
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateCanonicalDataPassport() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if tt.wantErr && err != nil && !strings.Contains(err.Error(), tt.errMsg) {
				t.Errorf("ValidateCanonicalDataPassport() error = %v, expected to contain %v", err, tt.errMsg)
			}
		})
	}
}

func TestValidateCDPGenerationRequest(t *testing.T) {
	tests := []struct {
		name    string
		req     *CDPGenerationRequest
		wantErr bool
		errMsg  string
	}{
		{
			name: "Valid Request",
			req: &CDPGenerationRequest{
				CustomerID:        "CUST-001",
				VerificationLevel: CDPVerificationStandard,
				ValidityDays:      90,
				ActorID:           "USER-001",
			},
			wantErr: false,
		},
		{
			name: "Missing CustomerID",
			req: &CDPGenerationRequest{
				VerificationLevel: CDPVerificationStandard,
				ValidityDays:      90,
				ActorID:           "USER-001",
			},
			wantErr: true,
			errMsg:  "customerID is required",
		},
		{
			name: "Invalid Validity Days - Zero",
			req: &CDPGenerationRequest{
				CustomerID:        "CUST-001",
				VerificationLevel: CDPVerificationStandard,
				ValidityDays:      0,
				ActorID:           "USER-001",
			},
			wantErr: true,
			errMsg:  "validityDays must be positive",
		},
		{
			name: "Invalid Validity Days - Too Long",
			req: &CDPGenerationRequest{
				CustomerID:        "CUST-001",
				VerificationLevel: CDPVerificationStandard,
				ValidityDays:      400,
				ActorID:           "USER-001",
			},
			wantErr: true,
			errMsg:  "validityDays cannot exceed 365 days",
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateCDPGenerationRequest(tt.req)
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateCDPGenerationRequest() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if tt.wantErr && err != nil && !strings.Contains(err.Error(), tt.errMsg) {
				t.Errorf("ValidateCDPGenerationRequest() error = %v, expected to contain %v", err, tt.errMsg)
			}
		})
	}
}

func TestValidateCDPRevocationRequest(t *testing.T) {
	tests := []struct {
		name    string
		req     *CDPRevocationRequest
		wantErr bool
		errMsg  string
	}{
		{
			name: "Valid Request",
			req: &CDPRevocationRequest{
				CDPID:            "CDP-001",
				RevocationReason: "Customer data updated",
				ActorID:          "USER-001",
			},
			wantErr: false,
		},
		{
			name: "Missing CDPID",
			req: &CDPRevocationRequest{
				RevocationReason: "Customer data updated",
				ActorID:          "USER-001",
			},
			wantErr: true,
			errMsg:  "cdpID is required",
		},
		{
			name: "Missing Revocation Reason",
			req: &CDPRevocationRequest{
				CDPID:   "CDP-001",
				ActorID: "USER-001",
			},
			wantErr: true,
			errMsg:  "revocationReason is required",
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateCDPRevocationRequest(tt.req)
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateCDPRevocationRequest() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if tt.wantErr && err != nil && !strings.Contains(err.Error(), tt.errMsg) {
				t.Errorf("ValidateCDPRevocationRequest() error = %v, expected to contain %v", err, tt.errMsg)
			}
		})
	}
}
