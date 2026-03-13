# attendance_system/utils.py

import streamlit as st
import pandas as pd
from PIL import Image
from datetime import datetime

import cv2
import numpy as np

import database as db
from config import (
    ID_YEAR_PREFIX,
    TEACHER_ID_PREFIX,
    STUDENT_ID_PREFIX,
    STUDENT_IMAGES_DIR,
    GROUP_PHOTOS_DIR,
)
import face_engine

# --- ID Generation ---
def generate_id(user_type):
    """Generates a new sequential ID for a teacher or student."""
    if user_type == 'teacher':
        serial_key = 'last_teacher_serial'
        prefix = TEACHER_ID_PREFIX
    elif user_type == 'student':
        serial_key = 'last_student_serial'
        prefix = STUDENT_ID_PREFIX
    else:
        raise ValueError("Invalid user type for ID generation.")
    
    next_serial = db.get_next_serial(serial_key)
    return f"{prefix}{ID_YEAR_PREFIX}{str(next_serial).zfill(4)}"

# --- File Handling ---
def save_image(uploaded_file, save_path):
    """Saves an uploaded image file (from file_uploader or camera_input) to a specified path."""
    try:
        if hasattr(uploaded_file, 'seek'):
            uploaded_file.seek(0)
        img = Image.open(uploaded_file)
        img.save(str(save_path))
        return True
    except Exception as e:
        st.error(f"Error saving image: {e}")
        return False

def generate_group_photo_path(teacher_id):
    """Generates a unique path for a group photo."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{teacher_id}_{timestamp}.jpg"
    return GROUP_PHOTOS_DIR / filename

# --- Data Conversion ---
def to_csv(df):
    """Converts a DataFrame to a CSV string for download."""
    return df.to_csv(index=False).encode("utf-8")


def to_excel(df):
    """Returns Excel file bytes for download."""
    import io
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Attendance")
    buf.seek(0)
    return buf.getvalue()


def to_pdf(df, title="Attendance Report"):
    """Returns PDF file bytes for download (simple table)."""
    try:
        from fpdf import FPDF
    except ImportError:
        return None
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, title, ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.ln(5)
    cols = df.columns.tolist()
    col_w = 190 / len(cols) if cols else 40
    for col in cols:
        pdf.cell(col_w, 7, str(col)[:20], border=1)
    pdf.ln()
    for _, row in df.iterrows():
        for col in cols:
            pdf.cell(col_w, 6, str(row[col])[:20] if pd.notna(row[col]) else "", border=1)
        pdf.ln()
    return bytes(pdf.output())

def recognize_from_group_photo(group_photo_path, threshold: float = 0.4):
    """
    Run the full group-photo pipeline: load, preprocess, detect, align, recognize.
    Uses SCRFD for multi-face detection, ArcFace for embeddings, DB for matching.

    Args:
        group_photo_path: Path to the saved group photo (string or Path).
        threshold: Cosine similarity threshold for recognizing a face.

    Returns:
        Tuple of (list of RecognitionResult, RecognitionReport).
        Report contains num_detected, num_recognized, num_unknown, confidence_scores.
    """
    try:
        image = cv2.imread(str(group_photo_path))
    except Exception as e:
        st.error(f"Could not load group photo: {e}")
        return [], face_engine.RecognitionReport()

    if image is None:
        st.error("Could not read the group photo from disk.")
        return [], face_engine.RecognitionReport()

    try:
        results, report = face_engine.recognize_faces_in_group_photo(
            image, threshold=threshold
        )
        return results, report
    except Exception as e:
        st.error(f"Face recognition failed: {e}")
        return [], face_engine.RecognitionReport()