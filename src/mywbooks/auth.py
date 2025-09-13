from __future__ import annotations

from argon2 import PasswordHasher
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import User

_ph = PasswordHasher()


def create_user(email: str, password: str, kindle_email: str | None = None) -> int:
    with SessionLocal() as db:
        exists = db.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()
        if exists:
            raise ValueError("Email already registered")
        user = User(
            email=email,
            password_hash=_ph.hash(password),
            kindle_email=kindle_email,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id


def verify_user(email: str, password: str) -> int | None:
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if not user:
            return None
        try:
            _ph.verify(user.password_hash, password)
            return user.id
        except Exception:
            return None
