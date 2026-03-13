# student_panel.py - Student dashboard with nav

import streamlit as st
import pandas as pd
import database as db
import utils


def student_dashboard():
    nav = st.session_state.get("current_nav", "Dashboard")
    if nav == "Dashboard":
        _student_home()
    elif nav == "My Attendance":
        _student_attendance()
    elif nav == "Messages":
        _student_messages()
    else:
        _student_home()


def _student_home():
    user_info = st.session_state.user_info
    st.title(f"Welcome, {user_info['name']} 🎓")
    col1, col2 = st.columns([1, 3])
    with col1:
        try:
            st.image(user_info.get("photo_path") or "https://via.placeholder.com/150?text=Photo", width=120)
        except Exception:
            st.caption("No photo")
    with col2:
        st.write(f"**Student ID:** {user_info['student_id']}")
        st.write(f"**Roll:** {user_info.get('roll')} | **Class:** {user_info.get('class')} | **Section:** {user_info.get('section')}")
    records = db.get_attendance_by_student(user_info["student_id"])
    if records:
        df = pd.DataFrame([dict(r) for r in records])
        total = len(df)
        present = (df["status"] == "Present").sum()
        pct = (present / total * 100) if total > 0 else 0
        st.metric("Overall Attendance", f"{pct:.1f}%", f"{present}/{total} classes")
        st.progress(pct / 100)
    else:
        st.info("No attendance records yet.")

    # Notifications and complaints moved to dedicated sections.


def _student_attendance():
    user_info = st.session_state.user_info
    st.title("My Attendance")
    records = db.get_attendance_by_student(user_info["student_id"])
    if not records:
        st.info("No records.")
        return
    df = pd.DataFrame([dict(r) for r in records])
    total = len(df)
    present = (df["status"] == "Present").sum()
    pct = (present / total * 100) if total > 0 else 0
    st.metric("Attendance", f"{pct:.2f}%", f"{present}/{total}")
    st.progress(pct / 100)
    st.dataframe(df, width="stretch", hide_index=True)
    st.download_button("📥 Download CSV", data=utils.to_csv(df), file_name=f"{user_info['student_id']}_attendance.csv", mime="text/csv")


def _student_messages():
    user_info = st.session_state.user_info
    st.title("Messages & Notifications")
    st.caption("Messages from your teachers and system notifications.")

    messages = db.list_messages_for_student(user_info["student_id"])
    if not messages:
        st.info("No messages yet.")
    else:
        for m in messages:
            teacher_label = m.get("teacher_name") or m.get("teacher_id") or "Teacher"
            st.markdown(f"**From:** {teacher_label}")
            st.caption(m["created_at"])
            st.write(m["message"])
            st.markdown("---")

    st.markdown("---")
    st.subheader("Notifications")
    notifs = db.list_notifications_for_role("Student")
    if not notifs:
        st.info("No notifications.")
    else:
        for n in notifs:
            st.markdown(f"**{n['title']}**")
            st.caption(n["created_at"])
            st.write(n["body"])
            st.markdown("---")

    st.subheader("Submit Complaint")
    with st.form("student_complaint_form"):
        subj = st.text_input("Subject")
        msg = st.text_area("Message")
        submit = st.form_submit_button("Submit")
        if submit:
            if subj and msg:
                db.create_complaint("Student", user_info["student_id"], subj, msg)
                st.success("Complaint submitted.")
            else:
                st.warning("Subject and message are required.")
