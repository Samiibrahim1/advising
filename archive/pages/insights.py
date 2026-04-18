import streamlit as st
import pandas as pd

def render_insights():
    """Render the Insights Hub - uses the original Full Student View which has all tabs built-in."""
    
    progress_df = st.session_state.get("progress_df", pd.DataFrame())
    courses_df = st.session_state.get("courses_df", pd.DataFrame())
    
    if progress_df.empty or courses_df.empty:
        st.warning("Please upload data files in the Setup tab first.")
        return
    
    st.markdown("## Insights Hub")
    
    from full_student_view import full_student_view
    full_student_view()
