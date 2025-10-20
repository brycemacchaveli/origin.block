"""
Materialized Views for analytical queries.

This module defines materialized views for common analytical patterns
including loan processing metrics, compliance dashboards, and performance tracking.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class ViewType(Enum):
    """Types of materialized views."""
    PERFORMANCE_METRICS = "performance_metrics"
    COMPLIANCE_DASHBOARD = "compliance_dashboard"
    OPERATIONAL_SUMMARY = "operational_summary"
    REAL_TIME_TRACKING = "real_time_tracking"


@dataclass
class MaterializedView:
    """Materialized view definition."""
    view_name: str
    view_type: ViewType
    base_query: str
    refresh_interval_minutes: int
    description: str
    dependencies: List[str]  # Tables this view depends on


class MaterializedViewManager:
    """
    Manager for analytical materialized views.
    
    Provides pre-defined materialized views for common analytical patterns
    and real-time process tracking.
    """
    
    def __init__(self, project_id: str, dataset_id: str):
        """Initialize materialized view manager."""
        self.project_id = project_id
        self.dataset_id = dataset_id
        
        # Define all materialized views
        self.views = self._define_materialized_views()
    
    def _define_materialized_views(self) -> Dict[str, MaterializedView]:
        """Define all materialized views."""
        return {
            # Loan processing performance metrics
            'mv_loan_processing_metrics': MaterializedView(
                view_name='mv_loan_processing_metrics',
                view_type=ViewType.PERFORMANCE_METRICS,
                base_query=self._get_loan_processing_metrics_query(),
                refresh_interval_minutes=15,  # Refresh every 15 minutes
                description="Loan application processing metrics with stage durations and bottleneck analysis",
                dependencies=['fact_loan_application_events', 'dim_loan_application', 'dim_customer', 'dim_actor']
            ),
            
            # Real-time loan status tracking
            'mv_loan_status_realtime': MaterializedView(
                view_name='mv_loan_status_realtime',
                view_type=ViewType.REAL_TIME_TRACKING,
                base_query=self._get_loan_status_realtime_query(),
                refresh_interval_minutes=5,  # Refresh every 5 minutes for real-time
                description="Real-time loan application status tracking with current stage and duration",
                dependencies=['fact_loan_application_events', 'dim_loan_application', 'dim_customer']
            ),
            
            # Compliance dashboard metrics
            'mv_compliance_dashboard': MaterializedView(
                view_name='mv_compliance_dashboard',
                view_type=ViewType.COMPLIANCE_DASHBOARD,
                base_query=self._get_compliance_dashboard_query(),
                refresh_interval_minutes=30,  # Refresh every 30 minutes
                description="Compliance dashboard with violation rates, resolution times, and trends",
                dependencies=['fact_compliance_events', 'dim_compliance_rule', 'dim_actor']
            ),
            
            # Daily operational summary
            'mv_daily_operations_summary': MaterializedView(
                view_name='mv_daily_operations_summary',
                view_type=ViewType.OPERATIONAL_SUMMARY,
                base_query=self._get_daily_operations_summary_query(),
                refresh_interval_minutes=60,  # Refresh hourly
                description="Daily operational summary with key metrics and trends",
                dependencies=['fact_loan_application_events', 'fact_compliance_events', 'dim_date']
            ),
            
            # Processing bottleneck analysis
            'mv_processing_bottlenecks': MaterializedView(
                view_name='mv_processing_bottlenecks',
                view_type=ViewType.PERFORMANCE_METRICS,
                base_query=self._get_processing_bottlenecks_query(),
                refresh_interval_minutes=30,  # Refresh every 30 minutes
                description="Processing bottleneck identification with stage-wise analysis",
                dependencies=['fact_loan_application_events', 'dim_loan_application']
            ),
            
            # Customer journey analytics
            'mv_customer_journey': MaterializedView(
                view_name='mv_customer_journey',
                view_type=ViewType.PERFORMANCE_METRICS,
                base_query=self._get_customer_journey_query(),
                refresh_interval_minutes=60,  # Refresh hourly
                description="Customer journey analytics from onboarding to loan completion",
                dependencies=['fact_loan_application_events', 'dim_customer', 'dim_loan_application']
            )
        }
    
    def _get_loan_processing_metrics_query(self) -> str:
        """Get loan processing metrics materialized view query."""
        return f"""
        WITH loan_stage_durations AS (
          SELECT 
            f.loan_application_id,
            f.customer_id,
            f.event_type,
            f.previous_status,
            f.new_status,
            f.processing_duration_hours,
            f.event_timestamp,
            l.loan_type,
            l.requested_amount,
            l.approval_amount,
            c.first_name,
            c.last_name,
            c.kyc_status,
            c.aml_status,
            -- Calculate cumulative processing time
            SUM(COALESCE(f.processing_duration_hours, 0)) OVER (
              PARTITION BY f.loan_application_id 
              ORDER BY f.event_timestamp 
              ROWS UNBOUNDED PRECEDING
            ) as cumulative_processing_hours,
            -- Rank events by timestamp
            ROW_NUMBER() OVER (
              PARTITION BY f.loan_application_id 
              ORDER BY f.event_timestamp DESC
            ) as event_rank
          FROM `{self.project_id}.{self.dataset_id}.fact_loan_application_events` f
          JOIN `{self.project_id}.{self.dataset_id}.dim_loan_application` l
            ON f.loan_application_key = l.loan_application_key AND l.is_current = TRUE
          JOIN `{self.project_id}.{self.dataset_id}.dim_customer` c
            ON f.customer_key = c.customer_key AND c.is_current = TRUE
          WHERE f.event_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
        ),
        
        stage_statistics AS (
          SELECT
            new_status as stage,
            loan_type,
            COUNT(*) as stage_entries,
            AVG(processing_duration_hours) as avg_stage_duration_hours,
            PERCENTILE_CONT(processing_duration_hours, 0.5) OVER (PARTITION BY new_status, loan_type) as median_stage_duration_hours,
            PERCENTILE_CONT(processing_duration_hours, 0.9) OVER (PARTITION BY new_status, loan_type) as p90_stage_duration_hours,
            MIN(processing_duration_hours) as min_stage_duration_hours,
            MAX(processing_duration_hours) as max_stage_duration_hours
          FROM loan_stage_durations
          WHERE processing_duration_hours IS NOT NULL
          GROUP BY new_status, loan_type
        )
        
        SELECT
          lsd.loan_application_id,
          lsd.customer_id,
          lsd.first_name,
          lsd.last_name,
          lsd.loan_type,
          lsd.requested_amount,
          lsd.approval_amount,
          lsd.kyc_status,
          lsd.aml_status,
          
          -- Current status (most recent event)
          FIRST_VALUE(lsd.new_status) OVER (
            PARTITION BY lsd.loan_application_id 
            ORDER BY lsd.event_timestamp DESC
          ) as current_status,
          
          -- Total processing time
          MAX(lsd.cumulative_processing_hours) as total_processing_hours,
          
          -- Application date (first event)
          MIN(lsd.event_timestamp) as application_date,
          
          -- Last update
          MAX(lsd.event_timestamp) as last_update,
          
          -- Days in current status
          DATETIME_DIFF(
            CURRENT_DATETIME(), 
            MAX(CASE WHEN lsd.event_rank = 1 THEN lsd.event_timestamp END),
            DAY
          ) as days_in_current_status,
          
          -- Stage performance comparison
          ss.avg_stage_duration_hours as stage_avg_duration,
          ss.median_stage_duration_hours as stage_median_duration,
          ss.p90_stage_duration_hours as stage_p90_duration,
          
          -- Performance indicators
          CASE 
            WHEN MAX(lsd.cumulative_processing_hours) > ss.p90_stage_duration_hours THEN 'SLOW'
            WHEN MAX(lsd.cumulative_processing_hours) < ss.median_stage_duration_hours THEN 'FAST'
            ELSE 'NORMAL'
          END as processing_speed_category,
          
          -- Bottleneck indicators
          CASE
            WHEN DATETIME_DIFF(CURRENT_DATETIME(), MAX(lsd.event_timestamp), DAY) > 7 THEN 'STALLED'
            WHEN DATETIME_DIFF(CURRENT_DATETIME(), MAX(lsd.event_timestamp), DAY) > 3 THEN 'DELAYED'
            ELSE 'ON_TRACK'
          END as bottleneck_status,
          
          CURRENT_TIMESTAMP() as last_refresh
          
        FROM loan_stage_durations lsd
        LEFT JOIN stage_statistics ss 
          ON lsd.new_status = ss.stage AND lsd.loan_type = ss.loan_type
        WHERE lsd.event_rank = 1  -- Only current status
        GROUP BY 
          lsd.loan_application_id, lsd.customer_id, lsd.first_name, lsd.last_name,
          lsd.loan_type, lsd.requested_amount, lsd.approval_amount, 
          lsd.kyc_status, lsd.aml_status,
          ss.avg_stage_duration_hours, ss.median_stage_duration_hours, ss.p90_stage_duration_hours
        """
    
    def _get_loan_status_realtime_query(self) -> str:
        """Get real-time loan status tracking query."""
        return f"""
        WITH latest_events AS (
          SELECT 
            f.loan_application_id,
            f.customer_id,
            f.new_status as current_status,
            f.event_timestamp as status_change_time,
            f.processing_duration_hours,
            l.loan_type,
            l.requested_amount,
            c.first_name,
            c.last_name,
            ROW_NUMBER() OVER (
              PARTITION BY f.loan_application_id 
              ORDER BY f.event_timestamp DESC
            ) as rn
          FROM `{self.project_id}.{self.dataset_id}.fact_loan_application_events` f
          JOIN `{self.project_id}.{self.dataset_id}.dim_loan_application` l
            ON f.loan_application_key = l.loan_application_key AND l.is_current = TRUE
          JOIN `{self.project_id}.{self.dataset_id}.dim_customer` c
            ON f.customer_key = c.customer_key AND c.is_current = TRUE
          WHERE f.event_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
        ),
        
        status_durations AS (
          SELECT
            current_status,
            AVG(DATETIME_DIFF(CURRENT_DATETIME(), status_change_time, HOUR)) as avg_hours_in_status,
            PERCENTILE_CONT(DATETIME_DIFF(CURRENT_DATETIME(), status_change_time, HOUR), 0.5) OVER (PARTITION BY current_status) as median_hours_in_status
          FROM latest_events
          WHERE rn = 1
          GROUP BY current_status
        )
        
        SELECT
          le.loan_application_id,
          le.customer_id,
          CONCAT(le.first_name, ' ', le.last_name) as customer_name,
          le.loan_type,
          le.requested_amount,
          le.current_status,
          le.status_change_time,
          
          -- Time in current status
          DATETIME_DIFF(CURRENT_DATETIME(), le.status_change_time, HOUR) as hours_in_current_status,
          DATETIME_DIFF(CURRENT_DATETIME(), le.status_change_time, DAY) as days_in_current_status,
          
          -- Performance indicators
          sd.avg_hours_in_status,
          sd.median_hours_in_status,
          
          -- Alert flags
          CASE 
            WHEN DATETIME_DIFF(CURRENT_DATETIME(), le.status_change_time, HOUR) > sd.avg_hours_in_status * 2 THEN TRUE
            ELSE FALSE
          END as is_overdue,
          
          CASE
            WHEN le.current_status = 'SUBMITTED' AND DATETIME_DIFF(CURRENT_DATETIME(), le.status_change_time, HOUR) > 24 THEN 'REVIEW_NEEDED'
            WHEN le.current_status = 'UNDERWRITING' AND DATETIME_DIFF(CURRENT_DATETIME(), le.status_change_time, HOUR) > 72 THEN 'ESCALATE'
            WHEN le.current_status = 'APPROVED' AND DATETIME_DIFF(CURRENT_DATETIME(), le.status_change_time, HOUR) > 48 THEN 'DISBURSE_READY'
            ELSE 'NORMAL'
          END as action_required,
          
          -- Next expected action time
          DATETIME_ADD(
            le.status_change_time, 
            INTERVAL CAST(sd.avg_hours_in_status AS INT64) HOUR
          ) as expected_next_action,
          
          CURRENT_TIMESTAMP() as last_refresh
          
        FROM latest_events le
        LEFT JOIN status_durations sd ON le.current_status = sd.current_status
        WHERE le.rn = 1
        ORDER BY 
          CASE 
            WHEN DATETIME_DIFF(CURRENT_DATETIME(), le.status_change_time, HOUR) > sd.avg_hours_in_status * 2 THEN 1
            ELSE 2
          END,
          le.status_change_time DESC
        """
    
    def _get_compliance_dashboard_query(self) -> str:
        """Get compliance dashboard materialized view query."""
        return f"""
        WITH daily_compliance_metrics AS (
          SELECT
            DATE(f.event_timestamp) as event_date,
            f.event_type,
            f.severity,
            f.affected_entity_type,
            COUNT(*) as event_count,
            SUM(CASE WHEN f.is_violation THEN 1 ELSE 0 END) as violation_count,
            AVG(f.resolution_duration_hours) as avg_resolution_hours,
            COUNT(CASE WHEN f.resolution_duration_hours IS NULL THEN 1 END) as unresolved_count
          FROM `{self.project_id}.{self.dataset_id}.fact_compliance_events` f
          WHERE f.event_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
          GROUP BY event_date, event_type, severity, affected_entity_type
        ),
        
        trend_analysis AS (
          SELECT
            event_date,
            SUM(violation_count) as daily_violations,
            SUM(event_count) as daily_events,
            AVG(avg_resolution_hours) as daily_avg_resolution,
            SUM(unresolved_count) as daily_unresolved,
            
            -- 7-day moving averages
            AVG(SUM(violation_count)) OVER (
              ORDER BY event_date 
              ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            ) as violations_7day_avg,
            
            AVG(AVG(avg_resolution_hours)) OVER (
              ORDER BY event_date 
              ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            ) as resolution_7day_avg
            
          FROM daily_compliance_metrics
          GROUP BY event_date
        )
        
        SELECT
          dcm.event_date,
          dcm.event_type,
          dcm.severity,
          dcm.affected_entity_type,
          dcm.event_count,
          dcm.violation_count,
          dcm.avg_resolution_hours,
          dcm.unresolved_count,
          
          -- Violation rate
          SAFE_DIVIDE(dcm.violation_count, dcm.event_count) * 100 as violation_rate_percent,
          
          -- Trend indicators
          ta.violations_7day_avg,
          ta.resolution_7day_avg,
          
          -- Performance indicators
          CASE
            WHEN SAFE_DIVIDE(dcm.violation_count, dcm.event_count) > 0.1 THEN 'HIGH_VIOLATION_RATE'
            WHEN dcm.avg_resolution_hours > 24 THEN 'SLOW_RESOLUTION'
            WHEN dcm.unresolved_count > 10 THEN 'HIGH_BACKLOG'
            ELSE 'NORMAL'
          END as alert_status,
          
          -- Compliance score (0-100)
          GREATEST(0, 
            100 - (SAFE_DIVIDE(dcm.violation_count, dcm.event_count) * 100 * 2) 
                - (LEAST(dcm.avg_resolution_hours, 48) / 48 * 20)
                - (LEAST(dcm.unresolved_count, 20) / 20 * 10)
          ) as compliance_score,
          
          CURRENT_TIMESTAMP() as last_refresh
          
        FROM daily_compliance_metrics dcm
        LEFT JOIN trend_analysis ta ON dcm.event_date = ta.event_date
        WHERE dcm.event_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
        ORDER BY dcm.event_date DESC, dcm.violation_count DESC
        """
    
    def _get_daily_operations_summary_query(self) -> str:
        """Get daily operations summary query."""
        return f"""
        WITH daily_loan_metrics AS (
          SELECT
            DATE(f.event_timestamp) as business_date,
            COUNT(DISTINCT f.loan_application_id) as applications_processed,
            COUNT(CASE WHEN f.event_type = 'APPLICATION_SUBMITTED' THEN 1 END) as new_applications,
            COUNT(CASE WHEN f.event_type = 'APPROVAL' THEN 1 END) as approvals,
            COUNT(CASE WHEN f.event_type = 'REJECTION' THEN 1 END) as rejections,
            SUM(f.requested_amount) as total_requested_amount,
            SUM(f.approval_amount) as total_approved_amount,
            AVG(f.processing_duration_hours) as avg_processing_hours
          FROM `{self.project_id}.{self.dataset_id}.fact_loan_application_events` f
          WHERE f.event_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
          GROUP BY business_date
        ),
        
        daily_compliance_metrics AS (
          SELECT
            DATE(f.event_timestamp) as business_date,
            COUNT(*) as compliance_events,
            SUM(CASE WHEN f.is_violation THEN 1 ELSE 0 END) as violations,
            COUNT(CASE WHEN f.severity = 'CRITICAL' THEN 1 END) as critical_events,
            AVG(f.resolution_duration_hours) as avg_resolution_hours
          FROM `{self.project_id}.{self.dataset_id}.fact_compliance_events` f
          WHERE f.event_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
          GROUP BY business_date
        )
        
        SELECT
          d.date_key,
          d.full_date as business_date,
          d.day_name,
          d.is_weekend,
          
          -- Loan metrics
          COALESCE(lm.applications_processed, 0) as applications_processed,
          COALESCE(lm.new_applications, 0) as new_applications,
          COALESCE(lm.approvals, 0) as approvals,
          COALESCE(lm.rejections, 0) as rejections,
          COALESCE(lm.total_requested_amount, 0) as total_requested_amount,
          COALESCE(lm.total_approved_amount, 0) as total_approved_amount,
          COALESCE(lm.avg_processing_hours, 0) as avg_processing_hours,
          
          -- Approval rate
          SAFE_DIVIDE(lm.approvals, lm.approvals + lm.rejections) * 100 as approval_rate_percent,
          
          -- Compliance metrics
          COALESCE(cm.compliance_events, 0) as compliance_events,
          COALESCE(cm.violations, 0) as violations,
          COALESCE(cm.critical_events, 0) as critical_events,
          COALESCE(cm.avg_resolution_hours, 0) as avg_resolution_hours,
          
          -- Violation rate
          SAFE_DIVIDE(cm.violations, cm.compliance_events) * 100 as violation_rate_percent,
          
          -- Operational efficiency score
          CASE
            WHEN d.is_weekend THEN NULL
            ELSE GREATEST(0, LEAST(100,
              (COALESCE(lm.applications_processed, 0) / 10.0 * 20) +  -- Volume score
              (SAFE_DIVIDE(lm.approvals, lm.approvals + lm.rejections) * 30) +  -- Approval rate score
              (GREATEST(0, 48 - COALESCE(lm.avg_processing_hours, 48)) / 48 * 30) +  -- Speed score
              (GREATEST(0, 100 - COALESCE(SAFE_DIVIDE(cm.violations, cm.compliance_events) * 100, 0)) * 0.2)  -- Compliance score
            ))
          END as operational_efficiency_score,
          
          CURRENT_TIMESTAMP() as last_refresh
          
        FROM `{self.project_id}.{self.dataset_id}.dim_date` d
        LEFT JOIN daily_loan_metrics lm ON DATE(d.full_date) = lm.business_date
        LEFT JOIN daily_compliance_metrics cm ON DATE(d.full_date) = cm.business_date
        WHERE d.full_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
          AND d.full_date <= CURRENT_DATE()
        ORDER BY d.full_date DESC
        """
    
    def _get_processing_bottlenecks_query(self) -> str:
        """Get processing bottlenecks analysis query."""
        return f"""
        WITH stage_transitions AS (
          SELECT
            f.loan_application_id,
            f.previous_status,
            f.new_status,
            f.processing_duration_hours,
            f.event_timestamp,
            l.loan_type,
            l.requested_amount,
            
            -- Calculate percentiles for each stage transition
            PERCENTILE_CONT(f.processing_duration_hours, 0.5) OVER (
              PARTITION BY f.previous_status, f.new_status, l.loan_type
            ) as median_duration,
            
            PERCENTILE_CONT(f.processing_duration_hours, 0.9) OVER (
              PARTITION BY f.previous_status, f.new_status, l.loan_type
            ) as p90_duration,
            
            AVG(f.processing_duration_hours) OVER (
              PARTITION BY f.previous_status, f.new_status, l.loan_type
            ) as avg_duration
            
          FROM `{self.project_id}.{self.dataset_id}.fact_loan_application_events` f
          JOIN `{self.project_id}.{self.dataset_id}.dim_loan_application` l
            ON f.loan_application_key = l.loan_application_key AND l.is_current = TRUE
          WHERE f.processing_duration_hours IS NOT NULL
            AND f.event_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
        )
        
        SELECT
          COALESCE(previous_status, 'START') as from_stage,
          new_status as to_stage,
          loan_type,
          
          -- Volume metrics
          COUNT(*) as transition_count,
          COUNT(DISTINCT loan_application_id) as unique_applications,
          
          -- Duration metrics
          AVG(processing_duration_hours) as avg_duration_hours,
          MIN(processing_duration_hours) as min_duration_hours,
          MAX(processing_duration_hours) as max_duration_hours,
          APPROX_QUANTILES(processing_duration_hours, 100)[OFFSET(50)] as median_duration_hours,
          APPROX_QUANTILES(processing_duration_hours, 100)[OFFSET(90)] as p90_duration_hours,
          APPROX_QUANTILES(processing_duration_hours, 100)[OFFSET(95)] as p95_duration_hours,
          
          -- Bottleneck indicators
          CASE
            WHEN AVG(processing_duration_hours) > APPROX_QUANTILES(processing_duration_hours, 100)[OFFSET(90)] * 0.8 THEN 'HIGH_BOTTLENECK'
            WHEN AVG(processing_duration_hours) > APPROX_QUANTILES(processing_duration_hours, 100)[OFFSET(75)] * 0.8 THEN 'MEDIUM_BOTTLENECK'
            ELSE 'LOW_BOTTLENECK'
          END as bottleneck_severity,
          
          -- Performance score (0-100, higher is better)
          GREATEST(0, LEAST(100,
            100 - (AVG(processing_duration_hours) / NULLIF(APPROX_QUANTILES(processing_duration_hours, 100)[OFFSET(95)], 0) * 100)
          )) as performance_score,
          
          -- Recommendations
          CASE
            WHEN AVG(processing_duration_hours) > 72 THEN 'URGENT: Review process automation'
            WHEN AVG(processing_duration_hours) > 24 THEN 'Consider process optimization'
            WHEN STDDEV(processing_duration_hours) > AVG(processing_duration_hours) THEN 'High variability - standardize process'
            ELSE 'Performance acceptable'
          END as recommendation,
          
          CURRENT_TIMESTAMP() as last_refresh
          
        FROM stage_transitions
        GROUP BY from_stage, to_stage, loan_type
        HAVING COUNT(*) >= 5  -- Only include transitions with sufficient data
        ORDER BY avg_duration_hours DESC, transition_count DESC
        """
    
    def _get_customer_journey_query(self) -> str:
        """Get customer journey analytics query."""
        return f"""
        WITH customer_timeline AS (
          SELECT
            f.customer_id,
            c.first_name,
            c.last_name,
            c.kyc_status,
            c.aml_status,
            f.loan_application_id,
            f.event_type,
            f.new_status,
            f.event_timestamp,
            l.loan_type,
            l.requested_amount,
            l.approval_amount,
            
            -- First and last events per customer
            MIN(f.event_timestamp) OVER (PARTITION BY f.customer_id) as first_interaction,
            MAX(f.event_timestamp) OVER (PARTITION BY f.customer_id) as last_interaction,
            
            -- Application sequence
            DENSE_RANK() OVER (
              PARTITION BY f.customer_id 
              ORDER BY f.loan_application_id
            ) as application_sequence
            
          FROM `{self.project_id}.{self.dataset_id}.fact_loan_application_events` f
          JOIN `{self.project_id}.{self.dataset_id}.dim_customer` c
            ON f.customer_key = c.customer_key AND c.is_current = TRUE
          JOIN `{self.project_id}.{self.dataset_id}.dim_loan_application` l
            ON f.loan_application_key = l.loan_application_key AND l.is_current = TRUE
          WHERE f.event_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
        )
        
        SELECT
          customer_id,
          CONCAT(first_name, ' ', last_name) as customer_name,
          kyc_status,
          aml_status,
          
          -- Journey metrics
          first_interaction,
          last_interaction,
          DATETIME_DIFF(last_interaction, first_interaction, DAY) as customer_lifetime_days,
          
          -- Application metrics
          COUNT(DISTINCT loan_application_id) as total_applications,
          MAX(application_sequence) as max_application_sequence,
          
          -- Financial metrics
          SUM(requested_amount) as total_requested_amount,
          SUM(approval_amount) as total_approved_amount,
          SAFE_DIVIDE(SUM(approval_amount), SUM(requested_amount)) * 100 as approval_amount_rate,
          
          -- Status distribution
          COUNT(CASE WHEN event_type = 'APPROVAL' THEN 1 END) as approvals,
          COUNT(CASE WHEN event_type = 'REJECTION' THEN 1 END) as rejections,
          SAFE_DIVIDE(
            COUNT(CASE WHEN event_type = 'APPROVAL' THEN 1 END),
            COUNT(CASE WHEN event_type IN ('APPROVAL', 'REJECTION') THEN 1 END)
          ) * 100 as approval_rate_percent,
          
          -- Customer segment
          CASE
            WHEN COUNT(DISTINCT loan_application_id) >= 3 THEN 'FREQUENT_BORROWER'
            WHEN SUM(requested_amount) >= 100000 THEN 'HIGH_VALUE'
            WHEN SAFE_DIVIDE(
              COUNT(CASE WHEN event_type = 'APPROVAL' THEN 1 END),
              COUNT(CASE WHEN event_type IN ('APPROVAL', 'REJECTION') THEN 1 END)
            ) >= 0.8 THEN 'PREFERRED_CUSTOMER'
            ELSE 'STANDARD'
          END as customer_segment,
          
          -- Risk indicators
          CASE
            WHEN kyc_status != 'VERIFIED' OR aml_status != 'CLEAR' THEN 'HIGH_RISK'
            WHEN SAFE_DIVIDE(
              COUNT(CASE WHEN event_type = 'REJECTION' THEN 1 END),
              COUNT(CASE WHEN event_type IN ('APPROVAL', 'REJECTION') THEN 1 END)
            ) > 0.5 THEN 'MEDIUM_RISK'
            ELSE 'LOW_RISK'
          END as risk_category,
          
          CURRENT_TIMESTAMP() as last_refresh
          
        FROM customer_timeline
        GROUP BY 
          customer_id, customer_name, kyc_status, aml_status,
          first_interaction, last_interaction
        ORDER BY total_approved_amount DESC, customer_lifetime_days DESC
        """
    
    def get_view_ddl(self, view_name: str) -> str:
        """Get DDL for creating materialized view."""
        if view_name not in self.views:
            raise ValueError(f"View {view_name} not found")
        
        view = self.views[view_name]
        
        return f"""
