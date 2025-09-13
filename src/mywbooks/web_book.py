from abc import abstractmethod
from dataclasses import dataclass

from pydantic_core import Url


@dataclass
class WebBookData:
    title: str
    language: str
    author: str
    cover_image: Url


class WebBook:
    data: WebBookData

    def __init__(self, data) -> None:
        self.data = data

    @abstractmethod
    def get_chapters():
        pass
