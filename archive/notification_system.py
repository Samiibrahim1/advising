"""
Unified Notification System
Consistent alerts, toasts, and status messages across the app.
"""

import streamlit as st
from typing import Literal


NotificationType = Literal["success", "info", "warning", "error"]


def show_notification(
    message: str,
    notification_type: NotificationType = "info",
    persistent: bool = False,
    key: str = None
):
    """
    Show a notification with consistent styling.
    
    Args:
        message: Message to display
        notification_type: Type of notification (success, info, warning, error)
        persistent: If True, shows as container; if False, shows as toast
        key: Unique key for persistent notifications
    """
    if persistent:
        if notification_type == "success":
            st.success(message)
        elif notification_type == "warning":
            st.warning(message)
        elif notification_type == "error":
            st.error(message)
        else:
            st.info(message)
    else:
        if hasattr(st, 'toast'):
            icon_map = {
                "success": "✅",
                "info": "ℹ️",
                "warning": "⚠️",
                "error": "❌"
            }
            icon = icon_map.get(notification_type, "ℹ️")
            st.toast(f"{icon} {message}")
        else:
            if notification_type == "success":
                st.success(message)
            elif notification_type == "warning":
                st.warning(message)
            elif notification_type == "error":
                st.error(message)
            else:
                st.info(message)


def show_action_feedback(
    action: str,
    success: bool = True,
    details: str = None
):
    """
    Show feedback for user actions with consistent messaging.
    
    Args:
        action: Action name (e.g., "save", "email", "upload")
        success: Whether action succeeded
        details: Additional details to show
    """
    action_verbs = {
        "save": ("Saved", "save"),
        "email": ("Sent", "send email"),
        "upload": ("Uploaded", "upload"),
        "delete": ("Deleted", "delete"),
        "sync": ("Synced", "sync"),
    }
    
    past_tense, present_tense = action_verbs.get(action.lower(), (action, action))
    
    if success:
        msg = f"{past_tense} successfully"
        if details:
            msg += f": {details}"
        show_notification(msg, "success")
    else:
        msg = f"Failed to {present_tense}"
        if details:
            msg += f": {details}"
        show_notification(msg, "error", persistent=True)


def show_validation_error(field: str, issue: str):
    """
    Show validation error with consistent formatting.
    
    Args:
        field: Field name that failed validation
        issue: Description of the issue
    """
    show_notification(
        f"Validation error in {field}: {issue}",
        "error",
        persistent=True
    )


def show_data_status(
    courses_loaded: bool,
    progress_loaded: bool,
    num_students: int = 0
):
    """
    Show data loading status with consistent formatting.
    
    Args:
        courses_loaded: Whether courses table is loaded
        progress_loaded: Whether progress report is loaded
        num_students: Number of students loaded
    """
    if courses_loaded and progress_loaded:
        show_notification(
            f"Data ready: {num_students} students loaded",
            "success"
        )
    elif courses_loaded:
        show_notification(
            "Courses table loaded. Upload progress report to continue.",
            "warning",
            persistent=True
        )
    elif progress_loaded:
        show_notification(
            "Progress report loaded. Upload courses table to continue.",
            "warning",
            persistent=True
        )
    else:
        show_notification(
            "Upload courses table and progress report to begin",
            "info",
            persistent=True
        )
