from mywbooks.db import SessionLocal, init_db
from mywbooks.models import Book, Chapter, User

init_db()

with SessionLocal() as db:
    print("=== Users ===")
    for u in db.query(User).all():
        print(f"{u.id}: {u.email} (kindle={u.kindle_email})")

    print("\n=== Books ===")
    for b in db.query(Book).all():
        print(f"{b.id}: {b.title} by {b.author} [{b.provider}]")
        print(f"  URL: {b.source_url}")
        print(f"  Chapters: {len(b.chapters)}")
