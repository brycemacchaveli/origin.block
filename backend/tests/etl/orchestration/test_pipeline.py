"""
Unit tests for ETL Pipeline orchestration.

Tests pipeline job management, execution, and dependency handling.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock, AsyncMock, patch
import asyncio

from etl.orchestration.pipeline import (
    ETLPipeline, ETLJob, PipelineRun, JobType, JobStatus, ETLScheduler
)
from etl.models import ETLBatch
from etl.transformers.base_transformer import BaseTransformer
from shared.database import DatabaseManager


class MockTransformer(BaseTransformer):
    """Mock transformer for testing."""
    
    def __init__(self, db_manager, batch_id=None, should_fail=False):
        super().__init__(batch_id)
        self.db_manager = db_manager
        self.should_fail = should_fail
    
    def extract(self, **kwargs):
        if self.should_fail:
            raise Exception("Mock extraction failed")
        return [{'id': 1, 'data': 'test'}]
    
    def transform(self, source_data):
        if self.should_fail:
            raise Exception("Mock transformation failed")
        return source_data
    
    def load(self, transformed_data):
        if self.should_fail:
            return False
        self.records_inserted = len(transformed_data)
        return True


class TestETLPipeline:
    """Test cases for ETLPipeline."""
    
    @pytest.fixture
    def mock_db_manager(self):
        """Create mock database manager."""
        return Mock(spec=DatabaseManager)
    
    @pytest.fixture
    def pipeline(self, mock_db_manager):
        """Create ETLPipeline instance."""
        return ETLPipeline(mock_db_manager, "test_pipeline")
    
    def test_init(self, mock_db_manager):
        """Test pipeline initialization."""
        pipeline = ETLPipeline(mock_db_manager, "test_pipeline")
        
        assert pipeline.pipeline_name == "test_pipeline"
        assert pipeline.db_manager == mock_db_manager
        assert len(pipeline.jobs) == 3  # Default jobs
        assert not pipeline.running
    
    def test_add_job(self, pipeline):
        """Test adding job to pipeline."""
        job = ETLJob(
            job_id="test_job",
            job_type=JobType.DAILY_CUSTOMER_DIMENSION,
            transformer_class=MockTransformer,
            schedule_cron="0 3 * * *",
            description="Test job"
        )
        
        pipeline.add_job(job)
        
        assert "test_job" in pipeline.jobs
        assert pipeline.jobs["test_job"] == job
    
    def test_remove_job(self, pipeline):
        """Test removing job from pipeline."""
        # Add a job first
        job = ETLJob(
            job_id="test_job",
            job_type=JobType.DAILY_CUSTOMER_DIMENSION,
            transformer_class=MockTransformer,
            schedule_cron="0 3 * * *",
            description="Test job"
        )
        pipeline.add_job(job)
        
        # Remove it
        pipeline.remove_job("test_job")
        
        assert "test_job" not in pipeline.jobs
    
    def test_enable_disable_job(self, pipeline):
        """Test enabling and disabling jobs."""
        job_id = list(pipeline.jobs.keys())[0]
        
        # Disable job
        pipeline.disable_job(job_id)
        assert not pipeline.jobs[job_id].enabled
        
        # Enable job
        pipeline.enable_job(job_id)
        assert pipeline.jobs[job_id].enabled
    
    @pytest.mark.asyncio
    async def test_execute_job_success(self, pipeline):
        """Test successful job execution."""
        # Add a test job
        job = ETLJob(
            job_id="test_job",
            job_type=JobType.DAILY_CUSTOMER_DIMENSION,
            transformer_class=MockTransformer,
            schedule_cron="0 3 * * *",
            description="Test job"
        )
        pipeline.add_job(job)
        
        # Mock data quality checker and monitor
        pipeline.data_quality_checker.check_batch_quality = AsyncMock()
        pipeline.data_quality_checker.check_batch_quality.return_value = Mock(
            passed=True, error_message=None
        )
        pipeline.monitor.record_job_execution = AsyncMock()
        
        # Execute job
        batch_result = await pipeline.execute_job("test_job")
        
        assert batch_result is not None
        assert batch_result.status == "SUCCESS"
        assert pipeline.jobs["test_job"].status == JobStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_execute_job_failure(self, pipeline):
        """Test job execution failure."""
        # Add a failing test job
        job = ETLJob(
            job_id="failing_job",
            job_type=JobType.DAILY_CUSTOMER_DIMENSION,
            transformer_class=lambda db, batch_id: MockTransformer(db, batch_id, should_fail=True),
            schedule_cron="0 3 * * *",
            description="Failing test job"
        )
        pipeline.add_job(job)
        
        # Mock monitor
        pipeline.monitor.record_job_failure = AsyncMock()
        
        # Execute job and expect failure
        with pytest.raises(Exception):
            await pipeline.execute_job("failing_job")
        
        assert pipeline.jobs["failing_job"].status == JobStatus.FAILED
        assert pipeline.jobs["failing_job"].retry_count == 1
    
    @pytest.mark.asyncio
    async def test_execute_job_disabled(self, pipeline):
        """Test executing disabled job."""
        job_id = list(pipeline.jobs.keys())[0]
        pipeline.disable_job(job_id)
        
        result = await pipeline.execute_job(job_id)
        
        assert result is None
        assert pipeline.jobs[job_id].status == JobStatus.SKIPPED
    
    @pytest.mark.asyncio
    async def test_execute_job_force_disabled(self, pipeline):
        """Test force executing disabled job."""
        # Add a test job and disable it
        job = ETLJob(
            job_id="test_job",
            job_type=JobType.DAILY_CUSTOMER_DIMENSION,
            transformer_class=MockTransformer,
            schedule_cron="0 3 * * *",
            description="Test job",
            enabled=False
        )
        pipeline.add_job(job)
        
        # Mock dependencies
        pipeline.data_quality_checker.check_batch_quality = AsyncMock()
        pipeline.data_quality_checker.check_batch_quality.return_value = Mock(
            passed=True, error_message=None
        )
        pipeline.monitor.record_job_execution = AsyncMock()
        
        # Force execute
        batch_result = await pipeline.execute_job("test_job", force=True)
        
        assert batch_result is not None
        assert batch_result.status == "SUCCESS"
    
    @pytest.mark.asyncio
    async def test_execute_pipeline(self, pipeline):
        """Test executing complete pipeline."""
        # Mock all jobs to succeed
        for job in pipeline.jobs.values():
            job.enabled = True
        
        # Mock dependencies
        pipeline.data_quality_checker.check_batch_quality = AsyncMock()
        pipeline.data_quality_checker.check_batch_quality.return_value = Mock(
            passed=True, error_message=None
        )
        pipeline.monitor.record_job_execution = AsyncMock()
        
        # Execute pipeline
        pipeline_run = await pipeline.execute_pipeline()
        
        assert isinstance(pipeline_run, PipelineRun)
        assert pipeline_run.status == JobStatus.SUCCESS
        assert len(pipeline_run.jobs_executed) > 0
        assert len(pipeline_run.jobs_failed) == 0
    
    @pytest.mark.asyncio
    async def test_execute_pipeline_with_failures(self, pipeline):
        """Test pipeline execution with some job failures."""
        # Add a failing job
        failing_job = ETLJob(
            job_id="failing_job",
            job_type=JobType.DAILY_CUSTOMER_DIMENSION,
            transformer_class=lambda db, batch_id: MockTransformer(db, batch_id, should_fail=True),
            schedule_cron="0 3 * * *",
            description="Failing job"
        )
        pipeline.add_job(failing_job)
        
        # Mock dependencies
        pipeline.data_quality_checker.check_batch_quality = AsyncMock()
        pipeline.data_quality_checker.check_batch_quality.return_value = Mock(
            passed=True, error_message=None
        )
        pipeline.monitor.record_job_execution = AsyncMock()
        pipeline.monitor.record_job_failure = AsyncMock()
        
        # Execute pipeline
        pipeline_run = await pipeline.execute_pipeline()
        
        assert pipeline_run.status == JobStatus.FAILED
        assert len(pipeline_run.jobs_failed) > 0
        assert "failing_job" in pipeline_run.jobs_failed
    
    def test_sort_jobs_by_dependencies(self, pipeline):
        """Test job dependency sorting."""
        # Create jobs with dependencies
        job1 = ETLJob(
            job_id="job1",
            job_type=JobType.DAILY_CUSTOMER_DIMENSION,
            transformer_class=MockTransformer,
            schedule_cron="0 3 * * *",
            description="Job 1"
        )
        
        job2 = ETLJob(
            job_id="job2",
            job_type=JobType.HOURLY_LOAN_EVENTS,
            transformer_class=MockTransformer,
            schedule_cron="0 * * * *",
            description="Job 2",
            dependencies=["job1"]
        )
        
        jobs = [job2, job1]  # Intentionally out of order
        sorted_jobs = pipeline._sort_jobs_by_dependencies(jobs)
        
        # job1 should come before job2
        job_ids = [job.job_id for job in sorted_jobs]
        assert job_ids.index("job1") < job_ids.index("job2")
    
    @pytest.mark.asyncio
    async def test_run_daily_pipeline(self, pipeline):
        """Test running daily pipeline."""
        # Mock dependencies
        pipeline.data_quality_checker.check_batch_quality = AsyncMock()
        pipeline.data_quality_checker.check_batch_quality.return_value = Mock(
            passed=True, error_message=None
        )
        pipeline.monitor.record_job_execution = AsyncMock()
        
        # Run daily pipeline
        result = await pipeline.run_daily_pipeline()
        
        # Should execute daily jobs
        if result:
            assert isinstance(result, PipelineRun)
    
    @pytest.mark.asyncio
    async def test_run_hourly_pipeline(self, pipeline):
        """Test running hourly pipeline."""
        # Mock dependencies
        pipeline.data_quality_checker.check_batch_quality = AsyncMock()
        pipeline.data_quality_checker.check_batch_quality.return_value = Mock(
            passed=True, error_message=None
        )
        pipeline.monitor.record_job_execution = AsyncMock()
        
        # Run hourly pipeline
        result = await pipeline.run_hourly_pipeline()
        
        # Should execute hourly jobs
        if result:
            assert isinstance(result, PipelineRun)
    
    def test_get_job_status(self, pipeline):
        """Test getting job status."""
        job_id = list(pipeline.jobs.keys())[0]
        
        status = pipeline.get_job_status(job_id)
        
        assert status['job_id'] == job_id
        assert 'status' in status
        assert 'enabled' in status
        assert 'description' in status
    
    def test_get_job_status_not_found(self, pipeline):
        """Test getting status for non-existent job."""
        with pytest.raises(ValueError):
            pipeline.get_job_status("nonexistent_job")
    
    def test_get_pipeline_status(self, pipeline):
        """Test getting pipeline status."""
        status = pipeline.get_pipeline_status()
        
        assert status['pipeline_name'] == "test_pipeline"
        assert 'total_jobs' in status
        assert 'enabled_jobs' in status
        assert 'jobs' in status
        assert len(status['jobs']) == len(pipeline.jobs)
    
    @pytest.mark.asyncio
    async def test_check_dependencies_success(self, pipeline):
        """Test successful dependency checking."""
        # Create jobs with dependencies
        job1 = ETLJob(
            job_id="job1",
            job_type=JobType.DAILY_CUSTOMER_DIMENSION,
            transformer_class=MockTransformer,
            schedule_cron="0 3 * * *",
            description="Job 1"
        )
        job1.status = JobStatus.SUCCESS
        
        job2 = ETLJob(
            job_id="job2",
            job_type=JobType.HOURLY_LOAN_EVENTS,
            transformer_class=MockTransformer,
            schedule_cron="0 * * * *",
            description="Job 2",
            dependencies=["job1"]
        )
        
        pipeline.add_job(job1)
        pipeline.add_job(job2)
        
        # Check dependencies
        result = await pipeline._check_dependencies(job2)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_check_dependencies_failure(self, pipeline):
        """Test failed dependency checking."""
        # Create jobs with dependencies
        job1 = ETLJob(
            job_id="job1",
            job_type=JobType.DAILY_CUSTOMER_DIMENSION,
            transformer_class=MockTransformer,
            schedule_cron="0 3 * * *",
            description="Job 1"
        )
        job1.status = JobStatus.FAILED  # Dependency failed
        
        job2 = ETLJob(
            job_id="job2",
            job_type=JobType.HOURLY_LOAN_EVENTS,
            transformer_class=MockTransformer,
            schedule_cron="0 * * * *",
            description="Job 2",
            dependencies=["job1"]
        )
        
        pipeline.add_job(job1)
        pipeline.add_job(job2)
        
        # Check dependencies
        result = await pipeline._check_dependencies(job2)
        
        assert result is False


class TestETLScheduler:
    """Test cases for ETLScheduler."""
    
    @pytest.fixture
    def mock_pipeline(self):
        """Create mock pipeline."""
        pipeline = Mock()
        pipeline.jobs = {
            "test_job": ETLJob(
                job_id="test_job",
                job_type=JobType.DAILY_CUSTOMER_DIMENSION,
                transformer_class=MockTransformer,
                schedule_cron="0 2 * * *",
                description="Test job"
            )
        }
        return pipeline
    
    def test_init(self, mock_pipeline):
        """Test scheduler initialization."""
        scheduler = ETLScheduler(mock_pipeline)
        
        assert scheduler.pipeline == mock_pipeline
        assert not scheduler.running
        assert len(scheduler.schedules) == 1
    
    def test_should_run_job_hourly(self, mock_pipeline):
        """Test hourly job scheduling logic."""
        scheduler = ETLScheduler(mock_pipeline)
        
        # Create hourly job
        job = ETLJob(
            job_id="hourly_job",
            job_type=JobType.HOURLY_LOAN_EVENTS,
            transformer_class=MockTransformer,
            schedule_cron="0 * * * *",
            description="Hourly job"
        )
        
        # Test should run (no last run)
        result = scheduler._should_run_job(job, datetime.now(timezone.utc))
        assert result is True
        
        # Test should not run (recent run)
        job.last_run = datetime.now(timezone.utc) - timedelta(minutes=30)
        result = scheduler._should_run_job(job, datetime.now(timezone.utc))
        assert result is False
        
        # Test should run (old run)
        job.last_run = datetime.now(timezone.utc) - timedelta(hours=2)
        result = scheduler._should_run_job(job, datetime.now(timezone.utc))
        assert result is True
    
    def test_should_run_job_daily(self, mock_pipeline):
        """Test daily job scheduling logic."""
        scheduler = ETLScheduler(mock_pipeline)
        
        # Create daily job
        job = ETLJob(
            job_id="daily_job",
            job_type=JobType.DAILY_CUSTOMER_DIMENSION,
            transformer_class=MockTransformer,
            schedule_cron="0 2 * * *",
            description="Daily job"
        )
        
        # Test at 2 AM (should run)
        test_time = datetime.now(timezone.utc).replace(hour=2, minute=0)
        result = scheduler._should_run_job(job, test_time)
        assert result is True
        
        # Test at different hour (should not run)
        test_time = datetime.now(timezone.utc).replace(hour=10, minute=0)
        result = scheduler._should_run_job(job, test_time)
        assert result is False
    
    def test_should_run_job_disabled(self, mock_pipeline):
        """Test disabled job should not run."""
        scheduler = ETLScheduler(mock_pipeline)
        
        job = ETLJob(
            job_id="disabled_job",
            job_type=JobType.DAILY_CUSTOMER_DIMENSION,
            transformer_class=MockTransformer,
            schedule_cron="0 2 * * *",
            description="Disabled job",
            enabled=False
        )
        
        result = scheduler._should_run_job(job, datetime.now(timezone.utc))
        assert result is False
    
    def test_should_run_job_running(self, mock_pipeline):
        """Test running job should not run again."""
        scheduler = ETLScheduler(mock_pipeline)
        
        job = ETLJob(
            job_id="running_job",
            job_type=JobType.DAILY_CUSTOMER_DIMENSION,
            transformer_class=MockTransformer,
            schedule_cron="0 2 * * *",
            description="Running job"
        )
        job.status = JobStatus.RUNNING
        
        result = scheduler._should_run_job(job, datetime.now(timezone.utc))
        assert result is False