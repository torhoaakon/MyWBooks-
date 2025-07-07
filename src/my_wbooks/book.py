import logging
import re
from dataclasses import dataclass
from typing import NamedTuple, Optional

from pydantic_core import Url

from my_wbooks.download_manager import DownlaodManager
from my_wbooks.utils import url_hash

ImageID = str


@dataclass(init=True)
class Image:
    url: str
    url_hash: str
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


ImageMap = dict[str, Image]


class Chapter(NamedTuple):
    title: str
    content: str
    images: ImageMap

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


class BookConfig(NamedTuple):
    title: str
    language: str
    author: str
    cover_image: Url  # Maybe this should be image type
