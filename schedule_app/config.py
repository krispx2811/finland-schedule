"""Application constants and configuration."""

APP_NAME = "Finland Optical Center - Schedule Manager"
APP_VERSION = "1.0.9"

# Auto-update: the app checks this file on GitHub for a newer version.
UPDATE_MANIFEST_URL = "https://raw.githubusercontent.com/krispx2811/finland-schedule/main/version.json"

# Oman work week: Saturday (0) through Friday (6)
DAYS_OF_WEEK = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
DAYS_SHORT = ["Sat", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri"]

# Operating hours
OPENING_TIME = "10:00"  # 10 AM every day
CLOSING_TIME_WEEKDAY = "22:00"  # 10 PM (Sat-Wed)
CLOSING_TIME_WEEKEND = "00:00"  # 12 AM midnight (Thu-Fri)

# Default shift patterns (label, start_time, end_time)
# Sat-Wed shifts (close 10 PM)
# Thu-Fri shifts (close 12 AM)
DEFAULT_SHIFTS = [
    ("10-7", "10:00", "19:00"),       # 10am-7pm (all days)
    ("11:30-8:30", "11:30", "20:30"), # 11:30am-8:30pm (all days)
    ("12-9", "12:00", "21:00"),       # 12pm-9pm (all days)
    ("1-10", "13:00", "22:00"),       # 1pm-10pm (Sat-Wed closing shift)
    ("2-11", "14:00", "23:00"),       # 2pm-11pm (Thu-Fri)
    ("3-12", "15:00", "00:00"),       # 3pm-12am (Thu-Fri closing shift)
]

# Default locations (name, short_code, min_staff, max_staff)
DEFAULT_LOCATIONS = [
    ("Avenues", "AV", 2, 3),
    ("CCC", "CCC", 1, 2),
    ("QCC", "QCC", 2, 3),
    ("Salalah", "SALALAH", 3, 4),
    ("SUR", "SUR", 1, 2),
    ("Nizwa", "NIZWA", 1, 2),
    ("Office", "Office", 1, 3),
    ("Clinic", "Clinic", 1, 2),
]

# Assignment statuses
STATUS_ASSIGNED = "assigned"
STATUS_OFF = "off"
STATUS_LEAVE = "leave"

# Staff with fixed/permanent assignments
FIXED_ASSIGNMENTS = {
    "Wjdan": "Salalah",
    "Yassen": "Salalah",
    "M.Nada": "Salalah",
    "Bayan": "Salalah",
    "Abdulrahim": "Nizwa",
}

FIXED_ROLES = {
    "OSAMA": "Clinic",
    "Azmi": "Office",
    "Khulood": "Office",
}

# Leave defaults
DEFAULT_ANNUAL_LEAVE = 30
DEFAULT_SICK_LEAVE = 15
LEAVE_TYPES = ["annual", "sick", "unpaid"]

# Overtime threshold (weekly hours)
OVERTIME_THRESHOLD_HOURS = 45

# Location code mappings (Excel uses short codes)
LOCATION_CODE_MAP = {
    "AV": "Avenues",
    "CCC": "CCC",
    "QCC": "QCC",
    "SALALAH": "Salalah",
    "SUR": "SUR",
    "NIZWA": "Nizwa",
    "Office": "Office",
    "Clinic": "Clinic",
}

# DB file path — store in a writable per-user location.
# IMPORTANT (macOS): never write inside the .app bundle. The bundle is
# read-only when launched from a DMG, and writing into it invalidates the
# code signature (Gatekeeper then refuses to launch with "app is damaged").
import os
import sys

if getattr(sys, '_MEIPASS', None):
    # Running as a PyInstaller bundle.
    if sys.platform == "darwin":
        # macOS: standard per-user application data directory.
        DB_DIR = os.path.join(
            os.path.expanduser("~/Library/Application Support"),
            "Finland Schedule",
        )
    else:
        # Windows/Linux: store next to the executable (portable).
        DB_DIR = os.path.join(os.path.dirname(sys.executable), "data")
else:
    DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

DB_PATH = os.path.join(DB_DIR, "schedule.db")
