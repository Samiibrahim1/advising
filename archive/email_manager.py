# email_manager.py
"""
Email management module for sending advising sheets to students via Outlook/Office 365.
Works on both Replit and Streamlit Cloud using standard Python SMTP library.
"""

from __future__ import annotations

import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Any
import pandas as pd
import streamlit as st

from advising_utils import log_info, log_error

def _get_drive_module():
    """Lazy loader for google_drive module to avoid import-time side effects."""
    import google_drive as gd
    return gd


# ----------------- Email Roster Management -----------------

def _get_email_roster_filename() -> str:
    """Get the email roster filename for current major."""
    return "email_roster.json"


def _get_major_folder_id_internal() -> str:
    """Get major-specific folder ID for email roster storage."""
    try:
        gd = _get_drive_module()
        service = gd.initialize_drive_service()
        major = st.session_state.get("current_major", "DEFAULT")
        
        # Get root folder ID
        root_folder_id = ""
        try:
            if "google" in st.secrets:
                root_folder_id = st.secrets["google"].get("folder_id", "")
        except:
            pass
        
        if not root_folder_id:
            root_folder_id = os.getenv("GOOGLE_FOLDER_ID", "")
        
        if not root_folder_id:
            return ""
        
        # Get or create major-specific folder
        return gd.get_major_folder_id(service, major, root_folder_id)
    except Exception:
        return ""


def load_email_roster() -> Dict[str, str]:
    """
    Load email roster from Drive (student_id -> email mapping).
    Returns dict like: {"202001234": "student@example.com", ...}
    """
    # Get current major for scoped caching
    major = st.session_state.get("current_major", "DEFAULT")
    
    # Initialize per-major email roster storage
    if "email_rosters" not in st.session_state:
        st.session_state.email_rosters = {}
    
    # Try session state cache first (scoped per major)
    if major in st.session_state.email_rosters:
        return st.session_state.email_rosters[major]
    
    # Try loading from Drive
    try:
        gd = _get_drive_module()
        service = gd.initialize_drive_service()
        folder_id = _get_major_folder_id_internal()
        if not folder_id:
            st.session_state.email_rosters[major] = {}
            return {}
        
        fid = gd.find_file_in_drive(service, _get_email_roster_filename(), folder_id)
        if not fid:
            st.session_state.email_rosters[major] = {}
            return {}
        
        data = gd.download_file_from_drive(service, fid)
        roster = json.loads(data.decode("utf-8"))
        
        # Cache in session state (per major)
        st.session_state.email_rosters[major] = roster
        log_info(f"Email roster loaded from Drive for {major} ({len(roster)} emails)")
        return roster
    except Exception as e:
        log_error(f"Failed to load email roster from Drive for {major}", e)
        st.session_state.email_rosters[major] = {}
        return {}


def save_email_roster(roster: Dict[str, str]) -> None:
    """
    Save email roster to Drive and session state.
    roster: dict of student_id -> email
    """
    # Get current major for scoped caching
    major = st.session_state.get("current_major", "DEFAULT")
    
    # Initialize per-major email roster storage
    if "email_rosters" not in st.session_state:
        st.session_state.email_rosters = {}
    
    # Save to session state first (local-first, per major)
    st.session_state.email_rosters[major] = roster
    
    # Background save to Drive (best effort)
    try:
        gd = _get_drive_module()
        service = gd.initialize_drive_service()
        folder_id = _get_major_folder_id_internal()
        if not folder_id:
            log_info(f"Email roster saved locally only for {major} (no Drive folder configured)")
            return
        
        data = json.dumps(roster, ensure_ascii=False, indent=2).encode("utf-8")
        gd.sync_file_with_drive(service, data, _get_email_roster_filename(), "application/json", folder_id)
        log_info(f"Email roster synced to Drive for {major} ({len(roster)} emails)")
    except Exception as e:
        log_error(f"Failed to sync email roster to Drive for {major} (local copy preserved)", e)


