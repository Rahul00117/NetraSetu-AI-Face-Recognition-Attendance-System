import os
from datetime import datetime

import pandas as pd
import streamlit as st

import database as db
import face_engine
import sms_gateway
import utils
from config import STUDENT_IMAGES_DIR


def admin_dashboard():
    """Admin: Dashboard, Class Management, Student Management, Reports, Notifications."""
    nav = st.session_state.get("current_nav", "Dashboard")
    if nav == "Dashboard":
        _admin_dashboard_home()
    elif nav == "Class Management":
        _admin_class_management()
    elif nav in ("Manage Users", "Student Management"):
        _admin_manage_users()
    elif nav in ("Attendance Reports", "Reports"):
        _admin_reports()
    elif nav == "Notifications":
        _admin_notifications()
    else:
        _admin_dashboard_home()


def _admin_dashboard_home():
    st.title("Admin Dashboard")

    students = db.list_students()
    teachers = db.list_teachers()
    classes = db.list_classes()

    today_iso = datetime.today().date().isoformat()
    today_records = db.get_all_attendance_filtered(date_from=today_iso, date_to=today_iso)
    present_today_students = {
        r["student_id"]
        for r in today_records
        if r.get("status") == "Present" and r.get("student_id")
    }

    total_students = len(students)
    total_teachers = len(teachers)
    total_classes = len(classes)
    present_today = len(present_today_students)
    absent_today = max(total_students - present_today, 0)

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total Students", total_students)
    col2.metric("Total Teachers", total_teachers)
    col3.metric("Total Classes", total_classes)
    col4.metric("Present Today", present_today)
    col5.metric("Absent Students", absent_today)
    col6.metric("Recognition Accuracy", "—")

    # Notifications and complaints moved to dedicated admin sections.


def _admin_class_management():
    st.title("Class Management")

    st.info(
        "Edit existing classes. Changing a class name will automatically update all "
        "linked students and teacher-class mappings."
    )

    classes = db.list_classes_detailed()
    if not classes:
        st.warning("No classes found.")
    else:
        for c in classes:
            key_suffix = f"{c['id']}"
            with st.form(f"class_edit_{key_suffix}"):
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    new_name = st.text_input(
                        "Class Name",
                        value=c["name"],
                        key=f"class_name_{key_suffix}",
                    )
                with col2:
                    new_branch = st.text_input(
                        "Branch (e.g., AI, CSE, IT)",
                        value=c.get("branch") or "",
                        key=f"class_branch_{key_suffix}",
                    )
                with col3:
                    new_section = st.text_input(
                        "Section (e.g., A, B, C)",
                        value=c.get("section") or "",
                        key=f"class_section_{key_suffix}",
                    )
                submitted = st.form_submit_button("Save Changes")

                if submitted:
                    try:
                        db.update_class_and_mappings(
                            old_name=c["name"],
                            new_name=new_name.strip(),
                            branch=new_branch.strip().upper() or None,
                            section=new_section.strip().upper() or None,
                        )
                        st.success("Class updated successfully.")
                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"Failed to update class: {e}")

    st.markdown("---")
    st.subheader("Add New Class")
    with st.form("add_class_form"):
        new_name = st.text_input("Class Name", key="add_class_name")
        new_branch = st.text_input("Branch (optional)", key="add_class_branch")
        new_section = st.text_input("Section (optional)", key="add_class_section")
        submitted = st.form_submit_button("Add Class")
        if submitted:
            if not new_name.strip():
                st.warning("Class name is required.")
            else:
                try:
                    db.upsert_class(
                        new_name.strip(),
                        (new_branch or "").strip().upper() or None,
                        (new_section or "").strip().upper() or None,
                    )
                    st.success("Class added/updated successfully.")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Failed to add class: {e}")


def _admin_notifications():
    st.title("Notifications & Complaints")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Create Notification")
        title = st.text_input("Title", key="notif_title")
        body = st.text_area("Message", key="notif_body", height=80)
        audience = st.selectbox(
            "Audience", ["all", "students", "teachers"], key="notif_audience"
        )
        if st.button("Broadcast Notification", key="notif_send"):
            if title and body:
                db.create_notification(title, body, audience)
                st.success("Notification broadcasted.")
            else:
                st.warning("Title and message are required.")

    with col2:
        st.subheader("Open Complaints")
        complaints = db.list_complaints(status="open")
        if not complaints:
            st.info("No open complaints.")
        else:
            for c in complaints[:10]:
                st.markdown(f"**{c['role']} {c['user_id']}** — {c['subject']}")
                st.caption(f"{c['created_at']}")
                st.write(c["message"])
                if st.button("Mark resolved", key=f"compl_res_{c['id']}"):
                    db.set_complaint_status(c["id"], "resolved")
                    st.success("Complaint marked resolved.")
                    st.experimental_rerun()


