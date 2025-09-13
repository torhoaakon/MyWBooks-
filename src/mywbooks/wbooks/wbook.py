from abc import ABC, abstractmethod
from dataclasses import dataclass

from pydantic_core import Url

WbmID = str


@dataclass
class WBookData:
    wbm_id: WbmID
    book_id: str  # ObjectId as string or I just do my own ids

    title: str
    language: str
    author: str
    cover_image: Url


class WBookManager(ABC):

    default_kindle_css = "./data/kindle.css"
    url_pattern = None

    def __init__(self, WBook) -> None:
        # self.data = data
        pass

    @abstractmethod
    def get_chapters():
        pass