def upload_email_roster_from_file(uploaded_file) -> tuple[int, List[str]]:
    """
    Parse uploaded Excel/CSV file with student IDs and emails.
    Expected columns: 'ID' and 'Email' (or similar variations)
    
    Returns: (count_added, error_messages)
    """
    errors = []
    
    try:
        # Read file
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        # Normalize column names
        df.columns = [str(col).strip() for col in df.columns]
        
        # Find ID and Email columns (case-insensitive)
        id_col = None
        email_col = None
        
        for col in df.columns:
            col_lower = col.lower()
            if col_lower in ['id', 'student_id', 'student id', 'studentid']:
                id_col = col
            elif col_lower in ['email', 'e-mail', 'mail', 'email address']:
                email_col = col
        
        if not id_col:
            return 0, ["Could not find ID column. Expected: 'ID', 'Student_ID', or similar"]
        if not email_col:
            return 0, ["Could not find Email column. Expected: 'Email', 'E-mail', or similar"]
        
        # Load existing roster
        roster = load_email_roster()
        count_added = 0
        
        # Process each row
        for idx, row in df.iterrows():
            try:
                student_id = str(row[id_col]).strip()
                email = str(row[email_col]).strip().lower()
                
                # Skip empty rows
                if not student_id or student_id == 'nan' or not email or email == 'nan':
                    continue
                
                # Basic email validation
                if '@' not in email or '.' not in email:
                    errors.append(f"Row {idx+2}: Invalid email format: {email}")
                    continue
                
                # Add to roster
                roster[student_id] = email
                count_added += 1
                
            except Exception as e:
                errors.append(f"Row {idx+2}: Error processing row - {str(e)}")
        
        # Save updated roster
        if count_added > 0:
            save_email_roster(roster)
        
        return count_added, errors
        
    except Exception as e:
        return 0, [f"Failed to read file: {str(e)}"]


def get_student_email(student_id: str) -> Optional[str]:
    """Get email address for a student ID."""
    roster = load_email_roster()
    return roster.get(str(student_id))


# ----------------- Email Sending (Outlook/Office 365) -----------------

def get_email_credentials() -> tuple[Optional[str], Optional[str]]:
    """
    Get email credentials from secrets or environment variables.
    Works on both Replit and Streamlit Cloud.
    
    Returns: (email_address, password)
    """
    email_address = None
    password = None
    
    # Try Streamlit secrets first
    try:
        if "email" in st.secrets:
            email_address = st.secrets["email"].get("address")
            password = st.secrets["email"].get("password")
    except:
        pass
    
    # Fall back to environment variables
    if not email_address:
        email_address = os.getenv("EMAIL_ADDRESS")
    if not password:
        password = os.getenv("EMAIL_PASSWORD")
    
    return email_address, password


