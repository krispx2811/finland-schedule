"""SQLite database operations."""

import os
import sqlite3
from datetime import datetime, timedelta
from typing import Optional
from .config import (DB_PATH, DB_DIR, DEFAULT_SHIFTS, DEFAULT_LOCATIONS,
                     DEFAULT_ANNUAL_LEAVE, DEFAULT_SICK_LEAVE)
from .models import Staff, Location, Shift, Schedule, Assignment


def get_connection() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            is_active INTEGER DEFAULT 1,
            default_location TEXT,
            default_role TEXT,
            shift_preference TEXT DEFAULT 'Any',
            annual_leave_balance INTEGER DEFAULT 30,
            sick_leave_balance INTEGER DEFAULT 15,
            staff_tag TEXT DEFAULT 'regular',
            overtime_max_hours REAL DEFAULT 45
        );

        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            short_code TEXT NOT NULL UNIQUE,
            min_staff INTEGER DEFAULT 1,
            max_staff INTEGER DEFAULT 3,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS shifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL UNIQUE,
            start_time TEXT,
            end_time TEXT,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_start TEXT NOT NULL,
            week_end TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id INTEGER NOT NULL REFERENCES schedules(id) ON DELETE CASCADE,
            staff_id INTEGER NOT NULL REFERENCES staff(id),
            day_of_week INTEGER NOT NULL,
            day_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'assigned',
            location_id INTEGER REFERENCES locations(id),
            shift_id INTEGER REFERENCES shifts(id),
            UNIQUE(schedule_id, staff_id, day_date)
        );

        CREATE TABLE IF NOT EXISTS staff_availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
            date TEXT NOT NULL,
            is_available INTEGER DEFAULT 0,
            reason TEXT,
            UNIQUE(staff_id, date)
        );

        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            leave_type TEXT NOT NULL DEFAULT 'annual',
            status TEXT NOT NULL DEFAULT 'pending',
            reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS swap_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id INTEGER NOT NULL REFERENCES schedules(id) ON DELETE CASCADE,
            requester_staff_id INTEGER NOT NULL REFERENCES staff(id),
            target_staff_id INTEGER NOT NULL REFERENCES staff(id),
            requester_date TEXT NOT NULL,
            target_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS assignment_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            schedule_id INTEGER NOT NULL,
            staff_id INTEGER NOT NULL,
            day_date TEXT NOT NULL,
            old_status TEXT,
            old_location_id INTEGER,
            old_shift_id INTEGER,
            new_status TEXT,
            new_location_id INTEGER,
            new_shift_id INTEGER,
            changed_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS fairness_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
            stat_type TEXT NOT NULL,
            stat_value INTEGER DEFAULT 0,
            period TEXT NOT NULL,
            UNIQUE(staff_id, stat_type, period)
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    conn.commit()

    # Migrations for existing databases
    cols = [row[1] for row in cursor.execute("PRAGMA table_info(staff)").fetchall()]
    if "shift_preference" not in cols:
        cursor.execute("ALTER TABLE staff ADD COLUMN shift_preference TEXT DEFAULT 'Any'")
    if "annual_leave_balance" not in cols:
        cursor.execute(f"ALTER TABLE staff ADD COLUMN annual_leave_balance INTEGER DEFAULT {DEFAULT_ANNUAL_LEAVE}")
    if "sick_leave_balance" not in cols:
        cursor.execute(f"ALTER TABLE staff ADD COLUMN sick_leave_balance INTEGER DEFAULT {DEFAULT_SICK_LEAVE}")
    if "staff_tag" not in cols:
        cursor.execute("ALTER TABLE staff ADD COLUMN staff_tag TEXT DEFAULT 'regular'")
    if "overtime_max_hours" not in cols:
        cursor.execute("ALTER TABLE staff ADD COLUMN overtime_max_hours REAL DEFAULT 45")
    conn.commit()
    conn.close()


def seed_defaults():
    conn = get_connection()
    cursor = conn.cursor()
    for label, start, end in DEFAULT_SHIFTS:
        cursor.execute("INSERT OR IGNORE INTO shifts (label, start_time, end_time) VALUES (?, ?, ?)",
                       (label, start, end))
    for name, code, mn, mx in DEFAULT_LOCATIONS:
        cursor.execute("INSERT OR IGNORE INTO locations (name, short_code, min_staff, max_staff) VALUES (?, ?, ?, ?)",
                       (name, code, mn, mx))
    conn.commit()
    conn.close()


