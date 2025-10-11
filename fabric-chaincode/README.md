# Fabric Chaincode

Go-based chaincode implementation for the blockchain financial platform.

## Structure

- `customer/`: Customer Mastery domain chaincode
- `loan/`: Loan Origination domain chaincode  
- `compliance/`: Compliance & Regulatory domain chaincode
- `shared/`: Shared utilities and libraries
- `scripts/`: Deployment and testing scripts

## Development

1. Install Go dependencies:
   ```bash
   go mod tidy
   ```

2. Run tests:
   ```bash
   go test ./...
   ```

3. Deploy chaincode:
   ```bash
   ./scripts/deploy-chaincode.sh
   ```