from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from portal_app.persistence.database import check_database

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "portal"}


@router.get("/ready")
def ready(request: Request) -> dict[str, str]:
    try:
        check_database(request.app.state.database_engine)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ready", "service": "portal"}
