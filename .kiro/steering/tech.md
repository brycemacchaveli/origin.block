# Technology Stack

## Core Technologies

### Blockchain Layer
- **Hyperledger Fabric**: Permissioned blockchain network
- **Go 1.21**: Chaincode development language
- **Docker**: Container orchestration for Fabric network

### Backend Services
- **Python 3.x**: Primary backend language
- **FastAPI**: REST API framework with automatic OpenAPI documentation
- **SQLAlchemy**: ORM for database operations
- **PostgreSQL**: Primary operational database
- **Pydantic**: Data validation and serialization

### Infrastructure
- **Docker Compose**: Local development environment
- **Google Cloud Platform**: Production deployment target
- **Cloud Run**: Serverless API hosting
- **Cloud SQL**: Managed PostgreSQL
- **BigQuery**: Data warehousing and analytics

## Development Tools

### Code Quality
- **Black**: Python code formatting
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking
- **pytest**: Testing framework

### Testing
- **pytest-asyncio**: Async testing support
- **pytest-mock**: Mocking utilities
- **httpx**: HTTP client for API testing
- **testify**: Go testing assertions

## Common Commands

### Backend Development
```bash
# Setup virtual environment
cd backend
python -m venv venv
source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt

# Run development server
uvicorn main:app --reload

# Run tests
pytest -v

# Code formatting
black .
isort .
flake8 .
```

### Chaincode Development
```bash
# Install dependencies
cd fabric-chaincode
go mod tidy

# Run tests
go test ./...

# Test specific package
go test -v ./shared

# Deploy chaincode
./scripts/deploy-chaincode.sh
```

### Infrastructure
```bash
# Start development environment
docker-compose up -d

# View service status
docker-compose ps

# View logs
docker-compose logs -f [service-name]

# Stop environment
docker-compose down
```

### Database Operations
```bash
# Run migrations (when implemented)
cd backend
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```

## Architecture Patterns

- **Domain-Driven Design (DDD)**: Clear separation of business domains
- **API-First**: OpenAPI specifications drive development
- **Event-Driven**: Blockchain events trigger database synchronization
- **Microservices**: Separate services for each domain
- **Clean Architecture**: Dependency inversion and separation of concerns