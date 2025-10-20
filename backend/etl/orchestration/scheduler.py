"""
ETL Job Scheduler for automated pipeline execution.

This module provides scheduling capabilities for ETL jobs including
cron-based scheduling, job queuing, and execution management.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Callable
import asyncio
import signal
import sys
from dataclasses import dataclass
from enum import Enum
import uuid

import structlog

from etl.orchestration.types import JobType, JobStatus

logger = structlog.get_logger(__name__)


class ScheduleType(Enum):
    """Schedule types for ETL jobs."""
    CRON = "cron"
    INTERVAL = "interval"
    MANUAL = "manual"


@dataclass
class JobSchedule:
    """Job schedule configuration."""
    job_id: str
    schedule_type: ScheduleType
    cron_expression: Optional[str] = None
    interval_minutes: Optional[int] = None
    enabled: bool = True
    next_run_time: Optional[datetime] = None
    last_run_time: Optional[datetime] = None


class CronParser:
    """
    Simple cron expression parser.
    
    In production, use a proper library like croniter.
    """
    
    @staticmethod
    def parse_cron(cron_expr: str) -> Dict[str, Any]:
        """Parse cron expression into components."""
        parts = cron_expr.strip().split()
        
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {cron_expr}")
        
        return {
            'minute': parts[0],
            'hour': parts[1],
            'day': parts[2],
            'month': parts[3],
            'weekday': parts[4]
        }
    
    @staticmethod
    def next_run_time(cron_expr: str, from_time: datetime = None) -> datetime:
        """Calculate next run time for cron expression."""
        if from_time is None:
            from_time = datetime.now(timezone.utc)
        
        try:
            cron_parts = CronParser.parse_cron(cron_expr)
            
            # Simple implementation for common patterns
            # In production, use croniter library
            
            # Handle hourly jobs (0 * * * *)
            if cron_parts['minute'] == '0' and cron_parts['hour'] == '*':
                next_hour = from_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                return next_hour
            
            # Handle specific minute each hour (15 * * * *)
            if cron_parts['minute'].isdigit() and cron_parts['hour'] == '*':
                minute = int(cron_parts['minute'])
                next_run = from_time.replace(minute=minute, second=0, microsecond=0)
                if next_run <= from_time:
                    next_run += timedelta(hours=1)
                return next_run
            
            # Handle daily jobs (0 2 * * *)
            if (cron_parts['minute'] == '0' and 
                cron_parts['hour'].isdigit() and 
                cron_parts['day'] == '*'):
                hour = int(cron_parts['hour'])
                next_run = from_time.replace(hour=hour, minute=0, second=0, microsecond=0)
                if next_run <= from_time:
                    next_run += timedelta(days=1)
                return next_run
            
            # Default: run in 1 hour
            return from_time + timedelta(hours=1)
            
        except Exception as e:
            logger.error("Failed to parse cron expression", 
                        cron_expr=cron_expr, 
                        error=str(e))
            # Default to 1 hour from now
            return from_time + timedelta(hours=1)


class ETLScheduler:
    """
    ETL job scheduler with cron-like scheduling capabilities.
    
    Manages job scheduling, execution queuing, and lifecycle management.
    """
    
    def __init__(self, pipeline):
        """Initialize ETL scheduler."""
        self.pipeline = pipeline
        self.schedules: Dict[str, JobSchedule] = {}
        self.running = False
        self.scheduler_task: Optional[asyncio.Task] = None
        self.job_queue: asyncio.Queue = asyncio.Queue()
        self.worker_tasks: List[asyncio.Task] = []
        self.max_concurrent_jobs = 3
        
        # Initialize schedules from pipeline jobs
        self._initialize_schedules()
    
    def _initialize_schedules(self):
        """Initialize job schedules from pipeline configuration."""
        for job_id, job in self.pipeline.jobs.items():
            schedule = JobSchedule(
                job_id=job_id,
                schedule_type=ScheduleType.CRON,
                cron_expression=job.schedule_cron,
                enabled=job.enabled
            )
            
            # Calculate initial next run time
            if schedule.enabled and schedule.cron_expression:
                schedule.next_run_time = CronParser.next_run_time(schedule.cron_expression)
            
            self.schedules[job_id] = schedule
            
            logger.info("Initialized job schedule", 
                       job_id=job_id,
                       cron_expr=job.schedule_cron,
                       next_run=schedule.next_run_time.isoformat() if schedule.next_run_time else None)
    
    async def start(self):
        """Start the scheduler."""
        if self.running:
            logger.warning("Scheduler is already running")
            return
        
        self.running = True
        logger.info("Starting ETL scheduler", 
                   max_concurrent_jobs=self.max_concurrent_jobs)
        
        # Start scheduler task
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        # Start worker tasks
        for i in range(self.max_concurrent_jobs):
            worker_task = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self.worker_tasks.append(worker_task)
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        logger.info("ETL scheduler started successfully")
    
    async def stop(self):
        """Stop the scheduler gracefully."""
        if not self.running:
            return
        
        logger.info("Stopping ETL scheduler...")
        self.running = False
        
        # Cancel scheduler task
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        
        # Cancel worker tasks
        for worker_task in self.worker_tasks:
            worker_task.cancel()
        
        # Wait for workers to finish
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        
        logger.info("ETL scheduler stopped")
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info("Received shutdown signal", signal=signum)
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def _scheduler_loop(self):
        """Main scheduler loop that checks for jobs to run."""
        logger.info("Scheduler loop started")
        
        try:
            while self.running:
                current_time = datetime.now(timezone.utc)
                
                # Check each job schedule
                for job_id, schedule in self.schedules.items():
                    if not schedule.enabled:
                        continue
                    
                    if schedule.next_run_time and current_time >= schedule.next_run_time:
                        # Check if job is already running
                        job = self.pipeline.jobs.get(job_id)
                        if job and job.status != JobStatus.RUNNING:
                            logger.info("Scheduling job for execution", 
                                       job_id=job_id,
                                       scheduled_time=schedule.next_run_time.isoformat())
                            
                            # Queue job for execution
                            await self.job_queue.put({
                                'job_id': job_id,
                                'scheduled_time': schedule.next_run_time,
                                'execution_id': str(uuid.uuid4())
                            })
                            
                            # Update schedule for next run
                            if schedule.cron_expression:
                                schedule.next_run_time = CronParser.next_run_time(
                                    schedule.cron_expression, 
                                    current_time
                                )
                            elif schedule.interval_minutes:
                                schedule.next_run_time = current_time + timedelta(
                                    minutes=schedule.interval_minutes
                                )
                
                # Sleep for a short interval before checking again
                await asyncio.sleep(30)  # Check every 30 seconds
                
        except asyncio.CancelledError:
            logger.info("Scheduler loop cancelled")
        except Exception as e:
            logger.error("Scheduler loop error", error=str(e))
            if self.running:
                # Restart scheduler loop after error
                await asyncio.sleep(60)
                if self.running:
                    self.scheduler_task = asyncio.create_task(self._scheduler_loop())
    
    async def _worker_loop(self, worker_name: str):
        """Worker loop that executes queued jobs."""
        logger.info("Worker started", worker=worker_name)
        
        try:
            while self.running:
                try:
                    # Wait for job from queue
                    job_info = await asyncio.wait_for(
                        self.job_queue.get(), 
                        timeout=1.0
                    )
                    
                    job_id = job_info['job_id']
                    execution_id = job_info['execution_id']
                    
                    logger.info("Worker executing job", 
                               worker=worker_name,
                               job_id=job_id,
                               execution_id=execution_id)
                    
                    # Execute the job
                    try:
                        batch_result = await self.pipeline.execute_job(job_id)
                        
                        # Update schedule last run time
                        if job_id in self.schedules:
                            self.schedules[job_id].last_run_time = datetime.now(timezone.utc)
                        
                        logger.info("Worker completed job", 
                                   worker=worker_name,
                                   job_id=job_id,
                                   execution_id=execution_id,
                                   status="success")
                        
                    except Exception as e:
                        logger.error("Worker job execution failed", 
                                   worker=worker_name,
                                   job_id=job_id,
                                   execution_id=execution_id,
                                   error=str(e))
                    
                    # Mark task as done
                    self.job_queue.task_done()
                    
                except asyncio.TimeoutError:
                    # No job available, continue loop
                    continue
                    
        except asyncio.CancelledError:
            logger.info("Worker cancelled", worker=worker_name)
        except Exception as e:
            logger.error("Worker error", worker=worker_name, error=str(e))
    
    def add_job_schedule(
        self, 
        job_id: str, 
        cron_expression: Optional[str] = None,
        interval_minutes: Optional[int] = None
    ):
        """Add or update job schedule."""
        if job_id not in self.pipeline.jobs:
            raise ValueError(f"Job {job_id} not found in pipeline")
        
        if cron_expression:
            schedule_type = ScheduleType.CRON
            next_run_time = CronParser.next_run_time(cron_expression)
        elif interval_minutes:
            schedule_type = ScheduleType.INTERVAL
            next_run_time = datetime.now(timezone.utc) + timedelta(minutes=interval_minutes)
        else:
            schedule_type = ScheduleType.MANUAL
            next_run_time = None
        
        schedule = JobSchedule(
            job_id=job_id,
            schedule_type=schedule_type,
            cron_expression=cron_expression,
            interval_minutes=interval_minutes,
            next_run_time=next_run_time,
            enabled=True
        )
        
        self.schedules[job_id] = schedule
        
        logger.info("Added job schedule", 
                   job_id=job_id,
                   schedule_type=schedule_type.value,
                   next_run=next_run_time.isoformat() if next_run_time else None)
    
    def enable_job_schedule(self, job_id: str):
        """Enable job schedule."""
        if job_id in self.schedules:
            self.schedules[job_id].enabled = True
            
            # Recalculate next run time
            schedule = self.schedules[job_id]
            if schedule.cron_expression:
                schedule.next_run_time = CronParser.next_run_time(schedule.cron_expression)
            elif schedule.interval_minutes:
                schedule.next_run_time = datetime.now(timezone.utc) + timedelta(
                    minutes=schedule.interval_minutes
                )
            
            logger.info("Enabled job schedule", job_id=job_id)
    
    def disable_job_schedule(self, job_id: str):
        """Disable job schedule."""
        if job_id in self.schedules:
            self.schedules[job_id].enabled = False
            self.schedules[job_id].next_run_time = None
            logger.info("Disabled job schedule", job_id=job_id)
    
    async def trigger_job_now(self, job_id: str) -> str:
        """Manually trigger a job for immediate execution."""
        if job_id not in self.pipeline.jobs:
            raise ValueError(f"Job {job_id} not found")
        
        execution_id = str(uuid.uuid4())
        
        await self.job_queue.put({
            'job_id': job_id,
            'scheduled_time': datetime.now(timezone.utc),
            'execution_id': execution_id,
            'manual_trigger': True
        })
        
        logger.info("Manually triggered job", 
                   job_id=job_id,
                   execution_id=execution_id)
        
        return execution_id
    
    def get_schedule_status(self) -> Dict[str, Any]:
        """Get current schedule status for all jobs."""
        current_time = datetime.now(timezone.utc)
        
        schedule_status = {}
        for job_id, schedule in self.schedules.items():
            job = self.pipeline.jobs.get(job_id)
            
            schedule_status[job_id] = {
                'enabled': schedule.enabled,
                'schedule_type': schedule.schedule_type.value,
                'cron_expression': schedule.cron_expression,
                'interval_minutes': schedule.interval_minutes,
                'next_run_time': schedule.next_run_time.isoformat() if schedule.next_run_time else None,
                'last_run_time': schedule.last_run_time.isoformat() if schedule.last_run_time else None,
                'job_status': job.status.value if job else 'unknown',
                'time_until_next_run': (
                    (schedule.next_run_time - current_time).total_seconds() 
                    if schedule.next_run_time and schedule.next_run_time > current_time 
                    else None
                )
            }
        
        return {
            'scheduler_running': self.running,
            'current_time': current_time.isoformat(),
            'queue_size': self.job_queue.qsize(),
            'active_workers': len([t for t in self.worker_tasks if not t.done()]),
            'schedules': schedule_status
        }
    
    async def run_daily_schedule(self):
        """Execute all daily scheduled jobs."""
        daily_jobs = [
            job_id for job_id, schedule in self.schedules.items()
            if (schedule.enabled and 
                schedule.cron_expression and 
                '2 * * *' in schedule.cron_expression)  # Daily at 2 AM
        ]
        
        logger.info("Running daily schedule", jobs=daily_jobs)
        
        for job_id in daily_jobs:
            await self.trigger_job_now(job_id)
    
    async def run_hourly_schedule(self):
        """Execute all hourly scheduled jobs."""
        hourly_jobs = [
            job_id for job_id, schedule in self.schedules.items()
            if (schedule.enabled and 
                schedule.cron_expression and 
                '* * * *' in schedule.cron_expression)  # Hourly
        ]
        
        logger.info("Running hourly schedule", jobs=hourly_jobs)
        
        for job_id in hourly_jobs:
            await self.trigger_job_now(job_id)


# CLI interface for scheduler management
async def main():
    """Main function for running the scheduler as a standalone service."""
    from shared.database import DatabaseManager
    
    # Initialize components
    db_manager = DatabaseManager()
    pipeline = ETLPipeline(db_manager)
    scheduler = ETLScheduler(pipeline)
    
    try:
        # Start scheduler
        await scheduler.start()
        
        # Keep running until interrupted
        while scheduler.running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await scheduler.stop()


if __name__ == "__main__":
    asyncio.run(main())