# from pathlib import Path
#
# from mywbooks.book import BookConfig, Chapter
# from mywbooks.ebook_generator import EbookGenerator, EbookGeneratorConfig
#
#
# def test_epub_smoke(tmp_path: Path):
#     cfg = BookConfig(
#         title="Test Book",
#         language="en",
#         author="Tester",
#         cover_image=Path(tmp_path / "cover.jpg"),  # you can also use a URL or omit
#     )
#     eg = EbookGenerator(
#         book_id="test:UUID_123,
#
#
#         EbookGeneratorConfig(book_config=cfg, css_filepath=Path("examples/kindle.css"))
#     )
#     eg.add_chapter_page(
#         Chapter(
#             title="Ch 1", content="<p>Hi</p>", images={}, source_url="https://x/1"
#         ).get_content(True, True)
#     )
#     out = tmp_path / "out.epub"
#     eg.write(out)  # or whatever your builder’s save method is named
#     assert out.exists() and out.stat().st_size > 0
