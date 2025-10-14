# Shared Chaincode Utilities

This package provides shared utilities for the blockchain financial platform chaincode implementations. It includes validation, access control, cryptographic, and history tracking utilities that are used across all domain-specific chaincodes.

## Overview

The shared utilities are organized into several categories:

- **Basic Utilities**: ID generation, hashing, JSON marshaling/unmarshaling
- **Validation Utilities**: Email, phone, amount, status, and field validation
- **Access Control Utilities**: Actor management, permissions, and authorization
- **Cryptographic Utilities**: Document hashing, data encryption/decryption
- **History Tracking Utilities**: Immutable audit trail management
- **Domain-Specific Validation**: Financial domain validation rules

## Core Components

### Basic Utilities (`utils.go`)

#### ID Generation
```go
// Generate unique blockchain identifiers
id := GenerateID("CUSTOMER") // Returns: CUSTOMER_1234567890_abc123
```

#### Hashing
```go
// Create SHA256 hash of strings
hash := HashString("sensitive data")

// Hash documents for integrity verification
docHash := HashDocument([]byte("document content"))
```

#### State Management
```go
// Store/retrieve JSON data from blockchain state
err := PutStateAsJSON(stub, "key", dataStruct)
err := GetStateAsJSON(stub, "key", &dataStruct)
```

### Validation Utilities

#### Basic Validation
```go
// Validate required fields
fields := map[string]string{"email": "user@example.com", "name": "John"}
err := ValidateRequired(fields)

// Validate email format
err := ValidateEmail("user@example.com")

// Validate phone numbers
err := ValidatePhone("+1234567890")

// Validate amounts
err := ValidateAmount(1000.50)
```

#### Advanced Validation
```go
// Validate with custom rules
rules := map[string][]ValidationRule{
    "email": {{Name: "format", Validator: ValidateEmail}},
}
err := ValidateFields(fields, rules)
```

### Access Control

#### Actor Management
```go
// Define actor types and roles
actor := Actor{
    ActorID:    "USER_123",
    ActorType:  ActorTypeInternalUser,
    Role:       RoleUnderwriter,
    Permissions: GetRolePermissions(RoleUnderwriter),
    IsActive:   true,
}

// Check permissions
hasPermission := actor.HasPermission(PermissionViewCustomer)
```

#### Authorization
```go
// Validate actor access for operations
actor, err := ValidateActorAccess(stub, actorID, PermissionCreateLoan)

// Get caller identity from transaction context
callerID, err := GetCallerIdentity(stub)
```

### Cryptographic Utilities

#### Data Encryption
```go
// Encrypt sensitive data
encrypted, err := EncryptSensitiveData("sensitive info", "encryption-key")

// Decrypt data
decrypted, err := DecryptSensitiveData(encrypted, "encryption-key")

// Hash sensitive data with salt
hash := HashSensitiveData("national-id", "salt")
```

### History Tracking

#### Audit Trail
```go
// Record history entries for changes
err := RecordHistoryEntry(stub, entityID, "Customer", "UPDATE", 
    "email", "old@example.com", "new@example.com", actorID)

// Retrieve entity history
history, err := GetEntityHistory(stub, entityID)
```

### Domain-Specific Validation (`domain_validation.go`)

#### Status Validation
```go
// Validate loan application status
err := ValidateLoanApplicationStatus("SUBMITTED")

// Validate customer status
err := ValidateCustomerStatus("ACTIVE")

// Validate KYC/AML status
err := ValidateKYCStatus("VERIFIED")
err := ValidateAMLStatus("CLEAR")
```

#### Business Rules
```go
// Validate loan amounts by type
err := ValidateLoanAmount(50000, "PERSONAL")

// Validate status transitions
err := ValidateStatusTransition("SUBMITTED", "UNDERWRITING", "LoanApplication")

// Validate dates and personal information
err := ValidateDateOfBirth(time.Date(1990, 1, 1, 0, 0, 0, 0, time.UTC))
err := ValidateNationalID("ABC123456")
```

## Constants and Enums

### Actor Types
- `ActorTypeInternalUser`: Internal bank employees
- `ActorTypeExternalPartner`: External partners (introducers, etc.)
- `ActorTypeSystem`: System-generated transactions

### Actor Roles
- `RoleUnderwriter`: Loan underwriting staff
- `RoleIntroducer`: External loan introducers
- `RoleComplianceOfficer`: Compliance monitoring staff
- `RoleCreditOfficer`: Credit approval staff
- `RoleCustomerService`: Customer service representatives
- `RoleRiskAnalyst`: Risk analysis staff
- `RoleSystemAdmin`: System administrators
- `RoleRegulator`: Regulatory authorities

