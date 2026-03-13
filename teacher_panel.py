# teacher_panel.py - Teacher dashboard with analytics, reports, and attendance

import os
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import cv2
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

import database as db
import utils
import face_engine


def teacher_dashboard():
    """Teacher dashboard: nav-driven (Dashboard, Take Attendance, Student Performance, Reports)."""
    user_info = st.session_state.user_info
    nav = st.session_state.get("current_nav", "Dashboard")

    if nav == "Dashboard":
        _render_teacher_dashboard_home(user_info)
    elif nav == "Take Attendance":
        _render_take_attendance(user_info)
    elif nav == "Student Management":
        _render_student_performance(user_info)
    elif nav == "Reports":
        _render_reports(user_info)
    elif nav == "Messages":
        _render_teacher_messages(user_info)
    else:
        _render_teacher_dashboard_home(user_info)


def _render_teacher_dashboard_home(user_info):
    """Dashboard: metrics, charts."""
    st.title(f"Welcome, {user_info['name']} 👋")
    st.caption(f"Subject: **{user_info['subject']}** | Branch: **{user_info.get('branch', '—')}**")

    # Classes assigned to this teacher
    my_classes = db.get_teacher_classes(user_info["teacher_id"])
    students = db.list_students()
    # Only count students in teacher's classes
    class_students = [s for s in students if not my_classes or s["class"] in my_classes]
    total_students = len(class_students)
    # DB stores date as YYYY-MM-DD (from st.date_input().isoformat()).
    # Don't use datetime.isoformat() (includes time) or you'll get zero matches.
    today_iso = datetime.today().date().isoformat()
    subject = user_info["subject"]
    teacher_id = user_info["teacher_id"]

    # Today's attendance for this teacher's subject
    today_records = db.get_attendance_by_teacher_subject_date(teacher_id, subject, today_iso)
    present_today = sum(1 for r in today_records if r.get("status") == "Present")
    absent_today = total_students - present_today if total_students else 0

    # Metrics row 1
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Students", total_students)
    col2.metric("Today Present", present_today)
    col3.metric("Absent Today", absent_today)
    col4.metric("Recognition Accuracy", "—", help="Based on last session")
    col5.metric("Camera Status", "Ready" if not st.session_state.get("live_camera_active") else "Active")

    st.markdown("---")

    # Charts
    if total_students > 0:
        # Pie: today present vs absent
        fig_pie = go.Figure(data=[go.Pie(
            labels=["Present", "Absent"],
            values=[present_today, absent_today],
            hole=0.5,
            marker_colors=["#00d4aa", "#ff6b6b"],
        )])
        fig_pie.update_layout(title="Today's Attendance", height=280, margin=dict(t=40, b=20))
        st.plotly_chart(fig_pie, use_container_width=True, key="teacher_pie_today")

        # Weekly trend (last 7 days)
        date_from = (datetime.today().date() - timedelta(days=7)).isoformat()
        date_to = today_iso
        filtered = db.get_all_attendance_filtered(teacher_id=teacher_id, subject=subject, date_from=date_from, date_to=date_to)
        if filtered:
            df_week = pd.DataFrame(filtered)
            # FIX: correct agg syntax (must provide column + aggfunc tuple)
            daily = (
                df_week.groupby("date")
                .agg(
                    present=("status", lambda x: (x == "Present").sum()),
                    total=("student_id", "count"),
                )
                .reset_index()
            )
            daily["absent"] = daily["total"] - daily["present"]
            fig_bar = px.bar(
                daily,
                x="date",
                y=["present", "absent"],
                title="Weekly Attendance (Present vs Absent)",
                barmode="group",
                color_discrete_sequence=["#00d4aa", "#ff6b6b"],
            )
            fig_bar.update_layout(height=300, margin=dict(t=40, b=20))
            st.plotly_chart(fig_bar, use_container_width=True, key="teacher_week_bar")
    else:
        st.info("No students registered yet. Ask admin to register your classes.")

    # Low attendance students (across all time, for quick warning)
    stats = db.get_students_with_attendance_stats(
        user_info["teacher_id"], subject=subject
    )
    low_att = [s for s in stats if s["percentage"] < 75]
    if low_att:
        st.subheader("Students with Low Attendance (< 75%)")
        for s in low_att[:5]:
            st.write(
                f"**{s['name']}** ({s['student_id']}) — {s['percentage']}% "
                f"({s['present_count']}/{s['total_count']} classes)"
            )

    # Detailed notifications and messaging moved to dedicated navigation sections.

    # Profile expander
    with st.expander("Your Profile"):
        st.write(f"**Teacher ID:** {user_info['teacher_id']}")
        st.write(f"**Email:** {user_info['email']}")
        st.write(f"**Branch:** {user_info.get('branch', '—')}")
        st.write(f"**Subject:** {user_info['subject']}")


