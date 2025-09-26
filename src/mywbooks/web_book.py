from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterable, Optional

from pydantic_core import Url

from mywbooks import models
from mywbooks.download_manager import DownlaodManager
from mywbooks.ebook_generator import EbookGenerator, EbookGeneratorConfig

from .book import BookConfig, BookData, Chapter, ChapterRef


@DeprecationWarning
class WebBook(ABC):
    """Represents an online book (fiction page + chapter refs; chapters fetched on demand)."""

    bdata: BookData

    def __init__(
        self,
        meta: BookConfig,
        chap_refs: list[ChapterRef] = [],
        chapters: dict[ChapterRef, Chapter] = {},
        **kw: Any,
    ) -> None:
        self.bdata = BookData(config=meta)
        self.refs: list[ChapterRef] = chap_refs
        self.chapters: dict[ChapterRef, Chapter] = chapters

        self._book_model_id: int | None = kw.pop("book_model_id", None)

    @classmethod
    def from_model(cls, book: models.Book) -> "WebBook":
        return cls(BookConfig.from_model(book))

    # Concrete subclasses must populate self.refs; returning it helps with ergonomics
    @abstractmethod
    def list_chapter_refs(self) -> list[ChapterRef]:
        """Return an ordered list of ChapterRef for this fiction."""
        ...

    # Concrete subclasses implement how to fetch and parse a single chapter on demand
    @abstractmethod
    def _fetch_chapter(
        self,
        ref: ChapterRef,
        *,
        download_manager: DownlaodManager,
    ) -> Chapter:
        """Download + parse a chapter HTML into a Chapter object."""
        ...

    def get_chapter(self, ref: ChapterRef, dm: Optional[DownlaodManager]) -> Chapter:
        cptr = self.chapters.get(ref, None)
        if cptr is not None:
            return cptr

        cptr = self._fetch_chapter(
            ref, download_manager=dm or self._require_dm_for_iter()
        )
        self.chapters[ref] = cptr
        return cptr

    # Default: materialize chapters lazily using refs + fetch_chapter
    def get_chapters(
        self,
        *,
        download_manager: Optional[DownlaodManager] = None,
    ) -> Iterable[Chapter]:
        if not self.refs:
            self.refs = self.list_chapter_refs()
        for ref in self.refs:
            yield self.get_chapter(ref, download_manager)

    def to_epub(
        self,
        *,
        download_manager: DownlaodManager,
        css_filepath: Path,
        output_path: Path,
        # chapter_extractor: Optional[ChapterPageExtractor] = None,
        include_images: bool = True,
        include_chapter_titles: bool = True,
        image_resize_max: tuple[int, int] = (1024, 1024),
        book_id: Optional[str] = None,
    ) -> Path:
        """
        Build an EPUB from this WebBook using EbookGenerator.
        Returns the written output path.
        """
        cfg = EbookGeneratorConfig(
            book_config=self.bdata.config,
            css_filepath=css_filepath,
            include_images=include_images,
            include_chapter_titles=include_chapter_titles,
            image_resize_max=image_resize_max,
        )

        gen = EbookGenerator(
            book_id=book_id or self.bdata.config.title,
            download_manager=download_manager,
            config=cfg,
        )

        for ch in self.get_chapters(
            include_images=include_images,
            include_chapter_title=include_chapter_titles,
        ):
            gen.add_chapter(ch)

        gen.export_as_epub(output_path)
        return output_path

    # (Optional) If you want `get_chapters()` usable without passing dm each time,
    # you can set one via a small setter, and have _require_dm_for_iter() assert it exists.
    _iter_dm: Optional[DownlaodManager] = None

    @classmethod
    def use_downloader_for_iteration(cls, dm: DownlaodManager) -> None:
        cls._iter_dm = dm

    @classmethod
    def _require_dm_for_iter(cls) -> DownlaodManager:
        if not cls._iter_dm:
            raise RuntimeError(
                "DownloadManager not set. Call use_downloader_for_iteration(dm) first "
                "or iterate via to_epub(download_manager=...)"
            )
        return cls._iter_dm
