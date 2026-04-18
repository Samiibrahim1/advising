from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect as sa_inspect, select, text

from app.api.router import api_router
from app.core.config import get_settings
from app.db import Base, engine, SessionLocal
from app.services.bootstrap import seed_defaults

logger = logging.getLogger(__name__)

settings = get_settings()
app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.include_router(api_router, prefix='/api')


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all so unhandled crashes still return JSON with CORS headers."""
    logger.exception('Unhandled error on %s %s', request.method, request.url.path)
    origin = request.headers.get('origin', '')
    headers = {}
    if origin in settings.cors_origins:
        headers = {
            'access-control-allow-origin': origin,
            'access-control-allow-credentials': 'true',
        }
    return JSONResponse(status_code=500, content={'detail': f'{type(exc).__name__}: {exc}'}, headers=headers)


@app.on_event('startup')
def on_startup() -> None:
    # Create tables first (essential for fresh databases like Neon)
    Base.metadata.create_all(bind=engine)

    # Add progress_version_id column to advising_periods if it doesn't exist yet
    existing_cols = {col['name'] for col in sa_inspect(engine).get_columns('advising_periods')}
    if 'progress_version_id' not in existing_cols:
        try:
            with engine.connect() as conn:
                conn.execute(text(
                    'ALTER TABLE advising_periods '
                    'ADD COLUMN progress_version_id INTEGER '
                    'REFERENCES dataset_versions(id)'
                ))
                conn.commit()
        except Exception:
            logger.debug('Column progress_version_id already exists or migration skipped', exc_info=True)

    # Add progress_dataset_version_id and config_version_id to advising_periods
    for col_name in ('progress_dataset_version_id', 'config_version_id'):
        if col_name not in existing_cols:
            try:
                with engine.connect() as conn:
                    conn.execute(text(
                        f'ALTER TABLE advising_periods '
                        f'ADD COLUMN {col_name} INTEGER '
                        f'REFERENCES dataset_versions(id)'
                    ))
                    conn.commit()
            except Exception:
                logger.debug('Column %s already exists or migration skipped', col_name, exc_info=True)

    # Add per-major SMTP columns if they don't exist yet
    major_cols = {col['name'] for col in sa_inspect(engine).get_columns('majors')}
    try:
        with engine.connect() as conn:
            if 'smtp_email' not in major_cols:
                conn.execute(text('ALTER TABLE majors ADD COLUMN smtp_email VARCHAR(255)'))
            if 'smtp_password' not in major_cols:
                conn.execute(text('ALTER TABLE majors ADD COLUMN smtp_password VARCHAR(255)'))
            conn.commit()
    except Exception:
        logger.debug('SMTP columns already exist or migration skipped', exc_info=True)

    session = SessionLocal()
    try:
        seed_defaults(session)

        # Backfill NULL snapshot columns on existing periods
        from app.models import AdvisingPeriod, DatasetVersion
        snapshot_map = {
            'progress_report': 'progress_version_id',
            'progress': 'progress_dataset_version_id',
            'course_config': 'config_version_id',
        }
        periods = session.scalars(select(AdvisingPeriod)).all()
        patched = 0
        for period in periods:
            for ds_type, col_name in snapshot_map.items():
                if getattr(period, col_name) is not None:
                    continue
                # Find the latest dataset version for this major+type created at or before the period
                nearest = session.scalar(
                    select(DatasetVersion)
                    .where(
                        DatasetVersion.major_id == period.major_id,
                        DatasetVersion.dataset_type == ds_type,
                        DatasetVersion.created_at <= period.created_at,
                    )
                    .order_by(DatasetVersion.created_at.desc())
                )
                if nearest:
                    setattr(period, col_name, nearest.id)
                    patched += 1
        if patched:
            session.commit()
    finally:
        session.close()

    # Fix PostgreSQL sequences that are out of sync (e.g. after data migration)
    if 'postgresql' in settings.database_url:
        with engine.connect() as conn:
            tables = sa_inspect(engine).get_table_names()
            for table in tables:
                pk_cols = sa_inspect(engine).get_pk_constraint(table).get('constrained_columns', [])
                if len(pk_cols) == 1 and pk_cols[0] == 'id':
                    conn.execute(text(
                        f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                        f"COALESCE((SELECT MAX(id) FROM \"{table}\"), 0) + 1, false)"
                    ))
            conn.commit()
