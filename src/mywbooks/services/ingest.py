from __future__ import annotations

from pydantic_core import Url
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..book import BookConfig, ChapterRef
from ..download_manager import DownlaodManager
from ..models import Book, Chapter
from ..providers import Provider, ProviderKey, get_provider_by_key


def upsert_royalroad_book_from_url(
    db: Session, fiction_url: Url | str, dm: DownlaodManager
) -> int:
    prov: Provider = get_provider_by_key(ProviderKey.ROYALROAD)

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
            provider=ProviderKey.ROYALROAD,
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
            existing.source_url = str(ref.url)
    db.commit()
