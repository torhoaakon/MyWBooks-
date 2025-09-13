import hashlib
import io
from collections.abc import Buffer
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from PIL import Image
from pydantic_core import Url

from mywbooks.utils import url_hash

# TODO
## - Logging


class DownlaodManager:
    hdrs = {"User-Agent": "Mozilla/5.0"}

    def __init__(self, base_cache_dir: Path) -> None:
        self.base_cache_dir = base_cache_dir

    def get_url_hash(self, url: Url) -> str:
        # return hashlib.md5(str(url).encode("utf-8")).hexdigest()
        return url_hash(url)

    def get_cache_filename(self, url: Url, fileext: Optional[str] = None) -> str:
        hash_filename = self.get_url_hash(url)
        if fileext is not None:
            hash_filename += fileext
        return hash_filename

    def is_valid_cache(self, cache_filename: str) -> bool:
        cache_filepath = self.base_cache_dir / cache_filename
        return cache_filepath.exists()

    def read_valid_cache_file(self, cache_filename: str):
        with open(self.base_cache_dir / cache_filename, "rb") as f:
            return f.read()

    def write_to_cache_file(self, content: Buffer, cache_filename: str):
        with open(self.base_cache_dir / cache_filename, "wb") as f:
            return f.write(content)

    def get_data(
        self,
        url,
        fileext=None,
        cache_filename: Optional[str] = None,
        ignore_cache=False,
    ):
        if not ignore_cache:
            if cache_filename is None:
                cache_filename = self.get_cache_filename(url, fileext)
            if self.is_valid_cache(cache_filename):
                return self.read_valid_cache_file(cache_filename)

        print(f"Downloading '{url}'")
        req = Request(url, headers=self.hdrs)
        with urlopen(req) as response:
            return response.read()

    def get_and_cache_data(
        self,
        url,
        fileext=None,
        cache_filename: Optional[str] = None,
        ignore_cache=False,
    ):
        if cache_filename is None:
            cache_filename = self.get_cache_filename(url, fileext)

        if ignore_cache:
            content = self.get_data(url, fileext, ignore_cache=True)
        else:
            if self.is_valid_cache(cache_filename):
                return self.read_valid_cache_file(cache_filename)
            content = self.get_data(url, fileext, ignore_cache=True)

        self.write_to_cache_file(content, cache_filename)
        return content

    def get_html(self, url, ignore_cache=False) -> BeautifulSoup:
        content = self.get_data(url, fileext=".html", ignore_cache=ignore_cache)
        return BeautifulSoup(content, features="lxml")

    def get_and_cache_html(self, url: Url, ignore_cache=False):
        content = self.get_and_cache_data(
            url, fileext=".html", ignore_cache=ignore_cache
        )
        return BeautifulSoup(content, features="lxml")

    def get_and_cache_image_data(
        self, url, ignore_cache=False, max_width=8096, max_height=8096
    ):
        cache_filename = "%s_%u_%u.jpg" % (
            self.get_cache_filename(url, fileext=""),
            max_width,
            max_height,
        )

        if not ignore_cache and self.is_valid_cache(cache_filename):
            return self.read_valid_cache_file(cache_filename)

        content = self.get_and_cache_data(url, fileext=None, ignore_cache=ignore_cache)

        content_io = io.BytesIO(content)

        im = Image.open(content_io, "r")
        im.thumbnail((max_width, max_height))

        # Check if the image has an alpha channel
        if im.mode in ("RGBA", "LA"):
            print("Image has an alpha channel. Converting to RGB...")
            im = im.convert("RGB")

        im.save(self.base_cache_dir / cache_filename)
        return self.read_valid_cache_file(cache_filename)
