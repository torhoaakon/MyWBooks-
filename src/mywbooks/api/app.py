from __future__ import annotations

from typing import Any, AsyncGenerator, Iterable

import dotenv

from mywbooks.api.routers import tasks

dotenv.load_dotenv()

import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db, init_db
from .auth import CurrentUser
from .routers import books


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    init_db()
    yield


app = FastAPI(title="MyWBooks API", lifespan=lifespan)

# CORS (adjust to your frontend origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(books.router, prefix="/api/books", tags=["books"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True}


@app.get("/me")
def me(user: CurrentUser) -> dict[str, Any]:
    # Typical claims you’ll see: sub, email, role, aud, exp, iat
    return {
        "sub": user.get("sub"),
        "email": user.get("email"),
        "role": user.get("role"),
        "aud": user.get("aud"),
    }
