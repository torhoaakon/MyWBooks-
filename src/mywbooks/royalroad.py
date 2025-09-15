from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional, override
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, ResultSet, Tag
from pydantic_core import Url

from mywbooks.download_manager import DownlaodManager

from .book import BookConfig, Chapter, ChapterRef
from .ebook_generator import ChapterPageContent, ChapterPageExtractor, ExtractOptions
from .utils import _get_text
from .web_book import WebBook, WebBookData

PROVIDER_PREFIX = "royalroad"

CHAPTER_ID_RE = re.compile(r"/chapter/(\d+)", re.IGNORECASE)
FICTION_ID_RE = re.compile(r"/fiction/(\d+)(?:/|$)", re.IGNORECASE)


def rr_fiction_uid_from_url(url: str) -> str | None:
    m = FICTION_ID_RE.search(urlparse(url).path)
    if not m:
        return None
    return f"{PROVIDER_PREFIX}:{m.group(1)}"


def chapter_id_from_url(url: str) -> str | None:
    """
    Extract a RoyalRoad chapter id and return a *namespaced* id, e.g. "royalroad:1269041".
    """
    m = CHAPTER_ID_RE.search(url)
    if not m:
        return None
    return f"{PROVIDER_PREFIX}:{m.group(1)}"


def canonical_rr_chapter_url(chapter_id_prefixed: str) -> str:
    # "royalroad:1269041" -> "https://www.royalroad.com/fiction/chapter/1269041"
    _, raw = chapter_id_prefixed.split(":", 1)
    return f"https://www.royalroad.com/fiction/chapter/{raw}"


class ChapterParseError(Exception):
    def __init__(self, reason: str, *, url: str | None, tried_selectors: list[str]):
        self.reason = reason
        self.url = url
        self.tried_selectors = tried_selectors
        msg = f"Chapter parse failed: {reason}. Tried selectors: {tried_selectors}"
        if url:
            msg += f" | url={url}"
        super().__init__(msg)


class FictionParseError(Exception):
    def __init__(self, reason: str, *, url: str | None, tried_selectors: list[str]):
        self.reason = reason
        self.url = url
        self.tried_selectors = tried_selectors
        msg = f"Fiction parse failed: {reason}. Tried selectors: {tried_selectors}"
        if url:
            msg += f" | url={url}"
        super().__init__(msg)


class RoyalRoadChapterPageExtractor(ChapterPageExtractor):
    """
    Extract title + content from a RoyalRoad chapter page.
    Now tries multiple selectors (id or class) and gives clear errors.
    """

    # broadened sets; order matters (earlier = preferred)
    TITLE_SELECTORS: list[str] = [
        "div.fic-header h1",
        "#chapter-inner h1",
        "#chapter-content h1",
        ".chapter-inner h1",
        # "article h1",
        # "h1",
    ]

    CONTENT_SELECTORS: list[str] = [
        "div.chapter-inner",
        "#chapter-inner",
        "#chapter-content",
        "div#chapter-content",
        "article.chapter-content",
        "div.chapter-content",
        # "article",
        # "main",
    ]

    # fiction_title_selector: str = "div.fic-header h1"
    # fiction_content_selector: str = "div.chapter-inner"

    def _first_match(self, soup, selectors: Iterable[str]):
        for sel in selectors:
            node = soup.select_one(sel)
            if node is not None:
                return node, sel
        return None, None

    @override
    def extract_chapter(
        self,
        page_content_bs: BeautifulSoup,
        *,
        options: ExtractOptions | None = None,
    ) -> Optional[ChapterPageContent]:
        opts = options or ExtractOptions()

        # title
        title_node, _ = self._first_match(page_content_bs, self.TITLE_SELECTORS)
        title = title_node.get_text(strip=True) if title_node else None

        # content
        content_node, _ = self._first_match(page_content_bs, self.CONTENT_SELECTORS)

        if not content_node:
            if opts.strict:
                raise ChapterParseError(
                    reason="Could not locate chapter content",
                    url=opts.url,
                    tried_selectors=self.CONTENT_SELECTORS,
                )
            return None

        if not title:
            if opts.fallback_title:
                title = opts.fallback_title
            else:
                inner = content_node.select_one("h1, h2")
                if inner:
                    title = inner.get_text(strip=True)
                elif opts.strict:
                    raise ChapterParseError(
                        "Could not locate chapter title",
                        url=opts.url,
                        tried_selectors=self.TITLE_SELECTORS,
                    )
                else:
                    title = "Untitled Chapter"

        # TODO: We also need to do this:
        # hidden_class_names = self.identify_hiddden_class_names(soup)
        # self.dispose_hidden_elements(hidden_class_names, inner_content)

        return ChapterPageContent(title=title, content=content_node)

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


