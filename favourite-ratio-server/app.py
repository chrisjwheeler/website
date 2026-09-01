"""Favourite-ratio comparison collector for chris.osmarks.net.

Expects a reverse proxy (osmarks.net nginx) that sets X-Forwarded-For.
The last address in that header is treated as the client, since a trusted
proxy appends the connecting peer (or replaces the header with $remote_addr).
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

N_RATIOS = 9
MAX_BODY_BYTES = 2048
MAX_SESSION_LEN = 64
MAX_TRACKED_IPS = 20000
DB_PATH = Path(os.environ.get("COMPARISONS_DB", Path(__file__).resolve().parent / "data" / "comparisons.sqlite"))

DEFAULT_ORIGINS = [
    "https://twohalv.es",
    "http://127.0.0.1:4000",
    "http://localhost:4000",
]


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "")
    if raw.strip():
        return [item.strip() for item in raw.split(",") if item.strip()]
    return DEFAULT_ORIGINS


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        parts = [part.strip() for part in forwarded.split(",") if part.strip()]
        if parts:
            ip = parts[-1]
            if ip.startswith("[") and "]" in ip:
                ip = ip[1 : ip.index("]")]
            elif ip.count(":") == 1 and ip.rsplit(":", 1)[-1].isdigit():
                ip = ip.rsplit(":", 1)[0]
            return ip
    if request.client and request.client.host:
        return request.client.host
    return "0.0.0.0"


@dataclass
class _Bucket:
    tokens: float
    last: float
    minute_hits: int
    minute_start: float
    day_hits: int
    day_start: float


class RateLimiter:
    rate = 2.0
    burst = 8
    per_minute = 40
    per_day = 2500

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: dict[str, _Bucket] = {}

    def check(self, ip: str) -> Optional[int]:
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(ip)
            if bucket is None:
                if len(self._buckets) >= MAX_TRACKED_IPS:
                    oldest = min(self._buckets, key=lambda key: self._buckets[key].last)
                    del self._buckets[oldest]
                bucket = _Bucket(
                    tokens=self.burst,
                    last=now,
                    minute_hits=0,
                    minute_start=now,
                    day_hits=0,
                    day_start=now,
                )
                self._buckets[ip] = bucket

            bucket.tokens = min(self.burst, bucket.tokens + (now - bucket.last) * self.rate)
            bucket.last = now
            if now - bucket.minute_start >= 60:
                bucket.minute_hits = 0
                bucket.minute_start = now
            if now - bucket.day_start >= 86400:
                bucket.day_hits = 0
                bucket.day_start = now

            limited = bucket.tokens < 1 or bucket.minute_hits >= self.per_minute or bucket.day_hits >= self.per_day
            if limited:
                bucket.tokens = max(0.0, bucket.tokens - 0.25)
                if bucket.day_hits >= self.per_day:
                    return max(1, int(86400 - (now - bucket.day_start)))
                if bucket.minute_hits >= self.per_minute:
                    return max(1, int(60 - (now - bucket.minute_start)))
                return 1

            bucket.tokens -= 1
            bucket.minute_hits += 1
            bucket.day_hits += 1
            return None


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS comparisons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                ip TEXT NOT NULL,
                session TEXT,
                i INTEGER NOT NULL,
                j INTEGER NOT NULL,
                winner INTEGER NOT NULL,
                loser INTEGER NOT NULL,
                winner_ratio REAL,
                loser_ratio REAL
            )
            """
        )
        self._db.commit()

    def insert(self, ip: str, body: "ComparisonIn") -> None:
        row = (
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ip,
            body.session,
            body.i,
            body.j,
            body.winner,
            body.loser,
            body.winner_ratio,
            body.loser_ratio,
        )
        with self._lock:
            self._db.execute(
                """
                INSERT INTO comparisons (
                    ts, ip, session, i, j, winner, loser, winner_ratio, loser_ratio
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )
            self._db.commit()


class ComparisonIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    i: int = Field(ge=0, lt=N_RATIOS)
    j: int = Field(ge=0, lt=N_RATIOS)
    winner: int = Field(ge=0, lt=N_RATIOS)
    loser: int = Field(ge=0, lt=N_RATIOS)
    winner_ratio: Optional[float] = Field(default=None, gt=0, lt=1)
    loser_ratio: Optional[float] = Field(default=None, gt=0, lt=1)
    session: Optional[str] = Field(default=None, max_length=MAX_SESSION_LEN)

    @field_validator("session")
    @classmethod
    def session_charset(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
        if not value or any(ch not in allowed for ch in value):
            raise ValueError("invalid session")
        return value

    @model_validator(mode="after")
    def pair_is_a_real_comparison(self) -> "ComparisonIn":
        if self.i == self.j:
            raise ValueError("a comparison must be between two different ratios")
        if {self.winner, self.loser} != {self.i, self.j}:
            raise ValueError("winner and loser must be the two presented ratios")
        return self


app = FastAPI(title="favourite-ratio", docs_url=None, redoc_url=None, openapi_url=None)
limiter = RateLimiter()
store = Store(DB_PATH)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    allow_credentials=False,
    max_age=600,
)


@app.middleware("http")
async def reject_huge_bodies(request: Request, call_next):
    length = request.headers.get("content-length")
    if length is not None:
        try:
            size = int(length)
        except ValueError:
            return JSONResponse({"detail": "invalid content-length"}, status_code=400)
        if size > MAX_BODY_BYTES:
            return JSONResponse({"detail": "payload too large"}, status_code=413)
    return await call_next(request)


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/comparisons")
def submit_comparison(body: ComparisonIn, request: Request) -> dict[str, bool]:
    ip = client_ip(request)
    retry_after = limiter.check(ip)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="too many comparisons",
            headers={"Retry-After": str(retry_after)},
        )
    store.insert(ip, body)
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8080")),
        proxy_headers=False,
    )
