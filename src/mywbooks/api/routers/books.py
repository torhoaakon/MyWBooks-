from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from mywbooks import models
from mywbooks.api.auth import CurrentUser, UserClaims
from mywbooks.db import get_db
from mywbooks.download_manager import DownlaodManager, get_dm
from mywbooks.library import add_book_to_user
from mywbooks.services import ingest
from mywbooks.tasks import download_book_task

router = APIRouter()


# --- Schemas ------------------------------------------------------------------


class AddRoyalRoadBody(BaseModel):
    url: Optional[HttpUrl] = None
    fiction_id: Optional[int] = None

    @model_validator(mode="after")
    def check_at_least_one(self) -> "AddRoyalRoadBody":
        if not self.url and not self.fiction_id:
            raise ValueError("Either 'url' or 'fiction_id' must be provided")
        return self


class BookOut(BaseModel):
    id: int
    provider: str
    provider_fiction_uid: str
    source_url: str
    title: str
    author: Optional[str] = None
    language: Optional[str] = None
    cover_url: Optional[str] = None

    @classmethod
    def from_model(cls, b: models.Book) -> "BookOut":
        return cls(
            id=b.id,
            provider=(
                b.provider.value if hasattr(b.provider, "value") else str(b.provider)
            ),
            provider_fiction_uid=b.provider_fiction_uid,
            source_url=b.source_url,
            title=b.title,
            author=b.author,
            language=b.language,
            cover_url=b.cover_url,
        )


# ==== Response Messages ====


class ResponseMsg(BaseModel):
    ok: bool


class DownloadBookNowResponse(ResponseMsg):
    task_id: int
    task_status: models.TaskStatus


# --- Helpers ------------------------------------------------------------------


def _get_or_create_user_by_sub(db: Session, claims: UserClaims) -> models.User:
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="JWT missing 'sub' claim")

    # Optional: detect your provider from ISSUER
    provider = "supabase"

    u = db.execute(
        select(models.User).where(
            models.User.auth_provider == provider, models.User.auth_subject == sub
        )
    ).scalar_one_or_none()

    if u:
        # keep email fresh if present
        email = claims.get("email")
        if email and u.email != email:
            u.email = email
            db.commit()
        return u

    # First time we see this subject: create a row.
    u = models.User(
        auth_provider=provider,
        auth_subject=sub,
        email=claims.get("email"),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


# --- Routes -------------------------------------------------------------------


@router.post("/royalroad", response_model=BookOut, status_code=201)
def add_royalroad_book(
    body: AddRoyalRoadBody,
    user: CurrentUser,
    db: Session = Depends(get_db),
    dm: DownlaodManager = Depends(get_dm),
) -> BookOut:
    """
    Upsert a RoyalRoad book (by fiction URL or fiction_id) and subscribe the current user.
    """

    # 1) Upsert book via your ingest helpers
    if body.url:
        book_id = ingest.upsert_royalroad_book_from_url(db, body.url._url, dm)
    else:
        # If your ingest exposes a dedicated fiction-id helper, use it.
        # Otherwise, synthesize a URL (works with your current ingest).
        url = f"https://www.royalroad.com/fiction/{body.fiction_id}"
        book_id = ingest.upsert_royalroad_book_from_url(db, url, dm)

    # 2) Map Supabase user → local User and subscribe
    local_user = _get_or_create_user_by_sub(db, user)
    add_book_to_user(db, local_user.id, book_id)

    # 3) Return the book
    book = db.get(models.Book, book_id)
    if not book:
        raise HTTPException(status_code=500, detail="Book upserted but not found.")
    return BookOut.from_model(book)


@router.get("", response_model=list[BookOut])
def list_my_books(user: CurrentUser, db: Session = Depends(get_db)) -> list[BookOut]:
    """
    List books the current user has in their library (subscriptions).
    """
    local_user = _get_or_create_user_by_sub(db, user)

    q = (
        select(models.Book)
        .join(models.BookUser, models.BookUser.book_id == models.Book.id)
        .where(
            models.BookUser.user_id == local_user.id, models.BookUser.in_library == True
        )  # noqa: E712
        .order_by(models.Book.title.asc())
    )
    rows = db.execute(q).scalars().all()
    return [BookOut.from_model(b) for b in rows]


@router.delete("/{book_id}/unsubscribe")
def unsubscribe_book(
    book_id: int, user: CurrentUser, db: Session = Depends(get_db)
) -> ResponseMsg:
    """
    Remove the current user's subscription to a book (keeps the book for others).
    """
    local_user = _get_or_create_user_by_sub(db, user)

    # Flip in_library = False if the row exists; otherwise nothing to do.
    link = db.execute(
        select(models.BookUser).where(
            models.BookUser.user_id == local_user.id,
            models.BookUser.book_id == book_id,
        )
    ).scalar_one_or_none()

    if link:
        link.in_library = False
        db.commit()

    return ResponseMsg(ok=True)


# TODO: Here there should be some more generate config
@router.post("/{book_id}/download")
def download_book_now(
    book_id: int, user: CurrentUser, db: Session = Depends(get_db)
) -> DownloadBookNowResponse:
    """
    Queue a download/export job and return a task id the client can poll.
    """
    local_user = _get_or_create_user_by_sub(
        db, user
    )  # existing helper :contentReference[oaicite:2]{index=2}

    # Must be subscribed
    rel = db.execute(
        select(models.BookUser).where(
            models.BookUser.user_id == local_user.id,
            models.BookUser.book_id == book_id,
            models.BookUser.in_library == True,  # noqa: E712
        )
    ).scalar_one_or_none()
    if not rel:
        raise HTTPException(status_code=403, detail="Not subscribed to this book.")

    # Create a Task row
    task = models.Task(
        type=models.TaskType.DOWNLOAD_BOOK,
        status=models.TaskStatus.QUEUED,
        user_id=local_user.id,
        book_id=book_id,
        payload=None,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Enqueue the job (fire-and-forget)
    download_book_task.send(task.id)

    return DownloadBookNowResponse(
        ok=True, task_id=task.id, task_status=models.TaskStatus(task.status)
    )
