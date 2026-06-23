"""Dialog windows for editing assignments and adding entities."""

import tkinter as tk
from tkinter import ttk
from .. import database as db


class EditAssignmentDialog(tk.Toplevel):
    """Dialog to edit a single schedule assignment."""

    def __init__(self, parent, assignment, on_save=None):
        super().__init__(parent)
        self.title("Edit Assignment")
        self.geometry("350x280")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.assignment = assignment
        self.on_save = on_save
        self.result = None

        locations = db.get_all_locations()
        shifts = db.get_all_shifts()

        # Staff name (read-only)
        ttk.Label(self, text=f"Staff: {assignment.staff_name}", font=("Helvetica", 12, "bold")).pack(pady=(15, 5))
        ttk.Label(self, text=f"Day: {assignment.day_date}").pack(pady=(0, 10))

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="x", padx=20)

        # Status
        ttk.Label(frame, text="Status:").grid(row=0, column=0, sticky="w", pady=5)
        self.status_var = tk.StringVar(value=assignment.status)
        status_combo = ttk.Combobox(frame, textvariable=self.status_var,
                                     values=["assigned", "off", "leave"], state="readonly", width=20)
        status_combo.grid(row=0, column=1, pady=5, padx=(10, 0))
        status_combo.bind("<<ComboboxSelected>>", self._on_status_change)

        # Location
        ttk.Label(frame, text="Location:").grid(row=1, column=0, sticky="w", pady=5)
        self.loc_names = [""] + [l.short_code for l in locations]
        self.loc_ids = [None] + [l.id for l in locations]
        current_loc = ""
        if assignment.location_code:
            current_loc = assignment.location_code
        self.loc_var = tk.StringVar(value=current_loc)
        self.loc_combo = ttk.Combobox(frame, textvariable=self.loc_var,
                                       values=self.loc_names, state="readonly", width=20)
        self.loc_combo.grid(row=1, column=1, pady=5, padx=(10, 0))

        # Shift
        ttk.Label(frame, text="Shift:").grid(row=2, column=0, sticky="w", pady=5)
        self.shift_labels = [""] + [s.label for s in shifts]
        self.shift_ids = [None] + [s.id for s in shifts]
        current_shift = assignment.shift_label or ""
        self.shift_var = tk.StringVar(value=current_shift)
        self.shift_combo = ttk.Combobox(frame, textvariable=self.shift_var,
                                         values=self.shift_labels, state="readonly", width=20)
        self.shift_combo.grid(row=2, column=1, pady=5, padx=(10, 0))

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Save", command=self._save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=5)

        self._on_status_change()

    def _on_status_change(self, event=None):
        status = self.status_var.get()
        state = "readonly" if status == "assigned" else "disabled"
        self.loc_combo.config(state=state)
        self.shift_combo.config(state=state)

    def _save(self):
        status = self.status_var.get()
        loc_id = None
        shift_id = None

        if status == "assigned":
            loc_name = self.loc_var.get()
            if loc_name in self.loc_names:
                idx = self.loc_names.index(loc_name)
                loc_id = self.loc_ids[idx]

            shift_name = self.shift_var.get()
            if shift_name in self.shift_labels:
                idx = self.shift_labels.index(shift_name)
                shift_id = self.shift_ids[idx]

        db.update_assignment(self.assignment.id, status, loc_id, shift_id)

        if self.on_save:
            self.on_save()
        self.destroy()


