import re
from dataclasses import dataclass
from typing import Optional, override

from bs4 import BeautifulSoup, ResultSet, Tag
from pydantic_core import Url

from mywbooks.ebook_generator import ChapterPageContent, ChapterPageExtractor
from mywbooks.web_book import WebBook

# TODO ? :
# class RoyalRoadDownloader():
#     base_url = "https://www.royalroad.com"
#     url_pattern = "^(https?://)?(www\.)?royalroad\.com/fiction/(?P<id>[\d]+)(/.*)?$"


@dataclass
class RoyalRoad_WebBookData:
    fiction_page: Url


class RoyalRoad_WebBook(WebBook):
    pass


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
