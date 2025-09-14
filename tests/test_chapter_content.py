from mywbooks.book import Chapter

HTML = """
<div id="chapter-inner">
  <h1>Chapter One</h1>
  <p>Hello</p>
  <img src="https://cdn.example/x.jpg">
  <p>World</p>
</div>
"""


def test_chapter_get_content_includes_title_and_images():
    ch = Chapter(
        title="Chapter One",
        content=HTML,
        images={},  # image map not needed for this test
        source_url="https://rr/chapter/1",
    )
    out = ch.get_content(include_images=True, include_chapter_title=True)
    assert "Chapter One" in out
    assert "<img" in out
    assert "<p>Hello</p>" in out and "<p>World</p>" in out


def test_chapter_get_content_strips_images_when_disabled():
    ch = Chapter(
        title="Chapter One",
        content=HTML,
        images={},
        source_url="https://rr/chapter/1",
    )
    out = ch.get_content(include_images=False, include_chapter_title=False)
    assert "<img" not in out
    # still should include the text content
    assert "<p>Hello</p>" in out and "<p>World</p>" in out
