"""Flask web application for the schedule manager."""

import os
import sys
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file
from . import database as db
from .scheduler import generate_schedule
from .pdf_export import export_schedule_pdf
from .excel_export import export_schedule_excel
from .excel_import import import_excel
from .config import DAYS_SHORT, APP_NAME, APP_VERSION


def get_resource_path(relative_path):
    if getattr(sys, '_MEIPASS', None):
        return os.path.join(sys._MEIPASS, "schedule_app", relative_path)
    return os.path.join(os.path.dirname(__file__), relative_path)


def get_sample_excel_path():
    """Path to the bundled 'New Schedule.xlsx' used by Load Sample Data."""
    if getattr(sys, '_MEIPASS', None):
        return os.path.join(sys._MEIPASS, "New Schedule.xlsx")
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "New Schedule.xlsx")


app = Flask(__name__,
            template_folder=get_resource_path("templates"),
            static_folder=get_resource_path("static"))


@app.route("/")
def index():
    return render_template("index.html", app_name=APP_NAME)


# ==================== SCHEDULE API ====================

@app.route("/api/schedules")
def api_schedules():
    return jsonify([{"id": s.id, "week_start": s.week_start, "week_end": s.week_end, "notes": s.notes}
                    for s in db.get_all_schedules()])


@app.route("/api/schedule/<int:schedule_id>")
def api_schedule(schedule_id):
    assignments = db.get_schedule_assignments(schedule_id)
    staff_data = {}
    for a in assignments:
        if a.staff_name not in staff_data:
            staff_data[a.staff_name] = {"name": a.staff_name, "days": {}}
        staff_data[a.staff_name]["days"][str(a.day_of_week)] = {
            "id": a.id, "text": a.display_text(), "status": a.status,
            "location": a.location_code, "shift": a.shift_label,
            "staff_id": a.staff_id, "day_of_week": a.day_of_week, "day_date": a.day_date
        }
    return jsonify({"staff": sorted(staff_data.values(), key=lambda x: x["name"]), "days": DAYS_SHORT})


@app.route("/api/schedule/<int:schedule_id>/by-location")
def api_schedule_by_location(schedule_id):
    assignments = db.get_schedule_assignments(schedule_id)
    locations = db.get_all_locations()
    loc_data = {}
    for loc in locations:
        loc_data[loc.short_code] = {"name": loc.name, "code": loc.short_code,
                                     "min": loc.min_staff, "max": loc.max_staff, "days": {}}
        for d in range(7):
            loc_data[loc.short_code]["days"][str(d)] = []

    for a in assignments:
        if a.status == "assigned" and a.location_code and a.location_code in loc_data:
            loc_data[a.location_code]["days"][str(a.day_of_week)].append({
                "staff_name": a.staff_name, "shift": a.shift_label, "id": a.id
            })
    return jsonify({"locations": list(loc_data.values()), "days": DAYS_SHORT})


@app.route("/api/schedule/generate", methods=["POST"])
def api_generate():
    data = request.json
    date_str = data.get("week_start", "")
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        if dt.weekday() != 5:
            days_back = (dt.weekday() - 5) % 7
            dt = dt - timedelta(days=days_back)
            date_str = dt.strftime("%Y-%m-%d")
        sid = generate_schedule(date_str)
        conflicts = db.detect_conflicts(sid)
        return jsonify({"success": True, "schedule_id": sid, "week_start": date_str, "conflicts": conflicts})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/schedule/<int:schedule_id>/copy", methods=["POST"])
