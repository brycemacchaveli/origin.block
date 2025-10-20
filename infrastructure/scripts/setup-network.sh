#!/bin/bash

# This script sets up a fully functional Hyperledger Fabric development network
# with dynamic chaincode deployment for compliance, customer, and loan domains.
# It uses cryptogen and configtxgen to generate necessary artifacts and
# Docker Compose to orchestrate the network.

# --- Configuration Variables ---
CHANNEL_NAME="mychannel"

# Define all available chaincodes (using arrays for compatibility)
AVAILABLE_CHAINCODES=("compliance" "customer" "loan")

# Default chaincode deployment behavior
DEFAULT_DEPLOY_ALL="false"
CHAINCODE_VERSION="1.0"
CHAINCODE_SEQUENCE="1"
CHAINCODE_LANG="golang" # "golang", "node", or "java"

# Parse command line arguments
DEPLOY_ALL="${DEFAULT_DEPLOY_ALL}"
SPECIFIC_CHAINCODE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --all)
            DEPLOY_ALL="true"
            shift
            ;;
        --chaincode)
            SPECIFIC_CHAINCODE="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --all                Deploy all chaincodes (compliance, customer, loan)"
            echo "  --chaincode NAME     Deploy specific chaincode (compliance|customer|loan)"
            echo "  -h, --help          Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 --all                    # Deploy all chaincodes"
            echo "  $0 --chaincode compliance   # Deploy only compliance chaincode"
            echo "  $0 --chaincode customer     # Deploy only customer chaincode"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Function to check if chaincode is valid
is_valid_chaincode() {
    local chaincode=$1
    for valid in "${AVAILABLE_CHAINCODES[@]}"; do
        if [[ "$valid" == "$chaincode" ]]; then
            return 0
        fi
    done
    return 1
}

# Determine which chaincodes to deploy
CHAINCODES_TO_DEPLOY=()
if [[ "$DEPLOY_ALL" == "true" ]]; then
    CHAINCODES_TO_DEPLOY=("compliance" "customer" "loan")
elif [[ -n "$SPECIFIC_CHAINCODE" ]]; then
    if is_valid_chaincode "$SPECIFIC_CHAINCODE"; then
        CHAINCODES_TO_DEPLOY=("$SPECIFIC_CHAINCODE")
    else
        echo "Error: Invalid chaincode name '$SPECIFIC_CHAINCODE'"
        echo "Available chaincodes: ${AVAILABLE_CHAINCODES[*]}"
        exit 1
    fi
else
    # Default behavior: deploy compliance chaincode
    CHAINCODES_TO_DEPLOY=("compliance")
fi

# Determine script's absolute directory to derive other paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "${SCRIPT_DIR}")")" # Go up two levels from script dir
FABRIC_NETWORK_PATH="${PROJECT_ROOT}/infrastructure/fabric-network"
FABRIC_CONFIG_PATH="${FABRIC_NETWORK_PATH}/config"
CHANNEL_ARTIFACTS_PATH="${FABRIC_NETWORK_PATH}/channel-artifacts"
TEMP_CHAINCODE_PATH="${FABRIC_NETWORK_PATH}/tmp" # For chaincode package

# Path to the Docker Compose file
DOCKER_COMPOSE_FILE="${PROJECT_ROOT}/infrastructure/docker-compose.yaml"

# --- Environment Setup ---
# Export Fabric binaries path (assuming they are in PROJECT_ROOT/bin or system PATH)
# If your fabric-samples/bin is elsewhere, adjust this.
export PATH="${PROJECT_ROOT}/bin:$PATH"
export FABRIC_CFG_PATH="${PROJECT_ROOT}/config" # Default path for core.yaml/orderer.yaml.
# We will override for configtxgen.

# Ensure cryptogen, configtxgen, and docker-compose binaries are available
if ! command -v cryptogen &> /dev/null; then
    echo "Error: 'cryptogen' not found. Please ensure Fabric binaries are in your PATH (e.g., ${PROJECT_ROOT}/bin)."
    echo "You might need to download Fabric binaries: curl -sSL https://raw.githubusercontent.com/hyperledger/fabric/master/scripts/bootstrap.sh | bash -s -- 2.4.7 1.4.12 -d -s"
    exit 1
fi

if ! command -v configtxgen &> /dev/null; then
    echo "Error: 'configtxgen' not found. Please ensure Fabric binaries are in your PATH."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Error: 'docker-compose' not found. Please install Docker Compose."
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo "Warning: 'jq' not found. Chaincode query output parsing might fail. Please install jq."
fi

set -euo pipefail # Exit immediately if a command exits with a non-zero status.
# Exit if a command in a pipeline fails.
# Treat unset variables as an error.

