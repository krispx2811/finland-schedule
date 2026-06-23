"""Shared UI styling constants."""

# Colors
BG_COLOR = "#f5f5f5"
HEADER_BG = "#2c3e50"
HEADER_FG = "#ffffff"
BTN_BG = "#3498db"
BTN_FG = "#ffffff"
BTN_DANGER = "#e74c3c"
BTN_SUCCESS = "#27ae60"

# Schedule cell colors by status/location
CELL_COLORS = {
    "off": "#d5d8dc",       # Light gray
    "leave": "#f9e79f",     # Yellow
    "Clinic": "#aed6f1",    # Light blue
    "Office": "#abebc6",    # Light green
    "SALALAH": "#f5cba7",   # Light orange
    "NIZWA": "#d2b4de",     # Light purple
    "assigned": "#ffffff",  # White (default)
}

# Fonts
FONT_HEADER = ("Helvetica", 14, "bold")
FONT_LABEL = ("Helvetica", 11)
FONT_BUTTON = ("Helvetica", 10)
FONT_CELL = ("Helvetica", 9)
FONT_TITLE = ("Helvetica", 18, "bold")

# Dimensions
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
