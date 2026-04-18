from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import AdvisingPeriod, Major, SessionSnapshot, StudentSelection
from app.services.import_service import import_legacy_snapshot


def test_import_legacy_snapshot_loads_periods_and_sessions(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", future=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    major_root = tmp_path / "PBHL"
    sessions_root = major_root / "sessions"
    sessions_root.mkdir(parents=True)

    pd.DataFrame([{"Course Code": "PBHL201", "Type": "Required", "Credits": 3, "Offered": "Yes"}]).to_excel(
        major_root / "courses_table.xlsx", index=False
    )
    with pd.ExcelWriter(major_root / "progress_report.xlsx") as writer:
        pd.DataFrame([{"ID": "2023001", "NAME": "Alice Example", "# of Credits Completed": 30, "PBHL201": "Taken"}]).to_excel(
            writer, sheet_name="Required", index=False
        )
    (major_root / "email_roster.json").write_text(json.dumps({"2023001": "alice@example.com"}), encoding="utf-8")
    (major_root / "current_period.json").write_text(
        json.dumps({"period_id": "Spring_2026_A", "semester": "Spring", "year": 2026, "advisor_name": "Tester"}),
        encoding="utf-8",
    )
    (major_root / "periods_history.json").write_text(
        json.dumps([{"period_id": "Fall_2025_A", "semester": "Fall", "year": 2025, "advisor_name": "Tester"}]),
        encoding="utf-8",
    )
    (major_root / "course_exclusions.json").write_text(json.dumps({"2023001": ["PBHL270"]}), encoding="utf-8")
    (sessions_root / "advising_index.json").write_text(
        json.dumps(
            [
                {
                    "id": "sess-1",
                    "title": "Advising Session",
                    "created_at": "2026-01-10T10:00:00",
                    "student_id": "2023001",
                    "student_name": "Alice Example",
                    "period_id": "Spring_2026_A",
                    "session_file": "advising_session_sess-1.json",
                }
            ]
        ),
        encoding="utf-8",
    )
    (sessions_root / "advising_session_sess-1.json").write_text(
        json.dumps(
            {
                "meta": {"id": "sess-1"},
                "snapshot": {
                    "students": [
                        {
                            "ID": "2023001",
                            "NAME": "Alice Example",
                            "advised": ["PBHL202"],
                            "optional": ["PBHL270"],
                            "repeat": [],
                            "note": "Take PBHL202 first",
                            "bypasses": {"PBHL270": {"note": "Approved", "advisor": "Tester"}},
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    session = Session()
    try:
        session.add(Major(code="PBHL", name="Public Health"))
        session.commit()

        result = import_legacy_snapshot(session, major_code="PBHL", import_root=str(tmp_path), user_id=1)

        assert result["imported"]["periods"] == 2
    finally:
        session.close()

    session = Session()
    try:
        major = session.scalar(select(Major).where(Major.code == "PBHL"))
        periods = session.scalars(select(AdvisingPeriod).where(AdvisingPeriod.major_id == major.id)).all()
        selections = session.scalars(select(StudentSelection).where(StudentSelection.major_id == major.id)).all()
        snapshots = session.scalars(select(SessionSnapshot).where(SessionSnapshot.major_id == major.id)).all()

        assert len(periods) == 2
        assert len(selections) == 1
        assert selections[0].advised == ["PBHL202"]
        assert selections[0].optional == ["PBHL270"]
        assert selections[0].note == "Take PBHL202 first"
        assert len(snapshots) == 1
    finally:
        session.close()
