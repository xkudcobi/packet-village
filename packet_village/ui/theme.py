"""Colours and fonts for the window, in one place."""

import sys

BACKGROUND = "#f3ede2"
PANEL = "#fbf8f2"
PANEL_EDGE = "#e2d8c6"
INK = "#2f2a24"
INK_SOFT = "#7a6f62"
ACCENT = "#d9822b"
ACCENT_DARK = "#b2641a"

MAP_GRASS = "#e8efd9"
MAP_DOTS = "#d6e2c1"
CABLE = "#8d8579"
CABLE_CUT = "#d2463c"
CABLE_HOVER = "#3d7ea6"

HOUSE_WALL = "#fff6e6"
HOUSE_ROOF = "#d9822b"
HOUSE_EDGE = "#6b4a2b"
ROUTER_CALM = "#3aa39a"
ROUTER_BUSY = "#e0584f"
ROUTER_EDGE = "#23615c"

ENVELOPE = "#ffffff"
ENVELOPE_EDGE = "#3d7ea6"
ENVELOPE_RESENT = "#fff1c9"
ACK_DOT = "#3f9f5a"
BACKGROUND_DOT = "#9aa6b8"
BACKGROUND_ACK = "#b8c9b0"
DROP_PUFF = "#d2463c"
WAY_ARROW = "#e0a526"
SENDER_RING = "#3d7ea6"
RECEIVER_RING = "#e0a526"
SELECT_RING = "#2f2a24"

if sys.platform == "win32":
  FAMILY = "Segoe UI"
elif sys.platform == "darwin":
  FAMILY = "Helvetica Neue"
else:
  FAMILY = "DejaVu Sans"

FONT = (FAMILY, 10)
FONT_SMALL = (FAMILY, 9)
FONT_TINY = (FAMILY, 7, "bold")
FONT_ENVELOPE = (FAMILY, 9, "bold")
FONT_BOLD = (FAMILY, 10, "bold")
FONT_TITLE = (FAMILY, 16, "bold")
FONT_SECTION = (FAMILY, 10, "bold")
FONT_LABEL = (FAMILY, 9, "bold")
FONT_PROGRESS = ("Consolas" if sys.platform == "win32" else "Courier", 12, "bold")
