import json
import importlib
import sys
import types
from pathlib import Path

import pytest


class SessionState(dict):
    """Simple dict-backed stub to emulate Streamlit's session_state."""

    def get(self, key, default=None):  # type: ignore[override]
        return super().get(key, default)

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, item):
        try:
            del self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc


streamlit_stub = types.ModuleType("streamlit")
streamlit_stub.session_state = SessionState()
streamlit_stub.secrets = {}


def _passthrough_cache_decorator(*decorator_args, **decorator_kwargs):
    if decorator_args and callable(decorator_args[0]) and len(decorator_args) == 1 and not decorator_kwargs:
        return decorator_args[0]

    def decorator(func):
        return func

    return decorator


streamlit_stub.cache_resource = _passthrough_cache_decorator
streamlit_stub.cache_data = _passthrough_cache_decorator

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True, scope="module")
def install_streamlit_stub():
    original = sys.modules.get("streamlit")
    sys.modules["streamlit"] = streamlit_stub
    try:
        yield
    finally:
        if original is not None:
            sys.modules["streamlit"] = original
        else:
            sys.modules.pop("streamlit", None)


@pytest.fixture(autouse=True)
def reset_session_state():
    streamlit_stub.session_state.clear()
    streamlit_stub.session_state["current_major"] = "CS"
    yield
    streamlit_stub.session_state.clear()


@pytest.fixture
def advising_period_module():
    if "advising_period" in sys.modules:
        importlib.reload(sys.modules["advising_period"])
    else:
        importlib.import_module("advising_period")
    return sys.modules["advising_period"]


def test_get_all_periods_deduplicates_current_and_history(monkeypatch, advising_period_module):
    st = streamlit_stub
    current_period = {
        "period_id": "period-123",
        "semester": "Fall",
        "year": 2023,
        "advisor_name": "Advisor A",
        "created_at": "2023-08-01T10:00:00",
    }
    history_period = {
        "period_id": "period-123",
        "semester": "Fall",
        "year": 2023,
        "advisor_name": "Advisor A",
        "created_at": "2023-08-01T10:00:00",
        "archived_at": "2023-12-15T09:30:00",
    }

    st.session_state.setdefault("current_periods", {})["CS"] = current_period

    monkeypatch.setattr(advising_period_module, "initialize_drive_service", lambda: object())
    monkeypatch.setattr(advising_period_module, "_get_major_folder_id", lambda: "folder")
    monkeypatch.setattr(
        advising_period_module,
        "find_file_in_drive",
        lambda service, filename, folder_id: "history" if filename == advising_period_module.PERIODS_HISTORY_FILENAME else None,
    )
    monkeypatch.setattr(
        advising_period_module,
        "download_file_from_drive",
        lambda service, file_id: json.dumps([history_period]).encode("utf-8"),
    )

    periods = advising_period_module.get_all_periods()

    assert len(periods) == 1
    assert periods[0]["period_id"] == "period-123"
    assert periods[0]["archived_at"] == "2023-12-15T09:30:00"


def test_get_all_periods_falls_back_to_cache_on_drive_failure(monkeypatch, advising_period_module):
    st = streamlit_stub
    current_period = {
        "period_id": "period-999",
        "semester": "Spring",
        "year": 2024,
        "advisor_name": "Advisor B",
        "created_at": "2024-01-05T09:00:00",
    }
    history_period = {
        "period_id": "period-888",
        "semester": "Fall",
        "year": 2023,
        "advisor_name": "Advisor A",
        "created_at": "2023-08-01T10:00:00",
        "archived_at": "2023-12-15T09:30:00",
    }

    st.session_state.setdefault("current_periods", {})["CS"] = current_period

    # First call succeeds and populates the cache
    monkeypatch.setattr(advising_period_module, "initialize_drive_service", lambda: object())
    monkeypatch.setattr(advising_period_module, "_get_major_folder_id", lambda: "folder")
    monkeypatch.setattr(
        advising_period_module,
        "find_file_in_drive",
        lambda service, filename, folder_id: "history" if filename == advising_period_module.PERIODS_HISTORY_FILENAME else None,
    )
    monkeypatch.setattr(
        advising_period_module,
        "download_file_from_drive",
        lambda service, file_id: json.dumps([history_period]).encode("utf-8"),
    )

    first_results = advising_period_module.get_all_periods()
    assert len(first_results) == 2

    # Second call simulates Drive failure and should use cached history instead
    monkeypatch.setattr(advising_period_module, "initialize_drive_service", lambda: None)
    monkeypatch.setattr(advising_period_module, "_get_major_folder_id", lambda: "")

    second_results = advising_period_module.get_all_periods()

    assert second_results == first_results
