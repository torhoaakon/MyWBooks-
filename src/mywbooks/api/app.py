from __future__ import annotations

import dotenv

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
async def lifespan(app: FastAPI):
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


@app.get("/tasks/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(models.Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "id": task.id,
        "type": task.type,
        "status": task.status,
        "payload": task.payload,
        "error": task.error,
        "created_at": task.created_at.isoformat(),
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
    }
