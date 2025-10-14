#!/bin/bash

# Test deployed chaincodes with domain-specific operations
# Usage: ./test-chaincode.sh [chaincode_name]

CHANNEL_NAME="mychannel"
CHAINCODE_NAME="${1:-compliance}"

# Determine script's absolute directory to derive other paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "${SCRIPT_DIR}")")"
FABRIC_NETWORK_PATH="${PROJECT_ROOT}/infrastructure/fabric-network"

function set_org1_admin_cli_env() {
    export CORE_PEER_TLS_ENABLED=true
    export CORE_PEER_LOCALMSPID="Org1MSP"
    export CORE_PEER_TLS_ROOTCERT_FILE="${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt"
    export CORE_PEER_MSPCONFIGPATH="${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp"
    export CORE_PEER_ADDRESS=localhost:7051
}

function test_compliance_chaincode() {
    echo "Testing Compliance Chaincode..."
    
    # Test compliance rule creation
    echo "  - Creating compliance rule"
    peer chaincode invoke -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com \
        --tls --cafile "${FABRIC_NETWORK_PATH}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/tls/ca.crt" \
        -C "${CHANNEL_NAME}" -n "${CHAINCODE_NAME}" \
        --peerAddresses localhost:7051 --tlsRootCertFiles "${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt" \
        --peerAddresses localhost:9051 --tlsRootCertFiles "${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt" \
        -c '{"function":"CreateComplianceRule","Args":["RULE001", "KYC_VERIFICATION", "All customers must complete KYC verification", "ACTIVE"]}' || echo "  (CreateComplianceRule might not be available)"
    
    sleep 3
    
    # Query compliance rule
    echo "  - Querying compliance rule"
    peer chaincode query -C "${CHANNEL_NAME}" -n "${CHAINCODE_NAME}" -c '{"function":"GetComplianceRule","Args":["RULE001"]}' || echo "  (GetComplianceRule might not be available)"
}

function test_customer_chaincode() {
    echo "Testing Customer Chaincode..."
    
    # Test customer creation
    echo "  - Creating customer"
    peer chaincode invoke -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com \
        --tls --cafile "${FABRIC_NETWORK_PATH}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/tls/ca.crt" \
        -C "${CHANNEL_NAME}" -n "${CHAINCODE_NAME}" \
        --peerAddresses localhost:7051 --tlsRootCertFiles "${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt" \
        --peerAddresses localhost:9051 --tlsRootCertFiles "${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt" \
        -c '{"function":"CreateCustomer","Args":["CUST001", "John Doe", "john.doe@example.com", "ACTIVE"]}' || echo "  (CreateCustomer might not be available)"
    
    sleep 3
    
    # Query customer
    echo "  - Querying customer"
    peer chaincode query -C "${CHANNEL_NAME}" -n "${CHAINCODE_NAME}" -c '{"function":"GetCustomer","Args":["CUST001"]}' || echo "  (GetCustomer might not be available)"
}

function test_loan_chaincode() {
    echo "Testing Loan Chaincode..."
    
    # Test loan application creation
    echo "  - Creating loan application"
    peer chaincode invoke -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com \
        --tls --cafile "${FABRIC_NETWORK_PATH}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/tls/ca.crt" \
        -C "${CHANNEL_NAME}" -n "${CHAINCODE_NAME}" \
        --peerAddresses localhost:7051 --tlsRootCertFiles "${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt" \
        --peerAddresses localhost:9051 --tlsRootCertFiles "${FABRIC_NETWORK_PATH}/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt" \
        -c '{"function":"CreateLoanApplication","Args":["LOAN001", "CUST001", "50000", "PERSONAL", "SUBMITTED"]}' || echo "  (CreateLoanApplication might not be available)"
    
    sleep 3
    
    # Query loan application
    echo "  - Querying loan application"
    peer chaincode query -C "${CHANNEL_NAME}" -n "${CHAINCODE_NAME}" -c '{"function":"GetLoanApplication","Args":["LOAN001"]}' || echo "  (GetLoanApplication might not be available)"
}

function main() {
    echo "==============================================="
    echo "  Testing Chaincode: ${CHAINCODE_NAME}"
    echo "==============================================="
    
    # Set environment for Org1 Admin CLI
    set_org1_admin_cli_env
    
    case $CHAINCODE_NAME in
        "compliance")
            test_compliance_chaincode
            ;;
        "customer")
            test_customer_chaincode
            ;;
        "loan")
            test_loan_chaincode
            ;;
        *)
            echo "Unknown chaincode: ${CHAINCODE_NAME}"
            echo "Available chaincodes: compliance, customer, loan"
            exit 1
            ;;
    esac
    
    echo "==============================================="
    echo "  Chaincode testing completed"
    echo "==============================================="
}

# Run the main function
main "$@"