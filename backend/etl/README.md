# ETL (Extract, Transform, Load) Package

This package provides dimensional model transformers for converting operational data from the blockchain financial platform into analytical data warehouse structures optimized for BigQuery.

## Overview

The ETL package implements a comprehensive data transformation pipeline that:

- Extracts data from the operational PostgreSQL database
- Transforms it into dimensional models (facts and dimensions)
- Implements Slowly Changing Dimension (SCD) Type 2 logic
- Provides data validation and error handling
- Supports incremental and full data loads
- Maintains complete audit trails and batch tracking

## Architecture

```
etl/
├── __init__.py
├── README.md
├── models.py                    # Data models for dimensional structures
├── transformers/
│   ├── __init__.py
│   ├── base_transformer.py     # Abstract base class for all transformers
│   ├── customer_transformer.py # Customer dimension transformer
│   ├── loan_events_transformer.py      # Loan events fact transformer
│   └── compliance_events_transformer.py # Compliance events fact transformer
└── tests/                      # Comprehensive unit tests
```

## Data Models

### Dimensional Models

#### Fact Tables
- **FactLoanApplicationEvents**: Loan processing events with duration measures
- **FactComplianceEvents**: Compliance events with violation tracking

#### Dimension Tables
- **DimCustomer**: Customer master data with SCD Type 2
- **DimActor**: System actors and users with SCD Type 2
- **DimLoanApplication**: Loan application details with SCD Type 2
- **DimDate**: Date dimension for time-based analysis
- **DimComplianceRule**: Compliance rules with versioning

### SCD Type 2 Implementation

All dimension tables implement Slowly Changing Dimension Type 2 logic:

- **Effective Date**: When the record became active
- **Expiration Date**: When the record was superseded (NULL for current)
- **Is Current**: Boolean flag for current record
- **Version**: Incremental version number

## Transformers

### BaseTransformer

Abstract base class providing common functionality:

- Batch tracking and audit trails
- SCD Type 2 implementation
- Data validation framework
- Error handling and logging
- Surrogate key generation
- Date/time utilities

### CustomerTransformer

Transforms customer operational data into `DimCustomer`:

```python
from etl.transformers.customer_transformer import CustomerTransformer
from shared.database import DatabaseManager

db_manager = DatabaseManager()
transformer = CustomerTransformer(db_manager)

# Process incremental changes
batch_result = transformer.process(incremental=True, since_date=yesterday)
```

**Features:**
- SCD Type 2 for tracking customer data changes
- Consent preferences JSON handling
- KYC/AML status validation
- Actor attribution tracking

### LoanEventsTransformer

Transforms loan application history into `FactLoanApplicationEvents`:

```python
from etl.transformers.loan_events_transformer import LoanEventsTransformer

transformer = LoanEventsTransformer(db_manager)
batch_result = transformer.process()

# Get processing metrics for specific loan
metrics = transformer.get_processing_metrics('LOAN_001')
```

**Features:**
- Processing duration calculations between status changes
- Event type standardization
- Stage-by-stage workflow analysis
- Performance metrics generation

### ComplianceEventsTransformer

Transforms compliance events into `FactComplianceEvents`:

```python
from etl.transformers.compliance_events_transformer import ComplianceEventsTransformer

transformer = ComplianceEventsTransformer(db_manager)

# Get compliance metrics
metrics = transformer.get_compliance_metrics(date_range_days=30)
trends = transformer.get_violation_trends(days=90)
```

**Features:**
- Violation detection and classification
- Resolution time tracking
- Compliance metrics calculation
- Trend analysis for violations

## Usage Examples

### Basic ETL Process

```python
from etl.transformers.customer_transformer import CustomerTransformer
from shared.database import DatabaseManager

# Initialize
db_manager = DatabaseManager()
transformer = CustomerTransformer(db_manager, batch_id="daily_customer_etl")

# Execute ETL process
batch_result = transformer.process(incremental=True)

print(f"Status: {batch_result.status}")
print(f"Records Processed: {batch_result.records_processed}")
print(f"Records Inserted: {batch_result.records_inserted}")
```

### SCD Type 2 Processing

```python
# Get existing dimension records (from BigQuery)
existing_records = get_current_customer_records()

# Process new/changed records with SCD Type 2
new_records = transformer.transform(source_data)
scd_records = transformer.implement_scd_type2(
    existing_records=existing_records,
    new_records=new_records,
    business_key_field='customer_id',
    compare_fields=['first_name', 'last_name', 'address', 'kyc_status']
)

# Load to BigQuery
success = transformer.load(scd_records)
```

### Processing Metrics

```python
from etl.transformers.loan_events_transformer import LoanEventsTransformer

transformer = LoanEventsTransformer(db_manager)

# Get detailed processing metrics for a loan
metrics = transformer.get_processing_metrics('LOAN_001')

print(f"Total Processing Time: {metrics['total_processing_time_hours']} hours")
print(f"Average Stage Duration: {metrics['average_stage_duration_hours']} hours")

for stage in metrics['stages']:
    print(f"{stage['from_status']} → {stage['to_status']}: {stage['duration_hours']} hours")
```

### Compliance Analysis

