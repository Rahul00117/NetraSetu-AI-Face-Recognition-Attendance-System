# attendance_system/config.py

import os
from pathlib import Path

# --- DIRECTORIES ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_FILE = DATA_DIR / "app.db"
STUDENT_IMAGES_DIR = DATA_DIR / "students"
GROUP_PHOTOS_DIR = DATA_DIR / "group_photos"
ASSETS_DIR = BASE_DIR / "assets"

# --- ID GENERATION ---
ID_YEAR_PREFIX = "25"  # Represents the year 2025
TEACHER_ID_PREFIX = "T"
STUDENT_ID_PREFIX = "S"

# --- DEFAULT ADMIN ---
DEFAULT_ADMIN_EMAIL = "admin@college.com"
DEFAULT_ADMIN_PASSWORD = "Admin@123"
# T250008  S250015