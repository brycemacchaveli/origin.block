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

Domain-driven organization with shared utilities:

```
fabric-chaincode/
├── customer/                  # Customer Mastery domain
│   ├── main.go               # Customer chaincode implementation
│   ├── main_test.go          # Customer chaincode tests
│   ├── kyc_aml_test.go       # KYC/AML specific tests
│   ├── go.mod                # Customer module dependencies
│   └── go.sum                # Dependency checksums
├── loan/                     # Loan Origination domain
│   ├── main.go               # Loan chaincode implementation
│   └── go.mod                # Loan module dependencies
├── compliance/               # Compliance & Regulatory domain
│   ├── main.go               # Compliance chaincode implementation
│   └── go.mod                # Compliance module dependencies
├── shared/                   # Shared utilities and libraries
│   ├── utils.go              # Common utility functions
│   ├── utils_test.go         # Utility tests
│   ├── domain_validation.go  # Domain validation logic
│   ├── domain_validation_test.go # Validation tests
│   ├── go.mod                # Shared module dependencies
│   └── README.md             # Shared utilities documentation
├── scripts/                  # Deployment and utility scripts
│   └── deploy-chaincode.sh   # Chaincode deployment script
└── go.mod                    # Root module configuration
```

## Backend Structure (backend/)

FastAPI microservices with domain separation:

```
backend/
├── customer_mastery/         # Customer domain API service
│   ├── __init__.py
│   └── api.py               # Customer REST endpoints
├── loan_origination/        # Loan domain API service
│   ├── __init__.py
│   └── api.py               # Loan REST endpoints
├── compliance_reporting/    # Compliance domain API service
│   ├── __init__.py
│   └── api.py               # Compliance REST endpoints
├── event_listener/          # Blockchain event processor
│   ├── __init__.py
│   └── service.py           # Event listening service
├── shared/                  # Shared utilities and libraries
│   ├── __init__.py
│   └── config.py            # Application configuration
├── tests/                   # Test suites
│   ├── __init__.py
│   └── test_main.py         # Main application tests
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

## Naming Conventions

### Go Code (Chaincode)
- **Files**: snake_case for test files, PascalCase for main files
- **Functions**: PascalCase for exported functions, camelCase for private
- **Structs**: PascalCase for all structs
- **Constants**: UPPER_SNAKE_CASE

### Python Code (Backend)
- **Files**: snake_case.py
- **Functions**: snake_case
- **Classes**: PascalCase
- **Constants**: UPPER_SNAKE_CASE
- **API Endpoints**: kebab-case in URLs

### Directory Structure Rules
- Domain folders use snake_case
- Each domain is self-contained with its own dependencies
- Shared utilities are centralized in `/shared` directories
- Tests are co-located with implementation code
- Configuration files use standard naming conventions (.env, requirements.txt, go.mod)

## Import Patterns

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

// Local packages last
import (
    "github.com/blockchain-financial-platform/fabric-chaincode/shared"
)
```

### Python Backend
```python
# Standard library first
import json
from typing import List, Optional

# Third-party packages
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Local packages last
from shared.config import settings
```