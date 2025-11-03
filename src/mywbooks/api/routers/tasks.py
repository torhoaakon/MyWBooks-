from datetime import datetime
from typing import Any, Sequence

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from mywbooks.api.auth import CurrentUser, get_or_create_user_by_sub
from mywbooks.db import get_db  # adjust path if needed
from mywbooks.models import Task, TaskStatus  # adjust imports

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskOut(BaseModel):
    id: int
    book_id: int
    status: TaskStatus
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    attempts: int
    payload: dict[str, Any] | None = None

    class Config:
        from_attributes = True  # SQLAlchemy 2.x compatible
        # or: orm_mode = True  (if you're still on Pydantic v1)


@router.get("/", response_model=list[TaskOut])
def list_my_tasks(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    status: TaskStatus | None = Query(
        default=None,
        description="Optional filter by task status",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Max number of tasks to return",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Offset for pagination",
    ),
) -> Sequence[Task]:
    """
    List all tasks owned by the current user.
    """

    local_user = get_or_create_user_by_sub(db, current_user)

    # 🔐 Ownership filter
    stmt = select(Task).where(Task.user_id == local_user.id)

    # Optional status filter: ?status=SUCCEEDED
    if status is not None:
        stmt = stmt.where(Task.status == status)

    # Order newest first + pagination
    stmt = stmt.order_by(Task.created_at.desc()).offset(offset).limit(limit)

    tasks: Sequence[Task] = db.scalars(stmt).all()
    return tasks