```python
from etl.transformers.compliance_events_transformer import ComplianceEventsTransformer

transformer = ComplianceEventsTransformer(db_manager)

# Get compliance metrics
metrics = transformer.get_compliance_metrics(date_range_days=30)
print(f"Violation Rate: {metrics['violation_rate']}%")
print(f"Average Resolution Time: {metrics['avg_resolution_time_hours']} hours")

# Get violation trends
trends = transformer.get_violation_trends(days=90)
print(f"Trend Direction: {trends['trend_direction']}")
```

## Data Validation

All transformers implement comprehensive data validation:

### Customer Validation
- Required fields: customer_id, first_name, last_name, kyc_status, aml_status
- Valid KYC statuses: PENDING, VERIFIED, FAILED
- Valid AML statuses: PENDING, CLEAR, FLAGGED

### Loan Events Validation
- Required fields: loan_application_id, customer_id, actor_id, change_type, timestamp, requested_amount
- Positive requested amounts
- Valid timestamp formats
- Proper amount formatting

### Compliance Events Validation
- Required fields: event_id, event_type, affected_entity_type, affected_entity_id, severity, description, actor_id, timestamp
- Valid severity levels: INFO, WARNING, ERROR, CRITICAL
- Valid entity types: CUSTOMER, LOAN_APPLICATION, ACTOR, TRANSACTION
- Proper timestamp formats

## Error Handling

The ETL framework provides robust error handling:

```python
# Batch-level error tracking
batch_result = transformer.process()
if batch_result.status == "FAILED":
    print(f"Errors: {batch_result.error_message}")

# Record-level error tracking
print(f"Records Failed: {transformer.records_failed}")
for error in transformer.errors:
    print(f"Error: {error}")
```

## Batch Tracking

Every ETL execution is tracked with comprehensive metadata:

```python
@dataclass
class ETLBatch:
    batch_id: str
    batch_type: str  # FULL, INCREMENTAL
    start_time: datetime
    end_time: Optional[datetime]
    status: str  # RUNNING, SUCCESS, FAILED
    records_processed: int
    records_inserted: int
    records_updated: int
    records_failed: int
    error_message: Optional[str]
    source_system: str = "blockchain_platform"
```

## Testing

Comprehensive unit tests are provided for all transformers:

```bash
# Run all ETL tests
python -m pytest tests/etl/ -v

# Run specific transformer tests
python -m pytest tests/etl/test_customer_transformer.py -v
python -m pytest tests/etl/test_loan_events_transformer.py -v
python -m pytest tests/etl/test_compliance_events_transformer.py -v
```

## Configuration

### Database Connection
Transformers use the shared database manager:

```python
from shared.database import DatabaseManager

# Uses DATABASE_URL from environment or config
db_manager = DatabaseManager()
```

### BigQuery Integration
For production deployment, implement BigQuery loading in the `load()` methods:

```python
from google.cloud import bigquery

def load(self, transformed_data: List[DimCustomer]) -> bool:
    client = bigquery.Client()
    table_id = "project.dataset.dim_customer"
    
    # Convert to BigQuery format and load
    job = client.load_table_from_json(transformed_data, table_id)
    return job.state == "DONE"
```

## Performance Considerations

### Incremental Processing
Always use incremental processing for large datasets:

```python
# Process only recent changes
since_date = datetime.now() - timedelta(days=1)
batch_result = transformer.process(incremental=True, since_date=since_date)
```

### Batch Size Management
For large datasets, implement batch size limits:

```python
# Process in chunks
batch_size = 1000
for offset in range(0, total_records, batch_size):
    batch_data = extract_batch(offset, batch_size)
    transformer.transform(batch_data)
```

### Memory Management
Use generators for large datasets to avoid memory issues:

```python
def extract_large_dataset(self):
    # Yield records in batches instead of loading all at once
    for batch in self.get_batches():
        yield batch
```

## Monitoring and Alerting

### Logging
All transformers use structured logging:

```python
import structlog
logger = structlog.get_logger(__name__)

logger.info("ETL process started", 
           transformer=self.__class__.__name__, 
           batch_id=self.batch_id)
```

### Metrics
Key metrics to monitor:

- **Processing Time**: Duration of ETL batches
- **Record Counts**: Processed, inserted, updated, failed
- **Error Rates**: Percentage of failed records
- **Data Quality**: Validation failure rates
- **SCD Performance**: Time to process dimension changes

### Alerts
Set up alerts for:

- ETL batch failures
- High error rates (>5%)
- Processing time anomalies
- Data quality issues
- Missing incremental runs

## Best Practices

1. **Always use incremental processing** for production workloads
2. **Implement proper error handling** and retry logic
3. **Monitor data quality** with validation rules
4. **Use SCD Type 2** for tracking historical changes
5. **Maintain audit trails** with batch tracking
6. **Test thoroughly** with unit and integration tests
7. **Document data lineage** for compliance
8. **Implement data retention** policies for old versions

## Future Enhancements

- **Real-time streaming ETL** with Apache Kafka
- **Data quality scoring** and automated remediation
- **Machine learning integration** for anomaly detection
- **Advanced SCD types** (Type 3, Type 6)
- **Cross-domain data lineage** tracking
- **Automated schema evolution** handling