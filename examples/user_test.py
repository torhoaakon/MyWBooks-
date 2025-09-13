from mywbooks.auth import create_user, verify_user
from mywbooks.db import init_db
from mywbooks.ingest import (
    fetch_missing_chapters_for_book,
    upsert_royalroad_book_from_url,
)
from mywbooks.library import add_book_to_user

init_db()


uid = verify_user("me@example.com", "S3cret!")
if uid is None:
    uid = create_user("me@example.com", "S3cret!", "me@kindle.com")
if uid is None:
    exit(1)

book_id = upsert_royalroad_book_from_url(
    "https://www.royalroad.com/fiction/21220/mother-of-learning"
)

print("Indexed chapters. Now fetching first 5…")
n = fetch_missing_chapters_for_book(book_id, limit=5)
print("Fetched:", n)

add_book_to_user(uid, book_id)
