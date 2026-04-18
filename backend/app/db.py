from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# Neon / Render provide postgresql:// URLs; SQLAlchemy needs the +psycopg driver
# suffix to use the installed psycopg v3 (not the legacy psycopg2).
_url = settings.database_url
if _url.startswith('postgresql://'):
    _url = _url.replace('postgresql://', 'postgresql+psycopg://', 1)

_is_sqlite = _url.startswith('sqlite')
connect_args: dict = {'check_same_thread': False} if _is_sqlite else {}

# For Neon serverless Postgres: recycle stale connections aggressively so cold-start
# suspensions don't leave dead connections in the pool.
engine = create_engine(
    _url,
    future=True,
    pool_pre_ping=True,
    connect_args=connect_args,
    **({} if _is_sqlite else {'pool_recycle': 300, 'pool_size': 5, 'max_overflow': 10}),
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass
