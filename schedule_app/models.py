"""Data classes for the schedule application."""

from dataclasses import dataclass, field
from typing import Optional


SHIFT_PREFERENCES = ["Any", "Morning", "Evening", "Night"]
# Morning = 1-10, 2-11, 3-12  (early shifts)
# Evening = 10-7, 11:30-8:30  (mid-day shifts)
# Night   = 12-9              (late shifts)


@dataclass
class Staff:
    id: int = 0
    name: str = ""
    is_active: bool = True
    default_location: Optional[str] = None  # e.g., "Salalah" for fixed staff
    default_role: Optional[str] = None       # e.g., "Clinic", "Office"
    shift_preference: str = "Any"            # Any, Morning, Evening, Night
    staff_tag: str = "regular"               # regular, senior, trainee
    overtime_max_hours: float = 45           # max weekly hours before overtime warning


@dataclass
class Location:
    id: int = 0
    name: str = ""
    short_code: str = ""
    min_staff: int = 1
    max_staff: int = 3
    is_active: bool = True


@dataclass
class Shift:
    id: int = 0
    label: str = ""        # e.g., "10-7"
    start_time: str = ""   # e.g., "10:00"
    end_time: str = ""     # e.g., "19:00"
    is_active: bool = True


@dataclass
class Schedule:
    id: int = 0
    week_start: str = ""   # ISO date YYYY-MM-DD (Saturday)
    week_end: str = ""     # ISO date (Friday)
    created_at: str = ""
    notes: str = ""


@dataclass
class Assignment:
    id: int = 0
    schedule_id: int = 0
    staff_id: int = 0
    day_of_week: int = 0     # 0=Saturday, 6=Friday
    day_date: str = ""       # YYYY-MM-DD
    status: str = "assigned" # assigned, off, leave
    location_id: Optional[int] = None
    shift_id: Optional[int] = None
    # Denormalized fields for display
    staff_name: str = ""
    location_code: str = ""
    shift_label: str = ""

    def display_text(self) -> str:
        if self.status == "off":
            return "OFF"
        elif self.status == "leave":
            return "Leave"
        elif self.location_code in ("Clinic", "Office", "SALALAH", "NIZWA"):
            return self.location_code
        elif self.shift_label and self.location_code:
            return f"{self.shift_label} {self.location_code}"
        elif self.location_code:
            return self.location_code
        return ""