def api_copy_schedule(schedule_id):
    data = request.json
    new_start = data.get("week_start", "")
    try:
        new_id = db.copy_schedule(schedule_id, new_start)
        return jsonify({"success": True, "schedule_id": new_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/schedule/<int:schedule_id>/delete", methods=["DELETE"])
def api_delete_schedule(schedule_id):
    db.delete_schedule(schedule_id)
    return jsonify({"success": True})


@app.route("/api/schedule/<int:schedule_id>/conflicts")
def api_conflicts(schedule_id):
    return jsonify(db.detect_conflicts(schedule_id))


@app.route("/api/schedule/<int:schedule_id>/pdf")
def api_export_pdf(schedule_id):
    filepath = os.path.join(db.DB_DIR, f"schedule_{schedule_id}.pdf")
    export_schedule_pdf(schedule_id, filepath)
    return send_file(filepath, as_attachment=True, download_name=f"schedule_{schedule_id}.pdf")


@app.route("/api/schedule/<int:schedule_id>/excel")
def api_export_excel(schedule_id):
    filepath = os.path.join(db.DB_DIR, f"schedule_{schedule_id}.xlsx")
    export_schedule_excel(schedule_id, filepath)
    return send_file(filepath, as_attachment=True, download_name=f"schedule_{schedule_id}.xlsx")


@app.route("/api/schedule/<int:schedule_id>/messages")
def api_messages(schedule_id):
    schedule = None
    for s in db.get_all_schedules():
        if s.id == schedule_id:
            schedule = s
            break
    if not schedule:
        return jsonify({"messages": []})

    assignments = db.get_schedule_assignments(schedule_id)
    staff_data = {}
    for a in assignments:
        if a.staff_name not in staff_data:
            staff_data[a.staff_name] = [""] * 7
        staff_data[a.staff_name][a.day_of_week] = a.display_text()

    business = db.get_setting("business_name", DEFAULT_BUSINESS_NAME)
    messages = []
    for name in sorted(staff_data.keys()):
        lines = [f"Hi {name}! Your schedule for {schedule.week_start} to {schedule.week_end}:"]
        for i, day in enumerate(DAYS_SHORT):
            lines.append(f"{day}: {staff_data[name][i] or '-'}")
        lines.append(f"- {business}")
        messages.append({"staff_name": name, "text": "\n".join(lines)})
    return jsonify({"messages": messages})


@app.route("/api/schedule/<int:schedule_id>/history")
def api_history(schedule_id):
    return jsonify(db.get_assignment_history(schedule_id))


@app.route("/api/schedule/compare")
def api_compare():
    a = request.args.get("a", type=int)
    b = request.args.get("b", type=int)
    if not a or not b:
        return jsonify([])
    return jsonify(db.compare_schedules(a, b))


# ==================== ASSIGNMENT API ====================

@app.route("/api/assignment/<int:assignment_id>/update", methods=["POST"])
def api_update_assignment(assignment_id):
    data = request.json
    db.update_assignment(assignment_id, data.get("status", "assigned"),
                         data.get("location_id"), data.get("shift_id"))
    return jsonify({"success": True})


# ==================== STAFF API ====================

@app.route("/api/staff")
def api_staff():
    return jsonify([{
        "id": s.id, "name": s.name, "is_active": s.is_active,
        "default_location": s.default_location or "",
        "default_role": s.default_role or "",
        "shift_preference": s.shift_preference or "Any",
        "staff_tag": s.staff_tag or "regular",
        "overtime_max_hours": s.overtime_max_hours or 45
    } for s in db.get_all_staff(active_only=False)])


@app.route("/api/staff/add", methods=["POST"])
def api_add_staff():
    data = request.json
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"success": False, "error": "Name required"}), 400
    try:
        sid = db.add_staff(name, data.get("default_location") or None,
                           data.get("default_role") or None,
                           data.get("shift_preference", "Any"),
                           data.get("staff_tag", "regular"),
                           data.get("overtime_max_hours", 45))
        return jsonify({"success": True, "id": sid})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/staff/<int:staff_id>/update", methods=["POST"])
def api_update_staff(staff_id):
    data = request.json
    db.update_staff(staff_id, data.get("name", "").strip(),
                    data.get("default_location") or None,
                    data.get("default_role") or None,
                    data.get("is_active", True),
                    data.get("shift_preference", "Any"),
                    data.get("staff_tag", "regular"),
                    data.get("overtime_max_hours", 45))
    return jsonify({"success": True})


@app.route("/api/staff/<int:staff_id>/delete", methods=["DELETE"])
def api_delete_staff(staff_id):
    db.delete_staff(staff_id)
    return jsonify({"success": True})


@app.route("/api/staff/<int:staff_id>/leave-balance")
def api_leave_balance(staff_id):
    bal = db.get_staff_leave_balance(staff_id)
    return jsonify(bal) if bal else jsonify({}), 404


# ==================== AVAILABILITY API ====================

@app.route("/api/staff/<int:staff_id>/availability", methods=["GET", "POST"])
def api_availability(staff_id):
    if request.method == "POST":
        data = request.json
        for date in data.get("dates", []):
            db.set_availability(staff_id, date, data.get("is_available", False),
                               data.get("reason", ""))
        return jsonify({"success": True})
    else:
        ws = request.args.get("week_start", "")
        we = request.args.get("week_end", "")
        return jsonify(db.get_staff_availability(staff_id, ws, we))


