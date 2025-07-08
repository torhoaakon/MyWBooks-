from typing import Optional, override

from bs4 import BeautifulSoup, ResultSet, Tag

from my_wbooks.ebook_generator import ChapterPageContent, ChapterPageExtractor

# TODO: https://www.patreon.com/portal
# Maybe server- or client- side


class Patreon_ChapterPageExtractor(ChapterPageExtractor):

    fiction_title_selector: str = 'span[data-tag="post-title"]'
    fiction_content_selector: str = "div.chapter-inner"

    @override
    def extract_chapter(
        self, page_content_bs: BeautifulSoup
    ) -> Optional[ChapterPageContent]:

        bs = page_content_bs

        fic_titles: ResultSet[Tag] = bs.select(self.fiction_title_selector)

        # TODO: This should be logging instead
        assert len(fic_titles) == 1

        title_tag = fic_titles[0]

        fic_title = str(fic_titles[0].decode_contents())

        div = title_tag.parent
        while div is not None and len(div.contents) == 1:
            div = div.parent

        assert div is not None

        div = div.parent
        assert div is not None

        assert len(div.contents) >= 2
        div = div.contents[1]

        assert isinstance(div, Tag)

        while div is not None and len(div.contents) == 1:
            div = div.contents[0]
            assert isinstance(div, Tag)

        assert isinstance(div, Tag)

        # This is for Netherwitch specific
        # could maybe have some customizable post manipulations
        div.contents[0].decompose()
        # div.contents[0].decompose()

        return ChapterPageContent(title=fic_title, content=div)
