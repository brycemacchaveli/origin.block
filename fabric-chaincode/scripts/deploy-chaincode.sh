#!/bin/bash

# Deploy chaincode script
# This is a placeholder for chaincode deployment

echo "Deploying chaincode..."

# Set environment variables
export FABRIC_CFG_PATH=${PWD}/infrastructure/fabric-network/config/
export CORE_PEER_TLS_ENABLED=true
export CORE_PEER_LOCALMSPID="Org1MSP"
export CORE_PEER_TLS_ROOTCERT_FILE=${PWD}/infrastructure/fabric-network/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt
export CORE_PEER_MSPCONFIGPATH=${PWD}/infrastructure/fabric-network/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp
export CORE_PEER_ADDRESS=localhost:7051

echo "Environment configured"

# Package chaincode
echo "Packaging customer chaincode..."
peer lifecycle chaincode package customer.tar.gz --path ./customer --lang golang --label customer_1.0

echo "Packaging loan chaincode..."
peer lifecycle chaincode package loan.tar.gz --path ./loan --lang golang --label loan_1.0

echo "Packaging compliance chaincode..."
peer lifecycle chaincode package compliance.tar.gz --path ./compliance --lang golang --label compliance_1.0

echo "Chaincode packaging completed"
echo "Note: This is a basic deployment script. Full deployment requires a running Fabric network."