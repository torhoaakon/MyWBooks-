# Example factory that returns the right WebBook subclass from a DB Book row
from pathlib import Path
from typing import Any

import dramatiq
from pydantic_core import Url

from mywbooks import models
from mywbooks.book import DEFAULT_COVER_URL, BookConfig
from mywbooks.ebook_generator import EbookGeneratorConfig

from . import queue  # This import is IMPORTANT
from .db import SessionLocal
from .download_manager import DownlaodManager
from .models import Book, Task, TaskStatus
from .services.book_ops import export_book_to_epub_from_db, upsert_fiction_toc
from .utils import utcnow


@dramatiq.actor(max_retries=1)
def download_book_task(task_id: int) -> None:
    db = SessionLocal()
    try:
        task = db.get(models.Task, task_id)
        if not task:
            return  # nothing to do

        task.status = TaskStatus.RUNNING
        task.started_at = utcnow()
        task.attempts += 1
        db.commit()

        book = db.get(Book, task.book_id)
        if not book:
            raise RuntimeError(f"Book {task.book_id} not found")

        payload: dict[str, Any] = task.payload or {}

        dm = DownlaodManager(Path("./cache"))
        out_dir = Path("var/epubs")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"book-{book.id}.epub"

        # NOTE: Should probably not be doing this her here
        upsert_fiction_toc(
            db, book, dm
        )  ## Look for new chapters and changes to metadata

        cover_url: Url = Url(book.cover_url) if book.cover_url else DEFAULT_COVER_URL
        bcfg = BookConfig(
            title=payload.get("book-title", book.title),
            author=payload.get("book-author", book.author or ""),
            language=payload.get("book-language", book.language),
            cover_image=payload.get("book-cover", cover_url),
        )

        keys = [
            "include-images",
            "include-chapter-titles",
            "image-resize-max",
            "epub-css-filepath",
        ]
        cfg = EbookGeneratorConfig(
            book_config=bcfg,
            **{k: payload[k.replace("-", "_")] for k in keys if k in payload},
        )
        export_book_to_epub_from_db(db, book, dm=dm, cfg=cfg, out_path=out_path)

        # Mark success (you could store a file path in payload)
        task.status = TaskStatus.SUCCEEDED
        task.payload = {"output_path": str(out_path)}
        task.finished_at = utcnow()
        db.commit()

    except Exception as e:
        task = db.get(Task, task_id)  # re-read in case of rollback
        if task:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.finished_at = utcnow()
            db.commit()
        raise  # let Dramatiq retry
    finally:
        db.close()
