# tests/test_api_books.py
# tests/test_api_books.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from mywbooks import models
from mywbooks.library import add_book_to_user


def test_add_royalroad_book_by_url(client, db_session: Session, monkeypatch):
    # Pre-create a Book row in the SAME test DB
    b = models.Book(
        provider=(
            models.Provider.ROYALROAD if hasattr(models, "Provider") else "royalroad"
        ),
        provider_fiction_uid="royalroad:21220",
        source_url="https://www.royalroad.com/fiction/21220",
        title="Test RR Book",
        author="Author X",
        language="en",
        cover_url="https://example/cover.jpg",
    )
    db_session.add(b)
    db_session.commit()
    db_session.refresh(b)
    created_id = b.id

    # Monkeypatch ingest to just return the known id
    from mywbooks import ingest

    monkeypatch.setattr(
        ingest, "upsert_royalroad_book_from_url", lambda url: created_id
    )

    # Call the API
    resp = client.post("/api/books/royalroad", json={"url": b.source_url})
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["id"] == created_id
    assert data["title"] == "Test RR Book"

    # Assert subscription created
    user = db_session.execute(
        select(models.User).where(models.User.auth_subject == "test-user-sub-123")
    ).scalar_one()

    print("B", db_session, user.id, created_id)

    rel = db_session.execute(select(models.BookUser)).scalar_one_or_none()

    assert rel is not None


