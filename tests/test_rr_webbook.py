import pytest

import mywbooks.royalroad as rr
from mywbooks.royalroad import RoyalRoad_WebBook

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

CHAPTER1_HTML = """
<html><body>
  <div id="chapter-content">
    <h1>Chapter One</h1>
    <p>Text of chapter one.</p>
  </div>
</body></html>
"""

CHAPTER2_HTML = """
<html><body>
  <div id="chapter-content">
    <h1>Chapter Two</h1>
    <p>Text of chapter two.</p>
  </div>
</body></html>
"""


def test_webbook_yields_chapters(monkeypatch):
    calls = []

    def fake_get_text(url: str, *, timeout: float = 30.0) -> str:
        calls.append(url)
        if url == FICTION_URL:
            return FICTION_HTML
        if url.endswith("/chapter/1"):
            return CHAPTER1_HTML
        if url.endswith("/chapter/2"):
            return CHAPTER2_HTML
        raise AssertionError(f"Unexpected URL: {url}")

    # Monkeypatch the internal fetch function used by RoyalRoad_WebBook
    monkeypatch.setattr(rr, "_get_text", fake_get_text)

    wb = RoyalRoad_WebBook(FICTION_URL)

    # Metadata
    assert wb.data.title == "My RR Fiction"
    assert wb.data.author == "Author Name"

    chapters = list(wb.get_chapters(include_images=False, include_chapter_title=True))
    assert len(chapters) == 2

    assert chapters[0].title == "Chapter One"
    assert "Text of chapter one" in chapters[0].content
    assert chapters[1].title == "Chapter Two"
    assert "Text of chapter two" in chapters[1].content

    # ensure we fetched fiction + both chapters
    assert FICTION_URL in calls
    assert any(u.endswith("/chapter/1") for u in calls)
    assert any(u.endswith("/chapter/2") for u in calls)
