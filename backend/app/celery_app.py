"""
Celery Application Configuration
Background task processing with Redis broker
"""

from celery import Celery

# Redis as message broker and result backend
REDIS_URL = "redis://localhost:6379/0"

celery_app = Celery(
    "surveyscriber",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["backend.app.tasks"]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Result expiration (24 hours)
    result_expires=86400,
    
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Process one task at a time per worker
    worker_concurrency=4,          # Number of parallel workers
    
    # Task time limits
    task_soft_time_limit=300,      # 5 minutes soft limit
    task_time_limit=600,           # 10 minutes hard limit
)