def send_advising_email(
    to_email: str,
    student_name: str,
    student_id: str,
    advised_courses: List[str],
    repeat_courses: List[str],
    optional_courses: List[str],
    note: str,
    courses_df: pd.DataFrame,
    remaining_credits: int = 0,
    period_info: str = "",
    advisor_email: Optional[str] = None,
    cc_advisor: bool = True,
) -> tuple[bool, str]:
    """
    Send advising sheet email to student via Outlook/Office 365 SMTP.
    
    Args:
        to_email: Recipient email address
        student_name: Student's name
        student_id: Student's ID
        advised_courses: List of advised course codes
        repeat_courses: List of repeat course codes
        optional_courses: List of optional course codes
        note: Advisor's note/message
        courses_df: Courses table for course details
        remaining_credits: Remaining credits to graduation
        period_info: Advising period information (semester/year/advisor)
        advisor_email: Email of advisor to CC (optional)
        cc_advisor: Whether to CC the advisor on the email
    
    Returns:
        (success: bool, message: str)
    """
    # Get credentials
    from_email, password = get_email_credentials()
    
    if not from_email or not password:
        return False, "Email credentials not configured. Please add EMAIL_ADDRESS and EMAIL_PASSWORD to secrets."
    
    try:
        # Calculate credits for each category
        def get_credits(course_list):
            total = 0
            for code in course_list:
                course_info = courses_df[courses_df['Course Code'] == code]
                if not course_info.empty:
                    total += int(course_info.iloc[0].get('Credits', 0) or 0)
            return total
        
        advised_credits = get_credits(advised_courses)
        repeat_credits = get_credits(repeat_courses)
        optional_credits = get_credits(optional_courses)
        
        # Build email content
        subject = f"Academic Advising - {st.session_state.get('current_major', '')} Program"
        if period_info:
            subject = f"{subject} - {period_info}"
        
        # Create HTML email body
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background-color: #0066cc; color: white; padding: 20px; text-align: center; }}
                .period {{ background-color: #0052a3; color: white; padding: 10px; text-align: center; font-weight: bold; }}
                .content {{ padding: 20px; }}
                .summary {{ background-color: #f0f8ff; padding: 15px; margin: 15px 0; border-radius: 5px; }}
                .course-list {{ margin: 15px 0; }}
                .course-item {{ padding: 8px; margin: 5px 0; border-left: 3px solid #0066cc; background-color: #f5f5f5; }}
                .repeat-item {{ border-left-color: #ff6600; }}
                .optional-item {{ border-left-color: #666; }}
                .note {{ background-color: #fffacd; padding: 15px; margin: 15px 0; border-radius: 5px; }}
                .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 0.9em; color: #666; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Academic Advising Sheet</h1>
                <p>{st.session_state.get('current_major', '')} Program</p>
            </div>
            {f'<div class="period">{period_info}</div>' if period_info else ''}
            <div class="content">
                <p>Dear {student_name},</p>
                <p>Below is your academic advising recommendation for the upcoming semester.</p>
                
                <h3>Student Information</h3>
                <p><strong>Name:</strong> {student_name}<br>
                <strong>ID:</strong> {student_id}<br>
                <strong>Major:</strong> {st.session_state.get('current_major', '')}<br>
                <strong>Remaining Credits:</strong> {remaining_credits}</p>
                
                <div class="summary">
                    <strong>Summary:</strong><br>
                    Advised Courses: {len(advised_courses) + len(repeat_courses)} courses ({advised_credits + repeat_credits} credits)<br>
                    Optional Courses: {len(optional_courses)} courses ({optional_credits} credits)
                </div>
        """
        
        # Add advised courses
        if advised_courses:
            html_body += f"<h3>Advised Courses ({len(advised_courses)} courses, {advised_credits} credits)</h3><div class='course-list'>"
            for course_code in advised_courses:
                course_info = courses_df[courses_df['Course Code'] == course_code]
                if not course_info.empty:
                    title = course_info.iloc[0].get('Title', '')
                    credits = course_info.iloc[0].get('Credits', '')
                    html_body += f"<div class='course-item'><strong>{course_code}</strong> - {title} ({credits} credits)</div>"
                else:
                    html_body += f"<div class='course-item'><strong>{course_code}</strong></div>"
            html_body += "</div>"
        
        # Add repeat courses
        if repeat_courses:
            html_body += f"<h3>Repeat Courses ({len(repeat_courses)} courses, {repeat_credits} credits)</h3><div class='course-list'>"
            for course_code in repeat_courses:
                course_info = courses_df[courses_df['Course Code'] == course_code]
                if not course_info.empty:
                    title = course_info.iloc[0].get('Title', '')
                    credits = course_info.iloc[0].get('Credits', '')
                    html_body += f"<div class='course-item repeat-item'><strong>{course_code}</strong> - {title} ({credits} credits)</div>"
                else:
                    html_body += f"<div class='course-item repeat-item'><strong>{course_code}</strong></div>"
            html_body += "</div>"
        
        # Add optional courses
        if optional_courses:
            html_body += f"<h3>Optional Courses ({len(optional_courses)} courses, {optional_credits} credits)</h3><div class='course-list'>"
            for course_code in optional_courses:
                course_info = courses_df[courses_df['Course Code'] == course_code]
                if not course_info.empty:
                    title = course_info.iloc[0].get('Title', '')
                    credits = course_info.iloc[0].get('Credits', '')
                    html_body += f"<div class='course-item optional-item'><strong>{course_code}</strong> - {title} ({credits} credits)</div>"
                else:
                    html_body += f"<div class='course-item optional-item'><strong>{course_code}</strong></div>"
            html_body += "</div>"
        
        # Add advisor note
        if note:
            html_body += f"<div class='note'><h3>Advisor Note</h3><p>{note.replace(chr(10), '<br>')}</p></div>"
        
        # Footer
        html_body += """
                <div class="footer">
                    <p>If you have any questions or concerns about your advising plan, please contact your academic advisor.</p>
                    <p><em>This is an automated message from the Academic Advising System.</em></p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Create plain text version
        text_body = f"""
Academic Advising Sheet
{st.session_state.get('current_major', '')} Program

Dear {student_name},

Below is your academic advising recommendation for the upcoming semester.

Student Information:
Name: {student_name}
ID: {student_id}
Major: {st.session_state.get('current_major', '')}
Remaining Credits: {remaining_credits}

Summary:
Advised Courses: {len(advised_courses) + len(repeat_courses)} courses ({advised_credits + repeat_credits} credits)
Optional Courses: {len(optional_courses)} courses ({optional_credits} credits)

"""
        
        if advised_courses:
            text_body += f"Advised Courses ({len(advised_courses)} courses, {advised_credits} credits):\n"
            for course_code in advised_courses:
                course_info = courses_df[courses_df['Course Code'] == course_code]
                if not course_info.empty:
                    title = course_info.iloc[0].get('Title', '')
                    credits = course_info.iloc[0].get('Credits', '')
                    text_body += f"  • {course_code} - {title} ({credits} credits)\n"
                else:
                    text_body += f"  • {course_code}\n"
            text_body += "\n"
        
        if repeat_courses:
            text_body += f"Repeat Courses ({len(repeat_courses)} courses, {repeat_credits} credits):\n"
            for course_code in repeat_courses:
                course_info = courses_df[courses_df['Course Code'] == course_code]
                if not course_info.empty:
                    title = course_info.iloc[0].get('Title', '')
                    credits = course_info.iloc[0].get('Credits', '')
                    text_body += f"  • {course_code} - {title} ({credits} credits)\n"
                else:
                    text_body += f"  • {course_code}\n"
            text_body += "\n"
        
        if optional_courses:
            text_body += f"Optional Courses ({len(optional_courses)} courses, {optional_credits} credits):\n"
            for course_code in optional_courses:
                course_info = courses_df[courses_df['Course Code'] == course_code]
                if not course_info.empty:
                    title = course_info.iloc[0].get('Title', '')
                    credits = course_info.iloc[0].get('Credits', '')
                    text_body += f"  • {course_code} - {title} ({credits} credits)\n"
                else:
                    text_body += f"  • {course_code}\n"
            text_body += "\n"
        
        if note:
            text_body += f"Advisor Note:\n{note}\n\n"
        
        text_body += """
If you have any questions or concerns about your advising plan, please contact your academic advisor.

This is an automated message from the Academic Advising System.
"""
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = to_email
        
        # Add CC for advisor if provided
        if cc_advisor and advisor_email:
            msg['Cc'] = advisor_email
            recipient_list = [to_email, advisor_email]
        else:
            recipient_list = [to_email]
        
        # Attach both plain text and HTML versions
        part1 = MIMEText(text_body, 'plain')
        part2 = MIMEText(html_body, 'html')
        msg.attach(part1)
        msg.attach(part2)
        
        # Send via Outlook SMTP
        with smtplib.SMTP('smtp.office365.com', 587) as server:
            server.starttls()
            server.login(from_email, password)
            server.send_message(msg, to_addrs=recipient_list)
        
        if advisor_email:
            log_info(f"Advising email sent to {to_email} (CC: {advisor_email}) for student {student_id}")
            return True, f"Email sent successfully to {to_email} (CC: {advisor_email})"
        else:
            log_info(f"Advising email sent to {to_email} for student {student_id}")
            return True, f"Email sent successfully to {to_email}"
        
    except smtplib.SMTPAuthenticationError:
        error_msg = "Authentication failed. Please check your email address and password."
        log_error("Email authentication failed", Exception(error_msg))
        return False, error_msg
    except smtplib.SMTPException as e:
        error_msg = f"SMTP error: {str(e)}"
        log_error("Email sending failed (SMTP error)", e)
        return False, error_msg
    except Exception as e:
        error_msg = f"Failed to send email: {str(e)}"
        log_error("Email sending failed", e)
        return False, error_msg