# ==================== LEAVE API ====================

@app.route("/api/leave", methods=["GET", "POST"])
def api_leave():
    if request.method == "POST":
        data = request.json
        lid = db.create_leave_request(data["staff_id"], data["start_date"], data["end_date"],
                                       data.get("leave_type", "annual"), data.get("reason", ""))
        return jsonify({"success": True, "id": lid})
    else:
        staff_id = request.args.get("staff_id", type=int)
        status = request.args.get("status")
        return jsonify(db.get_leave_requests(staff_id, status))


@app.route("/api/leave/<int:request_id>/approve", methods=["POST"])
def api_approve_leave(request_id):
    db.update_leave_status(request_id, "approved")
    return jsonify({"success": True})


@app.route("/api/leave/<int:request_id>/reject", methods=["POST"])
def api_reject_leave(request_id):
    db.update_leave_status(request_id, "rejected")
    return jsonify({"success": True})


# ==================== SWAP API ====================

@app.route("/api/swaps", methods=["GET", "POST"])
def api_swaps():
    if request.method == "POST":
        data = request.json
        sid = db.create_swap_request(data["schedule_id"], data["requester_staff_id"],
                                      data["target_staff_id"], data["requester_date"],
                                      data["target_date"])
        return jsonify({"success": True, "id": sid})
    else:
        schedule_id = request.args.get("schedule_id", type=int)
        status = request.args.get("status")
        return jsonify(db.get_swap_requests(schedule_id, status))


@app.route("/api/swap/<int:request_id>/approve", methods=["POST"])
def api_approve_swap(request_id):
    db.approve_swap(request_id)
    return jsonify({"success": True})


@app.route("/api/swap/<int:request_id>/reject", methods=["POST"])
def api_reject_swap(request_id):
    db.reject_swap(request_id)
    return jsonify({"success": True})


# ==================== LOCATIONS API ====================

@app.route("/api/locations")
def api_locations():
    return jsonify([{
        "id": l.id, "name": l.name, "short_code": l.short_code,
        "min_staff": l.min_staff, "max_staff": l.max_staff, "is_active": l.is_active
    } for l in db.get_all_locations(active_only=False)])


@app.route("/api/location/add", methods=["POST"])
def api_add_location():
    data = request.json
    try:
        lid = db.add_location(data["name"], data["short_code"],
                               data.get("min_staff", 1), data.get("max_staff", 3))
        return jsonify({"success": True, "id": lid})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/location/<int:loc_id>/update", methods=["POST"])
def api_update_location(loc_id):
    data = request.json
    db.update_location(loc_id, data["name"], data["short_code"],
                       data.get("min_staff", 1), data.get("max_staff", 3),
                       data.get("is_active", True))
    return jsonify({"success": True})


@app.route("/api/location/<int:loc_id>/delete", methods=["DELETE"])
def api_delete_location(loc_id):
    db.delete_location(loc_id)
    return jsonify({"success": True})


# ==================== SHIFTS API ====================

@app.route("/api/shifts")
def api_shifts():
    return jsonify([{"id": s.id, "label": s.label, "start_time": s.start_time, "end_time": s.end_time}
                    for s in db.get_all_shifts(active_only=False)])


@app.route("/api/shift/add", methods=["POST"])
def api_add_shift():
    data = request.json
    label = (data.get("label") or "").strip()
    if not label:
        return jsonify({"success": False, "error": "Label required"}), 400
    try:
        sid = db.add_shift(label, data.get("start_time", ""), data.get("end_time", ""))
        return jsonify({"success": True, "id": sid})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/shift/<int:shift_id>/update", methods=["POST"])
def api_update_shift(shift_id):
    data = request.json
    label = (data.get("label") or "").strip()
    if not label:
        return jsonify({"success": False, "error": "Label required"}), 400
    try:
        db.update_shift(shift_id, label, data.get("start_time", ""),
                        data.get("end_time", ""), data.get("is_active", True))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/shift/<int:shift_id>/delete", methods=["DELETE"])
def api_delete_shift(shift_id):
    db.delete_shift(shift_id)
    return jsonify({"success": True})


# ==================== ADMIN / DATA API ====================

