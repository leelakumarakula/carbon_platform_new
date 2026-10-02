from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import DB
from app.core.config import get_settings

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: str
    database: str
    environment: str


@router.get("/health", response_model=Health)
def health(db: DB) -> Health:
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "unavailable"
    return Health(status="ok" if database == "ok" else "degraded", database=database,
                  environment=get_settings().APP_ENV)
