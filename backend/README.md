# Backend Services

Python/FastAPI-based application services for the blockchain financial platform.

## Structure

- `customer_mastery/`: Customer domain API service
- `loan_origination/`: Loan domain API service
- `compliance_reporting/`: Compliance domain API service
- `event_listener/`: Blockchain event processing service
- `shared/`: Shared utilities and libraries
- `tests/`: Test suites

## Development

1. Create and activate virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run development server:
   ```bash
   uvicorn main:app --reload
   ```

4. Run tests:
   ```bash
   pytest
   ```