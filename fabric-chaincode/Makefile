# Makefile for Blockchain Financial Platform Chaincodes

.PHONY: all build test clean lint fmt deps help

# Default target
all: deps fmt lint test build

# Build all chaincodes
build:
	@echo "Building all chaincodes..."
	@./scripts/build-all.sh

# Run tests for all modules
test:
	@echo "Running tests for all modules..."
	@cd shared && go test -v ./...
	@cd customer && go test -v ./...
	@cd loan && go test -v ./...
	@cd compliance && go test -v ./...

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	@rm -rf */bin/
	@rm -rf dist/
	@cd shared && go clean
	@cd customer && go clean
	@cd loan && go clean
	@cd compliance && go clean

# Lint all Go code
lint:
	@echo "Linting Go code..."
	@cd shared && go vet ./...
	@cd customer && go vet ./...
	@cd loan && go vet ./...
	@cd compliance && go vet ./...

# Format all Go code
fmt:
	@echo "Formatting Go code..."
	@cd shared && go fmt ./...
	@cd customer && go fmt ./...
	@cd loan && go fmt ./...
	@cd compliance && go fmt ./...

# Download and tidy dependencies
deps:
	@echo "Downloading and tidying dependencies..."
	@cd shared && go mod tidy
	@cd customer && go mod tidy
	@cd loan && go mod tidy
	@cd compliance && go mod tidy

# Run specific chaincode tests
test-shared:
	@cd shared && go test -v ./...

test-customer:
	@cd customer && go test -v ./...

test-loan:
	@cd loan && go test -v ./...

test-compliance:
	@cd compliance && go test -v ./...

# Build specific chaincodes
build-customer:
	@cd customer && go build -o bin/customer ./cmd/main.go

build-loan:
	@cd loan && go build -o bin/loan ./cmd/main.go

build-compliance:
	@cd compliance && go build -o bin/compliance ./cmd/main.go

# Development helpers
dev-setup: deps
	@echo "Setting up development environment..."
	@mkdir -p customer/bin loan/bin compliance/bin dist

# Package chaincodes for deployment
package: build
	@echo "Packaging chaincodes for deployment..."
	@mkdir -p dist
	@tar -czf dist/customer-chaincode.tar.gz -C customer .
	@tar -czf dist/loan-chaincode.tar.gz -C loan .
	@tar -czf dist/compliance-chaincode.tar.gz -C compliance .

# Help target
help:
	@echo "Available targets:"
	@echo "  all          - Run deps, fmt, lint, test, and build"
	@echo "  build        - Build all chaincodes"
	@echo "  test         - Run tests for all modules"
	@echo "  clean        - Clean build artifacts"
	@echo "  lint         - Lint all Go code"
	@echo "  fmt          - Format all Go code"
	@echo "  deps         - Download and tidy dependencies"
	@echo "  package      - Package chaincodes for deployment"
	@echo "  dev-setup    - Set up development environment"
	@echo ""
	@echo "Specific targets:"
	@echo "  test-shared     - Test shared library only"
	@echo "  test-customer   - Test customer chaincode only"
	@echo "  test-loan       - Test loan chaincode only"
	@echo "  test-compliance - Test compliance chaincode only"
	@echo "  build-customer  - Build customer chaincode only"
	@echo "  build-loan      - Build loan chaincode only"
	@echo "  build-compliance- Build compliance chaincode only"