def _admin_manage_users():
    st.title("Student Management")
    tab_reg_teacher, tab_reg_student, tab_list, tab_msg = st.tabs(
        ["Register Teacher", "Register Student", "View & Manage", "Messaging Center"]
    )

    classes = db.list_classes()

    # Register Teacher
    with tab_reg_teacher:
        with st.form("teacher_reg_form", clear_on_submit=True):
            name = st.text_input("Name")
            email = st.text_input("Email")
            phone = st.text_input("Mobile Number")
            branch = st.text_input("Branch")
            subject = st.text_input("Subject")
            assigned_classes = st.multiselect("Classes", classes)
            if st.form_submit_button("Register Teacher"):
                if all([name, email, phone, branch, subject]):
                    teacher_id = utils.generate_id("teacher")
                    password = teacher_id
                    ok = db.create_teacher(
                        teacher_id, name, email, branch, subject, password
                    )
                    if ok:
                        # save phone
                        conn = db.get_db_connection()
                        conn.execute(
                            "UPDATE Teachers SET phone = ? WHERE teacher_id = ?",
                            (phone, teacher_id),
                        )
                        conn.commit()
                        conn.close()
                        db.assign_teacher_classes(teacher_id, assigned_classes)
                        st.success("Teacher registered.")
                        st.info(f"ID: `{teacher_id}` | Password: `{password}`")
                    else:
                        st.error("Email already exists.")
                else:
                    st.warning("All fields are required.")

    # Register Student with camera control and optional photo upload
    with tab_reg_student:
        st.info("Use **Start Camera** → capture photo or **Upload Photo** → then **Register Student**.")

        if "admin_cam_active" not in st.session_state:
            st.session_state.admin_cam_active = False
        if "admin_captured_image" not in st.session_state:
            st.session_state.admin_captured_image = None

        colc1, colc2, colc3 = st.columns([1, 1, 2])
        with colc1:
            if st.button("Start Camera", key="admin_start_cam"):
                st.session_state.admin_cam_active = True
        with colc2:
            if st.button("Stop Camera", key="admin_stop_cam"):
                st.session_state.admin_cam_active = False
                st.session_state.admin_captured_image = None
        with colc3:
            st.caption("Alternatively, upload an existing photo in the form below.")

        camera_frame = None
        if st.session_state.admin_cam_active:
            camera_frame = st.camera_input(
                "Live camera (click camera icon to capture)", key="admin_cam"
            )
        if camera_frame is not None and st.button(
            "Capture Photo", key="admin_capture"
        ):
            st.session_state.admin_captured_image = camera_frame

        if st.session_state.admin_captured_image:
            st.image(
                st.session_state.admin_captured_image,
                width=180,
                caption="Captured photo preview",
            )

        with st.form("student_reg_form", clear_on_submit=True):
            name = st.text_input("Name")
            phone = st.text_input("Mobile Number")
            _class = st.selectbox("Class", classes)
            section = st.text_input("Section")
            branch = st.selectbox("Branch", ["AI", "CSE", "IT"], index=0)
            admission_year = st.number_input(
                "Admission Year (YYYY)", min_value=2000, max_value=2100, value=datetime.today().year, step=1
            )
            uploaded_photo = st.file_uploader(
                "Upload Student Photo (JPG/PNG)", type=["jpg", "jpeg", "png"], accept_multiple_files=False
            )
            submit = st.form_submit_button("Register Student")

            if submit:
                # Prefer uploaded photo if provided; otherwise use captured camera image
                photo_source = uploaded_photo or st.session_state.admin_captured_image

                if not all([name, phone, section, _class]):
                    st.warning("Name, mobile number, class, and section are required.")
                elif photo_source is None:
                    st.warning("Please upload a photo or capture one from the camera.")
                else:
                    student_id = utils.generate_id("student")
                    password = student_id
                    try:
                        roll = db.generate_roll_number(
                            year=int(admission_year),
                            branch=branch,
                            section=section.strip().upper() if section else "",
                        )
                    except Exception as e:
                        st.error(f"Could not generate roll number: {e}")
                        return

                    photo_path = STUDENT_IMAGES_DIR / f"{student_id}.jpg"
                    if utils.save_image(photo_source, photo_path):
                        ok = db.create_student(
                            student_id,
                            name,
                            roll,
                            section,
                            _class,
                            password,
                            str(photo_path),
                        )
                        if ok:
                            conn = db.get_db_connection()
                            conn.execute(
                                "UPDATE Students SET phone = ? WHERE student_id = ?",
                                (phone, student_id),
                            )
                            conn.commit()
                            conn.close()
                            with st.spinner("Extracting face embedding..."):
                                face_engine.register_student_face(
                                    student_id, str(photo_path)
                                )
                            st.success("Student registered.")
                            st.info(
                                f"ID: `{student_id}` | Password: `{password}` | Roll: `{roll}`"
                            )
                        else:
                            st.error("Database error creating student.")

    # View & Manage
    with tab_list:
        st.subheader("Teachers")
        teachers = db.list_teachers()
        if teachers:
            for t in teachers:
                c1, c2 = st.columns([4, 1])
                c1.write(f"**{t['name']}** — {t['teacher_id']} — {t['email']}")
                if c2.button("Delete", key=f"del_t_{t['teacher_id']}"):
                    db.delete_teacher(t["teacher_id"])
                    st.success("Teacher deleted.")
                    st.experimental_rerun()
        else:
            st.info("No teachers.")

        st.subheader("Students")
        students = db.list_students_with_photo()
        if students:
            for s in students:
                with st.container():
                    col_ph, col_inf, col_act = st.columns([1, 3, 1])
                    with col_ph:
                        pp = s.get("photo_path")
                        if pp and os.path.exists(str(pp)):
                            st.image(str(pp), width=70)
                        else:
                            st.caption("No photo")
                    with col_inf:
                        st.write(f"**{s['name']}**")
                        st.caption(
                            f"ID: {s['student_id']} | Roll: {s.get('roll')} | Class: {s.get('class')}"
                        )
                    with col_act:
                        if st.button("Delete", key=f"del_s_{s['student_id']}"):
                            db.delete_student(s["student_id"])
                            st.success("Student deleted.")
                            st.experimental_rerun()
                    st.markdown("---")
        else:
            st.info("No students.")

    # Messaging Center (SMS)
    with tab_msg:
        st.subheader("Messaging Center (SMS)")
        role = st.selectbox("Recipient type", ["Student", "Teacher"], key="msg_role")
        body = st.text_area("Message", key="msg_body")
        send_button = st.button("Send SMS", key="msg_send")

        if send_button:
            if not body:
                st.warning("Message body is required.")
            else:
                count = 0
                if role == "Student":
                    students = db.list_students_with_photo()
                    for s in students:
                        phone = s.get("phone")
                        if not phone:
                            continue
                        ok = sms_gateway.send_sms(phone, body)
                        db.create_message(
                            "Student",
                            s["student_id"],
                            phone,
                            body,
                            provider="Twilio",
                            status="OK" if ok else "FAIL",
                        )
                        count += 1
                else:
                    conn = db.get_db_connection()
                    rows = conn.execute(
                        "SELECT teacher_id, phone FROM Teachers"
                    ).fetchall()
                    conn.close()
                    for t in rows:
                        phone = t["phone"]
                        if not phone:
                            continue
                        ok = sms_gateway.send_sms(phone, body)
                        db.create_message(
                            "Teacher",
                            t["teacher_id"],
                            phone,
                            body,
                            provider="Twilio",
                            status="OK" if ok else "FAIL",
                        )
                        count += 1
                st.success(f"Queued SMS to approximately {count} recipients.")


def _admin_reports():
    st.title("Attendance Reports")
    records = db.get_all_attendance()
    if not records:
        st.info("No records.")
        return
    df = pd.DataFrame([dict(r) for r in records])
    col1, col2, col3 = st.columns(3)
    with col1:
        dates = sorted(df["date"].unique())
        date_f = st.multiselect("Date", dates, default=dates)
    with col2:
        subs = sorted(df["subject"].unique())
        sub_f = st.multiselect("Subject", subs, default=subs)
    with col3:
        status_f = st.multiselect(
            "Status", ["Present", "Absent"], default=["Present", "Absent"]
        )
    df = df[
        df["date"].isin(date_f)
        & df["subject"].isin(sub_f)
        & df["status"].isin(status_f)
    ]
    st.dataframe(df, width="stretch", hide_index=True)
    st.download_button(
        "📥 CSV",
        data=utils.to_csv(df),
        file_name="attendance_report.csv",
        mime="text/csv",
    )
