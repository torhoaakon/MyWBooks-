from __future__ import annotations

from sqlalchemy import select

from .db import get_db
from .models import BookUser


def add_book_to_user(user_id: int, book_id: int) -> None:
    with get_db() as db:

        print(db, user_id, book_id)

        existing = db.execute(
            select(BookUser).where(
                BookUser.user_id == user_id, BookUser.book_id == book_id
            )
        ).scalar_one_or_none()
        if not existing:
            db.add(BookUser(user_id=user_id, book_id=book_id, in_library=True))
            db.commit()
