"""Main application window."""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os

from .. import database as db
from ..excel_import import import_excel
from ..config import APP_NAME
from .schedule_tab import ScheduleTab
from .staff_tab import StaffTab
from .locations_tab import LocationsTab


class AppWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("1000x700")
        self.root.minsize(800, 500)

        # Style
        style = ttk.Style()
        style.theme_use("clam")

        self._build_menu()
        self._build_ui()

        # Auto-import Excel if DB is empty
        if not db.has_data():
            self._auto_import()

    def _build_menu(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Import from Excel...", command=self._import_excel)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    def _build_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=5, pady=5)

        self.schedule_tab = ScheduleTab(notebook)
        self.staff_tab = StaffTab(notebook)
        self.locations_tab = LocationsTab(notebook)

        notebook.add(self.schedule_tab, text="  Schedule  ")
        notebook.add(self.staff_tab, text="  Staff  ")
        notebook.add(self.locations_tab, text="  Locations  ")

    def _auto_import(self):
        """Auto-import from Excel if it exists in the project directory."""
        excel_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "New Schedule.xlsx"
        )
        if not os.path.exists(excel_path):
            # Try parent directory
            excel_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "New Schedule.xlsx"
            )

        if os.path.exists(excel_path):
            try:
                import_excel(excel_path)
                self.staff_tab.refresh()
                self.locations_tab.refresh()
                self.schedule_tab._refresh_schedule_list()
                self.schedule_tab._load_latest_schedule()
            except Exception as e:
                messagebox.showwarning("Import Warning",
                                       f"Auto-import had issues: {e}\nYou can import manually via File > Import.")

    def _import_excel(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("Excel files", "*.xlsx *.xls")],
            title="Select Schedule Excel File"
        )
        if filepath:
            try:
                import_excel(filepath)
                self.staff_tab.refresh()
                self.locations_tab.refresh()
                self.schedule_tab._refresh_schedule_list()
                self.schedule_tab._load_latest_schedule()
                messagebox.showinfo("Success", "Excel data imported successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import:\n{e}")

    def _show_about(self):
        messagebox.showinfo("About",
                           "Ghiath Optical - Schedule Manager\n"
                           "Version 1.0.0\n\n"
                           "Manage staff schedules for optical shops across Oman.\n"
                           "Auto-generate, edit, and export schedules to PDF.")

    def run(self):
        self.root.mainloop()
