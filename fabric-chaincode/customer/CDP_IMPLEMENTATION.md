# CDP (Canonical Data Passport) Implementation

## Overview

This document describes the implementation of the Canonical Data Passport (CDP) feature in the Customer Chaincode. The CDP is a reusable, immutable digital credential that eliminates repeated KYC/income verification across loan applications.

## Implementation Summary

### Files Created/Modified

1. **fabric-chaincode/customer/handlers/cdp_handler.go** (NEW)
   - Implements all CDP-related chaincode functions
   - Handles CDP generation, retrieval, validation, and revocation

2. **fabric-chaincode/customer/chaincode/router.go** (MODIFIED)
   - Added CDP handler registration
   - Registered 5 new CDP functions

3. **fabric-chaincode/shared/config/prefixes.go** (MODIFIED)
   - Added CDP prefix constant for ID generation

### Implemented Functions

#### 1. GenerateCDP
**Requirements: 1.1, 1.2, 1.10**

Generates a new Canonical Data Passport for a customer.

**Features:**
- Generates unique CDP ID using shared ID generator
- Creates SHA-256 cryptographic hashes for:
  - KYC data
  - Income verification data
  - Consent preferences
- Sets expiration date based on validity period (days)
- Stores CDP in both ledger and Private Data Collection
- Updates customer record with current CDP ID
- Maintains CDP history for audit trail
- Captures source transaction IDs for traceability

**Input:**
```json
{
  "customerID": "CUST_123",
  "verificationLevel": "STANDARD",
  "validityDays": 90,
  "actorID": "ACTOR_001"
}
```

**Output:**
```json
{
  "cdpID": "CDP_1234567890_abc123",
  "customerID": "CUST_123",
  "kycHash": "a1b2c3...",
  "incomeHash": "d4e5f6...",
  "consentHash": "g7h8i9...",
  "verificationLevel": "STANDARD",
  "generatedDate": "2024-01-01T00:00:00Z",
  "expirationDate": "2024-04-01T00:00:00Z",
  "sourceTransactionIDs": ["tx123"],
  "issuedBy": "ACTOR_001",
  "status": "VALID"
}
```

#### 2. GetCDP
**Requirements: 1.8**

Retrieves a CDP by ID from the ledger.

**Features:**
- Retrieves CDP from ledger by ID
- Validates access permissions (basic MSP check)
- Returns complete CDP with all metadata

**Input:**
```json
["CDP_1234567890_abc123"]
```

**Output:** Complete CDP object (same as GenerateCDP output)

#### 3. ValidateCDP
**Requirements: 1.5, 1.7**

Validates a CDP's current status and expiration.

**Features:**
- Checks CDP status (VALID, EXPIRED, REVOKED)
- Verifies expiration date against current time
- Automatically updates status to EXPIRED if past expiration date
- Returns detailed validation result with message

**Input:**
```json
["CDP_1234567890_abc123"]
```

**Output:**
```json
{
  "isValid": true,
  "cdpID": "CDP_1234567890_abc123",
  "verificationLevel": "STANDARD",
  "expirationDate": "2024-04-01T00:00:00Z",
  "status": "VALID",
  "validationMessage": "CDP is valid"
}
```

#### 4. RevokeCDP
**Requirements: 1.10**

Revokes a CDP when customer data changes.

**Features:**
- Updates CDP status to REVOKED
- Records revocation reason and timestamp
- Updates CDP in both ledger and Private Data Collection
- Clears current CDP ID from customer record
- Prevents double revocation

**Input:**
```json
{
  "cdpID": "CDP_1234567890_abc123",
  "revocationReason": "Customer data updated",
  "actorID": "ACTOR_001"
}
```

**Output:** Updated CDP object with REVOKED status

#### 5. GetCustomerCurrentCDP

Retrieves the current active CDP for a customer.

**Features:**
- Looks up customer's current CDP ID
- Retrieves and returns the CDP
- Handles case where customer has no current CDP

**Input:**
```json
["CUST_123"]
```

**Output:** Complete CDP object

## Data Structures

### CanonicalDataPassport
```go
type CanonicalDataPassport struct {
    CDPID                string
    CustomerID           string
    KYCHash              string    // SHA-256 hash
    IncomeHash           string    // SHA-256 hash
    ConsentHash          string    // SHA-256 hash
    VerificationLevel    CDPVerificationLevel
    GeneratedDate        time.Time
    ExpirationDate       time.Time
    SourceTransactionIDs []string
    IssuedBy             string
    Status               CDPStatus
    RevokedDate          *time.Time
    RevocationReason     string
}
```

### Customer Extension
```go
type Customer struct {
    // ... existing fields ...
    CurrentCDPID string
    CDPHistory   []string
}
```

## Private Data Collection

CDPs are stored in a Private Data Collection named `cdpPrivateData` to ensure sensitive verification data is only accessible to authorized organizations.

**Collection Configuration:**
- Name: `cdpPrivateData`
- Policy: Accessible to authorized organizations
- Member-only read and write
- No automatic expiration (blockToLive: 0)

## Security Features

1. **Cryptographic Hashing**: All sensitive data is hashed using SHA-256
2. **Private Data Storage**: CDPs stored in Private Data Collection
3. **Access Control**: Basic MSP-based access validation
4. **Immutable Audit Trail**: All CDP operations recorded on blockchain
5. **Transaction Tracking**: Source transaction IDs captured for traceability

## Integration Points

### Customer Chaincode Router
All CDP functions are registered in the router and accessible via:
- `GenerateCDP`
- `GetCDP`
- `ValidateCDP`
- `RevokeCDP`
- `GetCustomerCurrentCDP`

### Loan Chaincode Integration
The Loan Chaincode can invoke these functions using cross-chaincode invocation:
```go
response := ctx.GetStub().InvokeChaincode("customer", params, "mychannel")
```

## Testing

The implementation has been verified through:
1. Successful Go compilation (`go build`)
2. Domain model tests pass
3. Code structure follows existing patterns

## Next Steps

1. Configure Private Data Collection in deployment
2. Implement cross-chaincode validation in Loan Chaincode (Task 4)
3. Create API endpoints in Customer Mastery service (Task 5)
4. Write comprehensive unit and integration tests (Tasks 7-8)

## Requirements Coverage

- ✅ 1.1: CDP generation with cryptographic hashes
- ✅ 1.2: CDP includes expiration, verification level, and source transactions
- ✅ 1.5: CDP validation checks status and expiration
- ✅ 1.7: Validation returns detailed results
- ✅ 1.8: CDP retrieval with access validation
- ✅ 1.10: CDP revocation with reason tracking
