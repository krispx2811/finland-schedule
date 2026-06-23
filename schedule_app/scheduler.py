"""Auto-generate weekly schedules with constraint-based assignment."""

import random
from datetime import datetime, timedelta
from . import database as db


PREFERENCE_SHIFTS = {
    "Morning": ["10-7", "11:30-8:30"],          # Opens at 10am
    "Evening": ["12-9", "1-10"],                 # Mid-day to closing
    "Night":   ["2-11", "3-12"],                 # Late shifts (Thu/Fri only)
}


def get_preferred_shift(staff, available_shifts):
    pref = getattr(staff, 'shift_preference', 'Any') or 'Any'
    if not pref.strip() or pref == "Any":
        return random.choice(available_shifts)
    # Preference may be several shifts, comma-separated (e.g. "Morning,Evening").
    wanted = set()
    for token in pref.split(","):
        token = token.strip()
        if not token:
            continue
        wanted.add(token)                       # exact shift label
        wanted.update(PREFERENCE_SHIFTS.get(token, []))  # legacy category expansion
    matching = [s for s in available_shifts if s.label in wanted]
    return random.choice(matching) if matching else random.choice(available_shifts)


def generate_schedule(week_start_str, notes="", use_fairness=True):
    week_start = datetime.strptime(week_start_str, "%Y-%m-%d")
    week_end = week_start + timedelta(days=6)
    dates = [(week_start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

    schedule_id = db.create_schedule(week_start_str, week_end.strftime("%Y-%m-%d"), notes)

    staff_list = db.get_all_staff(active_only=True)
    locations = db.get_all_locations(active_only=True)
    shifts = db.get_all_shifts(active_only=True)
    if not staff_list or not locations or not shifts:
        return schedule_id

    # Get availability and leave data for the week
    unavailable_by_day = {}
    leave_by_day = {}
    for i, date in enumerate(dates):
        unavailable_by_day[i] = set(db.get_unavailable_staff(date))
        leave_by_day[i] = set(db.get_approved_leave_for_date(date))

    # Get fairness stats for weighted OFF assignment
    fairness = db.get_fairness_for_scheduler() if use_fairness else {}

    # Separate staff
    fixed_staff = [s for s in staff_list if s.default_location or s.default_role]
    rotating_staff = [s for s in staff_list if not s.default_location and not s.default_role]

    loc_by_name = {l.name: l for l in locations}
    loc_by_code = {l.short_code: l for l in locations}
    # Use every shift the user has defined — no hard-coded shift labels.
    rotation_shifts = list(shifts)
    # Rotating staff go to any location that isn't reserved for a fixed staff member.
    fixed_loc_keys = set()
    for s in fixed_staff:
        key = s.default_location or s.default_role
        if key:
            fixed_loc_keys.add(key)
    rotation_locations = [l for l in locations
                          if l.name not in fixed_loc_keys and l.short_code not in fixed_loc_keys]
    if not rotation_locations:
        rotation_locations = list(locations)

    # Phase 1: Fixed assignments
    for s in fixed_staff:
        loc_name = s.default_location or s.default_role
        loc = loc_by_name.get(loc_name) or loc_by_code.get(loc_name)
        loc_id = loc.id if loc else None
        for day_idx in range(7):
            if s.id in leave_by_day[day_idx]:
                db.add_assignment(schedule_id, s.id, day_idx, dates[day_idx], "leave")
            elif day_idx == 6 and s.default_role:
                db.add_assignment(schedule_id, s.id, day_idx, dates[day_idx], "off")
            else:
                # Fixed staff also get a (preferred) shift, not just a location.
                shift = get_preferred_shift(s, rotation_shifts) if rotation_shifts else None
                db.add_assignment(schedule_id, s.id, day_idx, dates[day_idx],
                                  "assigned", loc_id, shift.id if shift else None)

    # Phase 2: OFF days with fairness weighting
    off_assignments = {}
    day_off_counts = [0] * 7

    # Staff on leave get those days as leave (not counted as regular OFF)
    staff_leave_days = {}
    for s in rotating_staff:
        leave_days = [d for d in range(7) if s.id in leave_by_day[d]]
        unavail_days = [d for d in range(7) if s.id in unavailable_by_day[d] and d not in leave_days]
        staff_leave_days[s.id] = {"leave": leave_days, "unavailable": unavail_days}

    shuffled = list(rotating_staff)
    if use_fairness and fairness:
        # Sort so staff with MORE Fridays worked get priority for Friday OFF
        shuffled.sort(key=lambda s: fairness.get(s.id, {}).get("friday", 0), reverse=True)
    else:
        random.shuffle(shuffled)

    for s in shuffled:
        info = staff_leave_days[s.id]
        # If unavailable on specific days, use that as their OFF day
        if info["unavailable"]:
            off_assignments[s.id] = info["unavailable"][0]
            day_off_counts[info["unavailable"][0]] += 1
        else:
            # Weighted: prefer giving Friday (6) off to those who worked more Fridays
            best_day = min(range(7), key=lambda d: day_off_counts[d])
            off_assignments[s.id] = best_day
            day_off_counts[best_day] += 1

    # Phase 3: Assign staff to locations per day
    for day_idx in range(7):
        for s in rotating_staff:
            info = staff_leave_days[s.id]
            if day_idx in info["leave"]:
                db.add_assignment(schedule_id, s.id, day_idx, dates[day_idx], "leave")
            elif off_assignments.get(s.id) == day_idx:
                db.add_assignment(schedule_id, s.id, day_idx, dates[day_idx], "off")

        available = [s for s in rotating_staff
                     if off_assignments.get(s.id) != day_idx
                     and day_idx not in staff_leave_days[s.id]["leave"]
                     and s.id not in unavailable_by_day[day_idx]]

        random.shuffle(available)
        location_assignments = {loc.id: [] for loc in rotation_locations}
        staff_queue = list(available)

        for loc in rotation_locations:
            for _ in range(loc.min_staff):
                if staff_queue:
                    location_assignments[loc.id].append(staff_queue.pop(0))

        for loc in rotation_locations:
            current = len(location_assignments[loc.id])
            while current < loc.max_staff and staff_queue:
                location_assignments[loc.id].append(staff_queue.pop(0))
                current += 1

        while staff_queue:
            s = staff_queue.pop(0)
            best_loc = min(rotation_locations,
                          key=lambda l: len(location_assignments[l.id]) / max(l.max_staff, 1))
            location_assignments[best_loc.id].append(s)

        # Phase 4: Assign shifts. Every shift the user defined is eligible each day.
        for loc in rotation_locations:
            if not location_assignments[loc.id]:
                continue
            day_shifts = rotation_shifts
            if not day_shifts:
                continue

            for staff_member in location_assignments[loc.id]:
                shift = get_preferred_shift(staff_member, day_shifts)
                db.add_assignment(schedule_id, staff_member.id, day_idx, dates[day_idx],
                                 "assigned", loc.id, shift.id)

    # Update fairness stats
    db.update_fairness_stats(schedule_id)

    return schedule_id
