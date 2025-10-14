# Blockchain Financial Platform - Infrastructure

Complete infrastructure setup and deployment guide for the Hyperledger Fabric blockchain network supporting compliance, customer mastery, and loan origination domains.

## 🏗️ Architecture Overview

This infrastructure provides a production-ready Hyperledger Fabric network with:
- **2 Organizations** (Org1, Org2) with peer nodes
- **1 Orderer** using Raft consensus
- **3 Domain Chaincodes** (compliance, customer, loan)
- **PostgreSQL Database** for off-chain data
- **Certificate Authority** for identity management

## 📁 Directory Structure

```
infrastructure/
├── docker-compose.yaml          # Main orchestration file
├── fabric-network/              # Fabric network artifacts
│   ├── config/                  # Network configuration
│   │   ├── configtx.yaml       # Channel and genesis configuration
│   │   └── crypto-config.yaml  # Cryptographic material config
│   ├── organizations/           # Generated MSP certificates (ignored by git)
│   ├── channel-artifacts/       # Generated channel files (ignored by git)
│   ├── system-genesis-block/    # Genesis block (ignored by git)
│   └── tmp/                     # Temporary chaincode packages
└── scripts/                     # Deployment and utility scripts
    ├── setup-network.sh         # Main deployment script
    ├── test-chaincode-deployment.sh  # Chaincode deployment testing
    ├── test-chaincode.sh        # Chaincode functionality testing
    ├── set-org1-env.sh          # Environment setup for Org1
    ├── set-org2-env.sh          # Environment setup for Org2
    └── README.md                # Detailed script documentation
```

## 🚀 Quick Start Deployment

### Prerequisites

1. **Install Required Tools:**
   ```bash
   # Download Hyperledger Fabric binaries (if not already present)
   curl -sSL https://raw.githubusercontent.com/hyperledger/fabric/master/scripts/bootstrap.sh | bash -s -- 2.4.7 1.4.12 -d -s
   
   # Ensure binaries are in PATH
   export PATH=$PWD/bin:$PATH
   export FABRIC_CFG_PATH=$PWD/config
   ```

2. **Install Docker & Docker Compose:**
   - Docker Desktop (macOS/Windows) or Docker Engine (Linux)
   - Docker Compose v2.0+

3. **Install jq (recommended):**
   ```bash
   # macOS
   brew install jq
   
   # Ubuntu/Debian
   sudo apt-get install jq
   ```

### 🎯 Deploy Complete Blockchain Network

#### Option 1: Deploy Single Chaincode (Recommended for Testing)
```bash
# Deploy compliance chaincode only
export PATH=$PWD/bin:$PATH
export FABRIC_CFG_PATH=$PWD/config
./infrastructure/scripts/setup-network.sh --chaincode compliance
```

#### Option 2: Deploy All Chaincodes
```bash
# Deploy all three chaincodes (compliance, customer, loan)
export PATH=$PWD/bin:$PATH
export FABRIC_CFG_PATH=$PWD/config
./infrastructure/scripts/setup-network.sh --all
```

#### Option 3: Deploy Specific Chaincode
```bash
# Deploy customer chaincode
./infrastructure/scripts/setup-network.sh --chaincode customer

# Deploy loan chaincode
./infrastructure/scripts/setup-network.sh --chaincode loan
```

### ✅ Verify Deployment

1. **Check Container Status:**
   ```bash
   docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
   ```

2. **Test Chaincode Functionality:**
   ```bash
   # Test compliance chaincode
   ./infrastructure/scripts/test-chaincode.sh compliance
   
   # Test customer chaincode (if deployed)
   ./infrastructure/scripts/test-chaincode.sh customer
   
   # Test loan chaincode (if deployed)
   ./infrastructure/scripts/test-chaincode.sh loan
   ```

## 🔧 Manual Chaincode Interaction

### Setup Environment
```bash
# Set environment for Org1 operations
cd infrastructure/scripts
source set-org1-env.sh
export PATH=$PWD/../../bin:$PATH
export FABRIC_CFG_PATH=$PWD/../../config
```

### Common Operations

#### Initialize Ledger
```bash
peer chaincode invoke -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com \
  --tls --cafile $PWD/../fabric-network/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/tls/ca.crt \
  -C mychannel -n compliance -c '{"function":"InitLedger","Args":[]}'
```

#### Query Data
```bash
peer chaincode query -C mychannel -n compliance \
  -c '{"function":"GetComplianceRule","Args":["RULE001"]}'
```

#### Create New Records
```bash
peer chaincode invoke -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com \
  --tls --cafile $PWD/../fabric-network/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/tls/ca.crt \
  -C mychannel -n compliance \
  -c '{"function":"CreateComplianceRule","Args":["RULE004","DATA_PRIVACY","Customer data must be encrypted","ACTIVE"]}'
```

## 🌐 Network Endpoints

