#!/bin/bash

# Test script for network setup without backend services
# This script tests only the Fabric network components

# Parse command line arguments
CHAINCODE_NAME="${1:-compliance}"

# Determine script's absolute directory to derive other paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "${SCRIPT_DIR}")")"

# Export Fabric binaries path
export PATH="${PROJECT_ROOT}/bin:$PATH"

echo "==============================================="
echo "  TESTING FABRIC NETWORK SETUP"
echo "==============================================="
echo "  Testing with chaincode: ${CHAINCODE_NAME}"

# Create a temporary docker-compose file without backend
TEMP_COMPOSE_FILE="${PROJECT_ROOT}/infrastructure/docker-compose-network-only.yaml"

cat > "${TEMP_COMPOSE_FILE}" << 'EOF'
services:
  # Hyperledger Fabric CA
  ca.org1.example.com:
    image: hyperledger/fabric-ca:latest
    container_name: ca.org1.example.com
    environment:
      - FABRIC_CA_HOME=/etc/hyperledger/fabric-ca-server
      - FABRIC_CA_SERVER_CA_NAME=ca.org1.example.com
      - FABRIC_CA_SERVER_TLS_ENABLED=true
      - FABRIC_CA_SERVER_PORT=7054
    ports:
      - "7054:7054"
    command: sh -c 'fabric-ca-server start -b admin:adminpw -d'
    volumes:
      - ./fabric-network/organizations/peerOrganizations/org1.example.com/ca/:/etc/hyperledger/fabric-ca-server
    networks:
      - blockchain-network

  # Hyperledger Fabric Orderer
  orderer.example.com:
    image: hyperledger/fabric-orderer:latest
    container_name: orderer.example.com
    environment:
      - FABRIC_LOGGING_SPEC=INFO
      - ORDERER_GENERAL_LISTENADDRESS=0.0.0.0
      - ORDERER_GENERAL_LISTENPORT=7050
      - ORDERER_GENERAL_LOCALMSPID=OrdererMSP
      - ORDERER_GENERAL_LOCALMSPDIR=/var/hyperledger/orderer/msp
      - ORDERER_GENERAL_TLS_ENABLED=true
      - ORDERER_GENERAL_TLS_PRIVATEKEY=/var/hyperledger/orderer/tls/server.key
      - ORDERER_GENERAL_TLS_CERTIFICATE=/var/hyperledger/orderer/tls/server.crt
      - ORDERER_GENERAL_TLS_ROOTCAS=[/var/hyperledger/orderer/tls/ca.crt]
      - ORDERER_GENERAL_CLUSTER_CLIENTCERTIFICATE=/var/hyperledger/orderer/tls/server.crt
      - ORDERER_GENERAL_CLUSTER_CLIENTPRIVATEKEY=/var/hyperledger/orderer/tls/server.key
      - ORDERER_GENERAL_CLUSTER_ROOTCAS=[/var/hyperledger/orderer/tls/ca.crt]
      - ORDERER_GENERAL_BOOTSTRAPMETHOD=none
      - ORDERER_CHANNELPARTICIPATION_ENABLED=true
      - ORDERER_ADMIN_TLS_ENABLED=true
      - ORDERER_ADMIN_TLS_CERTIFICATE=/var/hyperledger/orderer/tls/server.crt
      - ORDERER_ADMIN_TLS_PRIVATEKEY=/var/hyperledger/orderer/tls/server.key
      - ORDERER_ADMIN_TLS_ROOTCAS=[/var/hyperledger/orderer/tls/ca.crt]
      - ORDERER_ADMIN_TLS_CLIENTROOTCAS=[/var/hyperledger/orderer/tls/ca.crt]
      - ORDERER_ADMIN_LISTENADDRESS=0.0.0.0:7053
    working_dir: /opt/gopath/src/github.com/hyperledger/fabric
    command: orderer
    volumes:
      - ./fabric-network/system-genesis-block/genesis.block:/var/hyperledger/orderer/orderer.genesis.block
      - ./fabric-network/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp:/var/hyperledger/orderer/msp
      - ./fabric-network/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/tls/:/var/hyperledger/orderer/tls
      - orderer.example.com:/var/hyperledger/production/orderer
    ports:
      - "7050:7050"
      - "7053:7053"
    networks:
      - blockchain-network

  # Hyperledger Fabric Peer Org1
  peer0.org1.example.com:
    image: hyperledger/fabric-peer:latest
    container_name: peer0.org1.example.com
    environment:
      - CORE_VM_ENDPOINT=unix:///host/var/run/docker.sock
      - CORE_VM_DOCKER_HOSTCONFIG_NETWORKMODE=infrastructure_blockchain-network
      - FABRIC_LOGGING_SPEC=INFO
      - CORE_PEER_TLS_ENABLED=true
      - CORE_PEER_PROFILE_ENABLED=false
      - CORE_PEER_TLS_CERT_FILE=/etc/hyperledger/fabric/tls/server.crt
      - CORE_PEER_TLS_KEY_FILE=/etc/hyperledger/fabric/tls/server.key
      - CORE_PEER_TLS_ROOTCERT_FILE=/etc/hyperledger/fabric/tls/ca.crt
      - CORE_PEER_ID=peer0.org1.example.com
      - CORE_PEER_ADDRESS=peer0.org1.example.com:7051
      - CORE_PEER_LISTENADDRESS=0.0.0.0:7051
      - CORE_PEER_CHAINCODEADDRESS=peer0.org1.example.com:7052
      - CORE_PEER_CHAINCODELISTENADDRESS=0.0.0.0:7052
      - CORE_PEER_GOSSIP_BOOTSTRAP=peer0.org1.example.com:7051
      - CORE_PEER_GOSSIP_EXTERNALENDPOINT=peer0.org1.example.com:7051
      - CORE_PEER_LOCALMSPID=Org1MSP
      - CORE_OPERATIONS_LISTENADDRESS=peer0.org1.example.com:9444
      - CORE_METRICS_PROVIDER=prometheus
      - CHAINCODE_AS_A_SERVICE_BUILDER_CONFIG={"peername":"peer0org1"}
      - CORE_CHAINCODE_EXECUTETIMEOUT=300s
    volumes:
      - /var/run/docker.sock:/host/var/run/docker.sock
      - ./fabric-network/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/msp:/etc/hyperledger/fabric/msp
      - ./fabric-network/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls:/etc/hyperledger/fabric/tls
      - peer0.org1.example.com:/var/hyperledger/production
    working_dir: /opt/gopath/src/github.com/hyperledger/fabric/peer
    command: peer node start
    ports:
      - "7051:7051"
      - "9444:9444"
    networks:
      - blockchain-network

  # Hyperledger Fabric Peer Org2
  peer0.org2.example.com:
    image: hyperledger/fabric-peer:latest
    container_name: peer0.org2.example.com
    environment:
      - CORE_VM_ENDPOINT=unix:///host/var/run/docker.sock
      - CORE_VM_DOCKER_HOSTCONFIG_NETWORKMODE=infrastructure_blockchain-network
      - FABRIC_LOGGING_SPEC=INFO
      - CORE_PEER_TLS_ENABLED=true
      - CORE_PEER_PROFILE_ENABLED=false
      - CORE_PEER_TLS_CERT_FILE=/etc/hyperledger/fabric/tls/server.crt
      - CORE_PEER_TLS_KEY_FILE=/etc/hyperledger/fabric/tls/server.key
      - CORE_PEER_TLS_ROOTCERT_FILE=/etc/hyperledger/fabric/tls/ca.crt
      - CORE_PEER_ID=peer0.org2.example.com
      - CORE_PEER_ADDRESS=peer0.org2.example.com:9051
      - CORE_PEER_LISTENADDRESS=0.0.0.0:9051
      - CORE_PEER_CHAINCODEADDRESS=peer0.org2.example.com:9052
      - CORE_PEER_CHAINCODELISTENADDRESS=0.0.0.0:9052
      - CORE_PEER_GOSSIP_BOOTSTRAP=peer0.org2.example.com:9051
      - CORE_PEER_GOSSIP_EXTERNALENDPOINT=peer0.org2.example.com:9051
      - CORE_PEER_LOCALMSPID=Org2MSP
      - CORE_OPERATIONS_LISTENADDRESS=peer0.org2.example.com:9445
      - CORE_METRICS_PROVIDER=prometheus
      - CHAINCODE_AS_A_SERVICE_BUILDER_CONFIG={"peername":"peer0org2"}
      - CORE_CHAINCODE_EXECUTETIMEOUT=300s
    volumes:
      - /var/run/docker.sock:/host/var/run/docker.sock
      - ./fabric-network/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/msp:/etc/hyperledger/fabric/msp
      - ./fabric-network/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls:/etc/hyperledger/fabric/tls
      - peer0.org2.example.com:/var/hyperledger/production
    working_dir: /opt/gopath/src/github.com/hyperledger/fabric/peer
    command: peer node start
    ports:
      - "9051:9051"
      - "9445:9445"
    networks:
      - blockchain-network

volumes:
  orderer.example.com:
  peer0.org1.example.com:
  peer0.org2.example.com:

networks:
  blockchain-network:
    driver: bridge
EOF

# Update the main setup script to use the network-only compose file
sed -i.bak "s|DOCKER_COMPOSE_FILE=.*|DOCKER_COMPOSE_FILE=\"${TEMP_COMPOSE_FILE}\"|" "${SCRIPT_DIR}/setup-network.sh"

# Run the setup script
"${SCRIPT_DIR}/setup-network.sh" --chaincode "${CHAINCODE_NAME}"

# Restore the original setup script
mv "${SCRIPT_DIR}/setup-network.sh.bak" "${SCRIPT_DIR}/setup-network.sh"

# Clean up temporary file
rm -f "${TEMP_COMPOSE_FILE}"

echo "==============================================="
echo "  NETWORK TEST COMPLETED"
echo "==============================================="