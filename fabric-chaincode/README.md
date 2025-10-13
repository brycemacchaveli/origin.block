# Fabric Chaincode

This directory contains the Go chaincode implementations for the Hyperledger Fabric blockchain network, organized using a clean, modular architecture with domain-driven design principles.

## Architecture Overview

The chaincode is structured as three separate bounded contexts (domains), each implemented as an independent chaincode:

- **Customer Chaincode** - Customer identity, KYC/AML verification, and consent management
- **Loan Chaincode** - Loan origination, application processing, and document management  
- **Compliance Chaincode** - Regulatory compliance, rule enforcement, and reporting

## Directory Structure

```
fabric-chaincode/
├── customer/                   # Customer domain chaincode
│   ├── cmd/main.go            # Chaincode entry point
│   ├── chaincode/             # Fabric-specific contract and routing
│   ├── domain/                # Business entities and validation
│   ├── handlers/              # Request handlers for each operation
│   ├── services/              # Domain-specific event services
│   ├── tests/                 # Unit and integration tests
│   └── go.mod                 # Module dependencies
├── loan/                      # Loan domain chaincode
│   ├── cmd/main.go            # Chaincode entry point
│   ├── chaincode/             # Fabric-specific contract and routing
│   ├── domain/                # Business entities and validation
│   ├── handlers/              # Request handlers for each operation
│   ├── services/              # Domain-specific event services
│   └── go.mod                 # Module dependencies
├── compliance/                # Compliance domain chaincode
│   ├── cmd/main.go            # Chaincode entry point
│   ├── chaincode/             # Fabric-specific contract and routing
│   ├── handlers/              # Request handlers for each operation
│   └── go.mod                 # Module dependencies
├── shared/                    # Shared utilities and libraries
│   ├── chaincode/             # Base contract for common functionality
│   ├── config/                # Configuration constants and prefixes
│   ├── interfaces/            # Common interfaces for services
│   ├── services/              # Shared services (persistence, base events)
│   ├── utils/                 # Utility functions (JSON, ID generation, time)
│   ├── validation/            # Domain validation rules and logic
│   └── go.mod                 # Shared module dependencies
├── scripts/                   # Build and deployment scripts
│   ├── build-all.sh          # Build all chaincodes
│   └── deploy-chaincode.sh   # Deployment script
├── Makefile                   # Build automation
└── README.md                  # This file
```

## Key Design Principles

### 1. Domain-Driven Design (DDD)
Each chaincode represents a bounded context with clear domain boundaries:
- Customer domain handles identity and verification
- Loan domain manages loan lifecycle
- Compliance domain enforces rules and generates reports

