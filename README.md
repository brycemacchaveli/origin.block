# Blockchain Financial Platform

A permissioned blockchain solution built on Hyperledger Fabric for legacy financial institutions, focusing on Loan Origination, Customer Mastery, and Compliance & Regulatory Reporting.

## Architecture

- **fabric-chaincode/**: Go-based chaincode for Hyperledger Fabric
- **backend/**: Python/FastAPI application services
- **frontend/**: Web UI (future implementation)
- **infrastructure/**: Docker and deployment configurations

## Quick Start

1. Start the development environment:
   ```bash
   docker-compose up -d
   ```

2. Set up the backend:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Deploy chaincode:
   ```bash
   cd fabric-chaincode
   ./scripts/deploy-chaincode.sh
   ```

## Development

See individual component READMEs for detailed development instructions:
- [Chaincode Development](fabric-chaincode/README.md)
- [Backend Development](backend/README.md)
- [Infrastructure Setup](infrastructure/README.md)