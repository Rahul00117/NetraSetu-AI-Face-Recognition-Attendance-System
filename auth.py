# attendance_system/auth.py

import streamlit as st
import database as db

def login():
    """Displays the login form and handles authentication."""
    st.header("Login Portal")
    
    role = st.selectbox("Select your role:", ["Admin", "Teacher", "Student"])
    
    with st.form(key=f'{role.lower()}_login_form'):
        if role == "Admin":
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
        else: # Teacher or Student
            user_id = st.text_input(f"{role} ID", placeholder=f"e.g., {'T250001' if role == 'Teacher' else 'S250001'}")
            password = st.text_input("Password", type="password")
        
        submit_button = st.form_submit_button(label=f"Login as {role}")

    if submit_button:
        if role == "Admin":
            admin = db.get_admin_by_email(email)
            if admin and admin['password'] == password:
                st.session_state.logged_in = True
                st.session_state.role = "Admin"
                st.session_state.user_info = {'email': admin['email']}
                st.rerun()
            else:
                st.error("Invalid admin credentials.")
        
        elif role == "Teacher":
            teacher = db.get_teacher(user_id)
            if teacher and teacher['password'] == password:
                st.session_state.logged_in = True
                st.session_state.role = "Teacher"
                st.session_state.user_info = dict(teacher)
                st.rerun()
            else:
                st.error("Invalid Teacher ID or password.")

        elif role == "Student":
            student = db.get_student(user_id)
            if student and student['password'] == password:
                st.session_state.logged_in = True
                st.session_state.role = "Student"
                st.session_state.user_info = dict(student)
                st.rerun()
            else:
                st.error("Invalid Student ID or password.")