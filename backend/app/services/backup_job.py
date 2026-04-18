from __future__ import annotations

import gzip
import json
import logging
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import SessionLocal, engine
from app.models import BackupRun
from app.services.storage import StorageService

logger = logging.getLogger(__name__)


def _pg_url(database_url: str) -> str:
    """Convert a SQLAlchemy database URL to a plain libpq connection string.

    Strips the '+driver' dialect suffix (e.g. postgresql+psycopg → postgresql)
    and removes channel_binding param which pg_dump/psql don't support.
    """
    import re
    url = re.sub(r'^postgresql\+\w+://', 'postgresql://', database_url)
    url = re.sub(r'[&?]channel_binding=[^&]*', '', url)
    # If the first remaining param lost its '?', fix it
    url = re.sub(r'\?&', '?', url)
    url = url.replace('&', '?', 1) if '?' not in url and '&' in url else url
    return url


def _find_pg_dump() -> str:
    """Locate pg_dump executable, searching common install paths."""
    found = shutil.which('pg_dump')
    if found:
        return found
    for candidate in [
        '/opt/homebrew/bin/pg_dump',      # Apple Silicon Homebrew
        '/usr/local/bin/pg_dump',          # Intel Homebrew
        '/usr/bin/pg_dump',                # Linux system
        '/usr/local/pgsql/bin/pg_dump',    # Manual PostgreSQL install
    ]:
        if Path(candidate).is_file():
            return candidate
    raise FileNotFoundError(
        'pg_dump not found. Install PostgreSQL client tools '
        '(e.g. `brew install libpq` on macOS, `apt install postgresql-client` on Linux).'
    )


def _count_storage_files(local_root: Path) -> dict[str, int]:
    """Return a compact count of stored files per category folder."""
    counts: dict[str, int] = {}
    if local_root.exists():
        for child in local_root.iterdir():
            if child.is_dir():
                counts[child.name] = sum(1 for _ in child.rglob('*') if _.is_file())
    return counts


def run_backup(triggered_by: str = 'scheduled') -> BackupRun:
    settings = get_settings()
    storage = StorageService()
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    database_url = settings.database_url

    if database_url.startswith('sqlite'):
        # SQLite: copy the .db file directly
        db_path = database_url.split(':///')[-1]
        dump_path = Path('/tmp') / f'advising-v2-{timestamp}.db.gz'
        with open(db_path, 'rb') as src, dump_path.open('wb') as dst:
            dst.write(gzip.compress(src.read()))
        key = f'backups/{timestamp}/database.db.gz'
    else:
        # PostgreSQL: use pg_dump
        dump_path = Path('/tmp') / f'advising-v2-{timestamp}.sql.gz'
        pg_dump_bin = _find_pg_dump()
        with dump_path.open('wb') as handle:
            proc = subprocess.run([pg_dump_bin, '--dbname', _pg_url(database_url)], check=True, capture_output=True)
            handle.write(gzip.compress(proc.stdout))
        key = f'backups/{timestamp}/database.sql.gz'

    storage.put_bytes(key, dump_path.read_bytes(), 'application/gzip')
    dump_path.unlink(missing_ok=True)
    storage_counts = _count_storage_files(storage.local_root)
    session: Session = SessionLocal()
    try:
        run = BackupRun(
            status='completed',
            storage_key=key,
            manifest={
                'timestamp': timestamp,
                'triggered_by': triggered_by,
                'storage_file_counts': storage_counts,
            },
            notes=f'Backup triggered by {triggered_by}',
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        return run
    finally:
        session.close()


if __name__ == '__main__':
    run = run_backup()
    print(json.dumps({'backup_run_id': run.id, 'storage_key': run.storage_key}))


def _find_psql() -> str:
    """Locate psql executable, searching common install paths."""
    found = shutil.which('psql')
    if found:
        return found
    for candidate in [
        '/opt/homebrew/bin/psql',
        '/usr/local/bin/psql',
        '/usr/bin/psql',
        '/usr/local/pgsql/bin/psql',
    ]:
        if Path(candidate).is_file():
            return candidate
    raise FileNotFoundError('psql not found. Install PostgreSQL client tools.')


def restore_backup(backup_id: int, triggered_by: str = 'admin') -> dict:
    """Restore a database from a completed backup.

    - Creates a safety backup before restoring.
    - SQLite: decompress .db.gz and overwrite the database file, then dispose engine pool.
    - PostgreSQL: decompress .sql.gz and pipe into psql.
    """
    settings = get_settings()
    storage = StorageService()
    database_url = settings.database_url

    session: Session = SessionLocal()
    try:
        backup = session.get(BackupRun, backup_id)
        if not backup:
            raise ValueError(f'Backup #{backup_id} not found.')
        if backup.status != 'completed' or not backup.storage_key:
            raise ValueError(f'Backup #{backup_id} is not a completed backup with a storage key.')

        storage_key = backup.storage_key
        logger.info('Restoring backup #%d from %s (triggered by %s)', backup_id, storage_key, triggered_by)

        compressed = storage.get_bytes(storage_key)
        raw = gzip.decompress(compressed)
    finally:
        session.close()

    # Safety net: create a pre-restore backup so the current state is recoverable
    try:
        safety = run_backup(triggered_by=f'pre-restore-safety (before restoring #{backup_id})')
        logger.info('Pre-restore safety backup created: #%d (%s)', safety.id, safety.storage_key)
    except Exception:
        logger.warning('Pre-restore safety backup failed — proceeding with restore anyway', exc_info=True)

    if database_url.startswith('sqlite'):
        db_path = Path(database_url.split(':///')[-1])
        # Close all pooled connections before overwriting the file
        engine.dispose()
        db_path.write_bytes(raw)
        logger.info('SQLite database restored (%d bytes) from backup #%d', len(raw), backup_id)
    else:
        psql_bin = _find_psql()
        proc = subprocess.run(
            [psql_bin, '--dbname', _pg_url(database_url)],
            input=raw,
            capture_output=True,
        )
        if proc.returncode != 0:
            stderr = proc.stderr.decode(errors='replace')[:500]
            raise RuntimeError(f'psql restore failed: {stderr}')
        logger.info('PostgreSQL database restored from backup #%d', backup_id)

    return {'message': f'Database restored from backup #{backup_id}.'}
