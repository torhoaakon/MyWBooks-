from pathlib import Path

from mywbooks.download_manager import DownlaodManager
from mywbooks.ebook_generator import BookConfig, EbookGenerator, EbookGeneratorConfig
from mywbooks.patreon import Patreon_ChapterPageExtractor

base_path = Path("./examples")
KINDLE_CSS = base_path / "kindle.css"


download_manager = DownlaodManager(Path("./cache"))
chapter_page_exacter = Patreon_ChapterPageExtractor()


book_config = BookConfig(
    title="Netherwitch c42",
    language="en",
    author="Wynn",
    cover_image=base_path / "5_cover_main_final.png",
)

config = EbookGeneratorConfig(
    book_config=book_config,
    include_images=True,
    include_chapter_titles=True,
    css_filepath=Path(KINDLE_CSS),
    # TODO: This should probably not include the extension
)


gen = EbookGenerator("netherwitch", chapter_page_exacter, download_manager, config)

output_path = Path("out")
output_path.mkdir(exist_ok=True)

for ch in range(40, 50):
    with open(base_path / "Netherwitch" / f"Netherwitch - {ch}.html", "r") as f:
        gen.add_chapter_page(f.read())

gen.export_as_epub(output_path / f"netherwitch.epub")