@app.route("/api/admin/clear-all", methods=["POST"])
def api_clear_all():
    db.clear_all_data()
    return jsonify({"success": True})


@app.route("/api/admin/load-sample", methods=["POST"])
def api_load_sample():
    """Populate the original Finland setup: default locations, shifts and staff."""
    try:
        db.seed_defaults()
        excel_path = get_sample_excel_path()
        imported = False
        if os.path.exists(excel_path):
            import_excel(excel_path)
            imported = True
        return jsonify({"success": True, "imported_staff": imported})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/admin/info")
def api_admin_info():
    """Report where the database file lives so the user can confirm it's saved."""
    path = db.DB_PATH
    exists = os.path.exists(path)
    return jsonify({
        "db_path": path,
        "exists": exists,
        "size": os.path.getsize(path) if exists else 0,
        "version": APP_VERSION,
    })


@app.route("/api/admin/backup")
def api_admin_backup():
    """Download a copy of the database file as a backup."""
    if not os.path.exists(db.DB_PATH):
        return jsonify({"success": False, "error": "No data saved yet"}), 404
    return send_file(db.DB_PATH, as_attachment=True,
                     download_name="finland_schedule_backup.db")


DEFAULT_BUSINESS_NAME = "Finland Optical"


@app.route("/api/admin/check-update")
def api_check_update():
    from . import updater
    return jsonify(updater.check_for_update())


@app.route("/api/admin/download-update", methods=["POST"])
def api_download_update():
    from . import updater
    data = request.json or {}
    url = data.get("download_url") or ""
    if not url:
        # fall back to whatever the manifest currently advertises
        url = updater.check_for_update().get("download_url", "")
    try:
        path = updater.download_and_open(url)
        return jsonify({"success": True, "path": path})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/settings")
def api_get_settings():
    return jsonify({
        "business_name": db.get_setting("business_name", DEFAULT_BUSINESS_NAME),
    })


@app.route("/api/settings", methods=["POST"])
def api_set_settings():
    data = request.json or {}
    if "business_name" in data:
        name = (data.get("business_name") or "").strip() or DEFAULT_BUSINESS_NAME
        db.set_setting("business_name", name)
    return jsonify({"success": True,
                    "business_name": db.get_setting("business_name", DEFAULT_BUSINESS_NAME)})


# ==================== DASHBOARD API ====================

@app.route("/api/dashboard/stats")
def api_dashboard_stats():
    schedule_id = request.args.get("schedule_id", type=int)
    if not schedule_id:
        return jsonify({})
    return jsonify(db.get_dashboard_stats(schedule_id))


@app.route("/api/fairness")
def api_fairness():
    period = request.args.get("period", "")
    if not period:
        period = datetime.now().strftime("%Y-%m")
    return jsonify(db.get_fairness_report(period))


@app.route("/api/reports/monthly")
def api_monthly_report():
    month = request.args.get("month", "")
    if not month:
        month = datetime.now().strftime("%Y-%m")
    return jsonify(db.get_monthly_report(month))


@app.route("/api/schedule/optimize", methods=["POST"])
def api_optimize():
    """Auto-optimize: generate multiple schedules, pick the one with best coverage and fewest conflicts."""
    data = request.json
    date_str = data.get("week_start", "")
    iterations = min(data.get("iterations", 5), 10)

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        if dt.weekday() != 5:
            days_back = (dt.weekday() - 5) % 7
            dt = dt - timedelta(days=days_back)
            date_str = dt.strftime("%Y-%m-%d")

        best_id = None
        best_score = -1

        for _ in range(iterations):
            sid = generate_schedule(date_str, notes="Auto-optimized")
            stats = db.get_dashboard_stats(sid)
            conflicts = db.detect_conflicts(sid)
            score = stats.get("coverage_score", 0) - len(conflicts) * 5

            if score > best_score:
                # Delete previous best if exists
                if best_id is not None:
                    db.delete_schedule(best_id)
                best_id = sid
                best_score = score
            else:
                db.delete_schedule(sid)

        conflicts = db.detect_conflicts(best_id)
        stats = db.get_dashboard_stats(best_id)
        return jsonify({
            "success": True, "schedule_id": best_id, "week_start": date_str,
            "score": best_score, "coverage": stats.get("coverage_score", 0),
            "conflicts": len(conflicts), "iterations": iterations
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
