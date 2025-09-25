from __future__ import annotations

from bs4 import BeautifulSoup
from pydantic_core import Url
from sqlalchemy import select
from sqlalchemy.orm import Session

from mywbooks import models
from mywbooks.book import BookConfig, ChapterRef
from mywbooks.download_manager import DownlaodManager
from mywbooks.providers import get_provider_by_key
from mywbooks.utils import utcnow

from ..models import Book, Chapter, Provider


def upsert_royalroad_book_from_url(
    db: Session, fiction_url: Url | str, dm: DownlaodManager
) -> int:
    prov = get_provider_by_key(Provider.ROYALROAD)

    meta: BookConfig
    refs: list[ChapterRef]
    meta, refs = prov.discover_fiction(dm, Url(str(fiction_url)))

    uid = prov.fiction_uid_from_url(str(fiction_url))
    if not uid:
        raise ValueError("Could not extract RoyalRoad fiction id from URL")
    book_id = _upsert_book_meta(
        db, prov, meta, uid, source_url=str(fiction_url), do_inserts=True
    )

    _upsert_chapter_index_from_refs(db, prov, refs, book_id)
    return book_id


def _upsert_book_meta(
    db: Session,
    prov: Provider,
    meta: BookConfig,
    fiction_uid: str | None = None,
    *,
    book: models.Book | None = None,
    source_url: str | None = None,
    do_inserts: bool = False,
) -> int:

    ## If book is not provided, look for it by fiction_id
    if not book:
        book = db.execute(
            select(Book).where(Book.provider_fiction_uid == fiction_uid)
        ).scalar_one_or_none()

    # Book entry does not exits
    if not book:
        if not do_inserts:
            raise RuntimeError(
                "Failed to find entry for fiction_uid: {fiction_uid}. And inserts are disabled (to enable, set argument `do_inserts=True`)"
            )

        if source_url is None:
            raise RuntimeError("source_url was not provided for new insert")

        book = Book(
            provider=Provider.ROYALROAD,
            provider_fiction_uid=fiction_uid,
            source_url=source_url,
            title=meta.title,
            author=meta.author,
            language=meta.language,
            cover_url=str(meta.cover_image),
        )
        db.add(book)
        db.commit()
        db.refresh(book)
    else:
        # keep metadata fresh
        book.title = meta.title or book.title
        book.author = meta.author or book.author
        book.cover_url = str(meta.cover_image) or book.cover_url
        db.commit()

    return book.id


def _upsert_chapter_index_from_refs(
    db: Session, prov: Provider, refs: list[ChapterRef], book_id: int
) -> None:
    """Insert/update Chapter rows with provider_chapter_id + URL only."""

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


def fetch_missing_chapters_for_book(
    db: Session, book_id: int, limit: int | None = None
) -> int:
    """
    Download chapter HTML for chapters with no content yet.
    Returns number of chapters fetched.
    """
    count = 0

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
