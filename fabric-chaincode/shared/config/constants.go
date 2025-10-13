package config

import "time"

// Application constants
const (
	// Validation limits
	MaxStringLength     = 1000
	MaxAddressLength    = 500
	MaxDescriptionLength = 2000
	MinPasswordLength   = 8
	
	// Business rules
	MinCustomerAge      = 18
	MaxCustomerAge      = 150
	MaxLoanAmount       = 10000000.0 // 10 million
	MinLoanAmount       = 1000.0
	
	// Time limits
	KYCValidityPeriod   = 365 * 24 * time.Hour // 1 year
	SessionTimeout      = 30 * time.Minute
	TransactionTimeout  = 5 * time.Minute
	
	// Pagination
	DefaultPageSize     = 20
	MaxPageSize         = 100
	
	// Encryption
	EncryptionKeySize   = 32 // 256 bits
)