from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Major
from app.services.dataset_service import _json_safe_records


def test_json_safe_records_replaces_nan():
    df = pd.DataFrame([{'ID': 1, 'NAME': 'Alice', 'Score': None}])
    records = _json_safe_records(df)
    assert records == [{'ID': 1, 'NAME': 'Alice', 'Score': None}]
