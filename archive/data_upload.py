# data_upload.py
# Auto-syncs uploads to Drive with per-major filenames (replaces existing files),
# and also writes a timestamped version for provenance/rollback.

from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import datetime

from advising_utils import log_info, log_error, load_progress_excel

def _get_drive_module():
    """Lazy loader for google_drive module to avoid import-time side effects."""
    import google_drive as gd
    return gd


def _drive_service_or_none():
    try:
        gd = _get_drive_module()
        return gd.initialize_drive_service()
    except Exception as e:
        # Clear message once in the sidebar; app still works locally
        st.sidebar.warning(
            "Google Drive sync unavailable: " + str(e) +
            "\n\nFix: Re-authorize and update google.refresh_token in your Streamlit Secrets."
        )
        log_error("Drive init failed", e)
        return None


def _get_root_folder_id() -> str:
    """Get root folder ID from secrets or env."""
    import os
    folder_id = ""
    try:
        if "google" in st.secrets:
            folder_id = st.secrets["google"].get("folder_id", "")
    except:
        pass
    
    if not folder_id:
        folder_id = os.getenv("GOOGLE_FOLDER_ID", "")
    
    return folder_id


def _sync_to_major_folder(
    *,
    service,
    major: str,
    base_name: str,          # "courses_table" OR "progress_report"
    content: bytes,
    mime: str = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
):
    """
    Sync file to major-specific folder in Drive, replacing if exists.
    File will be named: {base_name}.xlsx (e.g., courses_table.xlsx)
    Stored in folder: {ROOT_FOLDER}/{MAJOR}/ (e.g., {ROOT}/PBHL/)
    """
    if not service:
        return

    root_folder_id = _get_root_folder_id()
    if not root_folder_id:
        return
    
    # Get or create major-specific folder
    gd = _get_drive_module()
    major_folder_id = gd.get_major_folder_id(service, major, root_folder_id)
    
    # Sync file (replaces if exists)
    filename = f"{base_name}.xlsx"
    gd.sync_file_with_drive(
        service=service,
        file_content=content,
        drive_file_name=filename,
        mime_type=mime,
        parent_folder_id=major_folder_id,
    )


