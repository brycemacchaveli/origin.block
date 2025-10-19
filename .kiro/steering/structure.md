# Project Structure

## Root Directory Organization

```
blockchain-financial-platform/
├── fabric-chaincode/          # Go chaincode for Hyperledger Fabric
├── backend/                   # Python/FastAPI services
├── frontend/                  # Web UI (future implementation)
├── infrastructure/            # Docker and deployment configs
├── scripts/                   # Utility scripts
├── .kiro/                     # Kiro configuration and specs
├── docker-compose.yml         # Local development environment
└── README.md                  # Project documentation
```

## Chaincode Structure (fabric-chaincode/)

Domain-driven organization with shared utilities and modular design:

```
fabric-chaincode/
├── customer/                  # Customer Mastery domain
│   ├── main.go               # Customer chaincode implementation
│   ├── main_test.go          # Customer chaincode tests
│   ├── kyc_aml_test.go       # KYC/AML specific tests
│   ├── handlers.go           # Business logic handlers
│   ├── models.go             # Domain data structures
│   ├── validators.go         # Domain-specific validation
│   ├── interfaces.go         # Domain contracts
│   ├── go.mod                # Customer module dependencies
│   └── go.sum                # Dependency checksums
├── loan/                     # Loan Origination domain
│   ├── main.go               # Loan chaincode implementation
│   ├── main_test.go          # Loan chaincode tests
│   ├── handlers.go           # Business logic handlers
│   ├── models.go             # Domain data structures
│   ├── validators.go         # Domain-specific validation
│   ├── interfaces.go         # Domain contracts
│   └── go.mod                # Loan module dependencies
├── compliance/               # Compliance & Regulatory domain
│   ├── main.go               # Compliance chaincode implementation
│   ├── main_test.go          # Compliance chaincode tests
│   ├── handlers.go           # Business logic handlers
│   ├── models.go             # Domain data structures
│   ├── validators.go         # Domain-specific validation
│   ├── interfaces.go         # Domain contracts
│   └── go.mod                # Compliance module dependencies
├── shared/                   # Shared utilities and libraries
│   ├── interfaces.go         # Core system interfaces
│   ├── base_chaincode.go     # Abstract chaincode base
│   ├── utils.go              # Common utility functions
│   ├── utils_test.go         # Utility tests
│   ├── validation.go         # Common validation logic
│   ├── validation_test.go    # Validation tests
│   ├── errors.go             # Custom error types
│   ├── constants.go          # System-wide constants
│   ├── go.mod                # Shared module dependencies
│   └── README.md             # Shared utilities documentation
├── scripts/                  # Deployment and utility scripts
│   └── deploy-chaincode.sh   # Chaincode deployment script
└── go.mod                    # Root module configuration
```

## Backend Structure (backend/)

FastAPI microservices with domain separation and modular architecture:

```
backend/
├── customer_mastery/         # Customer domain API service
│   ├── __init__.py
│   ├── api.py               # Customer REST endpoints
│   ├── models.py            # Domain-specific data models
│   ├── services.py          # Business logic layer
│   ├── repositories.py      # Data access layer
│   └── interfaces.py        # Domain interfaces/contracts
├── loan_origination/        # Loan domain API service
│   ├── __init__.py
│   ├── api.py               # Loan REST endpoints
│   ├── models.py            # Domain-specific data models
│   ├── services.py          # Business logic layer
│   ├── repositories.py      # Data access layer
│   └── interfaces.py        # Domain interfaces/contracts
├── compliance_reporting/    # Compliance domain API service
│   ├── __init__.py
│   ├── api.py               # Compliance REST endpoints
│   ├── models.py            # Domain-specific data models
│   ├── services.py          # Business logic layer
│   ├── repositories.py      # Data access layer
│   └── interfaces.py        # Domain interfaces/contracts
├── event_listener/          # Blockchain event processor
│   ├── __init__.py
│   ├── service.py           # Event listening service
│   ├── handlers.py          # Event handler implementations
│   └── interfaces.py        # Event processing contracts
├── shared/                  # Shared utilities and libraries
│   ├── __init__.py
│   ├── config.py            # Application configuration
│   ├── database.py          # Database connection and base classes
│   ├── exceptions.py        # Custom exception classes
│   ├── validators.py        # Common validation logic
│   ├── utils.py             # Utility functions
│   ├── base_models.py       # Base Pydantic models
│   ├── base_repository.py   # Abstract repository pattern
│   ├── base_service.py      # Abstract service pattern
│   └── interfaces.py        # Core system interfaces
├── tests/                   # Test suites
│   ├── __init__.py
│   ├── conftest.py          # Pytest fixtures and configuration
│   ├── test_main.py         # Main application tests
│   ├── unit/                # Unit tests by domain
│   ├── integration/         # Integration tests
│   └── fixtures/            # Test data and mocks
├── main.py                  # FastAPI application entry point
├── requirements.txt         # Python dependencies
├── pytest.ini              # Pytest configuration
├── Dockerfile               # Container configuration
└── .env.example             # Environment variables template
```

