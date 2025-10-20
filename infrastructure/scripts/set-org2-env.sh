#!/bin/bash

# Set environment variables for Org2 Admin CLI operations
# Source this file: source infrastructure/scripts/set-org2-env.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "${SCRIPT_DIR}")")"
FABRIC_NETWORK_PATH="${PROJECT_ROOT}/infrastructure/fabric-network"

export CORE_PEER_TLS_ENABLED=true
export CORE_PEER_LOCALMSPID="Org2MSP"
export CORE_PEER_TLS_ROOTCERT_FILE="${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt"
export CORE_PEER_MSPCONFIGPATH="${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org2.example.com/users/Admin@org2.example.com/msp"
export CORE_PEER_ADDRESS=localhost:9051

echo "Environment set for Org2 Admin CLI operations"
echo "CORE_PEER_LOCALMSPID: ${CORE_PEER_LOCALMSPID}"
echo "CORE_PEER_ADDRESS: ${CORE_PEER_ADDRESS}"