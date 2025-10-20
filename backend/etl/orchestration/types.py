"""
Shared types and enums for ETL orchestration.

This module contains common types used across orchestration components
to avoid circular imports.
"""

from enum import Enum


class JobType(Enum):
    """ETL job types."""
    DAILY_CUSTOMER_DIMENSION = "daily_customer_dimension"
    HOURLY_LOAN_EVENTS = "hourly_loan_events"
    HOURLY_COMPLIANCE_EVENTS = "hourly_compliance_events"
    FULL_REFRESH = "full_refresh"


class JobStatus(Enum):
    """ETL job execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"