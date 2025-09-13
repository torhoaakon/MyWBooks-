from mywbooks.db import init_db
from mywbooks.ingest import upsert_royalroad_book_from_url

init_db()

book_id = upsert_royalroad_book_from_url(
    "https://www.royalroad.com/fiction/21220/mother-of-learning"
)
