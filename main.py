# main.py - AI-Based Face Recognition Attendance System

import streamlit as st
import database as db
import auth
import admin_panel
import teacher_panel
import student_panel
import chatbot
from ui_theme import apply_dark_theme, apply_page_background, render_footer, render_logo_and_title
from config import ASSETS_DIR

st.set_page_config(
    page_title="NetraSetu : AI-Based Face Recognition Attendance System",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply dark theme globally
apply_dark_theme()


def main():
    """Main function to run the Streamlit app."""
    db.init_db()

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.role = None
        st.session_state.user_info = None

    if st.session_state.logged_in:
        # Sidebar: logo, user, nav, logout
        with st.sidebar:
            logo_path = ASSETS_DIR / "logo.png"
            if logo_path.exists():
                st.image(str(logo_path), width=120)
            st.markdown("## 🎓 NetraSetu")
            user_name = st.session_state.user_info.get(
                "name", st.session_state.user_info.get("email", "User")
            )
            st.markdown(f"**{user_name}**")
            st.caption(f"Role: {st.session_state.role}")

            nav_options = ["Dashboard", "Take Attendance", "Student Management", "Reports", "AI Chatbot"]
            if st.session_state.role == "Admin":
                nav_options = ["Dashboard", "Class Management", "Student Management", "Reports", "Notifications", "AI Chatbot"]
            elif st.session_state.role == "Student":
                nav_options = ["Dashboard", "My Attendance", "Messages", "AI Chatbot"]
            elif st.session_state.role == "Teacher":
                nav_options = ["Dashboard", "Take Attendance", "Student Management", "Reports", "Messages", "AI Chatbot"]

            st.session_state.current_nav = st.sidebar.radio(
                "Navigation",
                nav_options,
                key="main_nav",
                label_visibility="collapsed",
            )

            if st.button("Logout", width="stretch", type="primary", key="logout_btn"):
                st.session_state.clear()
                st.rerun()

        # Main content: switch by nav (AI Chatbot fills main; else role dashboard)
        if st.session_state.get("current_nav") == "AI Chatbot":
            chatbot.render_chatbot_main()
        elif st.session_state.role == "Admin":
            apply_page_background("admin")
            admin_panel.admin_dashboard()
        elif st.session_state.role == "Teacher":
            apply_page_background("teacher")
            teacher_panel.teacher_dashboard()
        elif st.session_state.role == "Student":
            apply_page_background("student")
            student_panel.student_dashboard()

        render_footer()

    else:
        apply_page_background("welcome")
        render_logo_and_title(
            str(ASSETS_DIR / "welcome_background.png") if (ASSETS_DIR / "welcome_background.png").exists() else None,
            "NetraSetu : AI-Based Face Recognition Attendance System",
        )
        auth.login()
        render_footer()


if __name__ == "__main__":
    main()