def _render_take_attendance(user_info):
    """Tabs: Manual, Live Camera, Group Photo."""
    st.title("Take Attendance")
    tab_manual, tab_camera, tab_group = st.tabs(["Manual", "Live Camera", "Group Photo"])

    with tab_manual:
        _manual_attendance(user_info)
    with tab_camera:
        _live_camera_attendance(user_info)
    with tab_group:
        _group_photo_attendance(user_info)


def _manual_attendance(user_info):
    classes = db.get_teacher_classes(user_info["teacher_id"])
    if not classes:
        st.info("No classes assigned to you yet.")
        return

    selected_class = st.selectbox("Class", classes, key="manual_class")

    all_students = db.list_students()
    students = [s for s in all_students if s["class"] == selected_class]
    if not students:
        st.warning(f"No students registered in class {selected_class}.")
        return
    date = st.date_input("Select Date", value=datetime.today(), key="manual_date")
    date_iso = date.isoformat()
    with st.form("attendance_form"):
        attendance_data = {}
        for student in students:
            cols = st.columns([3, 1])
            cols[0].write(f"{student['name']} ({student['student_id']})")
            status = cols[1].radio(
                "Status", ["Present", "Absent"],
                key=f"status_{student['student_id']}",
                horizontal=True, label_visibility="collapsed"
            )
            attendance_data[student["student_id"]] = status
        submitted = st.form_submit_button("Submit Attendance")
        if submitted:
            failed = []
            for sid, status in attendance_data.items():
                if not db.mark_attendance(sid, user_info["subject"], date_iso, status, user_info["teacher_id"]):
                    failed.append(sid)
            if failed:
                st.warning(f"Some records failed: {failed}")
            else:
                st.success("Attendance marked successfully!")