# --- Helper Functions ---
function print_header() {
    echo "==============================================="
    echo "  $1"
    echo "==============================================="
}

function stop_and_remove_containers() {
    print_header "Stopping and removing existing Docker containers and networks"
    # Use -f $DOCKER_COMPOSE_FILE explicitly
    docker-compose -f "${DOCKER_COMPOSE_FILE}" down --volumes --remove-orphans || true
    docker system prune -f || true
    docker volume prune -f || true
    # Clean up any residual docker containers, images, and volumes
    CONTAINERS=$(docker ps -aq)
    if [ -n "$CONTAINERS" ]; then
        docker rm -f $CONTAINERS || true
    fi
    CHAINCODE_IMAGES=$(docker images dev-* -q)
    if [ -n "$CHAINCODE_IMAGES" ]; then
        docker rmi -f $CHAINCODE_IMAGES || true
    fi
}

function remove_artifacts() {
    print_header "Removing old crypto and config artifacts"
    rm -rf "${FABRIC_NETWORK_PATH}/organizations/peerOrganizations" || true
    rm -rf "${FABRIC_NETWORK_PATH}/organizations/ordererOrganizations" || true
    rm -rf "${FABRIC_NETWORK_PATH}/system-genesis-block" || true
    rm -rf "${CHANNEL_ARTIFACTS_PATH}" || true
    rm -rf "${TEMP_CHAINCODE_PATH}" || true
}

function create_dirs() {
    print_header "Creating network directory structure"
    mkdir -p "${FABRIC_NETWORK_PATH}/organizations"
    mkdir -p "${FABRIC_NETWORK_PATH}/system-genesis-block"
    mkdir -p "${CHANNEL_ARTIFACTS_PATH}"
    mkdir -p "${TEMP_CHAINCODE_PATH}" # For temporary chaincode packages
}

function generate_crypto_material() {
    print_header "Generating cryptographic material with cryptogen"
    CRYPTOGEN_CONFIG="${FABRIC_CONFIG_PATH}/crypto-config.yaml"
    if [ ! -f "${CRYPTOGEN_CONFIG}" ]; then
        echo "Error: crypto-config.yaml not found at ${CRYPTOGEN_CONFIG}"
        echo "Please create this file based on standard Fabric examples."
        exit 1
    fi
    cryptogen generate --config="${CRYPTOGEN_CONFIG}" --output="${FABRIC_NETWORK_PATH}/organizations"
}

function generate_configtx_artifacts() {
    print_header "Generating orderer genesis block and channel artifacts with configtxgen"
    # Temporarily set FABRIC_CFG_PATH to where configtx.yaml lives
    export FABRIC_CFG_PATH="${FABRIC_CONFIG_PATH}"
    
    # Generate Orderer Genesis Block
    configtxgen -profile TwoOrgsOrdererGenesis -channelID system-channel -outputBlock "${FABRIC_NETWORK_PATH}/system-genesis-block/genesis.block"
    echo "  - Generated genesis.block"
    
    # Generate Channel Configuration Transaction
    configtxgen -profile TwoOrgsChannel -outputCreateChannelTx "${CHANNEL_ARTIFACTS_PATH}/${CHANNEL_NAME}.tx" -channelID "${CHANNEL_NAME}"
    echo "  - Generated ${CHANNEL_NAME}.tx"
    
    # Generate Anchor Peer Update for Org1
    configtxgen -profile TwoOrgsChannel -outputAnchorPeersUpdate "${CHANNEL_ARTIFACTS_PATH}/Org1MSPanchors.tx" -channelID "${CHANNEL_NAME}" -asOrg Org1MSP
    echo "  - Generated Org1MSPanchors.tx"
    
    # Generate Anchor Peer Update for Org2
    configtxgen -profile TwoOrgsChannel -outputAnchorPeersUpdate "${CHANNEL_ARTIFACTS_PATH}/Org2MSPanchors.tx" -channelID "${CHANNEL_NAME}" -asOrg Org2MSP
    echo "  - Generated Org2MSPanchors.tx"
    
    # Reset FABRIC_CFG_PATH to its default for CLI commands
    export FABRIC_CFG_PATH="${PROJECT_ROOT}/config"
}