def test_list_my_books(client, db_session: Session):
    # Ensure a user + subscription exists (reuse from previous test or create here)
    user = db_session.execute(
        select(models.User).where(models.User.auth_subject == "test-user-sub-123")
    ).scalar_one_or_none()
    if not user:
        user = models.User(
            auth_provider="supabase",
            auth_subject="test-user-sub-123",
            email="tester@example.com",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

    b = models.Book(
        provider=(
            models.Provider.ROYALROAD if hasattr(models, "Provider") else "royalroad"
        ),
        provider_fiction_uid="royalroad:999",
        source_url="https://rr/fiction/999",
        title="Another Book",
        author="Z",
        language="en",
        cover_url=None,
    )
    db_session.add(b)
    db_session.commit()
    db_session.refresh(b)
    add_book_to_user(user.id, b.id)

    resp = client.get("/api/books")
    assert resp.status_code == 200
    titles = [row["title"] for row in resp.json()]
    assert "Another Book" in titles


def test_unsubscribe_book(client, db_session: Session):
    # Pick any book and ensure relation exists
    book = db_session.execute(select(models.Book)).scalars().first()
    user = db_session.execute(
        select(models.User).where(models.User.auth_subject == "test-user-sub-123")
    ).scalar_one()
    rel = db_session.execute(
        select(models.BookUser).where(
            models.BookUser.user_id == user.id, models.BookUser.book_id == book.id
        )
    ).scalar_one_or_none()
    if not rel:
        add_book_to_user(user.id, book.id)

    resp = client.delete(f"/api/books/{book.id}")
    assert resp.status_code == 204

    rel2 = db_session.execute(
        select(models.BookUser).where(
            models.BookUser.user_id == user.id, models.BookUser.book_id == book.id
        )
    ).scalar_one()
    assert rel2.in_library is False


def test_download_requires_subscription(client, db_session: Session):
    # Create a book with no subscription
    b = models.Book(
        provider=(
            models.Provider.ROYALROAD if hasattr(models, "Provider") else "royalroad"
        ),
        provider_fiction_uid="royalroad:unsub",
        source_url="https://rr/fiction/unsub",
        title="Unsubbed",
        author="N",
        language="en",
        cover_url=None,
    )
    db_session.add(b)
    db_session.commit()
    db_session.refresh(b)
    resp = client.post(f"/api/books/{b.id}/download")
    assert resp.status_code == 403


# def test_add_royalroad_book_by_url(client, monkeypatch):
#     """
#     POST /api/books/royalroad should upsert (mocked) and subscribe current user.
#     """
#     # Arrange: monkeypatch ingest to create a Book row and return its id
#     from mywbooks import ingest
#
#     created_ids = {}
#
#     def fake_upsert_from_url(url: str) -> int:
#         # Use the test DB session override to create a book row
#         # We can’t access the session from here directly—so make the API create it:
#         # Trick: call the endpoint twice? Better: patch ingest to stash a marker and
#         # create the row via ORM when the route fetches the book. An easier path:
#         # We know the route will db.get(Book, book_id); so we need a real row.
#         #
#         # Grab the test session via the router’s override:
#         from mywbooks.api.routers import books as books_router
#
#         db: Session = next(
#             books_router.get_db.__wrapped__()
#         )  # get a session from override
#         b = models.Book(
#             provider=(
#                 models.Provider.ROYALROAD
#                 if hasattr(models, "Provider")
#                 else "royalroad"
#             ),
#             provider_fiction_uid="royalroad:21220",
#             source_url=url,
#             title="Test RR Book",
#             author="Author X",
#             language="en",
#             cover_url="https://example/cover.jpg",
#         )
#         db.add(b)
#         db.commit()
#         db.refresh(b)
#         created_ids["id"] = b.id
#         db.close()
#         return b.id
#
#     monkeypatch.setattr(ingest, "upsert_royalroad_book_from_url", fake_upsert_from_url)
#
#     # Act
#     resp = client.post(
#         "/api/books/royalroad", json={"url": "https://www.royalroad.com/fiction/21220"}
#     )
#     assert resp.status_code == 201, resp.text
#     data = resp.json()
#     assert data["title"] == "Test RR Book"
#     assert data["id"] == created_ids["id"]
#
#     # Assert user subscription created
#     # Query the test DB to ensure a BookUser row exists
#     from mywbooks.api.routers import books as books_router
#
#     db: Session = next(books_router.get_db.__wrapped__())
#     user = db.execute(
#         select(models.User).where(models.User.auth_subject == "test-user-sub-123")
#     ).scalar_one()
#     rel = db.execute(
#         select(models.BookUser).where(
#             models.BookUser.user_id == user.id,
#             models.BookUser.book_id == created_ids["id"],
#             models.BookUser.in_library == True,  # noqa: E712
#         )
#     ).scalar_one_or_none()
#     assert rel is not None
#     db.close()
#
#
# def test_list_my_books(client, monkeypatch):
#     """
#     GET /api/books returns current user's library.
#     """
#     # Ensure there is at least one book linked to the user
#     from mywbooks.api.routers import books as books_router
#
#     db: Session = next(books_router.get_db.__wrapped__())
#
#     user = db.execute(
#         select(models.User).where(models.User.auth_subject == "test-user-sub-123")
#     ).scalar_one_or_none()
#     if not user:
#         user = models.User(
#             auth_provider="supabase",
#             auth_subject="test-user-sub-123",
#             email="tester@example.com",
#         )
#         db.add(user)
#         db.commit()
#         db.refresh(user)
#
#     b = models.Book(
#         provider=(
#             models.Provider.royalroad if hasattr(models, "Provider") else "royalroad"
#         ),
#         provider_fiction_uid="royalroad:999",
#         source_url="https://rr/fiction/999",
#         title="Another Book",
#         author="Z",
#         language="en",
#         cover_url=None,
#     )
#     db.add(b)
#     db.commit()
#     db.refresh(b)
#
#     # Use the library API to subscribe (so we test your core logic too)
#     add_book_to_user(user.id, b.id)
#
#     db.close()
#
#     # Act
#     resp = client.get("/api/books")
#     assert resp.status_code == 200
#     books = resp.json()
#     assert any(row["title"] == "Another Book" for row in books)
#
#
# def test_unsubscribe_book(client):
#     """
#     DELETE /api/books/{book_id} should clear in_library for that user.
#     """
#     # Find a book we created earlier
#     from mywbooks.api.routers import books as books_router
#
#     db: Session = next(books_router.get_db.__wrapped__())
#     user = db.execute(
#         select(models.User).where(models.User.auth_subject == "test-user-sub-123")
#     ).scalar_one()
#     book = db.execute(select(models.Book)).scalars().first()
#     # Ensure relation exists
#     rel = db.execute(
#         select(models.BookUser).where(
#             models.BookUser.user_id == user.id, models.BookUser.book_id == book.id
#         )
#     ).scalar_one_or_none()
#     if not rel:
#         add_book_to_user(user.id, book.id)
#     db.close()
#
#     # Act
#     resp = client.delete(f"/api/books/{book.id}")
#     assert resp.status_code == 204
#
#     # Assert flipped
#     db: Session = next(books_router.get_db.__wrapped__())
#     rel2 = db.execute(
#         select(models.BookUser).where(
#             models.BookUser.user_id == user.id, models.BookUser.book_id == book.id
#         )
#     ).scalar_one()
#     assert rel2.in_library is False
#     db.close()
#
#
# def test_download_requires_subscription(client):
#     """
#     POST /api/books/{id}/download returns 403 if the user isn't subscribed.
#     """
#     # Make a new book not in the user's library
#     from mywbooks.api.routers import books as books_router
#
#     db: Session = next(books_router.get_db.__wrapped__())
#     b = models.Book(
#         provider=(
#             models.Provider.royalroad if hasattr(models, "Provider") else "royalroad"
#         ),
#         provider_fiction_uid="royalroad:unsub",
#         source_url="https://rr/fiction/unsub",
#         title="Unsubbed",
#         author="N",
#         language="en",
#         cover_url=None,
#     )
#     db.add(b)
#     db.commit()
#     db.refresh(b)
#     bid = b.id
#     db.close()
#
#     resp = client.post(f"/api/books/{bid}/download")
#     assert resp.status_code == 403
