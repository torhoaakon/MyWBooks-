# Example factory that returns the right WebBook subclass from a DB Book row
from pathlib import Path

import dramatiq

from . import queue
from .db import SessionLocal
from .download_manager import DownlaodManager
from .models import Book, Provider, Task, TaskStatus
from .royalroad import RoyalRoad_WebBook
from .utils import utcnow
from .web_book import WebBook


def build_webbook_for(book: Book) -> WebBook:
    match book.provider:
        case Provider.ROYALROAD:
            return RoyalRoad_WebBook.from_model(book)
        case Provider.PATREON:
            raise RuntimeError("Unsupported model provider")
        case Provider.WUXIAWORLD:
            raise RuntimeError("Unsupported model provider")


@dramatiq.actor(max_retries=3)  # automatic retries on exception
def download_book_task(task_id: int):
    db = SessionLocal()
    try:
        task = db.get(Task, task_id)
        if not task:
            return  # nothing to do

        task.status = TaskStatus.RUNNING
        task.started_at = utcnow()
        task.attempts += 1
        db.commit()

        book = db.get(Book, task.book_id)
        if not book:
            raise RuntimeError(f"Book {task.book_id} not found")

        webbook = build_webbook_for(book)

        dm = DownlaodManager(Path("./cache"))
        css_path = Path("assets/kindle.css")
        out_dir = Path("var/epubs")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"book-{book.id}.epub"

        # cfg = EbookGeneratorConfig(
        #     book_config=webbook.bdata.config,
        #     css_filepath=css_path,
        #     include_images=True,
        #     include_chapter_titles=True,
        #     image_resize_max=(1024, 1024),
        # )

        # Drive generation through WebBook’s to_epub
        webbook.to_epub(
            download_manager=dm,
            css_filepath=css_path,
            output_path=out_path,
            include_images=True,
            include_chapter_titles=True,
            image_resize_max=(1024, 1024),
            book_id=f"book-{book.id}",
        )

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