# ===================== STAFF CRUD =====================

def add_staff(name, default_location=None, default_role=None, shift_preference="Any",
              staff_tag="regular", overtime_max_hours=45):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO staff (name, default_location, default_role, shift_preference, staff_tag, overtime_max_hours) VALUES (?, ?, ?, ?, ?, ?)",
        (name, default_location, default_role, shift_preference, staff_tag, overtime_max_hours))
    conn.commit()
    sid = cursor.lastrowid
    conn.close()
    return sid


def update_staff(staff_id, name, default_location=None, default_role=None,
                 is_active=True, shift_preference="Any", staff_tag="regular", overtime_max_hours=45):
    conn = get_connection()
    conn.execute(
        "UPDATE staff SET name=?, default_location=?, default_role=?, is_active=?, shift_preference=?, staff_tag=?, overtime_max_hours=? WHERE id=?",
        (name, default_location, default_role, int(is_active), shift_preference, staff_tag, overtime_max_hours, staff_id))
    conn.commit()
    conn.close()


def delete_staff(staff_id):
    conn = get_connection()
    # Remove dependent rows first so the delete never fails on a foreign-key
    # constraint (assignments.staff_id and swap_requests are NOT NULL with no
    # cascade). Availability, leave, and fairness rows cascade automatically.
    conn.execute("DELETE FROM assignments WHERE staff_id=?", (staff_id,))
    conn.execute("DELETE FROM swap_requests WHERE requester_staff_id=? OR target_staff_id=?",
                 (staff_id, staff_id))
    conn.execute("DELETE FROM staff WHERE id=?", (staff_id,))
    conn.commit()
    conn.close()


def _row_to_staff(r):
    return Staff(id=r["id"], name=r["name"], is_active=bool(r["is_active"]),
                 default_location=r["default_location"], default_role=r["default_role"],
                 shift_preference=r["shift_preference"] or "Any",
                 staff_tag=r["staff_tag"] or "regular",
                 overtime_max_hours=r["overtime_max_hours"] or 45)


def get_all_staff(active_only=True):
    conn = get_connection()
    q = "SELECT * FROM staff WHERE is_active=1 ORDER BY name" if active_only else "SELECT * FROM staff ORDER BY name"
    rows = conn.execute(q).fetchall()
    conn.close()
    return [_row_to_staff(r) for r in rows]


def get_staff_by_id(staff_id):
    conn = get_connection()
    r = conn.execute("SELECT * FROM staff WHERE id=?", (staff_id,)).fetchone()
    conn.close()
    return _row_to_staff(r) if r else None


def get_staff_leave_balance(staff_id):
    conn = get_connection()
    r = conn.execute("SELECT annual_leave_balance, sick_leave_balance FROM staff WHERE id=?",
                     (staff_id,)).fetchone()
    conn.close()
    return {"annual": r[0] or DEFAULT_ANNUAL_LEAVE, "sick": r[1] or DEFAULT_SICK_LEAVE} if r else None


def update_leave_balance(staff_id, annual=None, sick=None):
    conn = get_connection()
    if annual is not None:
        conn.execute("UPDATE staff SET annual_leave_balance=? WHERE id=?", (annual, staff_id))
    if sick is not None:
        conn.execute("UPDATE staff SET sick_leave_balance=? WHERE id=?", (sick, staff_id))
    conn.commit()
    conn.close()


# ===================== LOCATIONS CRUD =====================

def add_location(name, short_code, min_staff=1, max_staff=3):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO locations (name, short_code, min_staff, max_staff) VALUES (?, ?, ?, ?)",
                   (name, short_code, min_staff, max_staff))
    conn.commit()
    lid = cursor.lastrowid
    conn.close()
    return lid


def update_location(loc_id, name, short_code, min_staff=1, max_staff=3, is_active=True):
    conn = get_connection()
    conn.execute("UPDATE locations SET name=?, short_code=?, min_staff=?, max_staff=?, is_active=? WHERE id=?",
                 (name, short_code, min_staff, max_staff, int(is_active), loc_id))
    conn.commit()
    conn.close()


