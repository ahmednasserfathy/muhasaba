import os
from functools import lru_cache

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine():
    return create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)


def get_session():
    if not os.environ.get("DATABASE_URL"):
        raise HTTPException(503, "Database is not configured")
    try:
        with Session(get_engine()) as session:
            yield session
    except OperationalError as exc:
        raise HTTPException(503, "Database is unavailable") from exc
