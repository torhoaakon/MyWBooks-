from __future__ import annotations

import dotenv

dotenv.load_dotenv()

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mywbooks.db import init_db

from .auth import CurrentUser
from .routers import books


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup

    print(os.getenv("SUPABASE_ISSUER", "").rstrip("/"))

    init_db()
    yield


app = FastAPI(title="MyWBooks API")

# CORS (adjust to your frontend origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(books.router, prefix="/api/books", tags=["books"])


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/me")
def me(user: CurrentUser):
    # Typical claims you’ll see: sub, email, role, aud, exp, iat
    return {
        "sub": user.get("sub"),
        "email": user.get("email"),
        "role": user.get("role"),
        "aud": user.get("aud"),
    }
