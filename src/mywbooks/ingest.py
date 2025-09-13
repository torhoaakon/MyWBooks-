from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Book, Chapter, Provider
from .royalroad import RoyalRoad_WebBook, RoyalRoad_WebBookData, chapter_id_from_url


def upsert_royalroad_book_from_url(fiction_url: str) -> int:
    """
    Fetch a RoyalRoad fiction page, parse chapters via your WebBook,
    and upsert into the DB. Returns book_id.
    """
    wb = RoyalRoad_WebBook(fiction_url)
    return upsert_royalroad_book(wb)


def upsert_royalroad_book(wb: RoyalRoad_WebBook) -> int:

    with SessionLocal() as db:
        # Find or create book
        book = db.execute(
            select(Book).where(
                Book.provider == Provider.ROYALROAD,
                Book.source_url == wb.fiction_url,
            )
        ).scalar_one_or_none()

        if not book:
            book = Book(
                provider=Provider.ROYALROAD,
                source_url=wb.fiction_url,
                title=wb.data.title,
                author=wb.data.author,
                language=wb.data.language,
                cover_url=str(wb.data.cover_image),
            )
            db.add(book)
            db.commit()
            db.refresh(book)
        else:
            # Update basic metadata (optional)
            book.title = wb.data.title or book.title
            book.author = wb.data.author or book.author
            book.cover_url = str(wb.data.cover_image) or book.cover_url
            db.commit()

        db.commit()
        return book.id


def upsert_chapters(wb: RoyalRoad_WebBook, book: Book):
    # Upsert chapters
    with SessionLocal() as db:
        idx = 0
        for ch in wb.get_chapters(include_images=True, include_chapter_title=True):
            chap_id = (
                chapter_id_from_url(ch.source_url) if chsource_url is not None else None
            )
            # If Chapter class doesn't store source_url yet, you can pass the URL via a small wrapper
            # For now, fall back to idx as unique position if we don't have chap_id
            chap_id = chap_id or str(idx)

            existing = db.execute(
                select(Chapter).where(
                    Chapter.book_id == book.id,
                    Chapter.provider_chapter_id == chap_id,
                )
            ).scalar_one_or_none()

            if not existing:
                db.add(
                    Chapter(
                        book_id=book.id,
                        index=idx,
                        title=ch.title or f"Chapter {idx+1}",
                        content_html=ch.get_content(
                            include_images=True, include_chapter_title=True
                        ),
                        provider_chapter_id=chap_id,
                        source_url=ch.source_url if hasattr(ch, "source_url") else "",
                    )
                )
            else:
                # Optional: update content/title if changed
                existing.title = ch.title or existing.title
                existing.content_html = ch.get_content(
                    include_images=True, include_chapter_title=True
                )

            idx += 1
