# Infrastructure Scripts

This directory contains scripts for setting up and managing the Hyperledger Fabric network for the blockchain financial platform.

## Scripts Overview

### setup-network.sh
Main script for setting up the complete Hyperledger Fabric network with dynamic chaincode deployment.

**Usage:**
```bash
# Deploy all chaincodes (compliance, customer, loan)
./infrastructure/scripts/setup-network.sh --all

# Deploy specific chaincode
./infrastructure/scripts/setup-network.sh --chaincode compliance
./infrastructure/scripts/setup-network.sh --chaincode customer
./infrastructure/scripts/setup-network.sh --chaincode loan

# Show help
./infrastructure/scripts/setup-network.sh --help
```

**What it does:**
1. Stops and removes existing Docker containers
2. Removes old crypto material and artifacts
3. Creates directory structure
4. Generates cryptographic material using cryptogen
5. Generates genesis block and channel artifacts using configtxgen
6. Launches the Fabric network via Docker Compose
7. Creates and joins channel
8. Deploys selected chaincode(s)
9. Tests chaincode deployment

### set-org1-env.sh & set-org2-env.sh
Helper scripts to set environment variables for peer CLI operations.

**Usage:**
```bash
# Set environment for Org1 operations
source infrastructure/scripts/set-org1-env.sh

# Set environment for Org2 operations
source infrastructure/scripts/set-org2-env.sh
```

### test-chaincode.sh
Script for testing deployed chaincodes with domain-specific operations.

**Usage:**
```bash
# Test specific chaincode
./infrastructure/scripts/test-chaincode.sh compliance
./infrastructure/scripts/test-chaincode.sh customer
./infrastructure/scripts/test-chaincode.sh loan
```

## Prerequisites

Before running these scripts, ensure you have:

1. **Hyperledger Fabric Binaries**: Download and add to PATH
   ```bash
   curl -sSL https://raw.githubusercontent.com/hyperledger/fabric/master/scripts/bootstrap.sh | bash -s -- 2.4.7 1.4.12 -d -s
   export PATH=$PWD/bin:$PATH
   ```

2. **Docker and Docker Compose**: Installed and running

3. **jq**: For JSON parsing (optional but recommended)
   ```bash
   # macOS
   brew install jq
   
   # Ubuntu/Debian
   sudo apt-get install jq
   ```

4. **Go**: For chaincode compilation
   ```bash
   # macOS
   brew install go
   ```

## Network Configuration

The scripts expect the following configuration files:

- `infrastructure/fabric-network/config/configtx/crypto-config.yaml`
- `infrastructure/fabric-network/config/configtx/configtx.yaml`
- `infrastructure/docker-compose.yaml`

## Chaincode Structure

The scripts work with the following chaincode structure:
```
fabric-chaincode/
├── compliance/     # Compliance & Regulatory chaincode
├── customer/       # Customer Mastery chaincode
├── loan/          # Loan Origination chaincode
└── shared/        # Shared utilities
```

Each chaincode directory should contain:
- `main.go` - Main chaincode implementation
- `go.mod` - Go module definition
- Additional Go files as needed

## Environment Variables

The scripts use these key environment variables:

- `CORE_PEER_TLS_ENABLED=true`
- `CORE_PEER_LOCALMSPID` - Organization MSP ID
- `CORE_PEER_TLS_ROOTCERT_FILE` - TLS root certificate
- `CORE_PEER_MSPCONFIGPATH` - MSP configuration path
- `CORE_PEER_ADDRESS` - Peer address

## Troubleshooting

### Common Issues

1. **Cryptogen not found**
   - Ensure Fabric binaries are in your PATH
   - Download binaries using the bootstrap script

2. **Docker containers not starting**
   - Check Docker is running
   - Verify docker-compose.yaml exists
   - Check port conflicts (7050, 7051, 9051)

3. **Chaincode deployment fails**
   - Verify chaincode directory structure
   - Check Go module dependencies
   - Ensure network is fully started before deployment

4. **Permission denied**
   - Make scripts executable: `chmod +x infrastructure/scripts/*.sh`

### Logs and Debugging

View Docker container logs:
```bash
# View all container logs
docker-compose -f infrastructure/docker-compose.yaml logs

# View specific container logs
docker-compose -f infrastructure/docker-compose.yaml logs orderer.example.com
docker-compose -f infrastructure/docker-compose.yaml logs peer0.org1.example.com
```

Check chaincode container logs:
```bash
# List chaincode containers
docker ps --filter "name=dev-"

# View chaincode logs
docker logs <chaincode-container-name>
```

## Network Cleanup

To completely clean up the network:
```bash
# Stop and remove containers
docker-compose -f infrastructure/docker-compose.yaml down --volumes --remove-orphans

# Remove chaincode images
docker rmi -f $(docker images dev-* -q)

# Clean up artifacts
rm -rf infrastructure/fabric-network/organizations
rm -rf infrastructure/fabric-network/system-genesis-block
rm -rf infrastructure/fabric-network/channel-artifacts
```

## Development Workflow

1. **Initial Setup**
   ```bash
   ./infrastructure/scripts/setup-network.sh --all
   ```

2. **Develop Chaincode**
   - Modify chaincode in `fabric-chaincode/[domain]/`
   - Test locally with Go unit tests

3. **Deploy Updated Chaincode**
   ```bash
   # Increment version in setup-network.sh
   ./infrastructure/scripts/setup-network.sh --chaincode [domain]
   ```

4. **Test Chaincode**
   ```bash
   ./infrastructure/scripts/test-chaincode.sh [domain]
   ```

5. **Interactive Testing**
   ```bash
   source infrastructure/scripts/set-org1-env.sh
   peer chaincode query -C mychannel -n [chaincode] -c '{"function":"[function]","Args":["[args]"]}'
   ```