class RoyalRoad_WebBook(WebBook):
    """Concrete WebBook for a RoyalRoad fiction page."""

    def __init__(self, fiction_url: str):
        self.fiction_url = fiction_url
        html = _get_text(self.fiction_url)
        meta, chapter_urls = _parse_fiction_page(self.fiction_url, html, strict=True)
        super().__init__(meta)
        self._chapter_urls = chapter_urls
        self._chapter_extractor = RoyalRoadChapterPageExtractor()

        html = _get_text(
            fiction_url
        )  # or your DownloadManager if you’ve injected it here
        meta, chapter_urls = _parse_fiction_page(fiction_url, html, strict=True)
        super().__init__(meta)
        self.fiction_url = fiction_url
        self.refs = [
            ChapterRef(
                id=chapter_id_from_url(u) or "", url=u, title=None
            )  # TODO: Needs to handle id_from_url failing
            for u in chapter_urls
        ]
        self._extractor = RoyalRoadChapterPageExtractor()

    def list_chapter_refs(self) -> list[ChapterRef]:
        return self.refs

    def fetch_chapter(
        self,
        ref: ChapterRef,
        *,
        download_manager: DownlaodManager,
        include_images: bool = True,
        include_chapter_title: bool = True,
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


# ----------------- helpers -----------------


def _parse_fiction_page(
    base_url: str,
    html: str,
    chapter_toc_strategies: int = 0,
    strict: bool = True,
) -> tuple[BookConfig, list[str]]:
    """
    Extract book metadata (title, author, cover, language) and all chapter URLs
    from a RoyalRoad fiction page.
    """
    bs = BeautifulSoup(html, "lxml")

    # Title
    h1 = bs.select_one("div.fic-header h1") or bs.select_one("h1")
    title = h1.get_text(strip=True) if h1 else "Untitled"

    # Author
    author_tag = bs.select_one('a[href*="/profile/"], a[href*="/author/"]')
    author = author_tag.get_text(strip=True) if author_tag else "Unknown"

    # Cover
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

    # Language
    lang_meta = bs.select_one(
        'meta[http-equiv="content-language"], meta[name="language"]'
    )
    language = str(
        lang_meta.get("content") if lang_meta and lang_meta.get("content") else "en"
    ).lower()

    # Chapters:
    chapter_links = _extract_toc_chapter_links(
        base_url, bs, strict=strict, strategies=chapter_toc_strategies
    )

    meta = WebBookData(
        title=title,
        language=language,
        author=author,
        cover_image=Url(cover),
    )
    return meta, chapter_links


def _extract_toc_chapter_links(
    base_url: str, bs: BeautifulSoup, *, strategies: int = 0, strict: bool
) -> list[str]:
    """
    Try multiple strategies to find chapter links. If none found and strict=True,
    raise FictionParseError with selectors tried.
    """
    tried: list[str] = []

    strategies = strategies or 2  ## 0 means default:  2

    print("strategies", strategies)

    # 1) Canonical ToC container
    toc = bs.select_one("#chapters")
    tried.append("#chapters")
    if toc:
        links = _collect_rr_chapter_links(base_url, toc)
        if links:
            return links

    # 2) Common table/list containers people see on RR skins
    if strategies >= 2:
        selection = "div.chapters, div.chapter-list, div.fic-contents, section"
        # selection = "table, ul, ol, div.chapter-list, div.fic-contents, section"

        containers = bs.select(selection)
        tried.append(selection)
        for c in containers:
            links = _collect_rr_chapter_links(base_url, c)
            if links:
                return links

    # 3) Global fallback: any anchor with /chapter/ anywhere in the page
    if strategies >= 3:
        tried.append('a[href*="/chapter/"] (global)')
        links = _collect_rr_chapter_links(base_url, bs)
        if links:
            return links

    if strict:
        raise FictionParseError(
            reason="Could not locate chapter table of contents",
            url=base_url,
            tried_selectors=tried,
        )

    return []


def _collect_rr_chapter_links(base_url: str, scope: BeautifulSoup | Tag) -> list[str]:
    seen: dict[str, str] = {}
    for a in scope.select('a[href*="/chapter/"]'):
        href = str(a.get("href", "")).strip()
        if not href:
            continue
        full = urljoin(base_url, href)
        chap_id = chapter_id_from_url(full)
        if chap_id and chap_id not in seen:
            seen[chap_id] = full

    # Sort chapter by id
    # def _chapter_sort_key(u: str) -> tuple[int, str]:
    #     # matches .../chapter/<number>/
    #     m = re.search(r"/chapter/(\d+)", u)
    #     return (int(m.group(1)) if m else 10**9, u)
    #
    # return sorted(seen.values(), key=_chapter_sort_key)

    return list(seen.values())  # preserves appearance order