CREATE MATERIALIZED VIEW `{self.project_id}.{self.dataset_id}.{view_name}`
OPTIONS (
  enable_refresh = true,
  refresh_interval_minutes = {view.refresh_interval_minutes},
  description = "{view.description}"
)
AS {view.base_query}
"""
    
    def get_all_views_ddl(self) -> Dict[str, str]:
        """Get DDL for all materialized views."""
        return {
            view_name: self.get_view_ddl(view_name)
            for view_name in self.views.keys()
        }
    
    def get_view_dependencies(self, view_name: str) -> List[str]:
        """Get dependencies for a materialized view."""
        if view_name not in self.views:
            raise ValueError(f"View {view_name} not found")
        
        return self.views[view_name].dependencies
    
    def get_refresh_schedule(self) -> Dict[str, Dict[str, Any]]:
        """Get refresh schedule for all views."""
        schedule = {}
        
        for view_name, view in self.views.items():
            schedule[view_name] = {
                'refresh_interval_minutes': view.refresh_interval_minutes,
                'view_type': view.view_type.value,
                'dependencies': view.dependencies,
                'description': view.description
            }
        
        return schedule
    
    def get_performance_queries(self) -> Dict[str, str]:
        """Get common performance analysis queries."""
        return {
            'loan_processing_summary': f"""
            SELECT 
              current_status,
              COUNT(*) as application_count,
              AVG(total_processing_hours) as avg_processing_hours,
              AVG(days_in_current_status) as avg_days_in_status,
              COUNT(CASE WHEN bottleneck_status = 'STALLED' THEN 1 END) as stalled_count
            FROM `{self.project_id}.{self.dataset_id}.mv_loan_processing_metrics`
            GROUP BY current_status
            ORDER BY avg_processing_hours DESC
            """,
            
            'real_time_alerts': f"""
            SELECT 
              loan_application_id,
              customer_name,
              current_status,
              hours_in_current_status,
              action_required,
              expected_next_action
            FROM `{self.project_id}.{self.dataset_id}.mv_loan_status_realtime`
            WHERE is_overdue = TRUE OR action_required != 'NORMAL'
            ORDER BY hours_in_current_status DESC
            """,
            
            'compliance_summary': f"""
            SELECT 
              event_date,
              SUM(violation_count) as total_violations,
              AVG(compliance_score) as avg_compliance_score,
              COUNT(CASE WHEN alert_status != 'NORMAL' THEN 1 END) as alert_count
            FROM `{self.project_id}.{self.dataset_id}.mv_compliance_dashboard`
            WHERE event_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
            GROUP BY event_date
            ORDER BY event_date DESC
            """,
            
            'bottleneck_analysis': f"""
            SELECT 
              from_stage,
              to_stage,
              loan_type,
              avg_duration_hours,
              bottleneck_severity,
              performance_score,
              recommendation
            FROM `{self.project_id}.{self.dataset_id}.mv_processing_bottlenecks`
            WHERE bottleneck_severity IN ('HIGH_BOTTLENECK', 'MEDIUM_BOTTLENECK')
            ORDER BY avg_duration_hours DESC
            """
        }