from __future__ import annotations

import re
from typing import Any, Iterable, Optional, override
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from pydantic_core import Url

from mywbooks import models
from mywbooks.download_manager import DownlaodManager

from .book import BookConfig, Chapter, ChapterRef, Image
from .utils import url_hash
from .web_book import WebBook

PROVIDER_PREFIX = "royalroad"


class RoyalRoad_WebBook(WebBook):
    """Concrete WebBook for a RoyalRoad fiction page."""

    def __init__(self, meta: BookConfig, chap_refs: list[ChapterRef] = [], **kw: Any):
        super().__init__(meta, chap_refs, **kw)
        self._extractor = RoyalRoadChapterPageExtractor()

        self.fiction_url = kw.pop("fiction_url", None)

    @classmethod
    def from_fiction_url(
        cls, fiction_url: Url, dm: Optional[DownlaodManager]
    ) -> "RoyalRoad_WebBook":
        dm = dm or cls._require_dm_for_iter()

        html = dm.get_and_cache_data(fiction_url).decode("utf-8")
        meta, chapter_urls = _parse_fiction_page(str(fiction_url), html, strict=True)

        chap_refs = [
            ChapterRef(
                id=chapter_id_from_url(u) or "", url=u, title=None
            )  # TODO: Needs to handle id_from_url failing
            for u in chapter_urls
        ]

        return cls(meta, chap_refs, fiction_url=fiction_url)

    @override
    @classmethod
    def from_model(cls, book: models.Book) -> RoyalRoad_WebBook:
        meta = BookConfig.from_model(book)

        chap_refs = []
        if book.chapters:
            # keep DB order
            for ch in sorted(book.chapters, key=lambda c: c.index):
                chap_refs.append(
                    ChapterRef(
                        id=ch.provider_chapter_id, url=ch.source_url, title=ch.title
                    )
                )
                if ch.is_fetched:
                    Chapter.from_model(ch)

        return cls(
            meta, chap_refs, fiction_url=Url(book.source_url), book_model_id=book.id
        )

    def list_chapter_refs(self) -> list[ChapterRef]:
        if self.refs:
            return self.refs

        # Otherwise, lazy-fetch ToC from the fiction page,
        # but DO NOT stash metadata that contradicts DB — just populate refs.
        dm = self._require_dm_for_iter()
        html = dm.get_and_cache_data(self.fiction_url).decode("utf-8")
        _meta, chapter_urls = _parse_fiction_page(
            str(self.fiction_url), html, strict=True
        )  # meta ignored
        self.refs = [
            ChapterRef(id=chapter_id_from_url(u) or "", url=u, title=None)
            for u in chapter_urls
        ]
        return self.refs

    @override
    def _fetch_chapter(
        self,
        ref: ChapterRef,
        *,
        download_manager: DownlaodManager,
    ) -> Chapter:
        html = download_manager.get_and_cache_html(Url(ref.url))  # soup
        page = self._extractor.extract_chapter(html)
        content_html = str(page.content)

        # Build image map from the HTML (by URL); rewriting to packaged paths happens in the generator
        images = {}
        for tag in html.select("img[src]"):
            src = tag["src"].strip()
            full = src if src.startswith("http") else urljoin(ref.url, src)
            images[url_hash(full)] = Image.by_src_url(full)

        return Chapter(
            title=page.title or ref.title or "Untitled",
            content=content_html,
            images=images,
            source_url=ref.url,
        )
