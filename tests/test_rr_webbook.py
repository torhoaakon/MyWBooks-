from pathlib import Path
from urllib.parse import urljoin

import mywbooks.royalroad as rr
from mywbooks.royalroad import RoyalRoad_WebBook
from tests.fakes import FakeDownloadManager

FICTION_URL = "https://www.royalroad.com/fiction/5555/my-rr-fiction"


FICTION_HTML = """
<html>
  <body>
    <div class="fic-header">
      <h1>My RR Fiction</h1>
      <a href="/profile/1234/author-name">Author Name</a>
      <img src="https://royalroadcdn.com/covers/cover123.jpg">
    </div>
    <div class="chapters">
      <a href="/fiction/5555/my-rr-fiction/chapter/1">Chapter One</a>
      <a href="/fiction/5555/my-rr-fiction/chapter/2">Chapter Two</a>
    </div>
  </body>
</html>
"""

CHAPTER1_HTML = b"""
<html><body>
  <div id="chapter-content">
    <h1>Chapter One</h1>
    <p>Text of chapter one.</p>
  </div>
</body></html>
"""

CHAPTER2_HTML = b"""
<html><body>
  <div id="chapter-content">
    <h1>Chapter Two</h1>
    <p>Text of chapter two.</p>
  </div>
</body></html>
"""


def test_webbook_yields_chapters(monkeypatch, tmp_path: Path):
    calls = []

    def fake_get_text(url: str, *, timeout: float = 30.0) -> str:
        calls.append(url)
        if url == FICTION_URL:
            return FICTION_HTML
        raise AssertionError(f"Unexpected URL: {url}")

    # Monkeypatch the internal fetch function used by RoyalRoad_WebBook
    monkeypatch.setattr(rr, "_get_text", fake_get_text)

    wb = RoyalRoad_WebBook(FICTION_URL)

    # Metadata
    assert wb.bdata.config.title == "My RR Fiction"
    assert wb.bdata.config.author == "Author Name"

    url_ch1 = urljoin(FICTION_URL, "/fiction/5555/my-rr-fiction/chapter/1")
    url_ch2 = urljoin(FICTION_URL, "/fiction/5555/my-rr-fiction/chapter/2")

    fdm = FakeDownloadManager(
        tmp_path,
        {url_ch1: CHAPTER1_HTML, url_ch2: CHAPTER2_HTML},
    )
    wb._iter_dm = fdm

    chapters = list(wb.get_chapters(include_images=False, include_chapter_title=True))
    assert len(chapters) == 2

    assert chapters[0].title == "Chapter One"
    assert "Text of chapter one" in chapters[0].content
    assert chapters[1].title == "Chapter Two"
    assert "Text of chapter two" in chapters[1].content

    # ensure we fetched fiction + both chapters
    assert FICTION_URL in calls
