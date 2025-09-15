from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, Optional

from mywbooks.download_manager import DownlaodManager
from mywbooks.ebook_generator import EbookGenerator, EbookGeneratorConfig

from .book import BookConfig, BookData, Chapter, ChapterRef


class WebBook(ABC):
    """Represents an online book (fiction page + chapter refs; chapters fetched on demand)."""

    bdata: BookData

    def __init__(self, bconfig: BookConfig) -> None:
        self.bdata = BookData(config=bconfig)
        self.refs = []  # will be filled by concrete subclass

    # Concrete subclasses must populate self.refs; returning it helps with ergonomics
    @abstractmethod
    def list_chapter_refs(self) -> list[ChapterRef]:
        """Return an ordered list of ChapterRef for this fiction."""
        ...

    # Concrete subclasses implement how to fetch and parse a single chapter on demand
    @abstractmethod
    def fetch_chapter(
        self,
        ref: ChapterRef,
        *,
        download_manager: DownlaodManager,
        include_images: bool = True,
        include_chapter_title: bool = True,
    ) -> Chapter:
        """Download + parse a chapter HTML into a Chapter object."""
        ...

    # Default: materialize chapters lazily using refs + fetch_chapter
    def get_chapters(
        self,
        *,
        include_images: bool = True,
        include_chapter_title: bool = True,
        download_manager: Optional[DownlaodManager] = None,
    ) -> Iterable[Chapter]:
        if not self.refs:
            self.refs = self.list_chapter_refs()
        # defer downloading until iteration
        for ref in self.refs:
            yield self.fetch_chapter(
                ref,
                download_manager=download_manager or self._require_dm_for_iter(),
                include_images=include_images,
                include_chapter_title=include_chapter_title,
            )

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

    def use_downloader_for_iteration(self, dm: DownlaodManager) -> None:
        self._iter_dm = dm

    def _require_dm_for_iter(self) -> DownlaodManager:
        if not self._iter_dm:
            raise RuntimeError(
                "DownloadManager not set. Call use_downloader_for_iteration(dm) first "
                "or iterate via to_epub(download_manager=...)"
            )
        return self._iter_dm
