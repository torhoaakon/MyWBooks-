import logging
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import NamedTuple, Optional

from bs4 import BeautifulSoup, Tag
from ebooklib import epub
from pydantic_core import Url

from mywbooks.book import BookConfig, Chapter, Image
from mywbooks.download_manager import DownlaodManager


class ChapterPageContent(NamedTuple):
    title: str
    content: Tag
    # ? image_urls: list[str]


class ChapterPageExtractor(ABC):

    @abstractmethod
    def extract_chapter(
        self, page_content_bs: BeautifulSoup
    ) -> Optional[ChapterPageContent]:
        logging.fatal("Using base {self.class.name}")
        sys.exit(1)

    def __call__(self, page_content_bs: BeautifulSoup) -> Optional[ChapterPageContent]:
        return self.extract_chapter(page_content_bs)


class EbookGeneratorConfig(NamedTuple):
    book_config: BookConfig

    css_filepath: Path  # = KINDLE_CSS_DEFAULT

    include_images: bool = True
    include_chapter_titles: bool = False
    image_resize_max: tuple[int, int] = (1024, 1024)
    epub_css_filepath: str = "style/kindle.css"

    # TODO: This should probably not include the extension
    epub_cover_image_path: str = "cover.png"
    epub_images_path: str = "images"


class EbookGenerator:
    book_id: str
    config: EbookGeneratorConfig
    chapter_page_exacter: ChapterPageExtractor

    ebook: epub.EpubBook

    chapters: list[Chapter]
    # images: dict[str, tuple[str, epub.EpubImage]]
    images_new: dict[str, Image]  #  The keys should be the src_url

    # images_new: ImageMap

    def __init__(
        self,
        book_id,
        chapter_page_exacter: ChapterPageExtractor,
        download_manager: DownlaodManager,
        config: EbookGeneratorConfig,
    ):
        self.book_id = book_id
        self.config = config
        self.chapter_page_exacter = chapter_page_exacter
        self.download_manager = download_manager
        self.chapters = []
        self.images_new = {}

    def add_chapter_page(self, page_content: str):
        # NOTE: This ChapterPageContent type is a bit strange

        bs = BeautifulSoup(page_content, features="lxml")
        extracted_content = self.chapter_page_exacter(bs)
        assert extracted_content is not None  # TODO: Log error instead

        chpr_images = self.manage_chapter_img_tags(extracted_content.content)

        self.chapters.append(
            Chapter(
                title=extracted_content.title,
                content=str(extracted_content.content),
                images=chpr_images,
            )
        )

    def manage_chapter_img_tags(self, bs: Tag):
        images: dict[str, Image] = {}

        for img in bs.select("img"):
            src_url = img.get("src")
            # logging.info("Include: ", src_url)

            # We remove image tags with no src
            if src_url is None:
                img.decompose()
                continue

            assert isinstance(src_url, str)

            im = images.get(src_url)
            if not im:
                im = self.images_new.get(src_url)
                if not im:
                    im = Image.by_src_url(src_url)
                    self.images_new[src_url] = im

                images[src_url] = im

            img["src"] = im.get_ebook_src(self.config.epub_images_path)
        return images

    # Export the generated Ebook as an epub

    def export_as_epub(self, local_epub_filepath: Path):
        ebook = epub.EpubBook()
        # mandatory metadata
        ebook.set_identifier(self.book_id)

        cf = self.config.book_config
        ebook.set_title(cf.title)
        ebook.set_language(cf.language)
        ebook.add_author(cf.author)

        with open(self.config.css_filepath, "rb") as f:
            css = epub.EpubItem(
                uid="default",
                file_name=self.config.epub_css_filepath,  # This is a bit strange ?
                media_type="text/css",
                content=f.read(),
            )
            ebook.add_item(css)

        # Add cover image
        cf.cover_image
        if cf.cover_image is not None:
            if isinstance(cf.cover_image, Url):
                cover_img_data = self.download_manager.get_and_cache_image_data(
                    cf.cover_image
                )
            elif isinstance(cf.cover_image, Path):
                with open(cf.cover_image, "rb") as f:
                    cover_img_data = f.read()
            else:
                assert False, "Unreachable"
            ebook.set_cover(self.config.epub_cover_image_path, cover_img_data)

        # Include the chapters
        chapter_count = 0
        for chtr in self.chapters:
            content = chtr.get_content(
                include_images=self.config.include_images,
                include_chapter_title=self.config.include_chapter_titles,
            )

            # We are counting the added chapters
            chapter_count += 1
            epub_chapter = epub.EpubHtml(
                title=chtr.title, file_name=f"chapter_{chapter_count}.xhtml"
            )
            epub_chapter.set_content("".join(content))

            ebook.add_item(epub_chapter)
            ebook.toc.append(epub_chapter)
            ebook.spine.append(epub_chapter)

        # Include the Images
        for _, im in self.images_new.items():
            if not im.get_image_data(
                self.download_manager, *self.config.image_resize_max
            ):
                continue

            ebook.add_item(
                epub.EpubImage(
                    uid=im.get_id(),
                    file_name=im.get_ebook_src(self.config.epub_images_path),
                    media_type=im.get_media_type(),
                    content=im.image_data,
                )
            )

        ebook.add_item(epub.EpubNcx())
        ebook.add_item(epub.EpubNav())
        epub.write_epub(local_epub_filepath, ebook)
