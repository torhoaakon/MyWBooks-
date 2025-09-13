from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Iterable, Optional, override
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, ResultSet, Tag
from pydantic_core import Url

from mywbooks.book import Chapter
from mywbooks.ebook_generator import ChapterPageContent, ChapterPageExtractor
from mywbooks.web_book import WebBook, WebBookData

# TODO ? :
# class RoyalRoadDownloader():
#     base_url = "https://www.royalroad.com"
#     url_pattern = "^(https?://)?(www\.)?royalroad\.com/fiction/(?P<id>[\d]+)(/.*)?$"


class RoyalRoadChapterPageExtractor(ChapterPageExtractor):
    fiction_title_selector: str = "div.fic-header h1"
    fiction_content_selector: str = "div.chapter-inner"

    @override
    def extract_chapter(
        self, page_content_bs: BeautifulSoup
    ) -> Optional[ChapterPageContent]:

        # NOTE: The chapter title could be an
        # optional kwarument. Since it may already be known before the page is downloaded. For example if it is extracted from the chapter list instead of  from this page
        # (This may not be what you want, but having the option would be nice)

        bs = page_content_bs

        fic_titles: ResultSet[Tag] = bs.select(self.fiction_title_selector)

        # NOTE: IDEA: Chapter image could be a thing
        # For example included every time it changes ??

        # TODO: This should be logging instead
        assert len(fic_titles) == 1

        assert len(fic_titles[0]) == 1

        fic_title = str(fic_titles[0].contents[0])

        # TODO: Authors notes

        chapter_inner_res = bs.select(self.fiction_content_selector)
        assert len(chapter_inner_res) == 1

        inner_content: Tag = chapter_inner_res[0]

        hidden_class_names = self.identify_hiddden_class_names(bs)
        self.dispose_hidden_elements(hidden_class_names, inner_content)

        return ChapterPageContent(title=fic_title, content=inner_content)

    def identify_hiddden_class_names(self, bs: BeautifulSoup) -> list[str]:
        hidden_class_names: list[str] = []

        # TODO: replace this assert
        assert bs.head is not None

        for style_tag in bs.head.find_all("style"):
            css_content = style_tag.get_text()
            # Use regular expressions to find the class name with display: none;
            pattern = r"\.(.*?)\s*{[^}]*display:\s*none;[^}]*}"
            match: Optional[re.Match[str]] = re.search(pattern, css_content)
            if match:
                hidden_class_names.append(match.group(1))

        return hidden_class_names

    def dispose_hidden_elements(
        self, hidden_class_names: list[str], content_bs: Tag
    ) -> None:

        for class_name in hidden_class_names:
            for element in content_bs.find_all(class_=class_name):
                element.extract()


@dataclass
class RoyalRoad_WebBookData:
    fiction_page: Url


class RoyalRoad_WebBook(WebBook):
    """Concrete WebBook for a RoyalRoad fiction page."""

    def __init__(self, fiction_url: str):
        self.fiction_url = fiction_url
        # Parse fiction page once for metadata + initial chapter links
        html = _get_text(self.fiction_url)
        meta, chapter_urls = _parse_fiction_page(self.fiction_url, html)
        super().__init__(meta)
        self._chapter_urls = chapter_urls
        self._chapter_extractor = RoyalRoadChapterPageExtractor()

    def get_chapters(
        self, *, include_images: bool = True, include_chapter_title: bool = True
    ) -> Iterable[Chapter]:
        for idx, ch_url in enumerate(self._chapter_urls):
            ch_html = _get_text(ch_url)
            bs = BeautifulSoup(ch_html, "lxml")
            page = self._chapter_extractor.extract_chapter(bs)
            if page is None:
                continue

            # page.content is a Tag; preserve HTML
            content_html = str(page.content)
            # Images: for now, let Chapter strip <img> if include_images=False
            images = {}
            yield Chapter(
                title=page.title or f"Chapter {idx+1}",
                content=content_html,
                images=images,
            )


# ----------------- helpers -----------------


def _get_text(url: str, *, timeout: float = 30.0) -> str:
    # You can swap this to your DownloadManager later if you prefer.
    headers = {"User-Agent": "MyWBooksBot/0.1 (+https://example.com)"}
    with httpx.Client(
        timeout=timeout, headers=headers, follow_redirects=True
    ) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.text


def _parse_fiction_page(base_url: str, html: str) -> tuple[WebBookData, list[str]]:
    """
    Extract book metadata (title, author, cover, language) and all chapter URLs
    from a RoyalRoad fiction page.
    """
    bs = BeautifulSoup(html, "lxml")

    # Title: often under header like "div.fic-header h1" (same selector you use for chapter titles)
    h1 = bs.select_one("div.fic-header h1") or bs.select_one("h1")
    title = h1.get_text(strip=True) if h1 else "Untitled"

    # Author: RR usually links author name somewhere in header
    author_tag = bs.select_one('a[href*="/profile/"], a[href*="/author/"]')
    author = author_tag.get_text(strip=True) if author_tag else "Unknown"

    # Cover: common classes: .fic-header .cover or img[src*="royalroadcdn"]
    cover_img = (
        bs.select_one("div.fic-header img")
        or bs.select_one('img[src*="royalroadcdn"]')
        or bs.select_one("img")
    )

    cover_src = (
        str(cover_img["src"]).strip()
        if (cover_img and cover_img.has_attr("src"))
        else "/favicon.ico"
    )
    cover = urljoin(base_url, cover_src)

    # Language: RR is predominantly English. If there’s a hint in meta, use it; else default.
    lang_meta = bs.select_one(
        'meta[http-equiv="content-language"], meta[name="language"]'
    )
    language = str(
        lang_meta.get("content") if lang_meta and lang_meta.get("content") else "en"
    ).lower()

    # Chapters:
    chapter_links = _extract_toc_chapter_links(base_url, bs)

    meta = WebBookData(
        title=title,
        language=language,
        author=author,
        cover_image=Url(cover),
    )
    return meta, chapter_links


CHAPTER_ID_RE = re.compile(r"/chapter/(\d+)", re.IGNORECASE)


def _extract_toc_chapter_links(base_url: str, bs) -> list[str]:
    seen: dict[int, str] = {}
    toc = bs.select_one("#chapters")  # the ToC table
    if not toc:
        return []

    for a in toc.select("a[href]"):
        href = a.get("href", "").strip()
        if not href:
            continue
        full = urljoin(base_url, href)
        m = CHAPTER_ID_RE.search(full)
        if not m:
            continue
        chap_id = int(m.group(1))
        if chap_id not in seen:
            # store the first URL we encounter for this chapter id
            seen[chap_id] = full

    # Sort chapter by id
    # def _chapter_sort_key(u: str) -> tuple[int, str]:
    #     # matches .../chapter/<number>/
    #     m = re.search(r"/chapter/(\d+)", u)
    #     return (int(m.group(1)) if m else 10**9, u)
    #
    # return sorted(seen.values(), key=_chapter_sort_key)

    # return in appearance order (dict preserves insertion order in 3.7+)
    return list(seen.values())
