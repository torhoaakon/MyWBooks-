from __future__ import annotations

from bs4 import BeautifulSoup
from sqlalchemy import select

from mywbooks.utils import utcnow

from .db import SessionLocal
from .models import Book, Chapter, Provider
from .royalroad import (
    RoyalRoad_WebBook,
    RoyalRoadChapterPageExtractor,
    _get_text,
    rr_fiction_uid_from_url,
)


def upsert_royalroad_book_from_url(fiction_url: str) -> int:
    wb = RoyalRoad_WebBook(fiction_url)
    return upsert_royalroad_book(wb)


def upsert_royalroad_book(wb: RoyalRoad_WebBook) -> int:
    uid = rr_fiction_uid_from_url(wb.fiction_url)
    if not uid:
        raise ValueError("Could not extract RoyalRoad fiction id from URL")

    with SessionLocal() as db:
        book = db.execute(
            select(Book).where(Book.provider_fiction_uid == uid)
        ).scalar_one_or_none()

        if not book:
            book = Book(
                provider=Provider.ROYALROAD,
                provider_fiction_uid=uid,
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
            # keep metadata fresh
            book.title = wb.data.title or book.title
            book.author = wb.data.author or book.author
            book.cover_url = str(wb.data.cover_image) or book.cover_url
            db.commit()

        _upsert_chapter_index(wb, book.id)
        return book.id


def _upsert_chapter_index(wb: RoyalRoad_WebBook, book_id: int) -> None:
    """Insert/update Chapter rows with provider_chapter_id + URL only."""
    refs = wb.list_chapter_refs()
    with SessionLocal() as db:
        for idx, ref in enumerate(refs):
            existing = db.execute(
                select(Chapter).where(
                    Chapter.book_id == book_id,
                    Chapter.provider_chapter_id == ref.id,
                )
            ).scalar_one_or_none()

            if not existing:
                db.add(
                    Chapter(
                        book_id=book_id,
                        index=idx,
                        title=ref.title or f"Chapter {idx+1}",
                        content_html=None,
                        provider_chapter_id=ref.id,
                        source_url=ref.url,
                        is_fetched=False,
                    )
                )
            else:
                existing.index = idx
                if ref.title:
                    existing.title = ref.title
                existing.source_url = ref.url
        db.commit()


def fetch_missing_chapters_for_book(book_id: int, limit: int | None = None) -> int:
    """
    Download chapter HTML for chapters with no content yet.
    Returns number of chapters fetched.
    """
    count = 0
    with SessionLocal() as db:
        book = db.get(Book, book_id)
        if not book:
            return 0
        extractor = _select_extractor_for_book(book)

        q = (
            db.query(Chapter)
            .filter(
                Chapter.book_id == book_id,
                Chapter.content_html.is_(None),
            )
            .order_by(Chapter.index.asc())
        )

        if limit:
            q = q.limit(limit)

        chapters = q.all()

        for ch in chapters:
            html = _get_text(ch.source_url)  # or your DownloadManager
            bs = BeautifulSoup(html, "lxml")
            page = extractor.extract_chapter(bs)
            if not page or not page.content:
                continue

            ch.title = page.title or ch.title
            ch.content_html = str(page.content)
            ch.fetched_at = utcnow()
            ch.is_fetched = True
            count += 1

        db.commit()
    return count


# ----------------- helpers -----------------


def _select_extractor_for_book(book: Book):
    if book.provider == Provider.ROYALROAD:
        return RoyalRoadChapterPageExtractor()
    # elif book.provider == Provider.PATREON: return PatreonChapterPageExtractor()
    # elif ... more providers
    raise ValueError(f"No extractor for provider {book.provider}")
