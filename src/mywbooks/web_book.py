from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable

from pydantic_core import Url

from .book import Chapter  # reuse your existing representation


@dataclass
class WebBookData:
    title: str
    language: str
    author: str
    cover_image: Url


class WebBook(ABC):
    data: WebBookData

    def __init__(self, data: WebBookData) -> None:
        self.data = data

    @abstractmethod
    def get_chapters(
        self, *, include_images: bool = True, include_chapter_title: bool = True
    ) -> Iterable[Chapter]:
        """Yield Chapter objects for this web book."""
