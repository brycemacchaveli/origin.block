#!/bin/bash

# Test chaincode deployment on running network
# Usage: ./test-chaincode-deployment.sh [chaincode_name]

CHANNEL_NAME="mychannel"
CHAINCODE_NAME="${1:-compliance}"
CHAINCODE_VERSION="1.0"
CHAINCODE_SEQUENCE="1"
CHAINCODE_LANG="golang"

# Determine script's absolute directory to derive other paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "${SCRIPT_DIR}")")"
FABRIC_NETWORK_PATH="${PROJECT_ROOT}/infrastructure/fabric-network"
CHANNEL_ARTIFACTS_PATH="${FABRIC_NETWORK_PATH}/channel-artifacts"
TEMP_CHAINCODE_PATH="${FABRIC_NETWORK_PATH}/tmp"

# Export Fabric binaries path and config path
export PATH="${PROJECT_ROOT}/bin:$PATH"
export FABRIC_CFG_PATH="${PROJECT_ROOT}/config"

# Check if required binaries are available
if ! command -v configtxgen &> /dev/null; then
    echo "Error: configtxgen not found in PATH"
    exit 1
fi

if ! command -v osnadmin &> /dev/null; then
    echo "Error: osnadmin not found in PATH"
    exit 1
fi

# Set environment variables for Org1 Admin CLI
function set_org1_admin_cli_env() {
    export CORE_PEER_TLS_ENABLED=true
    export CORE_PEER_LOCALMSPID="Org1MSP"
    export CORE_PEER_TLS_ROOTCERT_FILE="${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt"
    export CORE_PEER_MSPCONFIGPATH="${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp"
    export CORE_PEER_ADDRESS=localhost:7051
}

# Set environment variables for Org2 Admin CLI
function set_org2_admin_cli_env() {
    export CORE_PEER_TLS_ENABLED=true
    export CORE_PEER_LOCALMSPID="Org2MSP"
    export CORE_PEER_TLS_ROOTCERT_FILE="${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt"
    export CORE_PEER_MSPCONFIGPATH="${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org2.example.com/users/Admin@org2.example.com/msp"
    export CORE_PEER_ADDRESS=localhost:9051
}

echo "==============================================="
echo "  TESTING CHAINCODE DEPLOYMENT"
echo "==============================================="
echo "  Chaincode: ${CHAINCODE_NAME}"

# Check if network is running
if ! docker ps | grep -q "orderer.example.com"; then
    echo "Error: Fabric network is not running. Please start it first."
    echo "Run: cd infrastructure && docker-compose up -d"
    exit 1
fi

# Create channel if it doesn't exist
echo "Creating channel '${CHANNEL_NAME}'..."
set_org1_admin_cli_env

# Create channel using channel participation API (Fabric 2.3+)
echo "Creating channel ${CHANNEL_NAME}..."

# First, create the genesis block for the channel using the application genesis profile
export FABRIC_CFG_PATH="${FABRIC_NETWORK_PATH}/config"
configtxgen -profile TwoOrgsApplicationGenesis -outputBlock "${CHANNEL_NAME}.block" -channelID "${CHANNEL_NAME}"

if [ $? -ne 0 ]; then
    echo "Failed to generate channel genesis block"
    exit 1
fi

# Join the orderer to the channel using the admin API
echo "Joining orderer to channel..."
osnadmin channel join --channelID "${CHANNEL_NAME}" --config-block "${CHANNEL_NAME}.block" \
    -o localhost:7053 --ca-file "${FABRIC_NETWORK_PATH}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/tls/ca.crt" \
    --client-cert "${FABRIC_NETWORK_PATH}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/tls/server.crt" \
    --client-key "${FABRIC_NETWORK_PATH}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/tls/server.key" || echo "Orderer might already be joined to channel"

# Reset FABRIC_CFG_PATH for peer commands
export FABRIC_CFG_PATH="${PROJECT_ROOT}/config"

sleep 2

# Join peers to channel
echo "Joining peers to channel..."
set_org1_admin_cli_env
echo "Joining Org1 peer to channel..."
peer channel join -b "${CHANNEL_NAME}.block"