function launch_network() {
    print_header "Launching Hyperledger Fabric network via Docker Compose"
    if [ ! -f "${DOCKER_COMPOSE_FILE}" ]; then
        echo "Error: Docker Compose file not found at ${DOCKER_COMPOSE_FILE}"
        echo "Please ensure 'docker-compose.yaml' exists in the 'infrastructure' directory."
        exit 1
    fi
    
    # Set the IMAGE_TAG for docker-compose (e.g., 2.4.7 or latest)
    # You might want to define this in an .env file or pass it directly
    # For now, let's assume a common tag.
    export IMAGE_TAG="2.4.7" # Or your preferred Fabric image tag
    
    # Ensure Docker volumes map correctly to the generated artifacts
    docker-compose -f "${DOCKER_COMPOSE_FILE}" up -d
    echo "Waiting for network components to start..."
    sleep 15 # Give services time to initialize, especially CAs and orderers
}

function set_org1_admin_cli_env() {
    export CORE_PEER_TLS_ENABLED=true
    export CORE_PEER_LOCALMSPID="Org1MSP"
    export CORE_PEER_TLS_ROOTCERT_FILE="${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt"
    export CORE_PEER_MSPCONFIGPATH="${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp"
    export CORE_PEER_ADDRESS=localhost:7051 # Peer0.Org1
}

function set_org2_admin_cli_env() {
    export CORE_PEER_TLS_ENABLED=true
    export CORE_PEER_LOCALMSPID="Org2MSP"
    export CORE_PEER_TLS_ROOTCERT_FILE="${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt"
    export CORE_PEER_MSPCONFIGPATH="${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org2.example.com/users/Admin@org2.example.com/msp"
    export CORE_PEER_ADDRESS=localhost:9051 # Peer0.Org2
}

function create_and_join_channel() {
    print_header "Creating channel '${CHANNEL_NAME}' and joining peers"
    
    # Create channel using channel participation API (Fabric 2.3+)
    echo "Creating channel ${CHANNEL_NAME}..."

    # First, create the genesis block for the channel using the application genesis profile
    export FABRIC_CFG_PATH="${FABRIC_CONFIG_PATH}"
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
    echo "  - Channel '${CHANNEL_NAME}' created and peers joined successfully."
}

function deploy_chaincode() {
    local chaincode_name=$1
    local chaincode_source_path="${PROJECT_ROOT}/fabric-chaincode/${chaincode_name}"
    local chaincode_label="${chaincode_name}_${CHAINCODE_VERSION}"
    
    print_header "Deploying chaincode '${chaincode_name}' from '${chaincode_source_path}'"
    
    if [ ! -d "${chaincode_source_path}" ]; then
        echo "Error: Chaincode source directory not found: ${chaincode_source_path}"
        echo "Please check chaincode structure."
        exit 1
    fi
    
    # Package chaincode
    print_header "Packaging chaincode '${chaincode_name}'"
    pushd "${chaincode_source_path}"
    GO111MODULE=on go mod vendor # Ensure Go modules are vendored for packaging
    popd
    
    peer lifecycle chaincode package "${TEMP_CHAINCODE_PATH}/${chaincode_name}.tar.gz" \
        --path "${chaincode_source_path}" --lang "${CHAINCODE_LANG}" --label "${chaincode_label}"
    echo "  - Chaincode packaged to ${TEMP_CHAINCODE_PATH}/${chaincode_name}.tar.gz"
    
    # --- Org1 Peer0 Operations ---
    set_org1_admin_cli_env
    export CORE_PEER_ADDRESS=localhost:7051
    
    # Install chaincode on peer0.org1
    print_header "Installing chaincode '${chaincode_name}' on peer0.org1.example.com"
    peer lifecycle chaincode install "${TEMP_CHAINCODE_PATH}/${chaincode_name}.tar.gz"
    PACKAGE_ID=$(peer lifecycle chaincode queryinstalled --output json | jq -r ".installed_chaincodes[] | select(.label == \"${chaincode_label}\") | .package_id")
    echo "  - Chaincode installed. Package ID: ${PACKAGE_ID}"
    
    # Approve chaincode for Org1
    print_header "Approving chaincode '${chaincode_name}' definition for Org1MSP"
    peer lifecycle chaincode approveformyorg -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com \
        --channelID "${CHANNEL_NAME}" --name "${chaincode_name}" --version "${CHAINCODE_VERSION}" \
        --package-id "${PACKAGE_ID}" --sequence "${CHAINCODE_SEQUENCE}" --tls \
        --cafile "${FABRIC_NETWORK_PATH}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/tls/ca.crt"
    echo "  - Chaincode approved by Org1MSP."
    sleep 3
    
    # --- Org2 Peer0 Operations ---
    set_org2_admin_cli_env
    export CORE_PEER_ADDRESS=localhost:9051
    
    # Install chaincode on peer0.org2
    print_header "Installing chaincode '${chaincode_name}' on peer0.org2.example.com"
    peer lifecycle chaincode install "${TEMP_CHAINCODE_PATH}/${chaincode_name}.tar.gz"
    
    # Approve chaincode for Org2
    print_header "Approving chaincode '${chaincode_name}' definition for Org2MSP"
    peer lifecycle chaincode approveformyorg -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com \
        --channelID "${CHANNEL_NAME}" --name "${chaincode_name}" --version "${CHAINCODE_VERSION}" \
        --package-id "${PACKAGE_ID}" --sequence "${CHAINCODE_SEQUENCE}" --tls \
        --cafile "${FABRIC_NETWORK_PATH}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/tls/ca.crt"
    echo "  - Chaincode approved by Org2MSP."
    sleep 3
    
    # --- Commit Chaincode (can be done by either org admin) ---
    set_org1_admin_cli_env # Using Org1 to commit
    print_header "Committing chaincode '${chaincode_name}' definition to the channel"
    peer lifecycle chaincode commit -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com \
        --channelID "${CHANNEL_NAME}" --name "${chaincode_name}" --version "${CHAINCODE_VERSION}" \
        --sequence "${CHAINCODE_SEQUENCE}" --tls \
        --cafile "${FABRIC_NETWORK_PATH}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/tls/ca.crt" \
        --peerAddresses localhost:7051 --tlsRootCertFiles "${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt" \
        --peerAddresses localhost:9051 --tlsRootCertFiles "${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt"
    echo "  - Chaincode '${chaincode_name}' definition committed to channel '${CHANNEL_NAME}'."
    sleep 7 # Give time for chaincode containers to start and be ready
    
    # Query committed chaincode to verify
    print_header "Verifying chaincode '${chaincode_name}' deployment (query committed definition)"
    peer lifecycle chaincode querycommitted --channelID "${CHANNEL_NAME}" --name "${chaincode_name}" --output json
    echo "  - Chaincode '${chaincode_name}' deployment verified."
}