def _live_camera_attendance(user_info):
    st.info("Click **Start Camera** → capture a frame → **Recognize & Mark Attendance**. Use **Stop Camera** when done.")
    if "live_camera_active" not in st.session_state:
        st.session_state.live_camera_active = False

    col1, col2, _ = st.columns([1, 1, 2])
    with col1:
        if st.button("Start Camera", type="primary", key="start_cam"):
            st.session_state.live_camera_active = True
            st.success("Camera started.")
            st.rerun()
    with col2:
        if st.button("Stop Camera", key="stop_cam"):
            st.session_state.live_camera_active = False
            st.info("Camera stopped.")
            st.rerun()

    classes = db.get_teacher_classes(user_info["teacher_id"])
    if not classes:
        st.info("No classes assigned to you yet.")
        return

    selected_class = st.selectbox("Class", classes, key="live_class")
    subject = st.text_input("Subject", value=user_info["subject"], key="live_subject")
    date = st.date_input("Date", value=datetime.today(), key="live_date")
    date_iso = date.isoformat()
    threshold = st.slider("Recognition Threshold", 0.2, 0.9, 0.4, 0.01, key="live_threshold")

    camera_image = None
    if st.session_state.live_camera_active:
        camera_image = st.camera_input("Capture frame (click camera icon to capture)", key="live_cam_input")

    if camera_image is not None and st.button("Recognize & Mark Attendance", type="primary", key="recognize_live"):
        buf = camera_image.getvalue()
        frame = cv2.imdecode(np.frombuffer(buf, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            st.error("Could not decode image.")
        else:
            with st.spinner("Detecting faces..."):
                try:
                    results = face_engine.recognize_faces_in_image(frame, threshold=threshold)
                except Exception as e:
                    st.error(f"Recognition failed: {e}")
                    results = []

            # Restrict to students in selected class
            class_students = [
                s for s in db.list_students() if s["class"] == selected_class
            ]
            allowed_ids = {s["student_id"] for s in class_students}
            recognized = {r.student_id for r in results if r.student_id is not None}
            recognized &= allowed_ids
            if not recognized:
                st.warning("No registered students recognized.")
            else:
                for sid in recognized:
                    db.mark_attendance(sid, subject, date_iso, "Present", user_info["teacher_id"])
                st.success(f"Marked {len(recognized)} students as Present.")

            # Show recognition UI: name, confidence, status
            for r in results:
                if r.student_id:
                    sim = (r.similarity or 0) * 100
                    st.caption(f"**Recognized:** {r.name or r.student_id} | Confidence: {sim:.0f}% | Status: Present")

            if results:
                annotated = face_engine.draw_recognition_results(frame, results)
                st.image(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB), caption="Results", width="stretch")


def _group_photo_attendance(user_info):
    """Group photo: support multiple photos, merge recognitions, mark Present/Absent once."""
    st.info(
        "Upload one or more class photos. Recognized students are marked **Present**. "
        "Others are marked **Absent**. Multiple photos for the same date: new recognitions "
        "are added; existing Present are kept."
    )
    classes = db.get_teacher_classes(user_info["teacher_id"])
    if not classes:
        st.info("No classes assigned to you yet.")
        return

    selected_class = st.selectbox("Class", classes, key="grp_class")
    subject = st.text_input("Subject", value=user_info["subject"], key="grp_subject")
    date = st.date_input("Date", value=datetime.today(), key="grp_date")
    date_iso = date.isoformat()
    threshold = st.slider("Recognition Threshold", 0.2, 0.9, 0.4, 0.01, key="grp_threshold")
    uploaded_photos = st.file_uploader(
        "Upload group photos", type=["jpg", "png", "jpeg"], key="grp_upload", accept_multiple_files=True
    )

    if uploaded_photos and st.button("Analyze Photos & Update Attendance", type="primary", key="analyze_grp"):
        teacher_id = user_info["teacher_id"]
        class_students = [s for s in db.list_students() if s["class"] == selected_class]
        all_students = {s["student_id"] for s in class_students}

        total_photos = len(uploaded_photos)
        total_faces = 0
        all_recognized_ids = set()

        # Keep previously present for this subject/date (so we don't downgrade)
        already_present = db.get_present_student_ids_for_subject_date(subject, date_iso)

        for idx, file in enumerate(uploaded_photos, start=1):
            st.write(f"Processing photo {idx} of {total_photos} ...")
            photo_path = utils.generate_group_photo_path(teacher_id)
            if not utils.save_image(file, photo_path):
                st.warning(f"Could not save photo {idx}, skipping.")
                continue

            image = cv2.imread(str(photo_path))
            if image is None:
                st.warning(f"Could not read saved photo {idx}, skipping.")
                continue

            with st.spinner(f"Detecting faces in photo {idx}..."):
                try:
                    results, report = utils.recognize_from_group_photo(photo_path, threshold=threshold)
                except Exception as e:
                    st.warning(f"Photo {idx}: {e}")
                    continue

            total_faces += report.num_detected
            rec_ids = {r.student_id for r in results if r.student_id is not None}
            all_recognized_ids |= rec_ids

            if report.num_detected == 0:
                st.warning(f"No faces detected in photo {idx}.")

            # Show per-photo annotated result optionally
            if results and image is not None:
                annotated = face_engine.draw_recognition_results(image, results)
                st.image(
                    cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB),
                    caption=f"Recognized faces (photo {idx})",
                    use_container_width=True,
                )

        # Merge new recognized with already present
        new_present = already_present | all_recognized_ids

        marked_present = 0
        marked_absent = 0
        for sid in all_students:
            status = "Present" if sid in new_present else "Absent"
            if db.mark_attendance(sid, subject, date_iso, status, teacher_id):
                if status == "Present":
                    marked_present += 1
                else:
                    marked_absent += 1

        st.success(
            f"Processed {total_photos} photos. Total faces detected: {total_faces}. "
            f"Attendance updated: **{marked_present}** Present, **{marked_absent}** Absent for {date_iso}."
        )


