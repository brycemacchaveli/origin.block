# Infrastructure

Docker and deployment configurations for the blockchain financial platform.

## Structure

- `docker/`: Docker configurations for services
- `fabric-network/`: Hyperledger Fabric network configuration
- `scripts/`: Deployment and utility scripts

## Quick Start

1. Start the complete development environment:
   ```bash
   docker-compose up -d
   ```

2. Check service status:
   ```bash
   docker-compose ps
   ```

3. View logs:
   ```bash
   docker-compose logs -f [service-name]
   ```

4. Stop all services:
   ```bash
   docker-compose down
   ```