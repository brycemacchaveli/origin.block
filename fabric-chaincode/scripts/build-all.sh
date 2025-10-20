#!/bin/bash

# Build script for all chaincodes
set -e

echo "Building all chaincodes..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to build a chaincode
build_chaincode() {
    local chaincode_name=$1
    local chaincode_path=$2
    
    echo -e "${YELLOW}Building ${chaincode_name} chaincode...${NC}"
    
    cd "${chaincode_path}"
    
    # Clean previous builds
    go clean
    
    # Download dependencies
    go mod tidy
    
    # Run tests
    echo -e "${YELLOW}Running tests for ${chaincode_name}...${NC}"
    if go test ./...; then
        echo -e "${GREEN}✓ Tests passed for ${chaincode_name}${NC}"
    else
        echo -e "${RED}✗ Tests failed for ${chaincode_name}${NC}"
        exit 1
    fi
    
    # Build the chaincode
    if go build -o bin/${chaincode_name} ./cmd/main.go; then
        echo -e "${GREEN}✓ Successfully built ${chaincode_name} chaincode${NC}"
    else
        echo -e "${RED}✗ Failed to build ${chaincode_name} chaincode${NC}"
        exit 1
    fi
    
    cd - > /dev/null
}

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHAINCODE_DIR="$(dirname "${SCRIPT_DIR}")"

# Build shared library first
echo -e "${YELLOW}Building shared library...${NC}"
cd "${CHAINCODE_DIR}/shared"
go mod tidy
if go test ./...; then
    echo -e "${GREEN}✓ Shared library tests passed${NC}"
else
    echo -e "${RED}✗ Shared library tests failed${NC}"
    exit 1
fi
cd - > /dev/null

# Build all chaincodes
build_chaincode "customer" "${CHAINCODE_DIR}/customer"
build_chaincode "loan" "${CHAINCODE_DIR}/loan"
build_chaincode "compliance" "${CHAINCODE_DIR}/compliance"

echo -e "${GREEN}✓ All chaincodes built successfully!${NC}"

# Create deployment package
echo -e "${YELLOW}Creating deployment packages...${NC}"
mkdir -p "${CHAINCODE_DIR}/dist"

for chaincode in customer loan compliance; do
    if [ -f "${CHAINCODE_DIR}/${chaincode}/bin/${chaincode}" ]; then
        tar -czf "${CHAINCODE_DIR}/dist/${chaincode}-chaincode.tar.gz" -C "${CHAINCODE_DIR}/${chaincode}" .
        echo -e "${GREEN}✓ Created deployment package for ${chaincode}${NC}"
    fi
done

echo -e "${GREEN}✓ Build and packaging complete!${NC}"