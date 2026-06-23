"""Launcher script — run this to start the app."""
import webbrowser
import threading
import sys
import os
from schedule_app import database as db
from schedule_app.excel_import import import_excel
from schedule_app.web_app import app


def get_base_path():
    """Get base path — works for dev and PyInstaller bundle."""
    if getattr(sys, '_MEIPASS', None):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def main():
    # Create the database schema if it doesn't exist yet.
    # We intentionally do NOT seed defaults or auto-import here: a fresh
    # install starts empty so the user can build (and permanently delete)
    # their own staff, locations, and shifts. The Settings page offers
    # "Load sample data" to populate the original Finland setup on demand.
    db.init_db()

    # Open browser after short delay
    def open_browser():
        webbrowser.open("http://127.0.0.1:5050")

    threading.Timer(1.5, open_browser).start()

    print("\n  Finland Optical Center - Schedule Manager")
    print("  Running at http://127.0.0.1:5050")
    print("  Press Ctrl+C to stop\n")

    app.run(host="127.0.0.1", port=5050, debug=False)


if __name__ == "__main__":
    main()