| Service | Endpoint | Purpose |
|---------|----------|---------|
| Orderer | `localhost:7050` | Transaction ordering |
| Orderer Admin | `localhost:7053` | Channel management |
| Peer0.Org1 | `localhost:7051` | Org1 peer operations |
| Peer0.Org2 | `localhost:9051` | Org2 peer operations |
| CA.Org1 | `localhost:7054` | Certificate authority |
| PostgreSQL | `localhost:5432` | Off-chain database |

## 🛠️ Development Workflow

### 1. Modify Chaincode
```bash
# Edit chaincode in fabric-chaincode/[domain]/
# Example: fabric-chaincode/compliance/chaincode/contract.go
```

### 2. Redeploy Chaincode
```bash
# Stop network
cd infrastructure && docker-compose down

# Clean and redeploy
./scripts/setup-network.sh --chaincode compliance
```

### 3. Test Changes
```bash
./scripts/test-chaincode.sh compliance
```

## 🔍 Troubleshooting

### Common Issues

#### 1. Containers Not Starting
```bash
# Check logs
docker-compose -f infrastructure/docker-compose.yaml logs orderer.example.com
docker-compose -f infrastructure/docker-compose.yaml logs peer0.org1.example.com

# Restart network
cd infrastructure
docker-compose down --volumes --remove-orphans
docker-compose up -d
```

#### 2. Chaincode Deployment Fails
```bash
# Check chaincode container logs
docker logs $(docker ps -q --filter "name=dev-peer")

# Verify Go modules
cd fabric-chaincode/compliance
go mod tidy
go build
```

#### 3. Channel Issues
```bash
# List channels
peer channel list

# Check channel info
peer channel getinfo -c mychannel
```

#### 4. Certificate Issues
```bash
# Regenerate crypto material
rm -rf infrastructure/fabric-network/organizations/peerOrganizations
rm -rf infrastructure/fabric-network/organizations/ordererOrganizations
./infrastructure/scripts/setup-network.sh --chaincode compliance
```

### Debug Commands

```bash
# Check peer status
peer node status

# List installed chaincodes
peer lifecycle chaincode queryinstalled

# Check committed chaincodes
peer lifecycle chaincode querycommitted -C mychannel

# View container logs
docker-compose -f infrastructure/docker-compose.yaml logs -f [service-name]
```

## 🧹 Cleanup

### Stop Network
```bash
cd infrastructure
docker-compose down
```

### Complete Cleanup
```bash
cd infrastructure
docker-compose down --volumes --remove-orphans
docker system prune -f
docker volume prune -f

# Remove generated artifacts
rm -rf fabric-network/organizations/peerOrganizations
rm -rf fabric-network/organizations/ordererOrganizations
rm -rf fabric-network/system-genesis-block/*
rm -rf fabric-network/channel-artifacts/*
rm -rf fabric-network/tmp/*
```

## 📊 Monitoring

### Container Health
```bash
# Check all containers
docker ps

# Monitor resource usage
docker stats

# View specific service logs
docker-compose logs -f peer0.org1.example.com
```

### Network Status
```bash
# Channel information
peer channel getinfo -c mychannel

# Chaincode status
peer lifecycle chaincode querycommitted -C mychannel --name compliance
```

## 🔐 Security Notes

- **Private Keys**: Never commit generated certificates or private keys
- **Network Access**: Default configuration is for development (localhost only)
- **TLS**: All peer-to-peer communication uses TLS
- **MSP**: Each organization has separate identity management

## 📚 Additional Resources

- [Hyperledger Fabric Documentation](https://hyperledger-fabric.readthedocs.io/)
- [Fabric Samples](https://github.com/hyperledger/fabric-samples)
- [Script Documentation](scripts/README.md)

## 🆘 Support

For issues with:
- **Network Setup**: Check `scripts/README.md`
- **Chaincode Development**: See `../fabric-chaincode/README.md`
- **Backend Integration**: See `../backend/README.md`

## ✨ Current Status

This infrastructure has been **tested and verified** with:
- ✅ **Hyperledger Fabric 2.4.7** - Latest stable version
- ✅ **Go 1.23** - Chaincode development
- ✅ **Docker Compose** - Container orchestration
- ✅ **Channel Participation API** - Modern channel management
- ✅ **TLS Enabled** - Secure peer communication
- ✅ **Multi-domain Chaincodes** - Compliance, Customer, Loan

### Deployment Verification
```bash
# Verify network is running
docker ps --format "table {{.Names}}\t{{.Status}}"

# Expected output should show:
# - orderer.example.com (Up)
# - peer0.org1.example.com (Up)  
# - peer0.org2.example.com (Up)
# - ca.org1.example.com (Up)
# - blockchain-finance-db (Up)
# - dev-peer0.org1.example.com-compliance_1.0-* (Up)
# - dev-peer0.org2.example.com-compliance_1.0-* (Up)
```

---

**Repository**: [https://github.com/brycemacchaveli/origin.block](https://github.com/brycemacchaveli/origin.block)

**Last Updated**: October 2024  
**Fabric Version**: 2.4.7  
**Status**: ✅ Production Ready