from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mywbooks.utils import utcnow

from .db import Base


class Provider(StrEnum):
    ROYALROAD = "royalroad"
    PATREON = "patreon"
    WUXIAWORLD = "wuxiaworld"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    auth_provider: Mapped[str | None] = mapped_column(
        String(40), nullable=True, index=True
    )
    auth_subject: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )

    kindle_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow())

    library: Mapped[list["BookUser"]] = relationship(
        back_populates="user", cascade="all, delete"
    )

    # Optionally, enforce uniqueness across provider+subject instead of just subject:
    __table_args__ = (
        UniqueConstraint(
            "auth_provider", "auth_subject", name="uq_user_provider_subject"
        ),
    )


class Book(Base):
    __tablename__ = "books"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    provider: Mapped[Provider] = mapped_column(Enum(Provider))
    provider_fiction_uid: Mapped[str] = mapped_column(String(128), index=True)
    source_url: Mapped[str] = mapped_column(String(1024))

    title: Mapped[str] = mapped_column(String(255))
    author: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(16), default="en")
    cover_url: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow(), onupdate=utcnow()
    )

    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )
    users: Mapped[list["BookUser"]] = relationship(
        back_populates="book", cascade="all, delete"
    )

    __table_args__ = (
        UniqueConstraint("provider_fiction_uid", name="uq_book_provider_fiction_uid"),
    )


class Chapter(Base):
    __tablename__ = "chapters"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), index=True
    )
    # order within the book; we keep as integer position
    index: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_chapter_id: Mapped[str] = mapped_column(String(32))  # e.g. "1269041"
    source_url: Mapped[str] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow())
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_fetched: Mapped[bool] = mapped_column(Boolean)

    book: Mapped[Book] = relationship(back_populates="chapters")

    __table_args__ = (
        # unique per book so re-ingests don't duplicate
        UniqueConstraint(
            "book_id", "provider_chapter_id", name="uq_chapter_book_chapid"
        ),
    )


class BookUser(Base):
    __tablename__ = "book_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), index=True
    )

    # user-specific flags
    in_library: Mapped[bool] = mapped_column(Boolean, default=True)
    want_send: Mapped[bool] = mapped_column(Boolean, default=False)  # queue to send
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="library")
    book: Mapped[Book] = relationship(back_populates="users")

    __table_args__ = (
        UniqueConstraint("user_id", "book_id", name="uq_bookuser_user_book"),
    )