function deploy_all_chaincodes() {
    print_header "Deploying chaincodes: ${CHAINCODES_TO_DEPLOY[*]}"
    
    for chaincode in "${CHAINCODES_TO_DEPLOY[@]}"; do
        echo ""
        echo ">>> Deploying chaincode: ${chaincode}"
        deploy_chaincode "${chaincode}"
        echo ">>> Chaincode '${chaincode}' deployment completed"
        echo ""
        
        # Increment sequence for next chaincode if deploying multiple
        if [[ ${#CHAINCODES_TO_DEPLOY[@]} -gt 1 ]]; then
            CHAINCODE_SEQUENCE=$((CHAINCODE_SEQUENCE + 1))
        fi
    done
}

function test_chaincode_deployment() {
    print_header "Testing deployed chaincodes"
    set_org1_admin_cli_env # Use Org1 Admin for interaction
    
    for chaincode in "${CHAINCODES_TO_DEPLOY[@]}"; do
        echo "  - Testing chaincode: ${chaincode}"
        
        # Test basic chaincode invocation (adapt based on your chaincode functions)
        case $chaincode in
            "compliance")
                echo "    Testing compliance chaincode..."
                # Add compliance-specific test calls here
                ;;
            "customer")
                echo "    Testing customer chaincode..."
                # Add customer-specific test calls here
                ;;
            "loan")
                echo "    Testing loan chaincode..."
                # Add loan-specific test calls here
                ;;
        esac
        
        # Generic test: query chaincode metadata
        peer lifecycle chaincode querycommitted --channelID "${CHANNEL_NAME}" --name "${chaincode}" --output json || echo "    Query failed for ${chaincode}"
        echo "    Test completed for ${chaincode}"
    done
}

# --- Main Execution Flow ---
function main() {
    print_header "STARTING HYPERLEDGER FABRIC NETWORK SETUP"
    echo "  Targeting Chaincodes: ${CHAINCODES_TO_DEPLOY[*]}"
    
    stop_and_remove_containers
    remove_artifacts
    create_dirs
    generate_crypto_material
    generate_configtx_artifacts
    launch_network
    create_and_join_channel
    deploy_all_chaincodes
    test_chaincode_deployment
    
    print_header "HYPERLEDGER FABRIC NETWORK SETUP COMPLETE!"
    echo "The network is now running and the following chaincodes have been deployed:"
    for chaincode in "${CHAINCODES_TO_DEPLOY[@]}"; do
        echo "  - ${chaincode}"
    done
    echo ""
    echo "You can interact with the network using the 'peer' CLI:"
    echo "  Set environment variables for Org1: source scripts/set-org1-env.sh"
    echo "  Set environment variables for Org2: source scripts/set-org2-env.sh"
    echo "To stop the network: docker-compose -f ${DOCKER_COMPOSE_FILE} down"
}

# Run the main function
main "$@"