def delete_location(loc_id):
    conn = get_connection()
    # Drop any schedule assignments that reference this location first.
    conn.execute("DELETE FROM assignments WHERE location_id=?", (loc_id,))
    conn.execute("DELETE FROM locations WHERE id=?", (loc_id,))
    conn.commit()
    conn.close()


def get_all_locations(active_only=True):
    conn = get_connection()
    q = "SELECT * FROM locations WHERE is_active=1 ORDER BY name" if active_only else "SELECT * FROM locations ORDER BY name"
    rows = conn.execute(q).fetchall()
    conn.close()
    return [Location(id=r["id"], name=r["name"], short_code=r["short_code"],
                     min_staff=r["min_staff"], max_staff=r["max_staff"],
                     is_active=bool(r["is_active"])) for r in rows]


def get_location_by_code(code):
    conn = get_connection()
    r = conn.execute("SELECT * FROM locations WHERE short_code=?", (code,)).fetchone()
    conn.close()
    if r:
        return Location(id=r["id"], name=r["name"], short_code=r["short_code"],
                        min_staff=r["min_staff"], max_staff=r["max_staff"], is_active=bool(r["is_active"]))
    return None


# ===================== SHIFTS CRUD =====================

def get_all_shifts(active_only=True):
    conn = get_connection()
    q = "SELECT * FROM shifts WHERE is_active=1 ORDER BY start_time" if active_only else "SELECT * FROM shifts ORDER BY start_time"
    rows = conn.execute(q).fetchall()
    conn.close()
    return [Shift(id=r["id"], label=r["label"], start_time=r["start_time"],
                  end_time=r["end_time"], is_active=bool(r["is_active"])) for r in rows]


def get_shift_by_label(label):
    conn = get_connection()
    r = conn.execute("SELECT * FROM shifts WHERE label=?", (label,)).fetchone()
    conn.close()
    if r:
        return Shift(id=r["id"], label=r["label"], start_time=r["start_time"],
                     end_time=r["end_time"], is_active=bool(r["is_active"]))
    return None


def add_shift(label, start_time, end_time):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO shifts (label, start_time, end_time) VALUES (?, ?, ?)",
                   (label, start_time, end_time))
    conn.commit()
    sid = cursor.lastrowid
    conn.close()
    return sid


def update_shift(shift_id, label, start_time, end_time, is_active=True):
    conn = get_connection()
    conn.execute("UPDATE shifts SET label=?, start_time=?, end_time=?, is_active=? WHERE id=?",
                 (label, start_time, end_time, int(is_active), shift_id))
    conn.commit()
    conn.close()


def delete_shift(shift_id):
    conn = get_connection()
    # Drop any schedule assignments that reference this shift first.
    conn.execute("DELETE FROM assignments WHERE shift_id=?", (shift_id,))
    conn.execute("DELETE FROM shifts WHERE id=?", (shift_id,))
    conn.commit()
    conn.close()


def clear_all_data():
    """Wipe every record so the app returns to a completely empty state.

    Settings (such as the business name) are preferences, not data, so they
    are intentionally left untouched here.
    """
    conn = get_connection()
    # Delete child rows before parents to satisfy foreign-key constraints.
    for table in ("assignment_history", "fairness_stats", "staff_availability",
                  "leave_requests", "swap_requests", "assignments",
                  "schedules", "staff", "locations", "shifts"):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    conn.close()


# ===================== SETTINGS (key/value) =====================

def get_setting(key, default=None):
    conn = get_connection()
    r = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return r["value"] if r else default


def set_setting(key, value):
    conn = get_connection()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def get_all_settings():
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


# ===================== SCHEDULES CRUD =====================

def create_schedule(week_start, week_end, notes=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO schedules (week_start, week_end, notes) VALUES (?, ?, ?)",
                   (week_start, week_end, notes))
    conn.commit()
    sid = cursor.lastrowid
    conn.close()
    return sid


def get_all_schedules():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM schedules ORDER BY week_start DESC").fetchall()
    conn.close()
    return [Schedule(id=r["id"], week_start=r["week_start"], week_end=r["week_end"],
                     created_at=r["created_at"], notes=r["notes"] or "") for r in rows]


def delete_schedule(sched_id):
    conn = get_connection()
    conn.execute("DELETE FROM schedules WHERE id=?", (sched_id,))
    conn.commit()
    conn.close()


