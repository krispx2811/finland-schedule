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


# Saturday (0) and Friday (6): only one Salesman works, everyone else is OFF.
WEEKEND_DAYS = (0, 6)


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

    unavailable_by_day = {}
    leave_by_day = {}
    for i, date in enumerate(dates):
        unavailable_by_day[i] = set(db.get_unavailable_staff(date))
        leave_by_day[i] = set(db.get_approved_leave_for_date(date))

    loc_by_name = {l.name: l for l in locations}
    loc_by_code = {l.short_code: l for l in locations}
    rotation_shifts = list(shifts)

    fixed_staff = [s for s in staff_list if s.default_location or s.default_role]
    rotating_staff = [s for s in staff_list if not (s.default_location or s.default_role)]

    fixed_loc_keys = set()
    for s in fixed_staff:
        key = s.default_location or s.default_role
        if key:
            fixed_loc_keys.add(key)
    rotation_locations = [l for l in locations
                          if l.name not in fixed_loc_keys and l.short_code not in fixed_loc_keys]
    if not rotation_locations:
        rotation_locations = list(locations)

    def shift_id_for(s):
        sh = get_preferred_shift(s, rotation_shifts) if rotation_shifts else None
        return sh.id if sh else None

    def fixed_loc_id(s):
        loc = (loc_by_name.get(s.default_location or s.default_role)
               or loc_by_code.get(s.default_location or s.default_role))
        return loc.id if loc else None

    # Salesmen who can cover the weekend (Sat/Fri). Pick the one who has worked the
    # FEWEST weekend shifts so far, so it rotates fairly and never doubles up.
    salesmen = [s for s in staff_list if (s.staff_tag or "").strip().lower() == "salesman"]
    random.shuffle(salesmen)  # random tie-break among equally-loaded salesmen
    weekend_load = db.get_weekend_work_counts()

    # Optional fixed shift for the Friday salesman (set in Settings → Scheduling).
    shift_by_label = {s.label: s for s in shifts}
    friday_shift = shift_by_label.get((db.get_setting("friday_shift", "") or "").strip())

    for day_idx in range(7):
        date = dates[day_idx]

        # ---- Weekend: only one salesman works, the rest are OFF ----
        if day_idx in WEEKEND_DAYS:
            avail = [s for s in salesmen
                     if s.id not in leave_by_day[day_idx] and s.id not in unavailable_by_day[day_idx]]
            chosen = min(avail, key=lambda s: weekend_load.get(s.id, 0)) if avail else None
            if chosen:
                # count it now so the other weekend day picks a different salesman
                weekend_load[chosen.id] = weekend_load.get(chosen.id, 0) + 1
            for s in staff_list:
                if s.id in leave_by_day[day_idx]:
                    db.add_assignment(schedule_id, s.id, day_idx, date, "leave")
                elif chosen and s.id == chosen.id:
                    loc_id = fixed_loc_id(s) or (rotation_locations[0].id if rotation_locations else None)
                    # Friday uses the configured Friday shift (if set); Saturday uses preference.
                    wsid = friday_shift.id if (day_idx == 6 and friday_shift) else shift_id_for(s)
                    db.add_assignment(schedule_id, s.id, day_idx, date, "assigned", loc_id, wsid)
                else:
                    db.add_assignment(schedule_id, s.id, day_idx, date, "off")
            continue

        # ---- Weekday (Sun–Thu): everyone available works ----
        # Fixed staff go to their location.
        for s in fixed_staff:
            if s.id in leave_by_day[day_idx]:
                db.add_assignment(schedule_id, s.id, day_idx, date, "leave")
            elif s.id in unavailable_by_day[day_idx]:
                db.add_assignment(schedule_id, s.id, day_idx, date, "off")
            else:
                db.add_assignment(schedule_id, s.id, day_idx, date, "assigned",
                                  fixed_loc_id(s), shift_id_for(s))

        # Rotating staff: leave/off where applicable, otherwise distribute across locations.
        for s in rotating_staff:
            if s.id in leave_by_day[day_idx]:
                db.add_assignment(schedule_id, s.id, day_idx, date, "leave")
            elif s.id in unavailable_by_day[day_idx]:
                db.add_assignment(schedule_id, s.id, day_idx, date, "off")

        available = [s for s in rotating_staff
                     if s.id not in leave_by_day[day_idx] and s.id not in unavailable_by_day[day_idx]]
        random.shuffle(available)

        location_assignments = {loc.id: [] for loc in rotation_locations}
        queue = list(available)
        for loc in rotation_locations:
            for _ in range(loc.min_staff):
                if queue:
                    location_assignments[loc.id].append(queue.pop(0))
        for loc in rotation_locations:
            while len(location_assignments[loc.id]) < loc.max_staff and queue:
                location_assignments[loc.id].append(queue.pop(0))
        while queue:
            s = queue.pop(0)
            best = min(rotation_locations,
                       key=lambda l: len(location_assignments[l.id]) / max(l.max_staff, 1))
            location_assignments[best.id].append(s)

        for loc in rotation_locations:
            for s in location_assignments[loc.id]:
                db.add_assignment(schedule_id, s.id, day_idx, date, "assigned", loc.id, shift_id_for(s))

    db.update_fairness_stats(schedule_id)
    return schedule_id
