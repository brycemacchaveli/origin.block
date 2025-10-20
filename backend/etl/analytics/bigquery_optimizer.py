"""
BigQuery optimization strategies and table management.

This module provides optimization strategies for BigQuery tables including
partitioning, clustering, and materialized views for analytical workloads.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json

import structlog

logger = structlog.get_logger(__name__)


class PartitionType(Enum):
    """BigQuery partition types."""
    TIME_UNIT_COLUMN = "TIME_UNIT_COLUMN"
    INGESTION_TIME = "INGESTION_TIME"
    INTEGER_RANGE = "INTEGER_RANGE"


class TimeUnit(Enum):
    """Time partitioning units."""
    HOUR = "HOUR"
    DAY = "DAY"
    MONTH = "MONTH"
    YEAR = "YEAR"


@dataclass
class PartitionConfig:
    """BigQuery partition configuration."""
    partition_type: PartitionType
    field: Optional[str] = None
    time_unit: Optional[TimeUnit] = None
    expiration_days: Optional[int] = None
    require_partition_filter: bool = True


@dataclass
class ClusterConfig:
    """BigQuery clustering configuration."""
    fields: List[str]
    max_fields: int = 4  # BigQuery limit


@dataclass
class TableOptimization:
    """Table optimization configuration."""
    table_name: str
    partition_config: Optional[PartitionConfig] = None
    cluster_config: Optional[ClusterConfig] = None
    description: str = ""


class BigQueryOptimizer:
    """
    BigQuery table optimization manager.
    
    Provides strategies for partitioning, clustering, and materialized views
    to optimize analytical query performance.
    """
    
    def __init__(self, project_id: str, dataset_id: str):
        """Initialize BigQuery optimizer."""
        self.project_id = project_id
        self.dataset_id = dataset_id
        
        # Define optimization strategies for each table
        self.table_optimizations = self._define_table_optimizations()
    
    def _define_table_optimizations(self) -> Dict[str, TableOptimization]:
        """Define optimization strategies for all tables."""
        return {
            # Fact tables - partition by date, cluster by frequently queried fields
            'fact_loan_application_events': TableOptimization(
                table_name='fact_loan_application_events',
                partition_config=PartitionConfig(
                    partition_type=PartitionType.TIME_UNIT_COLUMN,
                    field='event_timestamp',
                    time_unit=TimeUnit.DAY,
                    expiration_days=2555,  # ~7 years retention
                    require_partition_filter=True
                ),
                cluster_config=ClusterConfig(
                    fields=['loan_application_id', 'customer_id', 'event_type', 'actor_id']
                ),
                description="Loan application events partitioned by event date, clustered by key identifiers"
            ),
            
            'fact_compliance_events': TableOptimization(
                table_name='fact_compliance_events',
                partition_config=PartitionConfig(
                    partition_type=PartitionType.TIME_UNIT_COLUMN,
                    field='event_timestamp',
                    time_unit=TimeUnit.DAY,
                    expiration_days=2555,  # ~7 years retention
                    require_partition_filter=True
                ),
                cluster_config=ClusterConfig(
                    fields=['affected_entity_id', 'event_type', 'severity', 'actor_id']
                ),
                description="Compliance events partitioned by event date, clustered by entity and severity"
            ),
            
            # Dimension tables - cluster by business keys, no partitioning for SCD
            'dim_customer': TableOptimization(
                table_name='dim_customer',
                cluster_config=ClusterConfig(
                    fields=['customer_id', 'is_current', 'effective_date']
                ),
                description="Customer dimension clustered by customer ID and SCD fields"
            ),
            
            'dim_loan_application': TableOptimization(
                table_name='dim_loan_application',
                cluster_config=ClusterConfig(
                    fields=['loan_application_id', 'customer_key', 'is_current']
                ),
                description="Loan application dimension clustered by application ID and customer"
            ),
            
            'dim_actor': TableOptimization(
                table_name='dim_actor',
                cluster_config=ClusterConfig(
                    fields=['actor_id', 'actor_type', 'is_current']
                ),
                description="Actor dimension clustered by actor ID and type"
            ),
            
            'dim_compliance_rule': TableOptimization(
                table_name='dim_compliance_rule',
                cluster_config=ClusterConfig(
                    fields=['rule_id', 'applies_to_domain', 'is_current']
                ),
                description="Compliance rule dimension clustered by rule ID and domain"
            ),
            
            # Date dimension - partition by date for time-based queries
            'dim_date': TableOptimization(
                table_name='dim_date',
                partition_config=PartitionConfig(
                    partition_type=PartitionType.TIME_UNIT_COLUMN,
                    field='full_date',
                    time_unit=TimeUnit.MONTH,
                    require_partition_filter=False
                ),
                cluster_config=ClusterConfig(
                    fields=['year', 'quarter', 'month']
                ),
                description="Date dimension partitioned by month, clustered by time periods"
            )
        }
    
    def get_create_table_ddl(self, table_name: str) -> str:
        """Generate CREATE TABLE DDL with optimization settings."""
        if table_name not in self.table_optimizations:
            raise ValueError(f"No optimization defined for table: {table_name}")
        
        optimization = self.table_optimizations[table_name]
        
        # Get table schema based on table name
        schema = self._get_table_schema(table_name)
        
        # Build DDL
        ddl_parts = [
            f"CREATE TABLE `{self.project_id}.{self.dataset_id}.{table_name}` (",
            self._format_schema_fields(schema),
            ")"
        ]
        
        # Add partitioning
        if optimization.partition_config:
            partition_clause = self._build_partition_clause(optimization.partition_config)
            ddl_parts.append(partition_clause)
        
        # Add clustering
        if optimization.cluster_config:
            cluster_clause = self._build_cluster_clause(optimization.cluster_config)
            ddl_parts.append(cluster_clause)
        
        # Add options
        options = self._build_table_options(optimization)
        if options:
            ddl_parts.append(f"OPTIONS({options})")
        
        return "\n".join(ddl_parts)
    
    def _get_table_schema(self, table_name: str) -> List[Dict[str, str]]:
        """Get table schema definition."""
        schemas = {
            'fact_loan_application_events': [
                {'name': 'loan_application_key', 'type': 'INT64', 'mode': 'REQUIRED'},
                {'name': 'customer_key', 'type': 'INT64', 'mode': 'REQUIRED'},
                {'name': 'actor_key', 'type': 'INT64', 'mode': 'REQUIRED'},
                {'name': 'date_key', 'type': 'INT64', 'mode': 'REQUIRED'},
                {'name': 'loan_application_id', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'customer_id', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'actor_id', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'event_type', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'previous_status', 'type': 'STRING', 'mode': 'NULLABLE'},
                {'name': 'new_status', 'type': 'STRING', 'mode': 'NULLABLE'},
                {'name': 'change_type', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'requested_amount', 'type': 'FLOAT64', 'mode': 'REQUIRED'},
                {'name': 'approval_amount', 'type': 'FLOAT64', 'mode': 'NULLABLE'},
                {'name': 'processing_duration_hours', 'type': 'FLOAT64', 'mode': 'NULLABLE'},
                {'name': 'blockchain_transaction_id', 'type': 'STRING', 'mode': 'NULLABLE'},
                {'name': 'notes', 'type': 'STRING', 'mode': 'NULLABLE'},
                {'name': 'event_timestamp', 'type': 'TIMESTAMP', 'mode': 'REQUIRED'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'mode': 'REQUIRED'},
                {'name': 'etl_batch_id', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'source_system', 'type': 'STRING', 'mode': 'REQUIRED'}
            ],
            
            'fact_compliance_events': [
                {'name': 'compliance_rule_key', 'type': 'INT64', 'mode': 'NULLABLE'},
                {'name': 'actor_key', 'type': 'INT64', 'mode': 'REQUIRED'},
                {'name': 'date_key', 'type': 'INT64', 'mode': 'REQUIRED'},
                {'name': 'event_id', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'rule_id', 'type': 'STRING', 'mode': 'NULLABLE'},
                {'name': 'actor_id', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'affected_entity_id', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'event_type', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'affected_entity_type', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'severity', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'resolution_status', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'resolution_duration_hours', 'type': 'FLOAT64', 'mode': 'NULLABLE'},
                {'name': 'is_violation', 'type': 'BOOLEAN', 'mode': 'REQUIRED'},
                {'name': 'alert_count', 'type': 'INT64', 'mode': 'REQUIRED'},
                {'name': 'description', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'details', 'type': 'JSON', 'mode': 'NULLABLE'},
                {'name': 'blockchain_transaction_id', 'type': 'STRING', 'mode': 'NULLABLE'},
                {'name': 'event_timestamp', 'type': 'TIMESTAMP', 'mode': 'REQUIRED'},
                {'name': 'acknowledged_at', 'type': 'TIMESTAMP', 'mode': 'NULLABLE'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'mode': 'REQUIRED'},
                {'name': 'etl_batch_id', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'source_system', 'type': 'STRING', 'mode': 'REQUIRED'}
            ],
            
            'dim_customer': [
                {'name': 'customer_key', 'type': 'INT64', 'mode': 'REQUIRED'},
                {'name': 'customer_id', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'first_name', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'last_name', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'date_of_birth', 'type': 'DATE', 'mode': 'NULLABLE'},
                {'name': 'national_id_hash', 'type': 'STRING', 'mode': 'NULLABLE'},
                {'name': 'address', 'type': 'STRING', 'mode': 'NULLABLE'},
                {'name': 'contact_email', 'type': 'STRING', 'mode': 'NULLABLE'},
                {'name': 'contact_phone', 'type': 'STRING', 'mode': 'NULLABLE'},
                {'name': 'kyc_status', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'aml_status', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'consent_preferences', 'type': 'JSON', 'mode': 'NULLABLE'},
                {'name': 'created_by_actor_id', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'effective_date', 'type': 'TIMESTAMP', 'mode': 'REQUIRED'},
                {'name': 'expiration_date', 'type': 'TIMESTAMP', 'mode': 'NULLABLE'},
                {'name': 'is_current', 'type': 'BOOLEAN', 'mode': 'REQUIRED'},
                {'name': 'version', 'type': 'INT64', 'mode': 'REQUIRED'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'mode': 'REQUIRED'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'mode': 'REQUIRED'},
                {'name': 'etl_batch_id', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'source_system', 'type': 'STRING', 'mode': 'REQUIRED'}
            ]
        }
        
        return schemas.get(table_name, [])
    
    def _format_schema_fields(self, schema: List[Dict[str, str]]) -> str:
        """Format schema fields for DDL."""
        field_definitions = []
        
        for field in schema:
            field_def = f"  {field['name']} {field['type']}"
            if field['mode'] == 'REQUIRED':
                field_def += " NOT NULL"
            field_definitions.append(field_def)
        
        return ",\n".join(field_definitions)
    
    def _build_partition_clause(self, config: PartitionConfig) -> str:
        """Build partition clause for DDL."""
        if config.partition_type == PartitionType.TIME_UNIT_COLUMN:
            clause = f"PARTITION BY DATE({config.field})"
            if config.time_unit and config.time_unit != TimeUnit.DAY:
                clause = f"PARTITION BY {config.time_unit.value}_TRUNC({config.field})"
        elif config.partition_type == PartitionType.INGESTION_TIME:
            clause = f"PARTITION BY DATE(_PARTITIONTIME)"
        else:
            clause = f"PARTITION BY RANGE_BUCKET({config.field}, GENERATE_ARRAY(0, 1000000, 1000))"
        
        return clause
    
    def _build_cluster_clause(self, config: ClusterConfig) -> str:
        """Build cluster clause for DDL."""
        # Limit to max fields allowed by BigQuery
        cluster_fields = config.fields[:config.max_fields]
        return f"CLUSTER BY {', '.join(cluster_fields)}"
    
    def _build_table_options(self, optimization: TableOptimization) -> str:
        """Build table options clause."""
        options = []
        
        if optimization.description:
            options.append(f'description="{optimization.description}"')
        
        if optimization.partition_config and optimization.partition_config.expiration_days:
            # Convert days to milliseconds
            expiration_ms = optimization.partition_config.expiration_days * 24 * 60 * 60 * 1000
            options.append(f'partition_expiration_days={optimization.partition_config.expiration_days}')
        
        if optimization.partition_config and optimization.partition_config.require_partition_filter:
            options.append('require_partition_filter=true')
        
        return ", ".join(options)
    
    def get_optimization_recommendations(self, table_name: str, query_patterns: List[str]) -> Dict[str, Any]:
        """Get optimization recommendations based on query patterns."""
        if table_name not in self.table_optimizations:
            return {'error': f'No optimization defined for table: {table_name}'}
        
        optimization = self.table_optimizations[table_name]
        recommendations = {
            'table_name': table_name,
            'current_optimization': {
                'partitioned': optimization.partition_config is not None,
                'clustered': optimization.cluster_config is not None,
                'partition_field': optimization.partition_config.field if optimization.partition_config else None,
                'cluster_fields': optimization.cluster_config.fields if optimization.cluster_config else []
            },
            'recommendations': []
        }
        
        # Analyze query patterns and provide recommendations
        for pattern in query_patterns:
            pattern_lower = pattern.lower()
            
            # Check for date filtering
            if 'where' in pattern_lower and any(date_field in pattern_lower for date_field in ['date', 'timestamp', 'created_at']):
                if not optimization.partition_config:
                    recommendations['recommendations'].append({
                        'type': 'partitioning',
                        'suggestion': 'Consider partitioning by date field for time-based filtering',
                        'impact': 'high'
                    })
            
            # Check for frequent GROUP BY fields
            if 'group by' in pattern_lower:
                group_fields = self._extract_group_by_fields(pattern)
                if optimization.cluster_config:
                    missing_fields = [f for f in group_fields if f not in optimization.cluster_config.fields]
                    if missing_fields:
                        recommendations['recommendations'].append({
                            'type': 'clustering',
                            'suggestion': f'Consider adding {missing_fields} to clustering fields',
                            'impact': 'medium'
                        })
            
            # Check for JOIN patterns
            if 'join' in pattern_lower:
                join_fields = self._extract_join_fields(pattern)
                recommendations['recommendations'].append({
                    'type': 'clustering',
                    'suggestion': f'Ensure JOIN fields {join_fields} are in clustering configuration',
                    'impact': 'high'
                })
        
        return recommendations
    
    def _extract_group_by_fields(self, query: str) -> List[str]:
        """Extract GROUP BY fields from query (simplified)."""
        # This is a simplified implementation
        # In production, use a proper SQL parser
        try:
            group_by_index = query.lower().find('group by')
            if group_by_index == -1:
                return []
            
            group_clause = query[group_by_index + 8:].split('order by')[0].split('having')[0]
            fields = [field.strip() for field in group_clause.split(',')]
            return [field for field in fields if field and not field.isdigit()]
        except:
            return []
    
    def _extract_join_fields(self, query: str) -> List[str]:
        """Extract JOIN fields from query (simplified)."""
        # This is a simplified implementation
        # In production, use a proper SQL parser
        join_fields = []
        try:
            words = query.lower().split()
            for i, word in enumerate(words):
                if word == 'on' and i + 1 < len(words):
                    # Look for field = field pattern
                    condition = ' '.join(words[i+1:i+5])
                    if '=' in condition:
                        parts = condition.split('=')
                        if len(parts) == 2:
                            left_field = parts[0].strip().split('.')[-1]
                            right_field = parts[1].strip().split('.')[-1]
                            join_fields.extend([left_field, right_field])
        except:
            pass
        
        return join_fields
    
    def generate_materialized_view_ddl(self, view_name: str, base_query: str, refresh_interval_minutes: int = 60) -> str:
        """Generate materialized view DDL."""
        return f"""
