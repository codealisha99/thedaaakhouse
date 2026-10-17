"""Queue delivery. Redis/RQ is the optional transport; PostgreSQL is the
source of truth. If Redis is not configured (or publishing fails) the outbox
row stays pending and the dispatcher retries publication later, so no accepted
work can be lost by a queue outage.

Tests may monkeypatch ``publish`` or set ``app.workflows.queue.publisher``.
"""

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

#: Populated with a custom callable by tests: f(task_id) -> published(bool)
publisher = None


def redis_configured() -> bool:
    return bool(get_settings().redis_url.strip())


def publish(task_id: str) -> bool:
    """Deliver one task to the queue. Returns True if the task was handed to
    a queue consumer; False signals 'leave the outbox row pending'."""
    if publisher is not None:
        return bool(publisher(task_id))
    return publish_rq(task_id)


def publish_rq(task_id: str) -> bool:
    if not redis_configured():
        return False
    import redis
    import rq

    settings = get_settings()
    conn = redis.from_url(settings.redis_url)
    queue = rq.Queue(settings.redis_queue_name, connection=conn)
    job = queue.enqueue(
        "app.workflows.executor.perform_task",
        task_id=task_id,
        job_timeout=settings.wf_lease_seconds + 60,
    )
    log.info("published task %s to %s as job %s", task_id, settings.redis_queue_name, job.id)
    return True
