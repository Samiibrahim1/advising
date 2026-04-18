"""
Workspace page - Uses the original student eligibility view for advising.
"""

import streamlit as st

def render_workspace():
    """Render the Advisor Workspace using the original eligibility view."""
    
    st.markdown("## Advisor Workspace")
    
    # Use the original eligibility view which has:
    # - Student search dropdown
    # - Required and Intensive course tables
    # - Advised/Optional/Repeat selection with mutual exclusivity
    # - Advisor notes
    # - Email functionality
    from eligibility_view import student_eligibility_view
    student_eligibility_view()