CREATE MATERIALIZED VIEW `{self.project_id}.{self.dataset_id}.{view_name}`
OPTIONS (
  enable_refresh = true,
  refresh_interval_minutes = {refresh_interval_minutes}
)
AS {base_query}
"""
    
    def get_table_statistics(self, table_name: str) -> Dict[str, Any]:
        """Get table statistics for optimization analysis."""
        # In production, this would query BigQuery INFORMATION_SCHEMA
        # For now, return mock statistics
        return {
            'table_name': table_name,
            'row_count': 1000000,  # Mock data
            'size_bytes': 50000000,
            'partition_count': 365 if self.table_optimizations.get(table_name, {}).partition_config else 1,
            'last_modified': datetime.now(timezone.utc).isoformat(),
            'optimization_score': self._calculate_optimization_score(table_name)
        }
    
    def _calculate_optimization_score(self, table_name: str) -> float:
        """Calculate optimization score for table (0-100)."""
        if table_name not in self.table_optimizations:
            return 0.0
        
        optimization = self.table_optimizations[table_name]
        score = 0.0
        
        # Base score for having optimization defined
        score += 20.0
        
        # Partitioning score
        if optimization.partition_config:
            score += 40.0
            if optimization.partition_config.require_partition_filter:
                score += 10.0
        
        # Clustering score
        if optimization.cluster_config:
            score += 30.0
            # Bonus for appropriate number of cluster fields
            if 1 <= len(optimization.cluster_config.fields) <= 4:
                score += 10.0
        
        return min(score, 100.0)
    
    def get_all_optimizations_summary(self) -> Dict[str, Any]:
        """Get summary of all table optimizations."""
        summary = {
            'total_tables': len(self.table_optimizations),
            'partitioned_tables': 0,
            'clustered_tables': 0,
            'avg_optimization_score': 0.0,
            'tables': {}
        }
        
        total_score = 0.0
        
        for table_name, optimization in self.table_optimizations.items():
            if optimization.partition_config:
                summary['partitioned_tables'] += 1
            
            if optimization.cluster_config:
                summary['clustered_tables'] += 1
            
            score = self._calculate_optimization_score(table_name)
            total_score += score
            
            summary['tables'][table_name] = {
                'partitioned': optimization.partition_config is not None,
                'clustered': optimization.cluster_config is not None,
                'optimization_score': score,
                'description': optimization.description
            }
        
        if summary['total_tables'] > 0:
            summary['avg_optimization_score'] = total_score / summary['total_tables']
        
        return summary