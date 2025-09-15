import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple, Optional

from pydantic_core import Url

from mywbooks.download_manager import DownlaodManager
from mywbooks.utils import url_hash

ImageID = str


@dataclass(init=True)
class Image:
    url: str
    url_hash: ImageID
    # image_hash ? TODO: It would be cool to hash the image itself
    image_data: Optional[bytes] = None

    @staticmethod
    def by_src_url(src_url):
        return Image(url=src_url, url_hash=url_hash(src_url))

    def get_image_data(
        self, dm: DownlaodManager, max_width, max_height
    ):  #  -> Result[bytes]:
        if self.image_data is not None:
            return self.image_data

        try:
            self.image_data = dm.get_and_cache_image_data(
                self.url, max_width=max_width, max_height=max_height
            )
            return self.image_data
        except Exception as e:
            logging.error(str(e))

            # TODO: Report this in the download status.
            return None

    def get_id(self) -> ImageID:
        return self.url_hash

    def get_extension(self) -> str:
        return "jpg"

    def get_media_type(self) -> str:
        return "image/jpg"

    def get_ebook_src(self, base_images_path: str) -> str:
        return f"{base_images_path}/{self.get_id()}.{self.get_extension()}"


@dataclass(frozen=True)
class ChapterRef:
    """Lightweight reference to a chapter that may not be downloaded yet."""

    id: str  # provider chapter id, e.g. "royalroad:21220:ch-123"
    url: str  # absolute chapter URL
    title: Optional[str] = None


class Chapter(NamedTuple):
    title: str
    content: str
    images: dict[ImageID, Image]

    source_url: Optional[str]

    def get_content(self, include_images: bool, include_chapter_title: bool) -> str:
        content: list[str] = []

        if include_chapter_title:
            content.append("<h1>%s</h1>" % self.title)

        content.append(
            str(self.content)
            if include_images
            else re.sub(r"<img.*>", "", self.content)
        )

        return "".join(content)


@dataclass
class BookConfig:
    title: str
    language: str
    author: str
    cover_image: Url | Path  # Maybe this should be image type


@dataclass
class BookData:
    """Aggregated extracted data (format agnostic)."""

    config: BookConfig
    chapters: list[Chapter] = field(default_factory=list)
    images: dict[ImageID, Image] = field(default_factory=dict)

    def add_chapter(self, chapter: Chapter) -> None:
        self.images.update(chapter.images)
        self.chapters.append(chapter)


# Export-time options (can be per-export)
@dataclass
class ExportOptions:
    include_images: bool = True
    include_chapter_titles: bool = True
    image_resize_max: tuple[int, int] = (1024, 1024)
