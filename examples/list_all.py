from mywbooks.db import SessionLocal, get_db, init_db
from mywbooks.models import Book, Chapter, User

init_db()

db = SessionLocal()

try:
    print("=== Users ===")
    for u in db.query(User).all():
        print(f"{u.id}: {u.email} (kindle={u.kindle_email})")

    print("\n=== Books ===")
    for b in db.query(Book).all():
        ch_count = db.query(Chapter).filter(Chapter.book_id == b.id).count()
        fetched = (
            db.query(Chapter)
            .filter(Chapter.book_id == b.id, Chapter.content_html.isnot(None))
            .count()
        )
        print(f"{b.id}: {b.title} [{b.provider}] chapters={ch_count} fetched={fetched}")
finally:
    db.close()
