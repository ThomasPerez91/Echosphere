"""Infrastructure probes only; no gameplay is implemented."""

import os

import psycopg
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Echosphere", version="0.0.1")


def check_database() -> None:
    # Keyword arguments preserve passwords containing URI-reserved characters.
    with psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "echosphere"),
        user=os.getenv("POSTGRES_USER", "echosphere"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        connect_timeout=3,
        options="-c timezone=UTC -c statement_timeout=3000",
    ) as connection:
        connection.execute("SELECT 1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    try:
        check_database()
    except (psycopg.Error, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ready"}
