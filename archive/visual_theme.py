"""
Visual Theme and Accessibility Enhancements
Provides CSS styling for better accessibility, mobile responsiveness, and visual polish.
"""

import streamlit as st


def apply_visual_theme():
    """
    Apply custom CSS for accessibility, mobile responsiveness, and visual improvements.
    """
    st.markdown(
        """
        <style>
        /* ========== Accessibility Improvements ========== */
        
        /* High contrast text for better readability */
        body {
            color: #1a1a1a;
        }
        
        /* Improved link contrast (WCAG AA compliant) */
        a {
            color: #0051a5;
            text-decoration: underline;
        }
        
        a:hover {
            color: #003d7a;
        }
        
        /* Focus indicators for keyboard navigation */
        button:focus, 
        input:focus, 
        select:focus, 
        textarea:focus {
            outline: 3px solid #4A90E2 !important;
            outline-offset: 2px;
        }
        
        /* ========== Mobile Responsiveness ========== */
        
        /* Responsive columns - stack on mobile */
        @media (max-width: 768px) {
            .row-widget.stHorizontalBlock {
                flex-direction: column !important;
            }
            
            /* Make tables scrollable on mobile */
            .dataframe-container {
                overflow-x: auto;
            }
            
            /* Larger touch targets on mobile */
            button {
                min-height: 44px !important;
                min-width: 44px !important;
            }
        }
        
        /* ========== Visual Polish ========== */
        
        /* Smoother transitions */
        button, input, select, textarea {
            transition: all 0.2s ease-in-out;
        }
        
        /* Better button styling */
        button[kind="primary"] {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            border: none !important;
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
        }
        
        button[kind="primary"]:hover {
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
            transform: translateY(-1px);
        }
        
        button[kind="secondary"] {
            border: 2px solid #667eea !important;
            background: white !important;
            color: #667eea !important;
        }
        
        button[kind="secondary"]:hover {
            background: #f0f2ff !important;
        }
        
        /* Improved card/container styling */
        .stExpander {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            margin-bottom: 1rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        
        /* Better metrics display */
        [data-testid="stMetricValue"] {
            font-size: 1.8rem;
            font-weight: 700;
            color: #667eea;
        }
        
        [data-testid="stMetricLabel"] {
            font-size: 0.9rem;
            font-weight: 500;
            color: #666;
        }
        
        /* Improved form styling */
        .stForm {
            background: #f8f9fa;
            padding: 1.5rem;
            border-radius: 8px;
            border: 1px solid #e0e0e0;
        }
        
        /* Better multiselect styling */
        .stMultiSelect > div {
            border-radius: 6px;
        }
        
        /* Improved table styling */
        .dataframe {
            border-collapse: separate;
            border-spacing: 0;
            border-radius: 8px;
            overflow: hidden;
        }
        
        .dataframe thead th {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: 600;
            padding: 12px;
            text-align: left;
        }
        
        .dataframe tbody tr:hover {
            background: #f0f2ff;
        }
        
        /* Improved alert/notification styling */
        .stSuccess {
            background: #d4edda;
            border-left: 4px solid #28a745;
            border-radius: 4px;
        }
        
        .stWarning {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            border-radius: 4px;
        }
        
        .stError {
            background: #f8d7da;
            border-left: 4px solid #dc3545;
            border-radius: 4px;
        }
        
        .stInfo {
            background: #d1ecf1;
            border-left: 4px solid #0dcaf0;
            border-radius: 4px;
        }
        
        /* ========== Tooltips and Help Text ========== */
        
        /* Better tooltip visibility */
        [data-testid="stTooltipIcon"] {
            color: #667eea;
        }
        
        .stTooltipContent {
            background: #333;
            color: white;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 0.9rem;
        }
        
        /* ========== Status Badges ========== */
        
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85rem;
            font-weight: 500;
        }
        
        .status-success {
            background: #d4edda;
            color: #155724;
        }
        
        .status-warning {
            background: #fff3cd;
            color: #856404;
        }
        
        .status-error {
            background: #f8d7da;
            color: #721c24;
        }
        
        .status-info {
            background: #d1ecf1;
            color: #0c5460;
        }
        
        /* ========== Loading States ========== */
        
        .stSpinner > div {
            border-color: #667eea #667eea transparent transparent;
        }
        
        /* ========== Sidebar Improvements ========== */
        
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #f8f9fa 0%, #ffffff 100%);
        }
        
        [data-testid="stSidebar"] .stExpander {
            background: white;
        }
        
        /* ========== Typography Scale ========== */
        
        h1 {
            font-weight: 700;
            color: #1a1a1a;
            letter-spacing: -0.5px;
        }
        
        h2 {
            font-weight: 600;
            color: #333;
            margin-top: 2rem;
        }
        
        h3 {
            font-weight: 600;
            color: #667eea;
            margin-top: 1.5rem;
        }
        
        /* ========== Print Styles ========== */
        
        @media print {
            .stSidebar {
                display: none !important;
            }
            
            button {
                display: none !important;
            }
            
            .dataframe {
                page-break-inside: avoid;
            }
        }
        
        /* ========== Reduced Motion (Accessibility) ========== */
        
        @media (prefers-reduced-motion: reduce) {
            * {
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
            }
        }
        
        /* ========== Dark Mode Support (if enabled) ========== */
        
        @media (prefers-color-scheme: dark) {
            /* Only apply if user prefers dark mode */
            /* These would override if Streamlit's dark mode is enabled */
        }
        </style>
        """,
        unsafe_allow_html=True
    )


def render_help_tooltip(text: str, help_text: str):
    """
    Render text with an accessible tooltip.
    
    Args:
        text: Main text to display
        help_text: Tooltip/help text
    """
    st.markdown(
        f"""
        <div style="display: inline-flex; align-items: center; gap: 0.5rem;">
            <span>{text}</span>
            <span title="{help_text}" style="cursor: help; color: #667eea;">ⓘ</span>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_status_badge(label: str, status: str = "info"):
    """
    Render a status badge with color coding.
    
    Args:
        label: Badge text
        status: Badge type (success, warning, error, info)
    """
    status_class = f"status-{status}"
    st.markdown(
        f'<span class="status-badge {status_class}">{label}</span>',
        unsafe_allow_html=True
    )
