"""
Data Quality Checker for ETL processes.

This module provides comprehensive data quality validation for ETL batches
including completeness, accuracy, consistency, and timeliness checks.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import statistics

import structlog

from etl.models import ETLBatch
from etl.orchestration.types import JobType
from shared.database import DatabaseManager

logger = structlog.get_logger(__name__)


class QualityCheckType(Enum):
    """Types of data quality checks."""
    COMPLETENESS = "completeness"
    ACCURACY = "accuracy"
    CONSISTENCY = "consistency"
    TIMELINESS = "timeliness"
    UNIQUENESS = "uniqueness"
    VALIDITY = "validity"


class QualitySeverity(Enum):
    """Severity levels for quality issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class QualityIssue:
    """Data quality issue."""
    check_type: QualityCheckType
    severity: QualitySeverity
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    affected_records: int = 0


@dataclass
class QualityCheckResult:
    """Result of data quality checks."""
    batch_id: str
    job_type: JobType
    check_timestamp: datetime
    passed: bool
    total_checks: int
    passed_checks: int
    failed_checks: int
    issues: List[QualityIssue] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


class DataQualityChecker:
    """
    Comprehensive data quality checker for ETL processes.
    
    Performs various quality checks on ETL batch results to ensure
    data integrity and reliability.
    """
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize data quality checker."""
        self.db_manager = db_manager
        
        # Quality thresholds (configurable)
        self.thresholds = {
            'min_completeness_rate': 0.95,  # 95% completeness required
            'max_error_rate': 0.05,         # 5% error rate allowed
            'max_processing_time_hours': 24, # 24 hours max processing time
            'min_records_per_batch': 1,      # At least 1 record expected
            'max_duplicate_rate': 0.01,     # 1% duplicate rate allowed
        }
    
    async def check_batch_quality(
        self, 
        batch_result: ETLBatch, 
        job_type: JobType
    ) -> QualityCheckResult:
        """
        Perform comprehensive quality checks on ETL batch.
        
        Args:
            batch_result: ETL batch execution result
            job_type: Type of ETL job
            
        Returns:
            Quality check result
        """
        logger.info("Starting data quality checks", 
                   batch_id=batch_result.batch_id,
                   job_type=job_type.value)
        
        quality_result = QualityCheckResult(
            batch_id=batch_result.batch_id,
            job_type=job_type,
            check_timestamp=datetime.now(timezone.utc),
            passed=True,
            total_checks=0,
            passed_checks=0,
            failed_checks=0
        )
        
        try:
            # Run different quality checks based on job type
            checks = [
                self._check_completeness,
                self._check_timeliness,
                self._check_consistency,
                self._check_validity
            ]
            
            # Add job-specific checks
            if job_type in [JobType.HOURLY_LOAN_EVENTS, JobType.HOURLY_COMPLIANCE_EVENTS]:
                checks.append(self._check_incremental_processing)
            
            if job_type == JobType.DAILY_CUSTOMER_DIMENSION:
                checks.append(self._check_scd_integrity)
            
            # Execute all checks
            for check_func in checks:
                try:
                    issues = await check_func(batch_result, job_type)
                    quality_result.issues.extend(issues)
                    quality_result.total_checks += 1
                    
                    # Check if any critical or error issues
                    has_critical_issues = any(
                        issue.severity in [QualitySeverity.CRITICAL, QualitySeverity.ERROR] 
                        for issue in issues
                    )
                    
                    if has_critical_issues:
                        quality_result.failed_checks += 1
                        quality_result.passed = False
                    else:
                        quality_result.passed_checks += 1
                        
                except Exception as e:
                    logger.error("Quality check failed", 
                               check=check_func.__name__,
                               error=str(e))
                    
                    quality_result.issues.append(QualityIssue(
                        check_type=QualityCheckType.VALIDITY,
                        severity=QualitySeverity.ERROR,
                        message=f"Quality check {check_func.__name__} failed: {str(e)}"
                    ))
                    quality_result.failed_checks += 1
                    quality_result.passed = False
            
            # Calculate overall metrics
            quality_result.metrics = self._calculate_quality_metrics(batch_result, quality_result)
            
            # Determine final pass/fail status
            critical_issues = [
                issue for issue in quality_result.issues 
                if issue.severity == QualitySeverity.CRITICAL
            ]
            
            if critical_issues:
                quality_result.passed = False
                quality_result.error_message = f"Critical quality issues found: {len(critical_issues)}"
            
            logger.info("Data quality checks completed", 
                       batch_id=batch_result.batch_id,
                       passed=quality_result.passed,
                       total_checks=quality_result.total_checks,
                       issues=len(quality_result.issues))
            
            return quality_result
            
        except Exception as e:
            logger.error("Data quality check process failed", 
                        batch_id=batch_result.batch_id,
                        error=str(e))
            
            quality_result.passed = False
            quality_result.error_message = str(e)
            return quality_result
    
    async def _check_completeness(
        self, 
        batch_result: ETLBatch, 
        job_type: JobType
    ) -> List[QualityIssue]:
        """Check data completeness."""
        issues = []
        
        # Check if batch processed minimum expected records
        if batch_result.records_processed < self.thresholds['min_records_per_batch']:
            issues.append(QualityIssue(
                check_type=QualityCheckType.COMPLETENESS,
                severity=QualitySeverity.WARNING,
                message=f"Low record count: {batch_result.records_processed} records processed",
                details={'records_processed': batch_result.records_processed},
                affected_records=batch_result.records_processed
            ))
        
        # Check success rate
        total_records = batch_result.records_processed
        failed_records = batch_result.records_failed
        
        if total_records > 0:
            error_rate = failed_records / total_records
            if error_rate > self.thresholds['max_error_rate']:
                issues.append(QualityIssue(
                    check_type=QualityCheckType.COMPLETENESS,
                    severity=QualitySeverity.ERROR,
                    message=f"High error rate: {error_rate:.2%} of records failed",
                    details={
                        'error_rate': error_rate,
                        'failed_records': failed_records,
                        'total_records': total_records
                    },
                    affected_records=failed_records
                ))
        
        # Check for missing required fields (job-specific)
        if job_type == JobType.DAILY_CUSTOMER_DIMENSION:
            missing_fields_issues = await self._check_customer_required_fields(batch_result)
            issues.extend(missing_fields_issues)
        
        return issues
    
    async def _check_timeliness(
        self, 
        batch_result: ETLBatch, 
        job_type: JobType
    ) -> List[QualityIssue]:
        """Check data timeliness."""
        issues = []
        
        # Check batch processing time
        if batch_result.start_time and batch_result.end_time:
            processing_time = batch_result.end_time - batch_result.start_time
            processing_hours = processing_time.total_seconds() / 3600
            
            if processing_hours > self.thresholds['max_processing_time_hours']:
                issues.append(QualityIssue(
                    check_type=QualityCheckType.TIMELINESS,
                    severity=QualitySeverity.WARNING,
                    message=f"Long processing time: {processing_hours:.2f} hours",
                    details={'processing_hours': processing_hours}
                ))
        
        # Check data freshness for incremental jobs
        if job_type in [JobType.HOURLY_LOAN_EVENTS, JobType.HOURLY_COMPLIANCE_EVENTS]:
            freshness_issues = await self._check_data_freshness(batch_result, job_type)
            issues.extend(freshness_issues)
        
        return issues
    
    async def _check_consistency(
        self, 
        batch_result: ETLBatch, 
        job_type: JobType
    ) -> List[QualityIssue]:
        """Check data consistency."""
        issues = []
        
        # Check for data consistency across related tables
        try:
            with self.db_manager.session_scope() as session:
                if job_type == JobType.DAILY_CUSTOMER_DIMENSION:
                    # Check customer-actor relationships
                    consistency_issues = await self._check_customer_actor_consistency(session)
                    issues.extend(consistency_issues)
                
                elif job_type == JobType.HOURLY_LOAN_EVENTS:
                    # Check loan-customer relationships
                    consistency_issues = await self._check_loan_customer_consistency(session)
                    issues.extend(consistency_issues)
                
        except Exception as e:
            issues.append(QualityIssue(
                check_type=QualityCheckType.CONSISTENCY,
                severity=QualitySeverity.ERROR,
                message=f"Consistency check failed: {str(e)}"
            ))
        
        return issues
    
    async def _check_validity(
        self, 
        batch_result: ETLBatch, 
        job_type: JobType
    ) -> List[QualityIssue]:
        """Check data validity."""
        issues = []
        
        # Check for valid data formats and ranges
        try:
            with self.db_manager.session_scope() as session:
                if job_type == JobType.DAILY_CUSTOMER_DIMENSION:
                    validity_issues = await self._check_customer_data_validity(session)
                    issues.extend(validity_issues)
                
                elif job_type == JobType.HOURLY_LOAN_EVENTS:
                    validity_issues = await self._check_loan_data_validity(session)
                    issues.extend(validity_issues)
                
        except Exception as e:
            issues.append(QualityIssue(
                check_type=QualityCheckType.VALIDITY,
                severity=QualitySeverity.ERROR,
                message=f"Validity check failed: {str(e)}"
            ))
        
        return issues
    
    async def _check_incremental_processing(
        self, 
        batch_result: ETLBatch, 
        job_type: JobType
    ) -> List[QualityIssue]:
        """Check incremental processing integrity."""
        issues = []
        
        # Check for gaps in incremental processing
        # This would involve checking timestamps and ensuring no data gaps
        
        # For demonstration, check if we have recent data
        current_time = datetime.now(timezone.utc)
        batch_time = batch_result.start_time
        
        if batch_time:
            time_diff = current_time - batch_time
            if time_diff > timedelta(hours=2):  # Data older than 2 hours
                issues.append(QualityIssue(
                    check_type=QualityCheckType.TIMELINESS,
                    severity=QualitySeverity.WARNING,
                    message=f"Batch data may be stale: {time_diff.total_seconds()/3600:.1f} hours old",
                    details={'batch_age_hours': time_diff.total_seconds()/3600}
                ))
        
        return issues
    
    async def _check_scd_integrity(
        self, 
        batch_result: ETLBatch, 
        job_type: JobType
    ) -> List[QualityIssue]:
        """Check SCD Type 2 integrity for dimension tables."""
        issues = []
        
        # Check for SCD Type 2 integrity issues
        # - Multiple current records for same business key
        # - Overlapping effective dates
        # - Missing expiration dates for non-current records
        
        try:
            with self.db_manager.session_scope() as session:
                # This would check the actual dimension table
                # For now, just a placeholder check
                
                # Check for multiple current records (should not happen)
                # In a real implementation, this would query the dimension table
                pass
                
        except Exception as e:
            issues.append(QualityIssue(
                check_type=QualityCheckType.CONSISTENCY,
                severity=QualitySeverity.ERROR,
                message=f"SCD integrity check failed: {str(e)}"
            ))
        
        return issues
    
    async def _check_customer_required_fields(self, batch_result: ETLBatch) -> List[QualityIssue]:
        """Check customer data for required fields."""
        issues = []
        
        # In a real implementation, this would query the operational database
        # to check for missing required fields in customer records
        
        return issues
    
    async def _check_data_freshness(
        self, 
        batch_result: ETLBatch, 
        job_type: JobType
    ) -> List[QualityIssue]:
        """Check data freshness for incremental jobs."""
        issues = []
        
        # Check if we have recent data in the source tables
        current_time = datetime.now(timezone.utc)
        
        try:
            with self.db_manager.session_scope() as session:
                # This would check the latest timestamps in source tables
                # For demonstration, assume data is fresh if batch completed recently
                
                if batch_result.end_time:
                    time_since_batch = current_time - batch_result.end_time
                    if time_since_batch > timedelta(hours=1):
                        issues.append(QualityIssue(
                            check_type=QualityCheckType.TIMELINESS,
                            severity=QualitySeverity.INFO,
                            message=f"Batch completed {time_since_batch.total_seconds()/3600:.1f} hours ago"
                        ))
                
        except Exception as e:
            issues.append(QualityIssue(
                check_type=QualityCheckType.TIMELINESS,
                severity=QualitySeverity.WARNING,
                message=f"Could not check data freshness: {str(e)}"
            ))
        
        return issues
    
    async def _check_customer_actor_consistency(self, session) -> List[QualityIssue]:
        """Check consistency between customer and actor tables."""
        issues = []
        
        # In a real implementation, this would check:
        # - All customers have valid created_by_actor_id
        # - Actor references exist and are valid
        
        return issues
    
    async def _check_loan_customer_consistency(self, session) -> List[QualityIssue]:
        """Check consistency between loan and customer tables."""
        issues = []
        
        # In a real implementation, this would check:
        # - All loans have valid customer_id references
        # - Customer records exist for all loan applications
        
        return issues
    
    async def _check_customer_data_validity(self, session) -> List[QualityIssue]:
        """Check validity of customer data."""
        issues = []
        
        # In a real implementation, this would check:
        # - Valid email formats
        # - Valid phone number formats
        # - Valid KYC/AML status values
        # - Reasonable date ranges
        
        return issues
    
    async def _check_loan_data_validity(self, session) -> List[QualityIssue]:
        """Check validity of loan data."""
        issues = []
        
        # In a real implementation, this would check:
        # - Positive loan amounts
        # - Valid status transitions
        # - Reasonable processing times
        # - Valid actor assignments
        
        return issues
    
    def _calculate_quality_metrics(
        self, 
        batch_result: ETLBatch, 
        quality_result: QualityCheckResult
    ) -> Dict[str, Any]:
        """Calculate quality metrics for the batch."""
        metrics = {}
        
        # Basic metrics
        total_records = batch_result.records_processed
        if total_records > 0:
            metrics['success_rate'] = (total_records - batch_result.records_failed) / total_records
            metrics['error_rate'] = batch_result.records_failed / total_records
        else:
            metrics['success_rate'] = 0.0
            metrics['error_rate'] = 0.0
        
        # Processing metrics
        if batch_result.start_time and batch_result.end_time:
            processing_time = batch_result.end_time - batch_result.start_time
            metrics['processing_time_seconds'] = processing_time.total_seconds()
            
            if total_records > 0:
                metrics['records_per_second'] = total_records / processing_time.total_seconds()
        
        # Quality metrics
        metrics['quality_score'] = quality_result.passed_checks / max(quality_result.total_checks, 1)
        
        # Issue metrics
        metrics['total_issues'] = len(quality_result.issues)
        metrics['critical_issues'] = len([
            i for i in quality_result.issues if i.severity == QualitySeverity.CRITICAL
        ])
        metrics['error_issues'] = len([
            i for i in quality_result.issues if i.severity == QualitySeverity.ERROR
        ])
        metrics['warning_issues'] = len([
            i for i in quality_result.issues if i.severity == QualitySeverity.WARNING
        ])
        
        return metrics
    
    def update_thresholds(self, new_thresholds: Dict[str, Any]):
        """Update quality check thresholds."""
        self.thresholds.update(new_thresholds)
        logger.info("Updated quality thresholds", thresholds=self.thresholds)
    
    def get_quality_report(self, quality_result: QualityCheckResult) -> Dict[str, Any]:
        """Generate a comprehensive quality report."""
        return {
            'batch_id': quality_result.batch_id,
            'job_type': quality_result.job_type.value,
            'check_timestamp': quality_result.check_timestamp.isoformat(),
            'overall_status': 'PASSED' if quality_result.passed else 'FAILED',
            'summary': {
                'total_checks': quality_result.total_checks,
                'passed_checks': quality_result.passed_checks,
                'failed_checks': quality_result.failed_checks,
                'total_issues': len(quality_result.issues)
            },
            'metrics': quality_result.metrics,
            'issues_by_severity': {
                'critical': [
                    {
                        'type': issue.check_type.value,
                        'message': issue.message,
                        'affected_records': issue.affected_records,
                        'details': issue.details
                    }
                    for issue in quality_result.issues 
                    if issue.severity == QualitySeverity.CRITICAL
                ],
                'error': [
                    {
                        'type': issue.check_type.value,
                        'message': issue.message,
                        'affected_records': issue.affected_records,
                        'details': issue.details
                    }
                    for issue in quality_result.issues 
                    if issue.severity == QualitySeverity.ERROR
                ],
                'warning': [
                    {
                        'type': issue.check_type.value,
                        'message': issue.message,
                        'affected_records': issue.affected_records,
                        'details': issue.details
                    }
                    for issue in quality_result.issues 
                    if issue.severity == QualitySeverity.WARNING
                ]
            },
            'recommendations': self._generate_recommendations(quality_result)
        }
    
    def _generate_recommendations(self, quality_result: QualityCheckResult) -> List[str]:
        """Generate recommendations based on quality issues."""
        recommendations = []
        
        # Analyze issues and provide recommendations
        critical_issues = [i for i in quality_result.issues if i.severity == QualitySeverity.CRITICAL]
        error_issues = [i for i in quality_result.issues if i.severity == QualitySeverity.ERROR]
        
        if critical_issues:
            recommendations.append("Address critical data quality issues immediately before proceeding")
        
        if error_issues:
            recommendations.append("Review and fix data validation errors")
        
        # Check for specific issue patterns
        completeness_issues = [i for i in quality_result.issues if i.check_type == QualityCheckType.COMPLETENESS]
        if completeness_issues:
            recommendations.append("Investigate data source completeness and ETL extraction logic")
        
        timeliness_issues = [i for i in quality_result.issues if i.check_type == QualityCheckType.TIMELINESS]
        if timeliness_issues:
            recommendations.append("Optimize ETL processing performance and scheduling")
        
        consistency_issues = [i for i in quality_result.issues if i.check_type == QualityCheckType.CONSISTENCY]
        if consistency_issues:
            recommendations.append("Review data relationships and referential integrity")
        
        if not recommendations:
            recommendations.append("Data quality is good - continue with normal processing")
        
        return recommendations