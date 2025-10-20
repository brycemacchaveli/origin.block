"""
Unit tests for BigQuery Optimizer.

Tests optimization strategies, DDL generation, and performance recommendations.
"""

import pytest
from etl.analytics.bigquery_optimizer import (
    BigQueryOptimizer, PartitionType, TimeUnit, PartitionConfig, ClusterConfig
)


class TestBigQueryOptimizer:
    """Test cases for BigQueryOptimizer."""
    
    @pytest.fixture
    def optimizer(self):
        """Create BigQueryOptimizer instance."""
        return BigQueryOptimizer("test_project", "test_dataset")
    
    def test_init(self, optimizer):
        """Test optimizer initialization."""
        assert optimizer.project_id == "test_project"
        assert optimizer.dataset_id == "test_dataset"
        assert len(optimizer.table_optimizations) > 0
    
    def test_get_create_table_ddl_fact_table(self, optimizer):
        """Test DDL generation for fact table."""
        ddl = optimizer.get_create_table_ddl("fact_loan_application_events")
        
        assert "CREATE TABLE" in ddl
        assert "test_project.test_dataset.fact_loan_application_events" in ddl
        assert "PARTITION BY" in ddl
        assert "CLUSTER BY" in ddl
        assert "event_timestamp" in ddl
    
    def test_get_create_table_ddl_dimension_table(self, optimizer):
        """Test DDL generation for dimension table."""
        ddl = optimizer.get_create_table_ddl("dim_customer")
        
        assert "CREATE TABLE" in ddl
        assert "test_project.test_dataset.dim_customer" in ddl
        assert "CLUSTER BY" in ddl
        # Dimension tables typically don't have partitioning
        assert "customer_id" in ddl
    
    def test_get_create_table_ddl_invalid_table(self, optimizer):
        """Test DDL generation for invalid table."""
        with pytest.raises(ValueError):
            optimizer.get_create_table_ddl("nonexistent_table")
    
    def test_build_partition_clause_time_unit(self, optimizer):
        """Test partition clause building for time unit partitioning."""
        config = PartitionConfig(
            partition_type=PartitionType.TIME_UNIT_COLUMN,
            field="event_timestamp",
            time_unit=TimeUnit.DAY
        )
        
        clause = optimizer._build_partition_clause(config)
        assert "PARTITION BY DATE(event_timestamp)" in clause
    
    def test_build_partition_clause_monthly(self, optimizer):
        """Test partition clause building for monthly partitioning."""
        config = PartitionConfig(
            partition_type=PartitionType.TIME_UNIT_COLUMN,
            field="event_timestamp",
            time_unit=TimeUnit.MONTH
        )
        
        clause = optimizer._build_partition_clause(config)
        assert "MONTH_TRUNC" in clause
    
    def test_build_cluster_clause(self, optimizer):
        """Test cluster clause building."""
        config = ClusterConfig(fields=["field1", "field2", "field3"])
        
        clause = optimizer._build_cluster_clause(config)
        assert "CLUSTER BY field1, field2, field3" in clause
    
    def test_build_cluster_clause_max_fields(self, optimizer):
        """Test cluster clause with max fields limit."""
        config = ClusterConfig(fields=["field1", "field2", "field3", "field4", "field5"])
        
        clause = optimizer._build_cluster_clause(config)
        # Should only include first 4 fields (BigQuery limit)
        assert "field1, field2, field3, field4" in clause
        assert "field5" not in clause
    
    def test_get_optimization_recommendations(self, optimizer):
        """Test optimization recommendations."""
        query_patterns = [
            "SELECT * FROM table WHERE event_timestamp > '2024-01-01'",
            "SELECT customer_id, COUNT(*) FROM table GROUP BY customer_id"
        ]
        
        recommendations = optimizer.get_optimization_recommendations(
            "fact_loan_application_events", 
            query_patterns
        )
        
        assert "table_name" in recommendations
        assert "current_optimization" in recommendations
        assert "recommendations" in recommendations
    
    def test_extract_group_by_fields(self, optimizer):
        """Test GROUP BY field extraction."""
        query = "SELECT customer_id, COUNT(*) FROM table GROUP BY customer_id, loan_type ORDER BY COUNT(*)"
        
        fields = optimizer._extract_group_by_fields(query)
        assert "customer_id" in fields
        assert "loan_type" in fields
    
    def test_extract_join_fields(self, optimizer):
        """Test JOIN field extraction."""
        query = "SELECT * FROM table1 t1 JOIN table2 t2 ON t1.customer_id = t2.customer_id"
        
        fields = optimizer._extract_join_fields(query)
        assert "customer_id" in fields
    
    def test_generate_materialized_view_ddl(self, optimizer):
        """Test materialized view DDL generation."""
        base_query = "SELECT customer_id, COUNT(*) as loan_count FROM loans GROUP BY customer_id"
        
        ddl = optimizer.generate_materialized_view_ddl("mv_customer_loans", base_query, 30)
        
        assert "CREATE MATERIALIZED VIEW" in ddl
        assert "mv_customer_loans" in ddl
        assert "refresh_interval_minutes = 30" in ddl
        assert base_query in ddl
    
    def test_get_table_statistics(self, optimizer):
        """Test table statistics retrieval."""
        stats = optimizer.get_table_statistics("fact_loan_application_events")
        
        assert "table_name" in stats
        assert "row_count" in stats
        assert "optimization_score" in stats
        assert stats["optimization_score"] >= 0
        assert stats["optimization_score"] <= 100
    
    def test_calculate_optimization_score(self, optimizer):
        """Test optimization score calculation."""
        # Test table with both partitioning and clustering
        score1 = optimizer._calculate_optimization_score("fact_loan_application_events")
        
        # Test table with only clustering
        score2 = optimizer._calculate_optimization_score("dim_customer")
        
        # Fact table should have higher score due to partitioning
        assert score1 > score2
        assert 0 <= score1 <= 100
        assert 0 <= score2 <= 100
    
    def test_get_all_optimizations_summary(self, optimizer):
        """Test all optimizations summary."""
        summary = optimizer.get_all_optimizations_summary()
        
        assert "total_tables" in summary
        assert "partitioned_tables" in summary
        assert "clustered_tables" in summary
        assert "avg_optimization_score" in summary
        assert "tables" in summary
        
        assert summary["total_tables"] > 0
        assert summary["avg_optimization_score"] >= 0
        assert summary["avg_optimization_score"] <= 100
    
    def test_table_schema_retrieval(self, optimizer):
        """Test table schema retrieval."""
        schema = optimizer._get_table_schema("fact_loan_application_events")
        
        assert len(schema) > 0
        assert all("name" in field for field in schema)
        assert all("type" in field for field in schema)
        assert all("mode" in field for field in schema)
    
    def test_format_schema_fields(self, optimizer):
        """Test schema field formatting."""
        schema = [
            {"name": "field1", "type": "STRING", "mode": "REQUIRED"},
            {"name": "field2", "type": "INT64", "mode": "NULLABLE"}
        ]
        
        formatted = optimizer._format_schema_fields(schema)
        
        assert "field1 STRING NOT NULL" in formatted
        assert "field2 INT64" in formatted
        assert "field2 INT64 NOT NULL" not in formatted  # Should not have NOT NULL for nullable
    
    def test_build_table_options(self, optimizer):
        """Test table options building."""
        optimization = optimizer.table_optimizations["fact_loan_application_events"]
        
        options = optimizer._build_table_options(optimization)
        
        assert "description=" in options
        # Should include partition expiration if configured
        if optimization.partition_config and optimization.partition_config.expiration_days:
            assert "partition_expiration_days=" in options