def _render_student_performance(user_info):
    """Student cards, search, filter, attendance %."""
    st.title("Student Performance")
    subject = user_info["subject"]
    teacher_id = user_info["teacher_id"]

    date_from = st.date_input("From", value=datetime.today() - timedelta(days=30), key="perf_from")
    date_to = st.date_input("To", value=datetime.today(), key="perf_to")
    search = st.text_input("Search student (name or ID)", key="perf_search")
    date_f = date_from.isoformat()
    date_t = date_to.isoformat()

    stats = db.get_students_with_attendance_stats(teacher_id, subject=subject, date_from=date_f, date_to=date_t)
    if search:
        search_lower = search.lower()
        stats = [s for s in stats if search_lower in (s["name"] or "").lower() or search_lower in (s["student_id"] or "").lower()]

    if not stats:
        st.info("No students or no attendance in this range.")
        return

    # Student cards
    for s in stats:
        with st.container():
            col_photo, col_info = st.columns([1, 4])
            with col_photo:
                photo_path = s.get("photo_path")
                try:
                    if photo_path and os.path.exists(str(photo_path)):
                        st.image(str(photo_path), width=80)
                    else:
                        st.caption("No photo")
                except Exception:
                    st.caption("No photo")
            with col_info:
                pct = s.get("percentage", 0)
                st.subheader(s["name"])
                st.caption(f"ID: {s['student_id']} | Roll: {s.get('roll', '—')} | Section: {s.get('section', '—')}")
                st.metric("Attendance %", f"{pct}%", f"{s.get('present_count', 0)}/{s.get('total_count', 0)} classes")
                st.progress(pct / 100)
            st.markdown("---")

    # Table view
    st.subheader("Table View")
    df = pd.DataFrame(stats)
    st.dataframe(df[["name", "student_id", "present_count", "total_count", "percentage"]], width="stretch", hide_index=True)


def _render_reports(user_info):
    """Attendance reports with filters and CSV/Excel/PDF download."""
    st.title("Attendance Reports")
    teacher_id = user_info["teacher_id"]
    subject = st.selectbox("Subject", [user_info["subject"]], key="rpt_subject")
    date_from = st.date_input("From", value=datetime.today() - timedelta(days=30), key="rpt_from")
    date_to = st.date_input("To", value=datetime.today(), key="rpt_to")

    records = db.get_all_attendance_filtered(
        teacher_id=teacher_id,
        subject=subject,
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
    )
    if not records:
        st.info("No records in this range.")
        return

    df = pd.DataFrame(records)
    st.dataframe(df, width="stretch", hide_index=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button("📥 Download CSV", data=utils.to_csv(df), file_name="attendance_report.csv", mime="text/csv", key="dl_csv")
    with c2:
        excel_bytes = utils.to_excel(df)
        if excel_bytes:
            st.download_button("📥 Download Excel", data=excel_bytes, file_name="attendance_report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_xlsx")
    with c3:
        pdf_bytes = utils.to_pdf(df, title="Attendance Report")
        if pdf_bytes:
            st.download_button("📥 Download PDF", data=pdf_bytes, file_name="attendance_report.pdf", mime="application/pdf", key="dl_pdf")


def _render_teacher_messages(user_info):
    """Teacher → Student messaging center and notifications."""
    st.title("Messages & Notifications")
    st.caption("Send messages to students, and view notifications relevant to you.")

    students = db.list_students_with_photo()
    if not students:
        st.info("No students registered yet.")
        return

    # Compose message
    st.subheader("Send Message to Student")
    student_options = {
        f"{s['name']} ({s['student_id']})": s["student_id"] for s in students
    }
    selected_label = st.selectbox(
        "Select Student",
        options=list(student_options.keys()),
        key="msg_student_select",
    )
    message_text = st.text_area("Message", key="msg_text")
    if st.button("Send Message", key="send_direct_msg"):
        if not message_text.strip():
            st.warning("Message cannot be empty.")
        else:
            student_id = student_options[selected_label]
            try:
                db.create_direct_message(
                    teacher_id=user_info["teacher_id"],
                    student_id=student_id,
                    message=message_text.strip(),
                )
                st.success("Message sent.")
            except Exception as e:
                st.error(f"Failed to send message: {e}")

    st.markdown("---")
    st.subheader("Your Recent Messages")
    messages = db.list_messages_for_teacher(user_info["teacher_id"])
    if not messages:
        st.info("You haven't sent any messages yet.")
    else:
        for m in messages[:20]:
            st.markdown(f"**To:** {m.get('student_name') or m['student_id']}")
            st.caption(m["created_at"])
            st.write(m["message"])
            st.markdown("---")

    st.markdown("---")
    st.subheader("Notifications")
    notifs = db.list_notifications_for_role("Teacher")
    if not notifs:
        st.info("No notifications.")
    else:
        for n in notifs[:10]:
            st.markdown(f"**{n['title']}**")
            st.caption(n["created_at"])
            st.write(n["body"])
            st.markdown("---")
