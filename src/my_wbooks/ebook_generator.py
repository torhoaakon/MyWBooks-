import logging
import sys
from abc import abstractmethod
from pathlib import Path
from re import A
from typing import Optional

from bs4 import BeautifulSoup
from ebooklib import epub
from pydantic import BaseModel
from pydantic_core import Url

from my_wbooks import download_manager


class ChapterContent:
    title: str
    content: BeautifulSoup
    # ? image_urls: list[str]


class ChapterPageExtractor:

    @abstractmethod
    def extract_chapter(self, page_content_bs: BeautifulSoup) -> ChapterContent:
        logging.fatal("Using base {self.class.name}")
        sys.exit(1)

    def __call__(self, page_content_bs: BeautifulSoup) -> ChapterContent:
        return self.extract_chapter(page_content_bs)


class EbookGeneratorConfig(BaseModel):
    include_images: bool = True
    book_title: str
    book_language: str
    book_author: str
    book_cover_image: Path

    css_filepath: Path  # = KINDLE_CSS_DEFAULT

    image_resize_max: tuple[int, int] = (1024, 1024)
    chapter_page_exacter: ChapterPageExtractor
    download_manager: download_manager.DownlaodManager

    epub_css_filepath: str = "style/kindle.css"

    # TODO: This should probably not include the extension
    epub_cover_image_path: str = "cover.png"


class EbookGenerator:
    book_id: str
    config: EbookGeneratorConfig
    page_content_exacter: ChapterPageExtractor

    ebook: epub.EpubBook

    images: dict[str, tuple[str, epub.EpubImage]]

    def __init__(self, book_id, config: EbookGeneratorConfig):
        self.book_id = book_id
        self.config = config
        self.page_content_exacter = config.chapter_page_exacter
        # self.chapters = []
        # self.images = {}

    def add_chapter(self, chapter: ChapterContent):  # add_images_in_content=True)
        # Note: This should probably just add the file to a list and include images,
        # then construct the epub separately

        self.chapter_count += 1
        epub_chapter = epub.EpubHtml(
            title=chapter.title, file_name=f"chapter_{self.chapter_count}.xhtml"
        )
        epub_chapter.set_content(chapter.content)
        self.ebook.add_item(epub_chapter)
        self.ebook.toc.append(epub_chapter)
        self.ebook.spine.append(epub_chapter)

    def add_chapter_page(self, page_content: str):
        # with open(filename, "r") as f:
        #     bs = BeautifulSoup(f.read(), features="lxml")

        bs = BeautifulSoup(page_content, features="lxml")
        chapter_content = self.config.chapter_page_exacter(bs)

        self.manage_img_tags(chapter_content)

        self.add_chapter(chapter_content)

    # This method should not be here, I think
    def generate(self, html_files: list[str]):
        self.init_epub()

        for file in html_files:
            self.load_chapter_file(file)

        self.write_epub("{}.epub".format(self.book_id))

    def load_chapter_file(self, filename: str):
        # from urllib.request import urlopen, Request
        from bs4 import BeautifulSoup

        #
        # with open(filename, "r") as f:
        #     bs = BeautifulSoup(f.read(), features="lxml")
        #
        # chapter_content = []
        # chapter_title = bs.select(self.config["title_selector"])[0].decode_contents()
        #
        # print("'%s'" % chapter_title)
        #
        # if self.config.get("include_chapter_titles", True):
        #     chapter_content.append("<h1>%s</h1>" % chapter_title)
        #
        # inner_content = bs.select(self.config["content_selector"])[0]
        #
        # print("Inner Content\n", inner_content)
        #
        #
        # chapter_content.append(str(inner_content))
        # self.add_chapter(chapter_title, "".join(chapter_content))

    def manage_img_tags(self, bs: BeautifulSoup):
        for img in bs.select("img"):
            if self.config.include_images:
                src_url = img.get("src")
                logging.info("Include: ", src_url)

                if src_url is None:
                    img.decompose()
                    continue

                assert isinstance(src_url, str)

                epub_image_path = self.include_image(src_url)
                if epub_image_path is None:
                    img.decompose()
                    continue

                img["src"] = epub_image_path
            else:
                img.decompose()

    def include_image(self, img_url: str) -> Optional[str]:
        if self.images.get(img_url) is None:
            image_count = len(self.images.keys())
            epub_image_path = "images/image_%u.jpg" % image_count

            try:
                dm = self.config.download_manager
                mxw, mxh = self.config.image_resize_max
                data = dm.get_and_cache_image_data(
                    img_url, max_width=mxw, max_height=mxh
                )
            except Exception as e:
                logging.error(str(e))

                # TODO: Report this in the download status.
                return None

            img = epub.EpubImage(
                uid="image_%u" % (image_count),
                file_name=epub_image_path,
                media_type="image/jpg",
                content=data,
            )
            self.ebook.add_item(img)
            self.images[img_url] = (epub_image_path, img)
            return epub_image_path

        return self.images[img_url][0]

    def init_epub(self, config_data=None):
        self.ebook = epub.EpubBook()
        # mandatory metadata
        self.ebook.set_identifier(self.book_id)

        cf = self.config
        self.ebook.set_title(cf.book_title)
        self.ebook.set_language(cf.book_language)
        self.ebook.add_author(cf.book_author)

        with open(cf.css_filepath, "r") as f:
            css = epub.EpubItem(
                uid="default",
                file_name=cf.epub_css_filepath,  # This is a bit strange ?
                media_type="text/css",
                content=f.read(),
            )
            self.ebook.add_item(css)

        cover_img_url = cf.book_cover_image
        if cover_img_url:
            dm = self.config.download_manager
            cover_img_data = dm.get_and_cache_image_data(cover_img_url)
            self.ebook.set_cover(cf.epub_cover_image_path, cover_img_data)

        self.chapter_count = 0

    def write_epub(self, local_epub_filepath):
        self.ebook.add_item(epub.EpubNcx())
        self.ebook.add_item(epub.EpubNav())
        epub.write_epub(local_epub_filepath, self.ebook)