set_org2_admin_cli_env
echo "Joining Org2 peer to channel..."
peer channel join -b "${CHANNEL_NAME}.block"

sleep 2

# Package chaincode
echo "Packaging chaincode '${CHAINCODE_NAME}'..."
CHAINCODE_SOURCE_PATH="${PROJECT_ROOT}/fabric-chaincode/${CHAINCODE_NAME}"
CHAINCODE_LABEL="${CHAINCODE_NAME}_${CHAINCODE_VERSION}"

if [ ! -d "${CHAINCODE_SOURCE_PATH}" ]; then
    echo "Error: Chaincode source directory not found: ${CHAINCODE_SOURCE_PATH}"
    exit 1
fi

# Ensure temp directory exists
mkdir -p "${TEMP_CHAINCODE_PATH}"

# Package chaincode
peer lifecycle chaincode package "${TEMP_CHAINCODE_PATH}/${CHAINCODE_NAME}.tar.gz" \
    --path "${CHAINCODE_SOURCE_PATH}" --lang "${CHAINCODE_LANG}" --label "${CHAINCODE_LABEL}"

echo "Chaincode packaged successfully"

# Install on Org1
echo "Installing chaincode on Org1..."
set_org1_admin_cli_env
peer lifecycle chaincode install "${TEMP_CHAINCODE_PATH}/${CHAINCODE_NAME}.tar.gz"

# Install on Org2
echo "Installing chaincode on Org2..."
set_org2_admin_cli_env
peer lifecycle chaincode install "${TEMP_CHAINCODE_PATH}/${CHAINCODE_NAME}.tar.gz"

# Get package ID
PACKAGE_ID=$(peer lifecycle chaincode queryinstalled --output json | jq -r ".installed_chaincodes[] | select(.label == \"${CHAINCODE_LABEL}\") | .package_id")
echo "Package ID: ${PACKAGE_ID}"

if [ -z "$PACKAGE_ID" ]; then
    echo "Error: Could not get package ID"
    exit 1
fi

# Approve for Org1
echo "Approving chaincode for Org1..."
set_org1_admin_cli_env
peer lifecycle chaincode approveformyorg -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com \
    --channelID "${CHANNEL_NAME}" --name "${CHAINCODE_NAME}" --version "${CHAINCODE_VERSION}" \
    --package-id "${PACKAGE_ID}" --sequence "${CHAINCODE_SEQUENCE}" --tls \
    --cafile "${FABRIC_NETWORK_PATH}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/tls/ca.crt"

# Approve for Org2
echo "Approving chaincode for Org2..."
set_org2_admin_cli_env
peer lifecycle chaincode approveformyorg -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com \
    --channelID "${CHANNEL_NAME}" --name "${CHAINCODE_NAME}" --version "${CHAINCODE_VERSION}" \
    --package-id "${PACKAGE_ID}" --sequence "${CHAINCODE_SEQUENCE}" --tls \
    --cafile "${FABRIC_NETWORK_PATH}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/tls/ca.crt"

sleep 3

# Commit chaincode
echo "Committing chaincode..."
set_org1_admin_cli_env
peer lifecycle chaincode commit -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com \
    --channelID "${CHANNEL_NAME}" --name "${CHAINCODE_NAME}" --version "${CHAINCODE_VERSION}" \
    --sequence "${CHAINCODE_SEQUENCE}" --tls \
    --cafile "${FABRIC_NETWORK_PATH}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/tls/ca.crt" \
    --peerAddresses localhost:7051 --tlsRootCertFiles "${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt" \
    --peerAddresses localhost:9051 --tlsRootCertFiles "${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt"

echo "Waiting for chaincode container to start..."
sleep 10

# Verify deployment
echo "Verifying chaincode deployment..."
peer lifecycle chaincode querycommitted --channelID "${CHANNEL_NAME}" --name "${CHAINCODE_NAME}"

echo "==============================================="
echo "  CHAINCODE DEPLOYMENT TEST COMPLETED"
echo "==============================================="
echo "Chaincode '${CHAINCODE_NAME}' has been successfully deployed!"
echo ""
echo "You can now test the chaincode with:"
echo "  ./infrastructure/scripts/test-chaincode.sh ${CHAINCODE_NAME}"