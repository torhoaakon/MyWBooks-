import hashlib
from datetime import date, datetime, timezone

import httpx
from pydantic_core import Url


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def url_hash(url: Url) -> str:
    return hashlib.md5(str(url).encode("utf-8")).hexdigest()


def _get_text(url: str, *, timeout: float = 30.0) -> str:
    # You can swap this to your DownloadManager later if you prefer.
    headers = {"User-Agent": "MyWBooksBot/0.1 (+https://example.com)"}
    with httpx.Client(
        timeout=timeout, headers=headers, follow_redirects=True
    ) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.text