def copy_schedule(source_id, new_week_start):
    """Duplicate a schedule with new dates."""
    conn = get_connection()
    source = conn.execute("SELECT * FROM schedules WHERE id=?", (source_id,)).fetchone()
    if not source:
        conn.close()
        return None

    old_start = datetime.strptime(source["week_start"], "%Y-%m-%d")
    new_start = datetime.strptime(new_week_start, "%Y-%m-%d")
    day_offset = (new_start - old_start).days
    new_end = (new_start + timedelta(days=6)).strftime("%Y-%m-%d")

    cursor = conn.cursor()
    cursor.execute("INSERT INTO schedules (week_start, week_end, notes) VALUES (?, ?, ?)",
                   (new_week_start, new_end, f"Copied from {source['week_start']}"))
    new_id = cursor.lastrowid

    assignments = conn.execute("SELECT * FROM assignments WHERE schedule_id=?", (source_id,)).fetchall()
    for a in assignments:
        old_date = datetime.strptime(a["day_date"], "%Y-%m-%d")
        new_date = (old_date + timedelta(days=day_offset)).strftime("%Y-%m-%d")
        cursor.execute(
            """INSERT INTO assignments (schedule_id, staff_id, day_of_week, day_date, status, location_id, shift_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (new_id, a["staff_id"], a["day_of_week"], new_date, a["status"], a["location_id"], a["shift_id"]))

    conn.commit()
    conn.close()
    return new_id


# ===================== ASSIGNMENTS CRUD =====================

def add_assignment(schedule_id, staff_id, day_of_week, day_date, status="assigned",
                   location_id=None, shift_id=None):
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO assignments
           (schedule_id, staff_id, day_of_week, day_date, status, location_id, shift_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (schedule_id, staff_id, day_of_week, day_date, status, location_id, shift_id))
    conn.commit()
    conn.close()


def update_assignment(assignment_id, status, location_id=None, shift_id=None):
    conn = get_connection()
    # Log history
    old = conn.execute("SELECT * FROM assignments WHERE id=?", (assignment_id,)).fetchone()
    if old:
        conn.execute(
            """INSERT INTO assignment_history
               (assignment_id, schedule_id, staff_id, day_date, old_status, old_location_id, old_shift_id,
                new_status, new_location_id, new_shift_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (assignment_id, old["schedule_id"], old["staff_id"], old["day_date"],
             old["status"], old["location_id"], old["shift_id"],
             status, location_id, shift_id))
    conn.execute("UPDATE assignments SET status=?, location_id=?, shift_id=? WHERE id=?",
                 (status, location_id, shift_id, assignment_id))
    conn.commit()
    conn.close()


def get_schedule_assignments(schedule_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT a.*, s.name as staff_name,
               COALESCE(l.short_code, '') as location_code,
               COALESCE(sh.label, '') as shift_label
        FROM assignments a
        JOIN staff s ON a.staff_id = s.id
        LEFT JOIN locations l ON a.location_id = l.id
        LEFT JOIN shifts sh ON a.shift_id = sh.id
        WHERE a.schedule_id = ?
        ORDER BY s.name, a.day_of_week
    """, (schedule_id,)).fetchall()
    conn.close()
    return [Assignment(
        id=r["id"], schedule_id=r["schedule_id"], staff_id=r["staff_id"],
        day_of_week=r["day_of_week"], day_date=r["day_date"], status=r["status"],
        location_id=r["location_id"], shift_id=r["shift_id"],
        staff_name=r["staff_name"], location_code=r["location_code"],
        shift_label=r["shift_label"]) for r in rows]


def has_data():
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM staff").fetchone()[0]
    conn.close()
    return count > 0


# ===================== AVAILABILITY =====================

def set_availability(staff_id, date, is_available, reason=""):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO staff_availability (staff_id, date, is_available, reason) VALUES (?, ?, ?, ?)",
        (staff_id, date, int(is_available), reason))
    conn.commit()
    conn.close()


def get_staff_availability(staff_id, week_start, week_end):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM staff_availability WHERE staff_id=? AND date BETWEEN ? AND ?",
        (staff_id, week_start, week_end)).fetchall()
    conn.close()
    return [{"date": r["date"], "is_available": bool(r["is_available"]), "reason": r["reason"]} for r in rows]


def get_unavailable_staff(date):
    conn = get_connection()
    rows = conn.execute(
        "SELECT staff_id FROM staff_availability WHERE date=? AND is_available=0",
        (date,)).fetchall()
    conn.close()
    return [r["staff_id"] for r in rows]


# ===================== LEAVE REQUESTS =====================

def create_leave_request(staff_id, start_date, end_date, leave_type="annual", reason=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO leave_requests (staff_id, start_date, end_date, leave_type, reason) VALUES (?, ?, ?, ?, ?)",
        (staff_id, start_date, end_date, leave_type, reason))
    conn.commit()
    lid = cursor.lastrowid
    conn.close()
    return lid


def get_leave_requests(staff_id=None, status=None):
    conn = get_connection()
    q = """SELECT lr.*, s.name as staff_name FROM leave_requests lr
           JOIN staff s ON lr.staff_id = s.id WHERE 1=1"""
    params = []
    if staff_id:
        q += " AND lr.staff_id=?"
        params.append(staff_id)
    if status:
        q += " AND lr.status=?"
        params.append(status)
    q += " ORDER BY lr.created_at DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_leave_status(request_id, status):
    conn = get_connection()
    conn.execute("UPDATE leave_requests SET status=? WHERE id=?", (status, request_id))
    if status == "approved":
        req = conn.execute("SELECT * FROM leave_requests WHERE id=?", (request_id,)).fetchone()
        if req:
            start = datetime.strptime(req["start_date"], "%Y-%m-%d")
            end = datetime.strptime(req["end_date"], "%Y-%m-%d")
            current = start
            while current <= end:
                date_str = current.strftime("%Y-%m-%d")
                conn.execute(
                    "INSERT OR REPLACE INTO staff_availability (staff_id, date, is_available, reason) VALUES (?, ?, 0, ?)",
                    (req["staff_id"], date_str, f"Approved {req['leave_type']} leave"))
                current += timedelta(days=1)
            # Deduct leave balance
            days = (end - start).days + 1
            if req["leave_type"] == "annual":
                conn.execute("UPDATE staff SET annual_leave_balance = annual_leave_balance - ? WHERE id=?",
                             (days, req["staff_id"]))
            elif req["leave_type"] == "sick":
                conn.execute("UPDATE staff SET sick_leave_balance = sick_leave_balance - ? WHERE id=?",
                             (days, req["staff_id"]))
    conn.commit()
    conn.close()


def get_approved_leave_for_date(date):
    conn = get_connection()
    rows = conn.execute(
        "SELECT staff_id FROM leave_requests WHERE status='approved' AND ? BETWEEN start_date AND end_date",
        (date,)).fetchall()
    conn.close()
    return [r["staff_id"] for r in rows]


# ===================== SWAP REQUESTS =====================

def create_swap_request(schedule_id, requester_id, target_id, requester_date, target_date):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO swap_requests (schedule_id, requester_staff_id, target_staff_id, requester_date, target_date)
           VALUES (?, ?, ?, ?, ?)""",
        (schedule_id, requester_id, target_id, requester_date, target_date))
    conn.commit()
    sid = cursor.lastrowid
    conn.close()
    return sid


def get_swap_requests(schedule_id=None, status=None):
    conn = get_connection()
    q = """SELECT sr.*, s1.name as requester_name, s2.name as target_name
           FROM swap_requests sr
           JOIN staff s1 ON sr.requester_staff_id = s1.id
           JOIN staff s2 ON sr.target_staff_id = s2.id WHERE 1=1"""
    params = []
    if schedule_id:
        q += " AND sr.schedule_id=?"
        params.append(schedule_id)
    if status:
        q += " AND sr.status=?"
        params.append(status)
    q += " ORDER BY sr.created_at DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def approve_swap(request_id):
    conn = get_connection()
    sr = conn.execute("SELECT * FROM swap_requests WHERE id=?", (request_id,)).fetchone()
    if not sr:
        conn.close()
        return False

    a1 = conn.execute(
        "SELECT * FROM assignments WHERE schedule_id=? AND staff_id=? AND day_date=?",
        (sr["schedule_id"], sr["requester_staff_id"], sr["requester_date"])).fetchone()
    a2 = conn.execute(
        "SELECT * FROM assignments WHERE schedule_id=? AND staff_id=? AND day_date=?",
        (sr["schedule_id"], sr["target_staff_id"], sr["target_date"])).fetchone()

    if a1 and a2:
        conn.execute("UPDATE assignments SET status=?, location_id=?, shift_id=? WHERE id=?",
                     (a2["status"], a2["location_id"], a2["shift_id"], a1["id"]))
        conn.execute("UPDATE assignments SET status=?, location_id=?, shift_id=? WHERE id=?",
                     (a1["status"], a1["location_id"], a1["shift_id"], a2["id"]))

    conn.execute("UPDATE swap_requests SET status='approved' WHERE id=?", (request_id,))
    conn.commit()
    conn.close()
    return True


def reject_swap(request_id):
    conn = get_connection()
    conn.execute("UPDATE swap_requests SET status='rejected' WHERE id=?", (request_id,))
    conn.commit()
    conn.close()


# ===================== CONFLICT DETECTION =====================

def detect_conflicts(schedule_id):
    conn = get_connection()
    conflicts = []
    locations = conn.execute("SELECT * FROM locations WHERE is_active=1").fetchall()
    assignments = conn.execute("""
        SELECT a.*, s.name as staff_name, COALESCE(l.short_code, '') as loc_code
        FROM assignments a
        JOIN staff s ON a.staff_id = s.id
        LEFT JOIN locations l ON a.location_id = l.id
        WHERE a.schedule_id = ?
    """, (schedule_id,)).fetchall()

    # Group by day
    from collections import defaultdict
    day_loc_count = defaultdict(lambda: defaultdict(int))
    day_staff = defaultdict(list)

    for a in assignments:
        if a["status"] == "assigned" and a["location_id"]:
            day_loc_count[a["day_date"]][a["location_id"]] += 1
        day_staff[a["day_date"]].append(a["staff_id"])

    # Check understaffed/overstaffed
    for loc in locations:
        for day_date, loc_counts in day_loc_count.items():
            count = loc_counts.get(loc["id"], 0)
            if count < loc["min_staff"]:
                conflicts.append({
                    "type": "understaffed", "day_date": day_date,
                    "location": loc["short_code"],
                    "message": f"{loc['short_code']} has {count}/{loc['min_staff']} min staff on {day_date}"
                })

    # Check double-bookings
    for day_date, staff_ids in day_staff.items():
        seen = set()
        for sid in staff_ids:
            if sid in seen:
                conflicts.append({
                    "type": "double_booked", "day_date": day_date,
                    "message": f"Staff ID {sid} is double-booked on {day_date}"
                })
            seen.add(sid)

    conn.close()
    return conflicts


# ===================== HISTORY =====================

def get_assignment_history(schedule_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT ah.*, s.name as staff_name,
               COALESCE(ol.short_code, '') as old_location, COALESCE(nl.short_code, '') as new_location,
               COALESCE(os.label, '') as old_shift, COALESCE(ns.label, '') as new_shift
        FROM assignment_history ah
        JOIN staff s ON ah.staff_id = s.id
        LEFT JOIN locations ol ON ah.old_location_id = ol.id
        LEFT JOIN locations nl ON ah.new_location_id = nl.id
        LEFT JOIN shifts os ON ah.old_shift_id = os.id
        LEFT JOIN shifts ns ON ah.new_shift_id = ns.id
        WHERE ah.schedule_id = ?
        ORDER BY ah.changed_at DESC
    """, (schedule_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def compare_schedules(id_a, id_b):
    conn = get_connection()
    a_rows = conn.execute("""
        SELECT a.staff_id, a.day_of_week, a.status, COALESCE(l.short_code,'') as loc, COALESCE(sh.label,'') as shift, s.name
        FROM assignments a JOIN staff s ON a.staff_id=s.id
        LEFT JOIN locations l ON a.location_id=l.id LEFT JOIN shifts sh ON a.shift_id=sh.id
        WHERE a.schedule_id=?""", (id_a,)).fetchall()
    b_rows = conn.execute("""
        SELECT a.staff_id, a.day_of_week, a.status, COALESCE(l.short_code,'') as loc, COALESCE(sh.label,'') as shift, s.name
        FROM assignments a JOIN staff s ON a.staff_id=s.id
        LEFT JOIN locations l ON a.location_id=l.id LEFT JOIN shifts sh ON a.shift_id=sh.id
        WHERE a.schedule_id=?""", (id_b,)).fetchall()
    conn.close()

    a_map = {(r["staff_id"], r["day_of_week"]): r for r in a_rows}
    b_map = {(r["staff_id"], r["day_of_week"]): r for r in b_rows}

    diffs = []
    all_keys = set(a_map.keys()) | set(b_map.keys())
    for key in sorted(all_keys):
        a = a_map.get(key)
        b = b_map.get(key)
        if a and b:
            if a["status"] != b["status"] or a["loc"] != b["loc"] or a["shift"] != b["shift"]:
                diffs.append({
                    "staff_name": a["name"], "day": key[1],
                    "before": f"{a['shift']} {a['loc']}" if a["status"] == "assigned" else a["status"].upper(),
                    "after": f"{b['shift']} {b['loc']}" if b["status"] == "assigned" else b["status"].upper()
                })
    return diffs


# ===================== FAIRNESS =====================

def update_fairness_stats(schedule_id):
    conn = get_connection()
    sched = conn.execute("SELECT * FROM schedules WHERE id=?", (schedule_id,)).fetchone()
    if not sched:
        conn.close()
        return

    period = sched["week_start"][:7]  # "YYYY-MM"
    assignments = conn.execute(
        "SELECT * FROM assignments WHERE schedule_id=?", (schedule_id,)).fetchall()

    from collections import defaultdict
    stats = defaultdict(lambda: {"friday": 0, "weekend": 0, "off_days": 0})

    for a in assignments:
        sid = a["staff_id"]
        if a["status"] == "off" or a["status"] == "leave":
            stats[sid]["off_days"] += 1
        else:
            if a["day_of_week"] == 6:  # Friday
                stats[sid]["friday"] += 1
            if a["day_of_week"] >= 5:  # Thursday + Friday
                stats[sid]["weekend"] += 1

    cursor = conn.cursor()
    for sid, s in stats.items():
        for stat_type, val in [("friday_work_count", s["friday"]),
                                ("weekend_work_count", s["weekend"]),
                                ("off_day_count", s["off_days"])]:
            cursor.execute("""
                INSERT INTO fairness_stats (staff_id, stat_type, stat_value, period)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(staff_id, stat_type, period)
                DO UPDATE SET stat_value = stat_value + ?
            """, (sid, stat_type, val, period, val))

    conn.commit()
    conn.close()


def get_fairness_report(period):
    conn = get_connection()
    rows = conn.execute("""
        SELECT fs.*, s.name as staff_name
        FROM fairness_stats fs JOIN staff s ON fs.staff_id = s.id
        WHERE fs.period = ? ORDER BY s.name
    """, (period,)).fetchall()
    conn.close()

    report = {}
    for r in rows:
        name = r["staff_name"]
        if name not in report:
            report[name] = {"staff_name": name, "friday_work_count": 0,
                           "weekend_work_count": 0, "off_day_count": 0}
        report[name][r["stat_type"]] = r["stat_value"]
    return list(report.values())


def get_fairness_for_scheduler():
    """Get cumulative fairness stats for scheduling decisions."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT staff_id, stat_type, SUM(stat_value) as total
        FROM fairness_stats GROUP BY staff_id, stat_type
    """).fetchall()
    conn.close()

    from collections import defaultdict
    stats = defaultdict(lambda: {"friday": 0, "weekend": 0})
    for r in rows:
        if r["stat_type"] == "friday_work_count":
            stats[r["staff_id"]]["friday"] = r["total"]
        elif r["stat_type"] == "weekend_work_count":
            stats[r["staff_id"]]["weekend"] = r["total"]
    return dict(stats)


def get_weekend_work_counts():
    """How many Friday/Saturday shifts each staff member has actually worked,
    across all schedules — used to rotate the weekend salesman fairly."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT staff_id, COUNT(*) AS c FROM assignments "
        "WHERE status='assigned' AND day_of_week IN (0, 6) GROUP BY staff_id"
    ).fetchall()
    conn.close()
    return {r["staff_id"]: r["c"] for r in rows}


# ===================== DASHBOARD STATS =====================

def get_dashboard_stats(schedule_id):
    conn = get_connection()
    assignments = conn.execute("""
        SELECT a.*, s.name as staff_name, sh.start_time, sh.end_time, sh.label as shift_label,
               COALESCE(l.short_code, '') as loc_code
        FROM assignments a
        JOIN staff s ON a.staff_id = s.id
        LEFT JOIN shifts sh ON a.shift_id = sh.id
        LEFT JOIN locations l ON a.location_id = l.id
        WHERE a.schedule_id = ?
    """, (schedule_id,)).fetchall()

    locations = conn.execute("SELECT * FROM locations WHERE is_active=1").fetchall()
    conn.close()

    # Calculate hours per staff
    from collections import defaultdict
    staff_hours = defaultdict(float)
    for a in assignments:
        if a["start_time"] and a["end_time"] and a["status"] == "assigned":
            hours = _calc_hours(a["start_time"], a["end_time"])
            staff_hours[a["staff_name"]] += hours

    # Location coverage
    loc_day_counts = defaultdict(lambda: defaultdict(int))
    for a in assignments:
        if a["status"] == "assigned" and a["loc_code"]:
            loc_day_counts[a["loc_code"]][a["day_of_week"]] += 1

    total_slots = 0
    covered_slots = 0
    for loc in locations:
        code = loc["short_code"]
        for day in range(7):
            total_slots += 1
            if loc_day_counts[code][day] >= loc["min_staff"]:
                covered_slots += 1

    coverage_score = round(covered_slots / max(total_slots, 1) * 100)

    # Get per-staff overtime thresholds
    staff_thresholds = {}
    staff_tags = {}
    conn2 = get_connection()
    for r in conn2.execute("SELECT name, overtime_max_hours, staff_tag FROM staff").fetchall():
        staff_thresholds[r["name"]] = r["overtime_max_hours"] or 45
        staff_tags[r["name"]] = r["staff_tag"] or "regular"
    conn2.close()

    overtime_list = []
    for n, h in staff_hours.items():
        threshold = staff_thresholds.get(n, 45)
        if h > threshold:
            overtime_list.append({"name": n, "hours": round(h, 1), "max": threshold})

    return {
        "staff_hours": dict(staff_hours),
        "staff_tags": staff_tags,
        "total_hours": round(sum(staff_hours.values()), 1),
        "overtime": overtime_list,
        "coverage_score": coverage_score,
        "location_coverage": {code: dict(days) for code, days in loc_day_counts.items()}
    }


def get_monthly_report(year_month):
    """Generate a monthly report for all staff. year_month = 'YYYY-MM'."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT a.staff_id, s.name, s.staff_tag, a.status, a.day_date,
               sh.start_time, sh.end_time, COALESCE(l.short_code, '') as loc_code
        FROM assignments a
        JOIN staff s ON a.staff_id = s.id
        LEFT JOIN shifts sh ON a.shift_id = sh.id
        LEFT JOIN locations l ON a.location_id = l.id
        JOIN schedules sc ON a.schedule_id = sc.id
        WHERE a.day_date LIKE ?
        ORDER BY s.name, a.day_date
    """, (year_month + "%",)).fetchall()
    conn.close()

    from collections import defaultdict
    report = defaultdict(lambda: {"days_worked": 0, "days_off": 0, "days_leave": 0,
                                   "total_hours": 0, "locations": defaultdict(int)})
    for r in rows:
        name = r["name"]
        report[name]["staff_tag"] = r["staff_tag"] or "regular"
        if r["status"] == "assigned":
            report[name]["days_worked"] += 1
            if r["start_time"] and r["end_time"]:
                report[name]["total_hours"] += _calc_hours(r["start_time"], r["end_time"])
            if r["loc_code"]:
                report[name]["locations"][r["loc_code"]] += 1
        elif r["status"] == "off":
            report[name]["days_off"] += 1
        elif r["status"] == "leave":
            report[name]["days_leave"] += 1

    result = []
    for name in sorted(report.keys()):
        d = report[name]
        result.append({
            "staff_name": name, "staff_tag": d.get("staff_tag", "regular"),
            "days_worked": d["days_worked"], "days_off": d["days_off"],
            "days_leave": d["days_leave"], "total_hours": round(d["total_hours"], 1),
            "top_location": max(d["locations"], key=d["locations"].get) if d["locations"] else "-"
        })
    return result


def _calc_hours(start, end):
    try:
        sh, sm = map(int, start.replace(".", ":").split(":"))
        eh, em = map(int, end.replace(".", ":").split(":"))
        start_min = sh * 60 + sm
        end_min = eh * 60 + em
        if end_min <= start_min:
            end_min += 24 * 60
        return (end_min - start_min) / 60
    except Exception:
        return 8  # default
