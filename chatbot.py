# attendance_system/chatbot.py

import streamlit as st
from groq import Groq
import database as db
import pandas as pd


# ---------------- GROQ API SETUP ----------------

try:
    groq_key = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=groq_key)
except Exception:
    client = None


# ---------------- AI RESPONSE FUNCTION ----------------

def get_ai_response(prompt: str):

    if not client:
        return "AI service is currently unavailable."

    try:

        completion = client.chat.completions.create(

            model="llama-3.3-70b-versatile",

            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful college assistant chatbot."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0.5,
            max_tokens=500
        )

        return completion.choices[0].message.content

    except Exception as e:
        return f"Groq API error: {str(e)}"


# ---------------- CHATBOT ----------------

def _process_prompt(prompt: str):
    """Compute AI response for user prompt; returns response string."""
    prompt_lower = prompt.lower()
    user_info = st.session_state.get("user_info") or {}
    role = st.session_state.get("role", "")

    attendance_keywords = [
        "attendance", "my attendance", "attendance percentage",
        "classes attended", "attendance record"
    ]

    if any(w in prompt_lower for w in attendance_keywords) and role == "Student" and user_info.get("student_id"):
        student_id = user_info["student_id"]
        student_name = user_info.get("name", "Student")
        records = db.get_attendance_by_student(student_id)
        if records:
            df = pd.DataFrame([dict(r) for r in records])
            total_classes = len(df)
            present_count = (df["status"] == "Present").sum()
            percentage = (present_count / total_classes * 100) if total_classes > 0 else 0
            status = "Good attendance" if percentage >= 75 else "Average attendance" if percentage >= 60 else "Low attendance"
            context_data = f"Student: {student_name}, ID: {student_id}, Classes: {total_classes}, Present: {present_count}, Percentage: {percentage:.2f}%, Status: {status}"
        else:
            context_data = "No attendance records found."
        ai_prompt = f"A student asked: {prompt}\n\nStudent data: {context_data}\nExplain clearly."
        return get_ai_response(ai_prompt)

    if any(w in prompt_lower for w in ["my name", "my id", "student details"]) and user_info:
        name = user_info.get("name", "—")
        sid = user_info.get("student_id") or user_info.get("teacher_id") or "—"
        return f"**Name:** {name}  \n**ID:** {sid}  \n\nFor attendance, ask: *What is my attendance?*"

    return get_ai_response(f"You are a helpful college assistant. User asked: {prompt}\nAnswer clearly.")


def render_chatbot_main():
    """ChatGPT-style chatbot in main content area."""
    st.title("🤖 AI College Assistant")
    st.caption("Ask about attendance, profile, or general college queries.")

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Hello! I'm your college assistant. Ask me anything—attendance, profile, or general help."}
        ]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("Type your message...")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = _process_prompt(prompt)
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})


def render_chatbot():
    """Legacy: sidebar chatbot (optional)."""
    with st.sidebar:
        st.markdown("## 🤖 AI Assistant")
        if "messages" not in st.session_state:
            st.session_state.messages = [
                {"role": "assistant", "content": "Hello! Ask me anything."}
            ]
        for msg in st.session_state.messages[-6:]:  # last 6 in sidebar
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
        prompt = st.chat_input("Ask...")
        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            response = _process_prompt(prompt)
            st.session_state.messages.append({"role": "assistant", "content": response})
            with st.chat_message("assistant"):
                st.markdown(response)