from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from bs4 import BeautifulSoup
from pydantic_core import Url

from mywbooks import models
from mywbooks.book import BookConfig, ChapterRef
from mywbooks.download_manager import DownlaodManager
from mywbooks.ebook_generator import ChapterPageContent, ExtractOptions


class Provider(ABC):
    """Stateless provider interface. No ORM/DTO state inside."""

    @classmethod
    def provider_key(cls) -> str:
        assert hasattr(
            cls, "_provider_key"
        ), "Invalid provider class, has not '_provider_key' attribute. Ensure that the class was obtained using the .providers.get_provider_by_key function"
        return getattr(cls, "_provider_key")

    # Identify a fiction (used for upsert / dedupe)
    @abstractmethod
    def fiction_uid_from_url(self, url: str) -> str | None: ...

    # Discover metadata + ToC from a fiction page
    @abstractmethod
    def discover_fiction(
        self, dm: DownlaodManager, fiction_url: Url
    ) -> tuple[BookConfig, list[ChapterRef]]: ...

    # Extract a chapter’s title+content from its page
    @abstractmethod
    def extract_chapter(
        self, soup: BeautifulSoup, *, options: Optional[ExtractOptions] = None
    ) -> ChapterPageContent | None: ...

    ### Maybe
    @abstractmethod
    def canonical_chapter_url(self, chapter_id_prefixed: str) -> str: ...
