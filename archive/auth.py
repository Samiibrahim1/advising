from __future__ import annotations

import json
import os
from typing import Any, Dict

import streamlit as st

AUTH_FILE_NAME = "major_auth.json"


def _auth_required() -> bool:
    raw = os.getenv("AUTH_REQUIRED")
    if raw is None:
        return True
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _get_root_folder_id() -> str:
    root_folder_id = ""
    try:
        if "google" in st.secrets:
            root_folder_id = st.secrets["google"].get("folder_id", "")
    except Exception:
        pass
    if not root_folder_id:
        root_folder_id = os.getenv("GOOGLE_FOLDER_ID", "")
    return root_folder_id


def _default_auth_config() -> Dict[str, Any]:
    return {
        "enabled": True,
        "majors": {},
        "error": "",
    }


def load_auth_config(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Load per-major auth config from Google Drive root folder.
    Expected JSON shape:
    {
      "enabled": true,
      "majors": {"PBHL": "pw1", ...}
    }
    """
    cache_key = "_major_auth_config"
    if not force_refresh and cache_key in st.session_state:
        return st.session_state[cache_key]

    cfg = _default_auth_config()

    if not _auth_required():
        cfg["enabled"] = False
        st.session_state[cache_key] = cfg
        return cfg

    root_folder_id = _get_root_folder_id()
    if not root_folder_id:
        cfg["error"] = "Missing GOOGLE folder configuration."
        st.session_state[cache_key] = cfg
        return cfg

    try:
        import google_drive as gd

        service = gd.initialize_drive_service()
        fid = gd.find_file_in_drive(service, AUTH_FILE_NAME, root_folder_id)
        if not fid:
            cfg["error"] = f"Auth file '{AUTH_FILE_NAME}' was not found in the Google Drive root folder."
            st.session_state[cache_key] = cfg
            return cfg

        raw = gd.download_file_from_drive(service, fid)
        payload = json.loads(raw.decode("utf-8"))

        cfg["enabled"] = bool(payload.get("enabled", True))
        majors = payload.get("majors", {})
        if isinstance(majors, dict):
            cfg["majors"] = {str(k): str(v) for k, v in majors.items()}
        else:
            cfg["error"] = "Invalid auth file format: 'majors' must be an object."
    except Exception as e:
        cfg["error"] = f"Failed to load auth config: {e}"

    st.session_state[cache_key] = cfg
    return cfg


def auth_is_enforced(cfg: Dict[str, Any]) -> bool:
    return _auth_required() and bool(cfg.get("enabled", True))


def _auth_map() -> Dict[str, bool]:
    if "auth_ok_by_major" not in st.session_state:
        st.session_state.auth_ok_by_major = {}
    return st.session_state.auth_ok_by_major


def is_authenticated_for_major(major: str) -> bool:
    return bool(_auth_map().get(str(major), False))


def set_authenticated_for_major(major: str, ok: bool) -> None:
    m = _auth_map()
    m[str(major)] = bool(ok)
    st.session_state.auth_ok_by_major = m


def render_login_gate(selected_major: str, cfg: Dict[str, Any]) -> bool:
    """
    Render major login gate.
    Returns True when user is authenticated for selected_major.
    """
    if not auth_is_enforced(cfg):
        return True

    if is_authenticated_for_major(selected_major):
        return True

    if cfg.get("error"):
        st.error(cfg["error"])
        st.info(
            f"Upload '{AUTH_FILE_NAME}' to your Google Drive root folder, "
            "or set AUTH_REQUIRED=false to temporarily bypass auth."
        )
        return False

    expected = cfg.get("majors", {}).get(selected_major)
    if not expected:
        st.error(f"No password is configured for major '{selected_major}' in {AUTH_FILE_NAME}.")
        return False

    st.markdown("## Login Required")
    st.info(f"Enter the password for **{selected_major}** to continue.")

    form_key = f"major_login_form_{selected_major}"
    with st.form(form_key):
        entered = st.text_input("Major Password", type="password", key=f"major_pw_{selected_major}")
        submitted = st.form_submit_button("Unlock Major", type="primary")

    if submitted:
        if entered == expected:
            set_authenticated_for_major(selected_major, True)
            st.success("Access granted.")
            st.rerun()
        else:
            st.error("Incorrect password.")

    return False
