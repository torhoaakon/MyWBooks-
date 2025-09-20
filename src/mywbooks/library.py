from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import BookUser


def add_book_to_user(db: Session, user_id: int, book_id: int) -> None:
    existing = db.execute(
        select(BookUser).where(BookUser.user_id == user_id, BookUser.book_id == book_id)
    ).scalar_one_or_none()
    if not existing:
        db.add(BookUser(user_id=user_id, book_id=book_id, in_library=True))
        db.commit()
