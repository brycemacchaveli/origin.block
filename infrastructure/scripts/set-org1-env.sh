#!/bin/bash

# Set environment variables for Org1 Admin CLI operations
# Source this file: source infrastructure/scripts/set-org1-env.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "${SCRIPT_DIR}")")"
FABRIC_NETWORK_PATH="${PROJECT_ROOT}/infrastructure/fabric-network"

export CORE_PEER_TLS_ENABLED=true
export CORE_PEER_LOCALMSPID="Org1MSP"
export CORE_PEER_TLS_ROOTCERT_FILE="${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt"
export CORE_PEER_MSPCONFIGPATH="${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp"
export CORE_PEER_ADDRESS=localhost:7051

echo "Environment set for Org1 Admin CLI operations"
echo "CORE_PEER_LOCALMSPID: ${CORE_PEER_LOCALMSPID}"
echo "CORE_PEER_ADDRESS: ${CORE_PEER_ADDRESS}"