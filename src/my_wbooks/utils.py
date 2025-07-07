import hashlib

from pydantic_core import Url


def url_hash(url: Url) -> str:
    return hashlib.md5(str(url).encode("utf-8")).hexdigest()
