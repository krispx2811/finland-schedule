"""Staff management tab."""

import tkinter as tk
from tkinter import ttk, messagebox
from .. import database as db
from .dialogs import AddStaffDialog


class StaffTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Title
        header = ttk.Frame(self)
        header.pack(fill="x", padx=10, pady=(10, 5))
        ttk.Label(header, text="Staff Management", font=("Helvetica", 14, "bold")).pack(side="left")

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(btn_frame, text="+ Add Staff", command=self._add).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Edit", command=self._edit).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Delete", command=self._delete).pack(side="left", padx=2)

        # Table
        columns = ("name", "location", "role", "active")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=20)
        self.tree.heading("name", text="Name")
        self.tree.heading("location", text="Fixed Location")
        self.tree.heading("role", text="Fixed Role")
        self.tree.heading("active", text="Active")
        self.tree.column("name", width=180)
        self.tree.column("location", width=130)
        self.tree.column("role", width=100)
        self.tree.column("active", width=70)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=5)
        scrollbar.pack(side="right", fill="y", padx=(0, 10), pady=5)

        self.tree.bind("<Double-1>", lambda e: self._edit())

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        staff_list = db.get_all_staff(active_only=False)
        for s in staff_list:
            self.tree.insert("", "end", iid=str(s.id), values=(
                s.name,
                s.default_location or "-",
                s.default_role or "-",
                "Yes" if s.is_active else "No"
            ))

    def _get_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Please select a staff member.")
            return None
        return db.get_staff_by_id(int(sel[0]))

    def _add(self):
        AddStaffDialog(self, on_save=self.refresh)

    def _edit(self):
        staff = self._get_selected()
        if staff:
            AddStaffDialog(self, staff=staff, on_save=self.refresh)

    def _delete(self):
        staff = self._get_selected()
        if staff:
            if messagebox.askyesno("Delete", f"Delete '{staff.name}'?"):
                db.delete_staff(staff.id)
                self.refresh()
