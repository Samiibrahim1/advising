"""
Simple Student Dropdown Component
"""

import streamlit as st
import pandas as pd
from typing import Optional


def render_student_search(view_key: str = "default") -> Optional[int]:
    """
    Render simple student dropdown selector.
    
    Args:
        view_key: Unique key to differentiate between views (e.g., "eligibility", "full_view")
    
    Returns:
        Selected student ID (int) or None if no student selected
    """
    if "progress_df" not in st.session_state or st.session_state.progress_df.empty:
        st.warning("No student data loaded.")
        return None
    
    students_df = st.session_state.progress_df.copy()
    
    students_df["Total Credits"] = (
        students_df.get("# of Credits Completed", 0).fillna(0).astype(float) +
        students_df.get("# Registered", 0).fillna(0).astype(float)
    )
    
    from advising_utils import get_student_standing
    students_df["Standing"] = students_df["Total Credits"].apply(get_student_standing)
    
    students_df["DISPLAY"] = (
        students_df["NAME"].astype(str) + 
        " — ID: " + 
        students_df["ID"].astype(str) + 
        " (" + 
        students_df["Standing"].astype(str) + 
        ")"
    )
    
    options = ["Select a student..."] + students_df["DISPLAY"].tolist()
    
    selected = st.selectbox(
        "Student",
        options=options,
        key=f"student_selectbox_{view_key}",
    )
    
    if selected == "Select a student...":
        return None
    
    selected_id = int(students_df.loc[students_df["DISPLAY"] == selected, "ID"].iloc[0])
    
    return selected_id
