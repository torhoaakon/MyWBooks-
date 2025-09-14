import pytest
from bs4 import BeautifulSoup

from mywbooks.royalroad import RoyalRoadChapterPageExtractor

CHAPTER_HTML = """
<html>
  <body>
    <div class="fic-header"><h1>Fiction Title</h1></div>
    <div class="chapter-content">
      <h1>Chapter 3 — A Great Reveal</h1>
      <p>First paragraph.</p>
      <p>Second paragraph.</p>
    </div>
  </body>
</html>
"""


def test_chapter_extractor_finds_title_and_content():
    extractor = RoyalRoadChapterPageExtractor()
    soup = BeautifulSoup(CHAPTER_HTML, "lxml")
    page = extractor.extract_chapter(soup)
    assert page is not None
    assert "Fiction Title" in (page.title or "")
    # Content should be a Tag; convert to string for simple assertions
    html = str(page.content)
    assert "<p>First paragraph.</p>" in html


def test_rr_extractor_strict_error_includes_url():
    from mywbooks.ebook_generator import ExtractOptions
    from mywbooks.royalroad import ChapterParseError, RoyalRoadChapterPageExtractor

    ex = RoyalRoadChapterPageExtractor()
    soup = BeautifulSoup("<html><body>No chapter</body></html>", "lxml")
    with pytest.raises(ChapterParseError) as ei:
        ex.extract_chapter(
            soup, options=ExtractOptions(url="https://rr/chap/42", strict=True)
        )
    assert "Could not locate chapter content" in str(ei.value)
    assert "https://rr/chap/42" in str(ei.value)