def upload_data():
    """
    Handle uploading of courses table, progress report, and advising selections
    for the CURRENT major. Automatically syncs to major-specific folder in Drive.
    Uses stepwise accordion interface with validation feedback.
    """
    st.sidebar.header(f"📁 Data Upload: {st.session_state.get('current_major', 'Select Major')}")

    current_major = st.session_state.get("current_major")
    if not current_major:
        st.sidebar.warning("Select a major to upload files.")
        return

    # Try Drive (optional; local still works)
    service = _drive_service_or_none()
    
    # Check current status
    courses_loaded = not st.session_state.get("courses_df", pd.DataFrame()).empty
    progress_loaded = not st.session_state.get("progress_df", pd.DataFrame()).empty
    num_students = len(st.session_state.get("progress_df", pd.DataFrame()))

    # ---------- Step 1: Upload Courses Table ----------
    step1_icon = "✅" if courses_loaded else "📋"
    with st.sidebar.expander(f"{step1_icon} Step 1: Courses Table", expanded=not courses_loaded):
        if courses_loaded:
            num_courses = len(st.session_state.courses_df)
            st.success(f"✅ {num_courses} courses loaded")
        else:
            st.info("Upload Excel file with course information")
        
        # Template download button
        try:
            with open("templates/courses_table_template.xlsx", "rb") as f:
                st.download_button(
                    label="📥 Download Template",
                    data=f.read(),
                    file_name="courses_table_template.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    help="Download blank template with example data and proper formatting"
                )
        except:
            pass  # Template file not found, skip download button
        
        courses_file = st.file_uploader(
            "Select Courses Table (Excel)",
            type=["xlsx"],
            key=f"courses_upload_{current_major}",
            label_visibility="collapsed"
        )
        if courses_file:
            try:
                courses_file.seek(0)
                df = pd.read_excel(courses_file)
                
                # Validation
                required_cols = ["Course Code", "Offered"]
                missing_cols = [col for col in required_cols if col not in df.columns]
                if missing_cols:
                    st.error(f"❌ Missing columns: {', '.join(missing_cols)}")
                    log_error("Courses table validation failed", Exception(f"Missing: {missing_cols}"))
                else:
                    st.session_state.courses_df = df
                    st.session_state.majors[current_major]["courses_df"] = df
                    # Clear cached co-requisite/concurrent courses list when new courses table is uploaded
                    if "coreq_concurrent_courses" in st.session_state:
                        del st.session_state.coreq_concurrent_courses
                    st.success(f"✅ Loaded {len(df)} courses")
                    log_info(f"Courses table uploaded via sidebar ({current_major}).")

                    # Auto-sync to Drive
                    if service:
                        courses_file.seek(0)
                        raw = courses_file.read()
                        _sync_to_major_folder(
                            service=service,
                            major=current_major,
                            base_name="courses_table",
                            content=raw,
                        )
                        st.info(f"☁️ Synced to Drive")
            except Exception as e:
                st.session_state.courses_df = pd.DataFrame()
                st.session_state.majors[current_major]["courses_df"] = pd.DataFrame()
                st.error(f"❌ Error: {str(e)}")
                log_error("Error loading courses table", e)

    # ---------- Step 2: Upload Progress Report ----------
    step2_icon = "✅" if progress_loaded else "📊"
    with st.sidebar.expander(f"{step2_icon} Step 2: Progress Report", expanded=courses_loaded and not progress_loaded):
        if progress_loaded:
            st.success(f"✅ {num_students} students loaded")
        else:
            st.info("Upload Excel file with student progress data")
            if not courses_loaded:
                st.warning("⚠️ Upload courses table first")
        
        # Template download button
        try:
            with open("templates/progress_report_template.xlsx", "rb") as f:
                st.download_button(
                    label="📥 Download Template",
                    data=f.read(),
                    file_name="progress_report_template.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    help="Download blank template with example student data and proper formatting"
                )
        except:
            pass  # Template file not found, skip download button
        
        progress_file = st.file_uploader(
            "Select Progress Report (Excel)",
            type=["xlsx"],
            key=f"progress_upload_{current_major}",
            label_visibility="collapsed",
            disabled=not courses_loaded
        )
        if progress_file:
            try:
                progress_file.seek(0)
                content = progress_file.read()
                df = load_progress_excel(content)
                
                # Validation
                required_cols = ["ID", "NAME"]
                missing_cols = [col for col in required_cols if col not in df.columns]
                if missing_cols:
                    st.error(f"❌ Missing columns: {', '.join(missing_cols)}")
                    log_error("Progress report validation failed", Exception(f"Missing: {missing_cols}"))
                else:
                    st.session_state.progress_df = df
                    st.session_state.majors[current_major]["progress_df"] = df
                    st.success(f"✅ Loaded {len(df)} students (Required + Intensive merged)")
                    log_info(f"Progress report uploaded and merged via sidebar ({current_major}).")

                    # Auto-sync to Drive
                    if service:
                        _sync_to_major_folder(
                            service=service,
                            major=current_major,
                            base_name="progress_report",
                            content=content,
                        )
                        st.info(f"☁️ Synced to Drive")
            except Exception as e:
                st.session_state.progress_df = pd.DataFrame()
                st.session_state.majors[current_major]["progress_df"] = pd.DataFrame()
                st.error(f"❌ Error: {str(e)}")
                log_error("Error loading progress report", e)

    # ---------- Step 3: Upload Advising Selections (Optional) ----------
    selections_loaded = bool(st.session_state.get("advising_selections"))
    step3_icon = "✅" if selections_loaded else "📝"
    with st.sidebar.expander(f"{step3_icon} Step 3: Advising Selections (Optional)", expanded=False):
        if selections_loaded:
            num_advised = len(st.session_state.advising_selections)
            st.success(f"✅ {num_advised} students have advising data")
        else:
            st.info("Optional: Upload pre-existing advising selections")
        
        sel_file = st.file_uploader(
            "Select Advising Selections (Excel/CSV)",
            type=["xlsx", "csv"],
            key=f"sel_upload_{current_major}",
            label_visibility="collapsed",
            help="Columns: ID, Advised, Optional, Note"
        )
        if sel_file:
            try:
                if sel_file.name.lower().endswith(".csv"):
                    df = pd.read_csv(sel_file)
                else:
                    df = pd.read_excel(sel_file)
                
                if "ID" not in df.columns:
                    st.error("❌ Missing 'ID' column")
                else:
                    selections = {}
                    for _, r in df.iterrows():
                        sid = int(r.get("ID"))
                        advised = str(r.get("Advised") or "").split(",") if "Advised" in r else []
                        optional = str(r.get("Optional") or "").split(",") if "Optional" in r else []
                        note = r.get("Note") or ""
                        selections[sid] = {
                            "advised": [c.strip() for c in advised if c.strip()],
                            "optional": [c.strip() for c in optional if c.strip()],
                            "note": note,
                        }
                    st.session_state.advising_selections = selections
                    st.session_state.majors[current_major]["advising_selections"] = selections
                    st.success(f"✅ Loaded advising data for {len(selections)} students")
                    log_info(f"Advising selections uploaded via sidebar ({current_major}).")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                log_error("Error loading advising selections", e)

    # ---------- Step 4: Upload Email Roster (Optional) ----------
    from email_manager import load_email_roster
    roster = load_email_roster()
    step4_icon = "✅" if roster else "📧"
    
    with st.sidebar.expander(f"{step4_icon} Step 4: Email Roster (Optional)", expanded=False):
        if roster:
            st.success(f"✅ {len(roster)} student emails on file")
        else:
            st.info("Optional: Upload student email addresses for emailing advising sheets")
        
        # Template download button
        try:
            with open("templates/email_roster_template.csv", "rb") as f:
                st.download_button(
                    label="📥 Download Template",
                    data=f.read(),
                    file_name="email_roster_template.csv",
                    mime="text/csv",
                    help="Download blank template for student email addresses"
                )
        except:
            pass  # Template file not found, skip download button
        
        email_file = st.file_uploader(
            "Select Email Roster (Excel/CSV)",
            type=["xlsx", "csv"],
            key=f"email_upload_{current_major}",
            label_visibility="collapsed",
            help="Columns: ID and Email"
        )
        if email_file:
            from email_manager import upload_email_roster_from_file
            count_added, errors = upload_email_roster_from_file(email_file)
            
            if count_added > 0:
                st.success(f"✅ Added/updated {count_added} email(s)")
                log_info(f"Email roster uploaded: {count_added} emails for {current_major}")
            
            if errors:
                with st.expander("⚠️ See errors", expanded=False):
                    for err in errors:
                        st.write(f"• {err}")
    
    # ---------- Email Settings ----------
    st.sidebar.markdown("---")
    with st.sidebar.expander("⚙️ Email Configuration", expanded=False):
        from email_manager import get_email_credentials
        
        email_addr, email_pass = get_email_credentials()
        
        if email_addr and email_pass:
            st.success(f"✅ Email configured: {email_addr}")
            st.info("Email credentials are stored in Replit/Streamlit secrets.")
        else:
            st.warning("⚠️ Email not configured")
            st.write("To enable email sending, add these secrets:")
            st.code("""
[email]
address = "your-email@outlook.com"
password = "your-app-password"
            """, language="toml")
            st.caption("**For Outlook/Office 365:**")
            st.caption("• Use your full university email address")
            st.caption("• Use app password (not regular password)")
            st.caption("• [Generate app password](https://support.microsoft.com/en-us/account-billing/using-app-passwords-with-apps-that-don-t-support-two-step-verification-5896ed9b-4263-e681-128a-a6f2979a7944)")
            st.caption("**On Streamlit Cloud:** Add to Secrets in Settings")
            st.caption("**On Replit:** Add to Secrets in Tools sidebar")
