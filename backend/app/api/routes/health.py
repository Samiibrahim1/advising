from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(prefix='/health', tags=['health'])


@router.get('')
def health_check():
    s = get_settings()
    # Search upward for legacy modules
    d = Path(__file__).resolve().parent
    legacy_root = None
    for _ in range(8):
        if (d / 'eligibility_utils.py').exists():
            legacy_root = d
            break
        d = d.parent
    return {
        'status': 'ok',
        'cors_origins': s.cors_origins,
        'db_driver': 'postgresql' if 'postgresql' in s.database_url else 'sqlite',
        'legacy_root': str(legacy_root) if legacy_root else None,
        'legacy_modules_found': legacy_root is not None,
        'cwd': str(Path.cwd()),
    }
