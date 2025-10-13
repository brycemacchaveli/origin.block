package domain

import (
	"time"
	
	"github.com/blockchain-financial-platform/fabric-chaincode/shared/validation"
)

// KYCRecord represents a KYC verification record
type KYCRecord struct {
	KYCID           string                `json:"kycID"`
	CustomerID      string                `json:"customerID"`
	Status          validation.KYCStatus  `json:"status"`
	VerificationDate *time.Time           `json:"verificationDate,omitempty"`
	ExpiryDate      *time.Time            `json:"expiryDate,omitempty"`
	DocumentHashes  []string              `json:"documentHashes"`
	VerificationNotes string              `json:"verificationNotes"`
	VerifiedBy      string                `json:"verifiedBy"`
	CreatedDate     time.Time             `json:"createdDate"`
	LastUpdated     time.Time             `json:"lastUpdated"`
}

// AMLRecord represents an AML check record
type AMLRecord struct {
	AMLID           string               `json:"amlID"`
	CustomerID      string               `json:"customerID"`
	Status          validation.AMLStatus `json:"status"`
	CheckDate       time.Time            `json:"checkDate"`
	RiskScore       float64              `json:"riskScore"`
	Flags           []string             `json:"flags"`
	CheckedBy       string               `json:"checkedBy"`
	Notes           string               `json:"notes"`
	CreatedDate     time.Time            `json:"createdDate"`
	LastUpdated     time.Time            `json:"lastUpdated"`
}

// KYCInitiationRequest represents a KYC initiation request
type KYCInitiationRequest struct {
	CustomerID     string   `json:"customerID"`
	DocumentHashes []string `json:"documentHashes"`
	ActorID        string   `json:"actorID"`
}

// KYCStatusUpdateRequest represents a KYC status update request
type KYCStatusUpdateRequest struct {
	KYCID             string               `json:"kycID"`
	NewStatus         validation.KYCStatus `json:"newStatus"`
	VerificationNotes string               `json:"verificationNotes"`
	ActorID           string               `json:"actorID"`
}

// AMLCheckRequest represents an AML check request
type AMLCheckRequest struct {
	CustomerID string  `json:"customerID"`
	ActorID    string  `json:"actorID"`
}

// AMLStatusUpdateRequest represents an AML status update request
type AMLStatusUpdateRequest struct {
	AMLID     string               `json:"amlID"`
	NewStatus validation.AMLStatus `json:"newStatus"`
	RiskScore float64              `json:"riskScore"`
	Flags     []string             `json:"flags"`
	Notes     string               `json:"notes"`
	ActorID   string               `json:"actorID"`
}