## Infrastructure Structure (infrastructure/)

Deployment and network configurations:

```
infrastructure/
├── fabric-network/          # Hyperledger Fabric network config
│   ├── organizations/       # MSP and certificate configurations
│   │   ├── ordererOrganizations/
│   │   └── peerOrganizations/
│   ├── system-genesis-block/
│   └── config/
└── scripts/                 # Infrastructure scripts
    └── setup-network.sh     # Network setup automation
```

## Code Organization Principles

### DRY (Don't Repeat Yourself)
- **Shared Libraries**: Common functionality extracted to `/shared` directories
- **Base Classes**: Abstract base classes for common patterns (API handlers, validators)
- **Configuration**: Centralized config management with environment-specific overrides
- **Utilities**: Reusable helper functions for common operations (validation, formatting, error handling)

### KISS (Keep It Simple, Stupid)
- **Single Responsibility**: Each module/function has one clear purpose
- **Minimal Dependencies**: Only include necessary dependencies per domain
- **Clear Interfaces**: Simple, well-defined APIs between components
- **Readable Code**: Self-documenting code with minimal complexity

### SOLID Principles
- **Single Responsibility**: Each class/module handles one concern
- **Open/Closed**: Extensible through interfaces, not modification
- **Liskov Substitution**: Implementations are interchangeable through interfaces
- **Interface Segregation**: Small, focused interfaces over large ones
- **Dependency Inversion**: Depend on abstractions, not concrete implementations

### Modular Architecture Patterns
- **Domain Boundaries**: Clear separation between customer, loan, and compliance domains
- **Layered Architecture**: Presentation → Business Logic → Data Access → Blockchain
- **Dependency Injection**: Constructor injection for testability and flexibility
- **Event-Driven**: Loose coupling through event publishing/subscribing
- **Factory Pattern**: Centralized object creation for complex dependencies

## Naming Conventions

### Go Code (Chaincode)
- **Files**: snake_case for test files, PascalCase for main files
- **Functions**: PascalCase for exported functions, camelCase for private
- **Structs**: PascalCase for all structs
- **Constants**: UPPER_SNAKE_CASE
- **Interfaces**: End with 'er' suffix (e.g., `Validator`, `Handler`)

### Python Code (Backend)
- **Files**: snake_case.py
- **Functions**: snake_case
- **Classes**: PascalCase
- **Constants**: UPPER_SNAKE_CASE
- **API Endpoints**: kebab-case in URLs
- **Abstract Classes**: Prefix with 'Abstract' or 'Base'

### Directory Structure Rules
- Domain folders use snake_case
- Each domain is self-contained with minimal cross-domain dependencies
- Shared utilities are centralized in `/shared` directories with clear interfaces
- Tests are co-located with implementation code
- Configuration files use standard naming conventions (.env, requirements.txt, go.mod)
- Interface definitions in separate files (e.g., `interfaces.py`, `contracts.go`)

## Import Patterns & Dependency Management

### Go Chaincode
```go
// Standard library first
import (
    "encoding/json"
    "fmt"
)

// Third-party packages
import (
    "github.com/hyperledger/fabric-chaincode-go/shim"
    "github.com/hyperledger/fabric-protos-go/peer"
)

// Local packages last - interfaces first, then implementations
import (
    "github.com/brycemacchaveli/origin.block/fabric-chaincode/shared/interfaces"
    "github.com/brycemacchaveli/origin.block/fabric-chaincode/shared"
)
```

### Python Backend
```python
# Standard library first
import json
from typing import List, Optional, Protocol

# Third-party packages
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

# Local packages last - interfaces first, then implementations
from shared.interfaces import Repository, Service
from shared.config import settings
from shared.base_models import BaseEntity
```

## Dependency Injection Patterns

### Python Service Layer
```python
# Abstract base for dependency injection
class ServiceBase(ABC):
    def __init__(self, repository: Repository):
        self._repository = repository

# Concrete implementation
class CustomerService(ServiceBase):
    def __init__(self, repository: CustomerRepository):
        super().__init__(repository)
```

### Go Interface-Based Design
```go
// Define interfaces for testability
type Validator interface {
    Validate(data interface{}) error
}

type Repository interface {
    Save(ctx context.Context, entity interface{}) error
    FindByID(ctx context.Context, id string) (interface{}, error)
}

// Implement through composition
type CustomerChaincode struct {
    validator Validator
    repo      Repository
}
```

## Code Reuse Strategies

### Shared Validation Logic
- Common validation rules in `/shared/validators.py` and `/shared/validation.go`
- Domain-specific validators extend base validation interfaces
- Reusable validation decorators/middleware

### Base Repository Pattern
- Abstract repository with common CRUD operations
- Domain repositories inherit and extend base functionality
- Consistent error handling and transaction management

### Event Handling Framework
- Common event publishing/subscribing infrastructure
- Reusable event handler base classes
- Standardized event payload structures