### Permissions
- `PermissionCreateCustomer`: Create new customers
- `PermissionUpdateCustomer`: Update customer information
- `PermissionViewCustomer`: View customer data
- `PermissionCreateLoan`: Create loan applications
- `PermissionUpdateLoan`: Update loan applications
- `PermissionApproveLoan`: Approve/reject loans
- `PermissionViewLoan`: View loan data
- `PermissionViewCompliance`: View compliance events
- `PermissionUpdateCompliance`: Update compliance rules
- `PermissionViewReports`: View regulatory reports
- `PermissionRegulatorAccess`: Special regulatory access

### Status Types

#### Loan Application Status
- `LoanStatusSubmitted`: Initial submission
- `LoanStatusUnderwriting`: Under review
- `LoanStatusCreditApproval`: Credit approval stage
- `LoanStatusApproved`: Approved for disbursement
- `LoanStatusRejected`: Rejected
- `LoanStatusDisbursed`: Funds disbursed

#### Customer Status
- `CustomerStatusActive`: Active customer
- `CustomerStatusInactive`: Inactive customer
- `CustomerStatusSuspended`: Suspended customer

#### KYC/AML Status
- `KYCStatusPending`: Verification pending
- `KYCStatusVerified`: Successfully verified
- `KYCStatusFailed`: Verification failed
- `KYCStatusExpired`: Verification expired
- `AMLStatusClear`: AML checks passed
- `AMLStatusFlagged`: Flagged for review
- `AMLStatusReviewing`: Under AML review
- `AMLStatusBlocked`: Blocked due to AML issues

## Usage Examples

### Customer Creation Validation
```go
// Validate customer data before creation
fields := map[string]string{
    "email": customer.Email,
    "phone": customer.Phone,
    "nationalID": customer.NationalID,
}

rules := map[string][]ValidationRule{
    "email": {{Name: "format", Validator: ValidateEmail}},
    "phone": {{Name: "format", Validator: ValidatePhone}},
    "nationalID": {{Name: "format", Validator: ValidateNationalID}},
}

if err := ValidateFields(fields, rules); err != nil {
    return fmt.Errorf("validation failed: %v", err)
}

// Validate date of birth
if err := ValidateDateOfBirth(customer.DateOfBirth); err != nil {
    return fmt.Errorf("invalid date of birth: %v", err)
}
```

### Loan Application Processing
```go
// Validate actor permissions
actor, err := ValidateActorAccess(stub, actorID, PermissionCreateLoan)
if err != nil {
    return fmt.Errorf("access denied: %v", err)
}

// Validate loan data
if err := ValidateLoanAmount(application.Amount, application.LoanType); err != nil {
    return fmt.Errorf("invalid loan amount: %v", err)
}

// Record history
err = RecordHistoryEntry(stub, application.ID, "LoanApplication", "CREATE",
    "status", "", "SUBMITTED", actor.ActorID)
```

### Compliance Rule Enforcement
```go
// Validate status transition
if err := ValidateStatusTransition(currentStatus, newStatus, "LoanApplication"); err != nil {
    return fmt.Errorf("invalid status transition: %v", err)
}

// Encrypt sensitive data
encryptedNationalID, err := EncryptSensitiveData(customer.NationalID, encryptionKey)
if err != nil {
    return fmt.Errorf("encryption failed: %v", err)
}
```

## Testing

The package includes comprehensive unit tests for all utilities:

```bash
cd fabric-chaincode/shared
go test -v
```

Tests cover:
- All validation functions with valid and invalid inputs
- Access control and permission checking
- Cryptographic operations
- History tracking functionality
- Domain-specific business rules
- Error handling and edge cases

## Requirements Mapping

This implementation addresses the following requirements:

- **Requirement 4.1**: Actor registry with blockchain identity, role, and type information
- **Requirement 4.2**: Master Customer record management with proper validation
- **Requirement 4.3**: LoanApplication entities with history tracking
- **Requirement 4.4**: Immutable history with timestamp, actor identity, and transaction details
- **Requirement 6.7**: Compliance checks without significant latency through optimized validation

## Integration

These utilities are designed to be imported and used by all domain-specific chaincodes:

```go
import "github.com/brycemacchaveli/origin.block/fabric-chaincode/shared"

// Use in chaincode functions
func CreateCustomer(stub shim.ChaincodeStubInterface, args []string) peer.Response {
    // Validate access
    actor, err := shared.ValidateActorAccess(stub, actorID, shared.PermissionCreateCustomer)
    if err != nil {
        return shim.Error(err.Error())
    }
    
    // Validate data
    if err := shared.ValidateEmail(customer.Email); err != nil {
        return shim.Error(err.Error())
    }
    
    // Store with history
    err = shared.RecordHistoryEntry(stub, customer.ID, "Customer", "CREATE", 
        "", "", "ACTIVE", actor.ActorID)
    
    return shim.Success(nil)
}
```