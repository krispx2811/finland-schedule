"""Entry point for the Ghiath Optical Schedule Manager."""

from . import database as db
from .ui.app_window import AppWindow


def main():
    # Initialize database and seed defaults
    db.init_db()
    db.seed_defaults()

    # Launch the application
    app = AppWindow()
    app.run()


if __name__ == "__main__":
    main()
