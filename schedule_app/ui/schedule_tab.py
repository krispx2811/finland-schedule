"""Schedule view and editing tab."""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta

from .. import database as db
from ..scheduler import generate_schedule
from ..pdf_export import export_schedule_pdf
from ..config import DAYS_SHORT
from .styles import CELL_COLORS
from .dialogs import EditAssignmentDialog


class ScheduleTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.current_schedule_id = None
        self.assignments_map = {}  # (staff_name, day_idx) -> Assignment
        self._build_ui()
        self._load_latest_schedule()

    def _build_ui(self):
        # Top bar
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=(10, 5))

        ttk.Label(top, text="Schedule", font=("Helvetica", 14, "bold")).pack(side="left")

        # Week selector
        ctrl = ttk.Frame(self)
        ctrl.pack(fill="x", padx=10, pady=5)

        ttk.Label(ctrl, text="Week starting (Saturday):").pack(side="left")

        # Default to next Saturday
        today = datetime.today()
        days_until_sat = (5 - today.weekday()) % 7
        if days_until_sat == 0 and today.weekday() != 5:
            days_until_sat = 7
        next_sat = today + timedelta(days=days_until_sat)
        # If today is Saturday, use today
        if today.weekday() == 5:
            next_sat = today

        self.date_var = tk.StringVar(value=next_sat.strftime("%Y-%m-%d"))
        date_entry = ttk.Entry(ctrl, textvariable=self.date_var, width=12)
        date_entry.pack(side="left", padx=5)

        ttk.Button(ctrl, text="Generate Schedule", command=self._generate).pack(side="left", padx=5)
        ttk.Button(ctrl, text="Export PDF", command=self._export_pdf).pack(side="left", padx=5)

        # Existing schedules dropdown
        ttk.Label(ctrl, text="  Load:").pack(side="left", padx=(15, 2))
        self.sched_var = tk.StringVar()
        self.sched_combo = ttk.Combobox(ctrl, textvariable=self.sched_var, state="readonly", width=25)
        self.sched_combo.pack(side="left", padx=2)
        self.sched_combo.bind("<<ComboboxSelected>>", self._on_schedule_selected)
        ttk.Button(ctrl, text="Delete", command=self._delete_schedule).pack(side="left", padx=5)

        # Schedule grid
        grid_frame = ttk.Frame(self)
        grid_frame.pack(fill="both", expand=True, padx=10, pady=5)

        columns = tuple(DAYS_SHORT)
        self.tree = ttk.Treeview(grid_frame, columns=columns, show="tree headings", height=24)
        self.tree.heading("#0", text="Staff", anchor="w")
        self.tree.column("#0", width=120, minwidth=100)

        for day in DAYS_SHORT:
            self.tree.heading(day, text=day, anchor="center")
            self.tree.column(day, width=110, anchor="center", minwidth=80)

        v_scroll = ttk.Scrollbar(grid_frame, orient="vertical", command=self.tree.yview)
        h_scroll = ttk.Scrollbar(grid_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        grid_frame.rowconfigure(0, weight=1)
        grid_frame.columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>", self._on_cell_double_click)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status_var).pack(fill="x", padx=10, pady=(0, 5))

        self._refresh_schedule_list()

    def _refresh_schedule_list(self):
        schedules = db.get_all_schedules()
        values = [f"{s.week_start} to {s.week_end} (ID: {s.id})" for s in schedules]
        self.sched_combo["values"] = values
        self._schedule_objects = schedules

    def _load_latest_schedule(self):
        schedules = db.get_all_schedules()
        if schedules:
            self.current_schedule_id = schedules[0].id
            self._display_schedule(schedules[0].id)

    def _on_schedule_selected(self, event=None):
        idx = self.sched_combo.current()
        if idx >= 0 and idx < len(self._schedule_objects):
            sched = self._schedule_objects[idx]
            self.current_schedule_id = sched.id
            self._display_schedule(sched.id)

    def _display_schedule(self, schedule_id: int):
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.assignments_map.clear()
        assignments = db.get_schedule_assignments(schedule_id)

        # Group by staff
        staff_rows = {}
        for a in assignments:
            if a.staff_name not in staff_rows:
                staff_rows[a.staff_name] = [""] * 7
            staff_rows[a.staff_name][a.day_of_week] = a.display_text()
            self.assignments_map[(a.staff_name, a.day_of_week)] = a

        # Configure tags for colors
        self.tree.tag_configure("off", background=CELL_COLORS["off"])
        self.tree.tag_configure("leave", background=CELL_COLORS["leave"])
        self.tree.tag_configure("clinic", background=CELL_COLORS["Clinic"])
        self.tree.tag_configure("office", background=CELL_COLORS["Office"])
        self.tree.tag_configure("salalah", background=CELL_COLORS["SALALAH"])
        self.tree.tag_configure("nizwa", background=CELL_COLORS["NIZWA"])

        for name in sorted(staff_rows.keys()):
            row = staff_rows[name]
            # Determine dominant tag for row coloring
            tags = ()
            # Check if all days are same type
            unique_vals = set(v.upper() for v in row if v)
            if unique_vals == {"SALALAH"}:
                tags = ("salalah",)
            elif unique_vals == {"CLINIC"} or unique_vals == {"CLINIC", "OFF"}:
                tags = ("clinic",)
            elif unique_vals == {"OFFICE"} or unique_vals == {"OFFICE", "OFF"}:
                tags = ("office",)

            self.tree.insert("", "end", text=name, values=tuple(row), tags=tags)

        total = len(staff_rows)
        self.status_var.set(f"Showing {total} staff members | Schedule ID: {schedule_id}")

    def _generate(self):
        date_str = self.date_var.get().strip()
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD.")
            return

        if dt.weekday() != 5:  # 5 = Saturday
            messagebox.showwarning("Warning", "Date should be a Saturday. Adjusting...")
            days_back = (dt.weekday() - 5) % 7
            dt = dt - timedelta(days=days_back)
            date_str = dt.strftime("%Y-%m-%d")
            self.date_var.set(date_str)

        self.status_var.set("Generating schedule...")
        self.update()

        try:
            schedule_id = generate_schedule(date_str)
            self.current_schedule_id = schedule_id
            self._refresh_schedule_list()
            self._display_schedule(schedule_id)
            self.status_var.set(f"Schedule generated! ID: {schedule_id}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate schedule:\n{e}")
            self.status_var.set("Error generating schedule")

    def _export_pdf(self):
        if not self.current_schedule_id:
            messagebox.showinfo("Info", "No schedule to export. Generate one first.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile="schedule.pdf",
            title="Export Schedule as PDF"
        )

        if filepath:
            try:
                export_schedule_pdf(self.current_schedule_id, filepath)
                self.status_var.set(f"PDF exported to {filepath}")
                messagebox.showinfo("Success", f"Schedule exported to:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export PDF:\n{e}")

    def _delete_schedule(self):
        if not self.current_schedule_id:
            return
        if messagebox.askyesno("Delete", "Delete this schedule?"):
            db.delete_schedule(self.current_schedule_id)
            self.current_schedule_id = None
            for item in self.tree.get_children():
                self.tree.delete(item)
            self._refresh_schedule_list()
            self.status_var.set("Schedule deleted")

    def _on_cell_double_click(self, event):
        """Handle double-click to edit a cell."""
        item = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)

        if not item or not col or col == "#0":
            return

        staff_name = self.tree.item(item, "text")
        col_idx = int(col.replace("#", "")) - 1  # Convert "#1" -> 0

        key = (staff_name, col_idx)
        assignment = self.assignments_map.get(key)

        if assignment:
            EditAssignmentDialog(self, assignment, on_save=lambda: self._display_schedule(self.current_schedule_id))
