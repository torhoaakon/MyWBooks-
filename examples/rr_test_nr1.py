from pathlib import Path

from pydantic_core import Url

from mywbooks.download_manager import DownlaodManager
from mywbooks.ebook_generator import BookConfig, EbookGenerator, EbookGeneratorConfig
from mywbooks.royalroad import RoyalRoadChapterPageExtractor

base_path = Path("./examples")
chapter_filepath = base_path / "Untouchable_chapter-5.html"
KINDLE_CSS = base_path / "kindle.css"

with open(chapter_filepath, "r") as f:
    raw = f.read()

download_manager = DownlaodManager(Path("./cache"))
chapter_page_exacter = RoyalRoadChapterPageExtractor()

book_config = BookConfig(
    title="Untouchable",
    language="en",
    author="Wynn",
    cover_image=Url(
        "https://www.royalroadcdn.com/public/covers-large/60276-untouchable-a-litrpg-manhwabook.jpg"
    ),
)

config = EbookGeneratorConfig(
    book_config=book_config,
    include_images=True,
    include_chapter_titles=True,
    css_filepath=Path(KINDLE_CSS),
    # TODO: This should probably not include the extension
)


gen = EbookGenerator("untouchable", chapter_page_exacter, download_manager, config)

output_path = Path("out")
output_path.mkdir(exist_ok=True)

gen.add_chapter_page(raw)
gen.export_as_epub(output_path / f"untouchable.epub")

# gen.init_epub()
# gen.write_epub()
