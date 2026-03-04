from __future__ import annotations

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from backend.app.core.settings import settings


def _connect_args(url: str) -> dict:
    if url.startswith("sqlite"):
        # Needed for SQLite in multithreaded FastAPI.
        return {"check_same_thread": False}
    return {}


engine = create_engine(settings.database_url, echo=False, connect_args=_connect_args(settings.database_url))


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


