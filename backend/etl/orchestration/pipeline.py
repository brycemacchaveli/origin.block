"""
ETL Pipeline orchestration and job management.

This module provides the main pipeline orchestration functionality including
job scheduling, execution, and monitoring.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
import asyncio
import logging
from dataclasses import dataclass, field
import uuid

import structlog

from etl.models import ETLBatch
from etl.transformers.base_transformer import BaseTransformer
from etl.transformers.customer_transformer import CustomerTransformer
from etl.transformers.loan_events_transformer import LoanEventsTransformer
from etl.transformers.compliance_events_transformer import ComplianceEventsTransformer
from etl.orchestration.types import JobType, JobStatus
from shared.database import DatabaseManager

logger = structlog.get_logger(__name__)


@dataclass
class ETLJob:
    """ETL job definition."""
    job_id: str
    job_type: JobType
    transformer_class: type
    schedule_cron: str  # Cron expression for scheduling
    description: str
    enabled: bool = True
    max_retries: int = 3
    timeout_minutes: int = 60
    dependencies: List[str] = field(default_factory=list)
    
    # Runtime fields
    status: JobStatus = JobStatus.PENDING
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    retry_count: int = 0
    error_message: Optional[str] = None


@dataclass
class PipelineRun:
    """Pipeline execution run."""
    run_id: str
    pipeline_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: JobStatus = JobStatus.RUNNING
    jobs_executed: List[str] = field(default_factory=list)
    jobs_failed: List[str] = field(default_factory=list)
    total_records_processed: int = 0
    error_message: Optional[str] = None


class ETLPipeline:
    """
    Main ETL pipeline orchestrator.
    
    Manages job scheduling, execution, dependencies, and monitoring.
    """
    
    def __init__(self, db_manager: DatabaseManager, pipeline_name: str = "blockchain_etl"):
        """Initialize ETL pipeline."""
        self.db_manager = db_manager
        self.pipeline_name = pipeline_name
        self.jobs: Dict[str, ETLJob] = {}
        self.running = False
        
        # Initialize default jobs
        self._setup_default_jobs()
        
        # Import here to avoid circular imports
        from etl.orchestration.data_quality import DataQualityChecker
        from etl.orchestration.monitoring import ETLMonitor
        
        self.data_quality_checker = DataQualityChecker(db_manager)
        self.monitor = ETLMonitor(db_manager)
    
    def _setup_default_jobs(self):
        """Setup default ETL jobs."""
        # Daily customer dimension update
        self.add_job(ETLJob(
            job_id="daily_customer_etl",
            job_type=JobType.DAILY_CUSTOMER_DIMENSION,
            transformer_class=CustomerTransformer,
            schedule_cron="0 2 * * *",  # Daily at 2 AM
            description="Daily customer dimension update with SCD Type 2",
            timeout_minutes=30
        ))
        
        # Hourly loan events processing
        self.add_job(ETLJob(
            job_id="hourly_loan_events_etl",
            job_type=JobType.HOURLY_LOAN_EVENTS,
            transformer_class=LoanEventsTransformer,
            schedule_cron="0 * * * *",  # Every hour
            description="Hourly loan application events processing",
            timeout_minutes=15
        ))
        
        # Hourly compliance events processing
        self.add_job(ETLJob(
            job_id="hourly_compliance_events_etl",
            job_type=JobType.HOURLY_COMPLIANCE_EVENTS,
            transformer_class=ComplianceEventsTransformer,
            schedule_cron="15 * * * *",  # Every hour at 15 minutes past
            description="Hourly compliance events processing",
            timeout_minutes=15
        ))
    
    def add_job(self, job: ETLJob):
        """Add job to pipeline."""
        self.jobs[job.job_id] = job
        logger.info("Added ETL job", job_id=job.job_id, job_type=job.job_type.value)
    
    def remove_job(self, job_id: str):
        """Remove job from pipeline."""
        if job_id in self.jobs:
            del self.jobs[job_id]
            logger.info("Removed ETL job", job_id=job_id)
    
    def enable_job(self, job_id: str):
        """Enable job execution."""
        if job_id in self.jobs:
            self.jobs[job_id].enabled = True
            logger.info("Enabled ETL job", job_id=job_id)
    
    def disable_job(self, job_id: str):
        """Disable job execution."""
        if job_id in self.jobs:
            self.jobs[job_id].enabled = False
            logger.info("Disabled ETL job", job_id=job_id)
    
    async def execute_job(self, job_id: str, force: bool = False) -> ETLBatch:
        """
        Execute a specific ETL job.
        
        Args:
            job_id: Job identifier
            force: Force execution even if job is disabled
            
        Returns:
            ETL batch result
        """
        if job_id not in self.jobs:
            raise ValueError(f"Job {job_id} not found")
        
        job = self.jobs[job_id]
        
        if not job.enabled and not force:
            logger.warning("Job is disabled", job_id=job_id)
            job.status = JobStatus.SKIPPED
            return None
        
        logger.info("Starting ETL job execution", job_id=job_id, job_type=job.job_type.value)
        
        job.status = JobStatus.RUNNING
        job.last_run = datetime.now(timezone.utc)
        
        try:
            # Check dependencies
            if not await self._check_dependencies(job):
                raise Exception(f"Job dependencies not met for {job_id}")
            
            # Create transformer instance
            transformer = job.transformer_class(
                self.db_manager, 
                batch_id=f"{job_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            )
            
            # Determine if incremental processing
            incremental = job.job_type != JobType.FULL_REFRESH
            kwargs = {}
            
            if incremental and job.last_run:
                # Use last successful run time for incremental processing
                kwargs['incremental'] = True
                kwargs['since_date'] = job.last_run - timedelta(hours=1)  # Small overlap
            
            # Execute transformation
            batch_result = transformer.process(**kwargs)
            
            # Run data quality checks
            quality_result = await self.data_quality_checker.check_batch_quality(
                batch_result, job.job_type
            )
            
            if not quality_result.passed:
                raise Exception(f"Data quality checks failed: {quality_result.error_message}")
            
            # Update job status
            job.status = JobStatus.SUCCESS
            job.retry_count = 0
            job.error_message = None
            
            # Record metrics
            await self.monitor.record_job_execution(job, batch_result, quality_result)
            
            logger.info("ETL job completed successfully", 
                       job_id=job_id,
                       records_processed=batch_result.records_processed,
                       records_inserted=batch_result.records_inserted)
            
            return batch_result
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.retry_count += 1
            
            logger.error("ETL job failed", 
                        job_id=job_id, 
                        error=str(e),
                        retry_count=job.retry_count)
            
            # Record failure
            await self.monitor.record_job_failure(job, str(e))
            
            # Check if retry is needed
            if job.retry_count < job.max_retries:
                logger.info("Scheduling job retry", 
                           job_id=job_id, 
                           retry_count=job.retry_count)
                # In a real implementation, this would schedule a retry
            
            raise
    
    async def _check_dependencies(self, job: ETLJob) -> bool:
        """Check if job dependencies are satisfied."""
        for dep_job_id in job.dependencies:
            if dep_job_id not in self.jobs:
                logger.error("Dependency job not found", 
                           job_id=job.job_id, 
                           dependency=dep_job_id)
                return False
            
            dep_job = self.jobs[dep_job_id]
            if dep_job.status != JobStatus.SUCCESS:
                logger.warning("Dependency job not successful", 
                             job_id=job.job_id, 
                             dependency=dep_job_id,
                             dep_status=dep_job.status.value)
                return False
        
        return True
    
    async def execute_pipeline(self, job_ids: Optional[List[str]] = None) -> PipelineRun:
        """
        Execute pipeline with specified jobs or all enabled jobs.
        
        Args:
            job_ids: Specific job IDs to execute, or None for all enabled jobs
            
        Returns:
            Pipeline run result
        """
        run_id = str(uuid.uuid4())
        pipeline_run = PipelineRun(
            run_id=run_id,
            pipeline_name=self.pipeline_name,
            start_time=datetime.now(timezone.utc)
        )
        
        logger.info("Starting pipeline execution", 
                   run_id=run_id, 
                   pipeline_name=self.pipeline_name)
        
        try:
            # Determine jobs to execute
            if job_ids is None:
                jobs_to_execute = [job for job in self.jobs.values() if job.enabled]
            else:
                jobs_to_execute = [self.jobs[job_id] for job_id in job_ids if job_id in self.jobs]
            
            # Sort jobs by dependencies (simple topological sort)
            sorted_jobs = self._sort_jobs_by_dependencies(jobs_to_execute)
            
            # Execute jobs in order
            for job in sorted_jobs:
                try:
                    batch_result = await self.execute_job(job.job_id)
                    if batch_result:
                        pipeline_run.jobs_executed.append(job.job_id)
                        pipeline_run.total_records_processed += batch_result.records_processed
                    
                except Exception as e:
                    pipeline_run.jobs_failed.append(job.job_id)
                    logger.error("Job failed in pipeline", 
                               job_id=job.job_id, 
                               error=str(e))
                    
                    # Continue with other jobs unless it's a critical dependency
                    continue
            
            # Determine overall pipeline status
            if pipeline_run.jobs_failed:
                pipeline_run.status = JobStatus.FAILED
                pipeline_run.error_message = f"Failed jobs: {', '.join(pipeline_run.jobs_failed)}"
            else:
                pipeline_run.status = JobStatus.SUCCESS
            
            pipeline_run.end_time = datetime.now(timezone.utc)
            
            logger.info("Pipeline execution completed", 
                       run_id=run_id,
                       status=pipeline_run.status.value,
                       jobs_executed=len(pipeline_run.jobs_executed),
                       jobs_failed=len(pipeline_run.jobs_failed),
                       total_records=pipeline_run.total_records_processed)
            
            return pipeline_run
            
        except Exception as e:
            pipeline_run.status = JobStatus.FAILED
            pipeline_run.error_message = str(e)
            pipeline_run.end_time = datetime.now(timezone.utc)
            
            logger.error("Pipeline execution failed", 
                        run_id=run_id, 
                        error=str(e))
            
            raise
    
    def _sort_jobs_by_dependencies(self, jobs: List[ETLJob]) -> List[ETLJob]:
        """Sort jobs by dependencies using topological sort."""
        # Simple implementation - in production, use proper topological sort
        job_dict = {job.job_id: job for job in jobs}
        sorted_jobs = []
        visited = set()
        
        def visit(job: ETLJob):
            if job.job_id in visited:
                return
            
            # Visit dependencies first
            for dep_id in job.dependencies:
                if dep_id in job_dict:
                    visit(job_dict[dep_id])
            
            visited.add(job.job_id)
            sorted_jobs.append(job)
        
        for job in jobs:
            visit(job)
        
        return sorted_jobs
    
    async def run_daily_pipeline(self):
        """Execute daily ETL pipeline."""
        daily_jobs = [
            job.job_id for job in self.jobs.values() 
            if job.job_type == JobType.DAILY_CUSTOMER_DIMENSION and job.enabled
        ]
        
        if daily_jobs:
            return await self.execute_pipeline(daily_jobs)
        else:
            logger.info("No daily jobs to execute")
    
    async def run_hourly_pipeline(self):
        """Execute hourly ETL pipeline."""
        hourly_jobs = [
            job.job_id for job in self.jobs.values() 
            if job.job_type in [JobType.HOURLY_LOAN_EVENTS, JobType.HOURLY_COMPLIANCE_EVENTS] 
            and job.enabled
        ]
        
        if hourly_jobs:
            return await self.execute_pipeline(hourly_jobs)
        else:
            logger.info("No hourly jobs to execute")
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get job status and metrics."""
        if job_id not in self.jobs:
            raise ValueError(f"Job {job_id} not found")
        
        job = self.jobs[job_id]
        return {
            'job_id': job.job_id,
            'job_type': job.job_type.value,
            'status': job.status.value,
            'enabled': job.enabled,
            'last_run': job.last_run.isoformat() if job.last_run else None,
            'next_run': job.next_run.isoformat() if job.next_run else None,
            'retry_count': job.retry_count,
            'max_retries': job.max_retries,
            'error_message': job.error_message,
            'description': job.description
        }
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get overall pipeline status."""
        job_statuses = {}
        for job_id, job in self.jobs.items():
            job_statuses[job_id] = {
                'status': job.status.value,
                'enabled': job.enabled,
                'last_run': job.last_run.isoformat() if job.last_run else None
            }
        
        return {
            'pipeline_name': self.pipeline_name,
            'total_jobs': len(self.jobs),
            'enabled_jobs': len([j for j in self.jobs.values() if j.enabled]),
            'running_jobs': len([j for j in self.jobs.values() if j.status == JobStatus.RUNNING]),
            'failed_jobs': len([j for j in self.jobs.values() if j.status == JobStatus.FAILED]),
            'jobs': job_statuses
        }