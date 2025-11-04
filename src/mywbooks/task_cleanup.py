from collections.abc import Callable
from datetime import timedelta

from mywbooks.models import Task, TaskStatus

# Table of time to retain tasks before deletion depending on status
TASK_RETENTION = {
    TaskStatus.SUCCEEDED: timedelta(days=7),
    TaskStatus.FAILED: timedelta(days=30),
    # TaskStatus.QUEUED:   infinite
    # TaskStatus.RUNNING:   infinite
}


CleanupHandler = Callable[[Task], None]
CLEANUP_HANDLERS: dict[str, CleanupHandler] = {}


def register_cleanup(task_type: str):
    """
    Wrapper for registering a task clean-up handler
    """

    def wrapper(fn: CleanupHandler) -> CleanupHandler:
        CLEANUP_HANDLERS[task_type] = fn
        return fn

    return wrapper


def run_task_cleanup(task: Task) -> None:
    """
    This function is called when a task is deleted
    """
    handler = CLEANUP_HANDLERS.get(task.type)
    if handler:
        handler(task)
