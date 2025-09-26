from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic_core import Url
from sqlalchemy.orm import Session

from mywbooks import models
from mywbooks.book import Chapter as ChapterDTO
from mywbooks.download_manager import DownlaodManager
from mywbooks.ebook_generator import (
    EbookGenerator,
    EbookGeneratorConfig,
    ExtractOptions,
)
from mywbooks.providers import get_provider_by_key
from mywbooks.utils import utcnow

from .ingest import _upsert_book_meta  # uses list_chapter_refs()
from .ingest import _upsert_chapter_index_from_refs


def provider_for(book: models.Book) -> str:
    return book.provider.value


def upsert_fiction_toc(
    db: Session, book: models.Book, dm: DownlaodManager, *, do_inserts: bool = False
) -> int:
    """
    Updates Chapter rows for this book (provider-specific ToC discovery).
    Returns number of chapter refs discovered (not inserted count).
    """
    prov = get_provider_by_key(book.provider)
    meta, refs = prov.discover_fiction(dm, Url(book.source_url))

    _upsert_book_meta(db, prov, meta, book=book, do_inserts=do_inserts)
    _upsert_chapter_index_from_refs(db, prov, refs, book.id)
    return len(refs)


def ensure_chapter_content(
    db: Session, book: models.Book, dm: DownlaodManager, *, limit: int | None = None
) -> int:
    """
    Fill missing Chapter.content_html in DB for this book (provider-agnostic).
    Returns number of chapters fetched.
    """

    prov = get_provider_by_key(book.provider)
    q = (
        db.query(models.Chapter)
        .filter(
            models.Chapter.book_id == book.id, models.Chapter.content_html.is_(None)
        )
        .order_by(models.Chapter.index.asc())
    )
    if limit:
        q = q.limit(limit)
    chapters = q.all()

    count = 0
    for ch in chapters:
        soup = dm.get_and_cache_html(Url(ch.source_url))
        page = prov.extract_chapter(
            soup,
            options=ExtractOptions(
                url=ch.source_url, strict=True, fallback_title=ch.title
            ),
        )
        if not page or not page.content:
            continue
        ch.title = page.title or ch.title
        ch.content_html = str(page.content)
        ch.fetched_at = utcnow()
        ch.is_fetched = True
        count += 1

    db.commit()
    return count


## This should specify a collection of chapters
def export_book_to_epub_from_db(
    db: Session,
    book: models.Book,
    cfg: EbookGeneratorConfig,
    out_path: Path,
    # exp_options: ExportOptions,
    *,
    dm: DownlaodManager,
    **kw: dict[str, Any],
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
    # NOTE: This should not be necessary, since this info is retrieved on book insertion
    if not book.chapters:
        upsert_fiction_toc(db, book, dm)

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
        ensure_chapter_content(db, book, dm)

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