### 2. Clean Architecture
Each chaincode follows consistent layering:
- **cmd/** - Application entry point
- **chaincode/** - Fabric framework integration
- **handlers/** - Request/response handling
- **domain/** - Business entities and rules
- **services/** - Infrastructure services

### 3. Event-Driven Communication
Chaincodes communicate through standardized events:
- Customer events trigger compliance checks
- Loan events notify compliance and customer systems
- All events follow consistent payload structure

### 4. Shared Libraries
Common functionality is centralized in the shared module:
- **Base contracts** - Common chaincode initialization and routing
- **Shared services** - Persistence and base event emission
- **Validation rules** - Domain validation and business logic
- **Utility functions** - JSON, ID generation, time handling
- **Configuration** - Constants, prefixes, and event definitions
- **Interfaces** - Common contracts for services and validators

## Development

### Prerequisites
- Go 1.21 or later
- Hyperledger Fabric development environment

### Quick Start

```bash
# Set up development environment
make dev-setup

# Install dependencies
make deps

# Format and lint code
make fmt lint

# Run all tests
make test

# Build all chaincodes
make build

# Package for deployment
make package
```

### Building Individual Chaincodes

```bash
# Build customer chaincode
make build-customer

# Build loan chaincode  
make build-loan

# Build compliance chaincode
make build-compliance
```

### Testing

```bash
# Run all tests
make test

# Test specific chaincode
make test-customer
make test-loan
make test-compliance
make test-shared

# Run tests with coverage
cd customer && go test -cover ./...
```

### Code Quality

```bash
# Format all code
make fmt

# Lint all code
make lint

# Clean build artifacts
make clean
```

## Chaincode APIs

### Customer Chaincode
- `RegisterCustomer` - Register a new customer
- `UpdateCustomer` - Update customer information
- `GetCustomer` - Retrieve customer details
- `UpdateCustomerStatus` - Change customer status
- `InitiateKYC` - Start KYC verification process
- `UpdateKYCStatus` - Update KYC verification status
- `InitiateAMLCheck` - Start AML compliance check
- `UpdateAMLStatus` - Update AML check results

### Loan Chaincode
- `SubmitLoanApplication` - Submit new loan application
- `UpdateLoanStatus` - Update loan application status
- `GetLoanApplication` - Retrieve loan details
- `ApproveLoan` - Approve loan with terms
- `RejectLoan` - Reject loan application
- `UploadDocument` - Upload loan documents
- `VerifyDocument` - Verify document authenticity

### Compliance Chaincode
- `PerformAMLCheck` - Execute AML compliance check
- `VerifyKYCDocuments` - Verify KYC documentation
- `GenerateComplianceReport` - Create compliance reports
- `GetComplianceReport` - Retrieve compliance reports

## Event System

The chaincodes use a standardized event system for cross-domain communication:

```go
type EventPayload struct {
    EventType   string      `json:"eventType"`
    EntityID    string      `json:"entityID"`
    EntityType  string      `json:"entityType"`
    ActorID     string      `json:"actorID"`
    Timestamp   string      `json:"timestamp"`
    Data        interface{} `json:"data"`
    Metadata    map[string]string `json:"metadata,omitempty"`
}
```

### Key Events
- `CustomerCreated` - New customer registered
- `KYCVerified` - KYC verification completed
- `AMLFlagged` - AML check flagged customer
- `LoanSubmitted` - New loan application
- `LoanApproved` - Loan approved
- `ComplianceRuleViolation` - Compliance rule violated

## Deployment

### Using Scripts
```bash
# Build and package all chaincodes
./scripts/build-all.sh

# Deploy to Fabric network
./scripts/deploy-chaincode.sh
```

### Manual Deployment
```bash
# Package chaincode
peer lifecycle chaincode package customer.tar.gz --path ./customer --lang golang --label customer_1.0

# Install on peer
peer lifecycle chaincode install customer.tar.gz

# Approve chaincode definition
peer lifecycle chaincode approveformyorg --channelID mychannel --name customer --version 1.0 --package-id <package-id> --sequence 1

# Commit chaincode definition
peer lifecycle chaincode commit --channelID mychannel --name customer --version 1.0 --sequence 1
```

## Configuration

### Environment Variables
- `FABRIC_LOGGING_SPEC` - Logging level (INFO, DEBUG, ERROR)
- `CORE_CHAINCODE_LOGGING_LEVEL` - Chaincode logging level

### Shared Configuration
Configuration constants are defined in `shared/config/`:
- `prefixes.go` - Entity key prefixes
- `events.go` - Event name constants  
- `constants.go` - Business rule constants

## Testing Strategy

### Unit Tests
- Domain logic validation
- Handler request/response processing
- Service layer functionality

### Integration Tests
- End-to-end chaincode flows
- Cross-chaincode event handling
- Database persistence

### Test Data
Test utilities provide consistent test data generation and mock services.

## Contributing

1. Follow the established directory structure
2. Add comprehensive tests for new functionality
3. Update documentation for API changes
4. Use consistent error handling patterns
5. Follow Go coding standards and conventions

## Troubleshooting

### Common Issues

**Build Failures**
```bash
# Clean and rebuild
make clean deps build
```

**Test Failures**
```bash
# Run tests with verbose output
cd <chaincode> && go test -v ./...
```

**Import Errors**
```bash
# Ensure shared module is properly linked
cd <chaincode> && go mod tidy
```

For more detailed troubleshooting, check the individual chaincode logs and Fabric peer logs.