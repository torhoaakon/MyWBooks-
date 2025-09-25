from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic_core import Url
from sqlalchemy import select
from sqlalchemy.orm import Session

from mywbooks import models
from mywbooks.book import BookConfig
from mywbooks.book import Chapter as ChapterDTO  # DTO layer
from mywbooks.book import ExportOptions
from mywbooks.download_manager import DownlaodManager
from mywbooks.ebook_generator import EbookGenerator, EbookGeneratorConfig
from mywbooks.ingest import _upsert_chapter_index  # uses list_chapter_refs()
from mywbooks.ingest import (
    fetch_missing_chapters_for_book,
)  # fills content_html/is_fetched
from mywbooks.royalroad import RoyalRoad_WebBook  # provides list_chapter_refs + parsing


def provider_for(book: models.Book) -> str:
    return book.provider.value


def ensure_toc(db: Session, book: models.Book, dm: DownlaodManager) -> int:
    """
    Ensure Chapter rows exist for this book (provider-specific ToC discovery).
    Returns number of chapter refs discovered (not inserted count).
    """
    # Dispatch by provider; only RoyalRoad implemented now.
    if book.provider == models.Provider.ROYALROAD:
        wb = RoyalRoad_WebBook.from_fiction_url(Url(book.source_url), dm)  # parse ToC
        _upsert_chapter_index(db, wb, book.id)  # writes Chapter rows
        return len(wb.list_chapter_refs())

    raise ValueError(f"No ToC strategy for provider {book.provider}")


def ensure_chapter_content(
    db: Session, book: models.Book, *, limit: int | None = None
) -> int:
    """
    Fill missing Chapter.content_html in DB for this book (provider-agnostic).
    Returns number of chapters fetched.
    """

    ## This should be using the various providers,
    #   fetch_missing_chapters_for_book (is deprecated) should not be used

    return fetch_missing_chapters_for_book(db, book.id, limit=limit)


## This should specify a collection of chapters
def export_book_to_epub_from_db(
    db: Session,
    book: models.Book,
    cfg: EbookGeneratorConfig,
    out_path: Path,
    # exp_options: ExportOptions,
    *,
    dm: DownlaodManager,
    **kw,
    # css_path: Path,
    # out_path: Path,
    # include_images: bool = True,
    # include_chapter_titles: bool = True,
    # image_resize_max: tuple[int, int] = (1024, 1024),
) -> Path:
    """
    Build an EPUB purely from DB rows (Book + fetched Chapters).
    If some chapters aren’t fetched yet, call ensure_chapter_content() first.
    """
    # Ensure at least one ToC row exists (no-op if already present)
    if not book.chapters:
        ensure_toc(db, book, dm)

    # If anything is missing HTML, fetch it now.
    missing = (
        db.query(models.Chapter)
        .filter(
            models.Chapter.book_id == book.id,
            models.Chapter.content_html.is_(None),
        )
        .count()
    )
    if missing:
        ensure_chapter_content(db, book)

    # Prepare generator config from DB-only metadata
    gen = EbookGenerator(
        book_id=f"book-{book.id}",
        download_manager=dm,
        config=cfg,
    )

    # Stream chapters from DB, in order
    rows = (
        db.query(models.Chapter)
        .filter(
            models.Chapter.book_id == book.id, models.Chapter.is_fetched == True
        )  # noqa: E712
        .order_by(models.Chapter.index.asc())
        .all()
    )
    for chm in rows:
        dto = ChapterDTO.from_model(
            chm
        )  # builds a Chapter DTO with images map, etc. :contentReference[oaicite:1]{index=1}
        gen.add_chapter(dto)

    gen.export_as_epub(out_path)
    return out_path
