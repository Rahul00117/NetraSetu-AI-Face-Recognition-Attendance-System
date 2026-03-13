# ui_theme.py - Shared UI: dark theme, backgrounds, footer

import streamlit as st
from pathlib import Path

from config import ASSETS_DIR

FOOTER_DEVS = [
    "Rahul Prajapat",
    "Rahul Kumar Jonwal",
    "Sahaj Vaishnav",
    "Rishab Thomar",
]


def apply_dark_theme():
    """Inject custom dark theme CSS."""
    st.markdown(
        """
    <style>
    /* Dark theme base */
    .stApp {
        background-color: #0e1117;
    }
    [data-testid="stHeader"] {
        background: rgba(14, 17, 23, 0.9);
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1d24 0%, #0e1117 100%);
    }
    [data-testid="stSidebar"] .stMarkdown {
        color: #fafafa;
    }
    /* IMPORTANT: Don't style all blocks as "cards".
       That causes lots of empty/blank boxes when Streamlit creates layout blocks. */

    /* Reserve space for fixed footer (prevents footer appearing mid-page/overlapping content) */
    [data-testid="stAppViewContainer"] {
        padding-bottom: 120px;
    }
    /* Metrics */
    [data-testid="stMetricValue"] {
        color: #00d4aa;
        font-weight: 700;
    }
    [data-testid="stMetricLabel"] {
        color: #b0b0b0;
    }
    /* Buttons */
    .stButton > button {
        background: linear-gradient(90deg, #2d3748 0%, #1a202c 100%);
        color: #e2e8f0;
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 6px;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background: linear-gradient(90deg, #3d4a5c 0%, #2d3748 100%);
        border-color: #00d4aa;
        color: #00d4aa;
    }
    /* Primary button */
    .stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #00b894 0%, #00d4aa 100%);
        color: #0e1117;
        border: none;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(90deg, #00d4aa 0%, #55efc4 100%);
        color: #0e1117;
    }
    /* Inputs */
    .stTextInput > div > div > input, .stSelectbox > div > div {
        background: #1a1d24 !important;
        color: #fafafa !important;
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 6px;
    }
    /* Expander */
    .streamlit-expanderHeader {
        background: rgba(30, 33, 40, 0.8);
        border-radius: 6px;
    }

    /* Footer as bottom section (not fixed overlay) */
    .app-footer {
        background: rgba(14, 17, 23, 0.92);
        border-top: 1px solid rgba(255,255,255,0.10);
        padding: 10px 0;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )


def get_background_css(image_path: str, blur_px: int = 12):
    """CSS for blurred background image."""
    return f"""
    <style>
    .stApp {{
        position: relative;
    }}
    .stApp::before {{
        content: '';
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        background: url('{image_path}') center/cover no-repeat;
        filter: blur({blur_px}px) brightness(0.35);
        z-index: -1;
    }}
    .stApp > div {{
        position: relative;
        z-index: 1;
    }}
    </style>
    """


def apply_page_background(background_key: str):
    """
    Apply blurred background for the current role.
    background_key: 'welcome' | 'teacher' | 'student' | 'admin'
    """
    # Support both naming conventions (backgrounds vs panels)
    candidates_map = {
        "welcome": ["welcome_background.png"],
        "teacher": ["teacher_background.png", "teacher_panel.png"],
        "student": ["student_background.png", "student_panel.png"],
        "admin": ["admin_background.png", "admin_panel.png"],
    }
    candidates = candidates_map.get(background_key, ["welcome_background.png"])
    path = None
    for fn in candidates:
        p = ASSETS_DIR / fn
        if p.exists():
            path = p
            break
    if path is None:
        return
    # Streamlit serves from app root; use path that works in browser
    try:
        import base64
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        data_uri = f"data:image/png;base64,{data}"
        st.markdown(get_background_css(data_uri, blur_px=14), unsafe_allow_html=True)
    except Exception:
        pass


def render_footer():
    """Professional footer on all pages."""
    devs = " | ".join(FOOTER_DEVS)
    st.markdown(
        f"""
    <div class="app-footer">
      <div style="max-width: 1200px; margin: 0 auto; padding: 0 1rem; text-align: center; color: #9aa0a6; font-size: 0.85rem;">
        <div style="font-weight: 600; color: #e5e7eb;">Developed by:</div>
        <div>{devs}</div>
        <div style="margin-top: 4px;">B.Tech Artificial Intelligence — Final Year Project</div>
        <div style="margin-top: 4px;">© 2025 NetraSetu : AI-Based Face Recognition Attendance System. All rights reserved.</div>
        <div style="margin-top: 4px;">Help &amp; Support:system@netrasetu.com Contact your department administrator.</div>
      </div>
    </div>
    """,
        unsafe_allow_html=True,
    )


def render_logo_and_title(logo_path: str = None, title: str = "NetraSetu : AI-Based Face Recognition Attendance System"):
    """Logo and main title at top."""
    if logo_path and Path(logo_path).exists():
        col_logo, col_title = st.columns([1, 4])
        with col_logo:
            st.image(logo_path, width=100)
        with col_title:
            st.title(title)
    else:
        st.title(f"🎓 {title}")