class AddStaffDialog(tk.Toplevel):
    """Dialog to add or edit a staff member."""

    def __init__(self, parent, staff=None, on_save=None):
        super().__init__(parent)
        self.title("Edit Staff" if staff else "Add Staff")
        self.geometry("350x250")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.staff = staff
        self.on_save = on_save

        locations = db.get_all_locations()

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)

        # Name
        ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky="w", pady=5)
        self.name_var = tk.StringVar(value=staff.name if staff else "")
        ttk.Entry(frame, textvariable=self.name_var, width=25).grid(row=0, column=1, pady=5, padx=(10, 0))

        # Default Location
        ttk.Label(frame, text="Fixed Location:").grid(row=1, column=0, sticky="w", pady=5)
        loc_options = ["None"] + [l.name for l in locations]
        current_loc = staff.default_location if staff and staff.default_location else "None"
        self.loc_var = tk.StringVar(value=current_loc)
        ttk.Combobox(frame, textvariable=self.loc_var, values=loc_options,
                     state="readonly", width=22).grid(row=1, column=1, pady=5, padx=(10, 0))

        # Default Role
        ttk.Label(frame, text="Fixed Role:").grid(row=2, column=0, sticky="w", pady=5)
        role_options = ["None", "Clinic", "Office"]
        current_role = staff.default_role if staff and staff.default_role else "None"
        self.role_var = tk.StringVar(value=current_role)
        ttk.Combobox(frame, textvariable=self.role_var, values=role_options,
                     state="readonly", width=22).grid(row=2, column=1, pady=5, padx=(10, 0))

        # Active
        self.active_var = tk.BooleanVar(value=staff.is_active if staff else True)
        ttk.Checkbutton(frame, text="Active", variable=self.active_var).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=5)

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Save", command=self._save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=5)

    def _save(self):
        name = self.name_var.get().strip()
        if not name:
            return

        loc = self.loc_var.get()
        role = self.role_var.get()
        default_loc = loc if loc != "None" else None
        default_role = role if role != "None" else None
        active = self.active_var.get()

        if self.staff:
            db.update_staff(self.staff.id, name, default_loc, default_role, active)
        else:
            db.add_staff(name, default_loc, default_role)

        if self.on_save:
            self.on_save()
        self.destroy()


class AddLocationDialog(tk.Toplevel):
    """Dialog to add or edit a location."""

    def __init__(self, parent, location=None, on_save=None):
        super().__init__(parent)
        self.title("Edit Location" if location else "Add Location")
        self.geometry("350x250")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.location = location
        self.on_save = on_save

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)

        # Name
        ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky="w", pady=5)
        self.name_var = tk.StringVar(value=location.name if location else "")
        ttk.Entry(frame, textvariable=self.name_var, width=25).grid(row=0, column=1, pady=5, padx=(10, 0))

        # Short Code
        ttk.Label(frame, text="Short Code:").grid(row=1, column=0, sticky="w", pady=5)
        self.code_var = tk.StringVar(value=location.short_code if location else "")
        ttk.Entry(frame, textvariable=self.code_var, width=25).grid(row=1, column=1, pady=5, padx=(10, 0))

        # Min Staff
        ttk.Label(frame, text="Min Staff:").grid(row=2, column=0, sticky="w", pady=5)
        self.min_var = tk.IntVar(value=location.min_staff if location else 1)
        ttk.Spinbox(frame, from_=0, to=10, textvariable=self.min_var, width=5).grid(
            row=2, column=1, sticky="w", pady=5, padx=(10, 0))

        # Max Staff
        ttk.Label(frame, text="Max Staff:").grid(row=3, column=0, sticky="w", pady=5)
        self.max_var = tk.IntVar(value=location.max_staff if location else 3)
        ttk.Spinbox(frame, from_=1, to=10, textvariable=self.max_var, width=5).grid(
            row=3, column=1, sticky="w", pady=5, padx=(10, 0))

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Save", command=self._save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=5)

    def _save(self):
        name = self.name_var.get().strip()
        code = self.code_var.get().strip()
        if not name or not code:
            return

        min_s = self.min_var.get()
        max_s = self.max_var.get()

        if self.location:
            db.update_location(self.location.id, name, code, min_s, max_s)
        else:
            db.add_location(name, code, min_s, max_s)

        if self.on_save:
            self.on_save()
        self.destroy()
