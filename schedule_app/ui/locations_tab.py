"""Locations management tab."""

import tkinter as tk
from tkinter import ttk, messagebox
from .. import database as db
from .dialogs import AddLocationDialog


class LocationsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = ttk.Frame(self)
        header.pack(fill="x", padx=10, pady=(10, 5))
        ttk.Label(header, text="Locations / Shops", font=("Helvetica", 14, "bold")).pack(side="left")

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(btn_frame, text="+ Add Location", command=self._add).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Edit", command=self._edit).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Delete", command=self._delete).pack(side="left", padx=2)

        columns = ("name", "code", "min", "max", "active")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=15)
        self.tree.heading("name", text="Name")
        self.tree.heading("code", text="Code")
        self.tree.heading("min", text="Min Staff")
        self.tree.heading("max", text="Max Staff")
        self.tree.heading("active", text="Active")
        self.tree.column("name", width=150)
        self.tree.column("code", width=100)
        self.tree.column("min", width=80)
        self.tree.column("max", width=80)
        self.tree.column("active", width=70)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=5)
        scrollbar.pack(side="right", fill="y", padx=(0, 10), pady=5)

        self.tree.bind("<Double-1>", lambda e: self._edit())

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        locations = db.get_all_locations(active_only=False)
        for l in locations:
            self.tree.insert("", "end", iid=str(l.id), values=(
                l.name, l.short_code, l.min_staff, l.max_staff,
                "Yes" if l.is_active else "No"
            ))

    def _get_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Please select a location.")
            return None
        locs = db.get_all_locations(active_only=False)
        for l in locs:
            if str(l.id) == sel[0]:
                return l
        return None

    def _add(self):
        AddLocationDialog(self, on_save=self.refresh)

    def _edit(self):
        loc = self._get_selected()
        if loc:
            AddLocationDialog(self, location=loc, on_save=self.refresh)

    def _delete(self):
        loc = self._get_selected()
        if loc:
            if messagebox.askyesno("Delete", f"Delete location '{loc.name}'?"):
                db.delete_location(loc.id)
                self.refresh()
