"""The panel on the right: send a letter, turn the knobs, read the counters.

The sidebar owns no simulation state. It shows what the app hands it and
reports user actions back through the callbacks it was given.
"""

import tkinter as tk
from tkinter import ttk

from ..settings import LIMITS
from ..strings import TABLES
from . import theme

PANEL_WIDTH = 330
DEMO_KEYS = ("demo_1", "demo_2", "demo_3", "demo_4")

# knob name -> (label key, scale factor between the setting and the slider)
KNOBS = (
  ("speed", "lbl_speed", 1),
  ("chatter", "lbl_chatter", 100),
  ("noise", "lbl_noise", 100),
  ("queue_size", "lbl_queue", 1),
  ("chunk_size", "lbl_chunk", 1),
)

PERCENT_KNOBS = ("chatter", "noise")

def _knob_text(name, slider_value):
  number = int(round(slider_value))
  return f"{number}%" if name in PERCENT_KNOBS else str(number)

COUNTERS = ("st_step", "st_sent", "st_arrived", "st_lost", "st_resent", "st_letters", "st_trip")

class Sidebar(tk.Frame):
  def __init__(self, parent, tr, settings, on_send, on_knob, on_way, on_repair):
    super().__init__(parent, bg=theme.PANEL, width=PANEL_WIDTH, highlightthickness=1,
                     highlightbackground=theme.PANEL_EDGE)
    self.tr = tr
    self._on_send = on_send
    self._on_knob = on_knob
    self._on_way = on_way
    self._translated = []
    self._house_ids = []
    self._house_names = []
    self._counter_values = {}
    self._knob_vars = {}
    self._suppress_knobs = False
    self.pack_propagate(False)
    self.grid_propagate(False)

    self._build_send()
    self._build_progress()
    self._build_knobs(settings, on_repair)
    self._build_counters()

  # -- helpers -----------------------------------------------------------

  def _label(self, parent, key, font=theme.FONT, fg=theme.INK):
    label = tk.Label(parent, text=self.tr.t(key), font=font, fg=fg, bg=theme.PANEL, anchor=tk.W)
    self._translated.append((label, key))
    return label

  def _section(self, key):
    frame = tk.Frame(self, bg=theme.PANEL)
    frame.pack(fill=tk.X, padx=14, pady=(10, 0))
    self._label(frame, key, font=theme.FONT_SECTION, fg=theme.ACCENT_DARK).pack(fill=tk.X)
    tk.Frame(frame, bg=theme.PANEL_EDGE, height=1).pack(fill=tk.X, pady=(2, 6))
    return frame

  def _button(self, parent, key, command, accent=False):
    button = tk.Button(parent, text=self.tr.t(key), command=command, font=theme.FONT_BOLD if accent else theme.FONT,
                       bg=theme.ACCENT if accent else theme.PANEL_EDGE,
                       fg="white" if accent else theme.INK,
                       activebackground=theme.ACCENT_DARK if accent else theme.BACKGROUND,
                       activeforeground="white" if accent else theme.INK,
                       relief=tk.FLAT, bd=0, padx=12, pady=4, cursor="hand2")
    self._translated.append((button, key))
    return button

  # -- sections ----------------------------------------------------------

  def _build_send(self):
    frame = self._section("sec_send")
    row = tk.Frame(frame, bg=theme.PANEL)
    row.pack(fill=tk.X)
    self._label(row, "lbl_from", font=theme.FONT_SMALL).grid(row=0, column=0, sticky=tk.W)
    self._label(row, "lbl_to", font=theme.FONT_SMALL).grid(row=0, column=1, sticky=tk.W, padx=(8, 0))
    self.from_box = ttk.Combobox(row, state="readonly", width=14, font=theme.FONT)
    self.to_box = ttk.Combobox(row, state="readonly", width=14, font=theme.FONT)
    self.from_box.grid(row=1, column=0, sticky=tk.EW)
    self.to_box.grid(row=1, column=1, sticky=tk.EW, padx=(8, 0))
    row.columnconfigure(0, weight=1)
    row.columnconfigure(1, weight=1)

    line = tk.Frame(frame, bg=theme.PANEL)
    line.pack(fill=tk.X, pady=(6, 0))
    self.message = tk.Entry(line, font=theme.FONT, relief=tk.FLAT, bg="white", fg=theme.INK,
                            highlightthickness=1, highlightbackground=theme.PANEL_EDGE,
                            highlightcolor=theme.ACCENT)
    self.message.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
    self.message.insert(0, self.tr.t("demo_2"))
    self.message.bind("<Return>", lambda _e: self._send())
    self._button(line, "btn_send", self._send, accent=True).pack(side=tk.LEFT, padx=(6, 0))
    self.error = tk.Label(frame, text="", font=theme.FONT_SMALL, fg=theme.CABLE_CUT, bg=theme.PANEL,
                          anchor=tk.W, justify=tk.LEFT, wraplength=PANEL_WIDTH - 30)
    self.error.pack(fill=tk.X)

  def _build_progress(self):
    frame = self._section("sec_progress")
    self.progress = tk.Label(frame, text="", font=theme.FONT_PROGRESS, fg=theme.INK, bg=theme.PANEL,
                             anchor=tk.W, justify=tk.LEFT, wraplength=PANEL_WIDTH - 30)
    self.progress.pack(fill=tk.X)
    self.progress_note = tk.Label(frame, text="", font=theme.FONT_SMALL, fg=theme.INK_SOFT,
                                  bg=theme.PANEL, anchor=tk.W)
    self.progress_note.pack(fill=tk.X)

  def _build_knobs(self, settings, on_repair):
    frame = self._section("sec_controls")
    grid = tk.Frame(frame, bg=theme.PANEL)
    grid.pack(fill=tk.X)
    for row, (name, key, factor) in enumerate(KNOBS):
      _, low, high, _ = LIMITS[name]
      self._label(grid, key, font=theme.FONT_SMALL).grid(row=row, column=0, sticky=tk.W)
      var = tk.DoubleVar(value=getattr(settings, name) * factor)
      shown = tk.StringVar(value=_knob_text(name, var.get()))
      value = tk.Label(grid, textvariable=shown, width=4, font=theme.FONT_SMALL, fg=theme.INK_SOFT,
                       bg=theme.PANEL, anchor=tk.E)
      value.grid(row=row, column=2, sticky=tk.E)
      scale = tk.Scale(grid, from_=low * factor, to=high * factor, orient=tk.HORIZONTAL,
                       variable=var, showvalue=False, resolution=1, length=140, sliderlength=16,
                       width=10, bd=0, highlightthickness=0, bg=theme.PANEL, fg=theme.INK_SOFT,
                       troughcolor=theme.PANEL_EDGE, activebackground=theme.ACCENT,
                       font=theme.FONT_SMALL,
                       command=lambda value, n=name: self._knob_moved(n, float(value)))
      scale.grid(row=row, column=1, sticky=tk.E, pady=3)
      self._knob_vars[name] = (var, factor, shown)
    grid.columnconfigure(0, weight=1)

    row = tk.Frame(frame, bg=theme.PANEL)
    row.pack(fill=tk.X, pady=(4, 0))
    self.way_var = tk.BooleanVar(value=True)
    way = tk.Checkbutton(row, text=self.tr.t("chk_way"), variable=self.way_var, bg=theme.PANEL,
                         fg=theme.INK, activebackground=theme.PANEL, selectcolor="white",
                         font=theme.FONT_SMALL, command=lambda: self._on_way(self.way_var.get()))
    self._translated.append((way, "chk_way"))
    way.pack(side=tk.LEFT)
    self._button(row, "btn_repair", on_repair).pack(side=tk.RIGHT)

  def _build_counters(self):
    frame = self._section("sec_stats")
    grid = tk.Frame(frame, bg=theme.PANEL)
    grid.pack(fill=tk.X)
    for index, key in enumerate(COUNTERS):
      row, col = divmod(index, 2)
      cell = tk.Frame(grid, bg=theme.PANEL)
      cell.grid(row=row, column=col, sticky=tk.EW, padx=(0 if col == 0 else 10, 0))
      self._label(cell, key, font=theme.FONT_SMALL, fg=theme.INK_SOFT).pack(side=tk.LEFT)
      value = tk.Label(cell, text="0", font=theme.FONT_BOLD, fg=theme.INK, bg=theme.PANEL, anchor=tk.E)
      value.pack(side=tk.RIGHT)
      self._counter_values[key] = value
    grid.columnconfigure(0, weight=1, uniform="counters")
    grid.columnconfigure(1, weight=1, uniform="counters")

  # -- actions -----------------------------------------------------------

  def _send(self):
    self._on_send(self.selected_house(self.from_box), self.selected_house(self.to_box),
                  self.message.get())

  def _knob_moved(self, name, slider_value):
    _, factor, shown = self._knob_vars[name]
    shown.set(_knob_text(name, slider_value))
    if not self._suppress_knobs:
      self._on_knob(name, slider_value / factor)

  def selected_house(self, box):
    index = box.current()
    if 0 <= index < len(self._house_ids):
      return self._house_ids[index]
    return None

  # -- updates from the app ----------------------------------------------

  def set_houses(self, houses, sender, receiver):
    """houses: list of (id, display name)."""
    self._house_ids = [h[0] for h in houses]
    self._house_names = [h[1] for h in houses]
    for box, chosen in ((self.from_box, sender), (self.to_box, receiver)):
      box["values"] = self._house_names
      if chosen in self._house_ids:
        box.current(self._house_ids.index(chosen))
      elif self._house_ids:
        box.current(0)

  def set_pair(self, sender, receiver):
    for box, chosen in ((self.from_box, sender), (self.to_box, receiver)):
      if chosen in self._house_ids:
        box.current(self._house_ids.index(chosen))

  def set_knob(self, name, value):
    var, factor, shown = self._knob_vars[name]
    self._suppress_knobs = True
    try:
      var.set(value * factor)
      shown.set(_knob_text(name, value * factor))
    finally:
      self._suppress_knobs = False

  def show_error(self, text):
    self.error.configure(text=text or "")

  def show_progress(self, text, note):
    if self.progress.cget("text") != text:
      self.progress.configure(text=text)
    if self.progress_note.cget("text") != note:
      self.progress_note.configure(text=note)

  def show_counters(self, values):
    for key, text in values.items():
      label = self._counter_values[key]
      if label.cget("text") != text:
        label.configure(text=text)

  def retranslate(self, previous_lang):
    """Refresh every label; a demo letter still in the box follows along."""
    for widget, key in self._translated:
      widget.configure(text=self.tr.t(key))
    current = self.message.get()
    for key in DEMO_KEYS:
      if TABLES[previous_lang].get(key) == current:
        self.message.delete(0, tk.END)
        self.message.insert(0, self.tr.t(key))
        break
