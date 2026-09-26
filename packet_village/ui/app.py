"""The main window. Owns the simulation and feeds the view and the sidebar.

All user actions end up here, change the simulation or the settings, and
the next animation frame shows the result.
"""

import random
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..engine import SimConfig, Simulation, SimulationError
from ..generator import random_town
from ..i18n import Translator
from ..narrate import node_label, routing_report, story_lines
from ..routing import shortest_costs
from ..scenarios import SCENARIOS, get_scenario
from ..settings import load_settings, save_settings
from ..storage import TownFileError, load_town, save_town
from . import theme
from .sidebar import DEMO_KEYS, Sidebar
from .view import Legend, TownView

FRAME_MS = 30
MAX_STEPS_PER_FRAME = 8
DEMO_PAUSE_TICKS = 45

def far_apart_houses(network):
  """The two houses with the longest shortest route between them."""
  houses = network.houses()
  best = (houses[0], houses[-1]) if len(houses) >= 2 else (None, None)
  best_cost = -1
  for house in houses:
    costs = shortest_costs(network, house)
    for other in houses:
      if other != house and costs.get(other, -1) > best_cost:
        best, best_cost = (house, other), costs[other]
  return best

class PacketVillageApp:
  def __init__(self, root, settings, scenario=None, town_file=None):
    self.root = root
    self.settings = settings
    self.tr = Translator(settings.lang)
    self.tr.subscribe(self._on_language)
    self.sim = None
    self.network = None
    self.scenario_key = None
    self.custom_title = None
    self.sender = None
    self.receiver = None
    self.selected = None
    self.paused = False
    self.auto_demo = True
    self._demo_index = 0
    self._demo_wait = 12
    self._budget = 0.0
    self._last_time = time.perf_counter()
    self._frame_count = 0
    self._drag = None
    self._story_serial = -1
    self._translated = []

    root.title(self.tr.t("app_title"))
    root.configure(bg=theme.BACKGROUND)
    width = min(1320, root.winfo_screenwidth() - 40)
    height = min(840, root.winfo_screenheight() - 90)
    root.geometry(f"{width}x{height}+10+10")
    root.minsize(min(1000, width), min(640, height))
    self._build_top_bar()
    self._build_body()
    self._build_status_bar()
    root.protocol("WM_DELETE_WINDOW", self._close)

    loaded = False
    if town_file:
      loaded = self._open_path(town_file)
    if not loaded:
      self.load_scenario(scenario or settings.scenario)
    self.root.after(FRAME_MS, self._frame)

  # -- layout ------------------------------------------------------------

  def _text(self, widget, key):
    widget.configure(text=self.tr.t(key))
    self._translated.append((widget, key))
    return widget

  def _top_button(self, parent, key, command):
    button = tk.Button(parent, command=command, font=theme.FONT, bg=theme.PANEL, fg=theme.INK,
                       activebackground=theme.PANEL_EDGE, relief=tk.FLAT, bd=0, padx=10, pady=3,
                       highlightthickness=1, highlightbackground=theme.PANEL_EDGE, cursor="hand2")
    return self._text(button, key)

  def _build_top_bar(self):
    bar = tk.Frame(self.root, bg=theme.BACKGROUND)
    bar.pack(side=tk.TOP, fill=tk.X, padx=14, pady=(10, 4))

    titles = tk.Frame(bar, bg=theme.BACKGROUND)
    titles.pack(side=tk.LEFT)
    self._text(tk.Label(titles, font=theme.FONT_TITLE, fg=theme.INK, bg=theme.BACKGROUND), "app_title").pack(anchor=tk.W)
    self._text(tk.Label(titles, font=theme.FONT_SMALL, fg=theme.INK_SOFT, bg=theme.BACKGROUND), "app_tagline").pack(anchor=tk.W)

    # The language switch sits on the far right and is always visible.
    lang = tk.Frame(bar, bg=theme.PANEL, highlightthickness=1, highlightbackground=theme.PANEL_EDGE,
                    cursor="hand2")
    lang.pack(side=tk.RIGHT, padx=(12, 0))
    self._lang_labels = {}
    for index, code in enumerate(("tr", "en")):
      if index:
        tk.Label(lang, text="|", bg=theme.PANEL, fg=theme.INK_SOFT, font=theme.FONT_BOLD).pack(side=tk.LEFT)
      label = tk.Label(lang, text=code.upper(), bg=theme.PANEL, font=theme.FONT_BOLD, padx=6, pady=3,
                       cursor="hand2")
      label.pack(side=tk.LEFT)
      label.bind("<Button-1>", lambda _e, c=code: self.tr.set_language(c))
      self._lang_labels[code] = label
    self._paint_language_switch()

    controls = tk.Frame(bar, bg=theme.BACKGROUND)
    controls.pack(side=tk.RIGHT)
    self._text(tk.Label(controls, font=theme.FONT, fg=theme.INK, bg=theme.BACKGROUND), "lbl_town").pack(side=tk.LEFT)
    self.town_box = ttk.Combobox(controls, state="readonly", width=22, font=theme.FONT)
    self.town_box.pack(side=tk.LEFT, padx=(6, 10))
    self.town_box.bind("<<ComboboxSelected>>", self._town_chosen)
    self._top_button(controls, "btn_random", self.new_random_town).pack(side=tk.LEFT, padx=2)
    self._top_button(controls, "btn_open", self.open_town).pack(side=tk.LEFT, padx=2)
    self._top_button(controls, "btn_save", self.save_town).pack(side=tk.LEFT, padx=2)
    self.pause_button = self._top_button(controls, "btn_pause", self.toggle_pause)
    self.pause_button.pack(side=tk.LEFT, padx=(8, 2))

  def _build_body(self):
    body = tk.Frame(self.root, bg=theme.BACKGROUND)
    body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=14, pady=4)

    self.sidebar = Sidebar(body, self.tr, self.settings, on_send=self.send,
                           on_knob=self.set_knob, on_way=self.set_show_way,
                           on_repair=self.repair_all)
    self.sidebar.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
    self.sidebar.from_box.bind("<<ComboboxSelected>>", self._pair_chosen)
    self.sidebar.to_box.bind("<<ComboboxSelected>>", self._pair_chosen)

    left = tk.Frame(body, bg=theme.BACKGROUND)
    left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    self.canvas = tk.Canvas(left, bg=theme.MAP_GRASS, highlightthickness=1,
                            highlightbackground=theme.PANEL_EDGE)
    self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    self.view = TownView(self.canvas, self.tr)
    self.canvas.bind("<Button-1>", self._press)
    self.canvas.bind("<B1-Motion>", self._drag_motion)
    self.canvas.bind("<ButtonRelease-1>", self._release)
    self.canvas.bind("<Motion>", self._hover)

    legend_canvas = tk.Canvas(left, height=26, bg=theme.BACKGROUND, highlightthickness=0)
    legend_canvas.pack(side=tk.TOP, fill=tk.X, pady=(4, 0))
    self.legend = Legend(legend_canvas, self.tr)

    bottom = tk.Frame(left, bg=theme.BACKGROUND)
    bottom.pack(side=tk.TOP, fill=tk.X, pady=(4, 0))
    self.story = self._text_panel(bottom, "sec_story", width=10)
    self.story.master.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    self.inspector = self._text_panel(bottom, "sec_inspect", width=44)
    self.inspector.master.pack(side=tk.LEFT, fill=tk.Y, padx=(8, 0))

  def _text_panel(self, parent, key, width):
    """A titled, read-only text box; returns the Text widget."""
    frame = tk.Frame(parent, bg=theme.PANEL, highlightthickness=1, highlightbackground=theme.PANEL_EDGE)
    self._text(tk.Label(frame, font=theme.FONT_SECTION, fg=theme.ACCENT_DARK, bg=theme.PANEL, anchor=tk.W),
               key).pack(fill=tk.X, padx=10, pady=(6, 0))
    text = tk.Text(frame, height=7, width=width, font=theme.FONT_SMALL, bg=theme.PANEL, fg=theme.INK,
                   relief=tk.FLAT, wrap=tk.WORD, padx=10, pady=4, cursor="arrow")
    text.pack(fill=tk.BOTH, expand=True)
    text.configure(state=tk.DISABLED)
    return text

  @staticmethod
  def _set_text(widget, content, follow_end=False):
    if widget.get("1.0", "end-1c") == content:
      return
    widget.configure(state=tk.NORMAL)
    widget.delete("1.0", tk.END)
    widget.insert(tk.END, content)
    if follow_end:
      widget.see(tk.END)
    widget.configure(state=tk.DISABLED)

  def _build_status_bar(self):
    bar = tk.Frame(self.root, bg=theme.BACKGROUND)
    bar.pack(side=tk.BOTTOM, fill=tk.X, padx=14, pady=(0, 8))
    self._text(tk.Label(bar, font=theme.FONT_SMALL, fg=theme.INK_SOFT, bg=theme.BACKGROUND, anchor=tk.W),
               "hint_bar").pack(side=tk.LEFT)
    self.routing_status = tk.Label(bar, text="", font=theme.FONT_SMALL, fg=theme.ACCENT_DARK,
                                   bg=theme.BACKGROUND, anchor=tk.E)
    self.routing_status.pack(side=tk.RIGHT)

  # -- towns -------------------------------------------------------------

  def load_scenario(self, key):
    scenario = get_scenario(key) or SCENARIOS[0]
    self.scenario_key = scenario.key
    self.custom_title = None
    self.settings.scenario = scenario.key
    self.settings.update("chatter", scenario.chatter)
    self.sidebar.set_knob("chatter", self.settings.chatter)
    self._install(scenario.build(), scenario.sender, scenario.receiver)

  def new_random_town(self):
    network = random_town(seed=random.randrange(1 << 30))
    self.scenario_key = None
    self.custom_title = ("key", "sc_random")
    self._install(network, *far_apart_houses(network))

  def open_town(self):
    path = filedialog.askopenfilename(
      parent=self.root, title=self.tr.t("dlg_open_title"),
      filetypes=[(self.tr.t("file_type"), "*.json"), (self.tr.t("file_all"), "*.*")])
    if path:
      self._open_path(path)

  def _open_path(self, path):
    try:
      network, title = load_town(path)
    except TownFileError as exc:
      self._complain(self.tr.t(exc.key, **exc.params))
      return False
    self.scenario_key = None
    self.custom_title = ("text", title) if title else ("key", "sc_loaded")
    self._install(network, *far_apart_houses(network))
    return True

  def save_town(self):
    path = filedialog.asksaveasfilename(
      parent=self.root, title=self.tr.t("dlg_save_title"), defaultextension=".json",
      filetypes=[(self.tr.t("file_type"), "*.json"), (self.tr.t("file_all"), "*.*")])
    if not path:
      return
    try:
      save_town(self.network, path, title=self._town_title())
    except TownFileError as exc:
      self._complain(self.tr.t(exc.key, **exc.params))

  def _install(self, network, sender, receiver):
    self.network = network
    s = self.settings
    config = SimConfig(queue_size=s.queue_size, chunk_size=s.chunk_size,
                       chatter=s.chatter, noise=s.noise)
    self.sim = Simulation(network, config)
    self.sender, self.receiver = sender, receiver
    self.selected = None
    self.auto_demo = True
    self._demo_wait = 12
    self._story_serial = -1
    self.view.rebuild(network)
    self._refresh_house_boxes()
    self._refresh_town_box()
    self.sidebar.show_error("")

  def _town_title(self):
    if self.scenario_key:
      return self.tr.t(get_scenario(self.scenario_key).title_key)
    kind, value = self.custom_title or ("key", "sc_loaded")
    return self.tr.t(value) if kind == "key" else value

  def _refresh_town_box(self):
    titles = [self.tr.t(s.title_key) for s in SCENARIOS]
    if self.scenario_key is None:
      titles.append(self._town_title())
      index = len(titles) - 1
    else:
      index = [s.key for s in SCENARIOS].index(self.scenario_key)
    self.town_box["values"] = titles
    self.town_box.current(index)

  def _refresh_house_boxes(self):
    houses = [self.network.nodes[h] for h in self.network.houses()]
    counts = {}
    for node in houses:
      counts[node.name] = counts.get(node.name, 0) + 1
    listing = [(n.id, n.name if counts[n.name] == 1 else f"{n.name} ({n.id})") for n in houses]
    self.sidebar.set_houses(listing, self.sender, self.receiver)

  def _town_chosen(self, _event):
    index = self.town_box.current()
    if 0 <= index < len(SCENARIOS):
      if SCENARIOS[index].key != self.scenario_key:
        self.load_scenario(SCENARIOS[index].key)

  def _pair_chosen(self, _event):
    self.sender = self.sidebar.selected_house(self.sidebar.from_box)
    self.receiver = self.sidebar.selected_house(self.sidebar.to_box)

  # -- actions -----------------------------------------------------------

  def send(self, src, dst, text):
    try:
      self.sim.send_message(src, dst, text.strip())
    except SimulationError as exc:
      self.sidebar.show_error(self.tr.t(exc.key, **exc.params))
      return
    self.sidebar.show_error("")
    self.sender, self.receiver = src, dst
    self.auto_demo = False

  def set_knob(self, name, value):
    value = self.settings.update(name, value)
    config = self.sim.config
    if name == "queue_size":
      config.queue_size = value
    elif name == "chunk_size":
      config.chunk_size = value
    elif name == "chatter":
      config.chatter = value
    elif name == "noise":
      config.noise = value

  def set_show_way(self, show):
    self.view.show_way = bool(show)

  def repair_all(self):
    self.sim.repair_all()

  def toggle_pause(self):
    self.paused = not self.paused
    key = "btn_play" if self.paused else "btn_pause"
    self._translated = [(w, k) for w, k in self._translated if w is not self.pause_button]
    self._text(self.pause_button, key)

  def _complain(self, text):
    messagebox.showerror(self.tr.t("dlg_error_title"), text, parent=self.root)

  # -- mouse -------------------------------------------------------------

  def _press(self, event):
    node_id = self.view.node_at(event.x, event.y)
    if node_id is not None:
      self._drag = [node_id, event.x, event.y, False]
      return
    link_key = self.view.link_at(event.x, event.y)
    if link_key is not None:
      self.sim.toggle_link(*link_key)
      return
    self.selected = None

  def _drag_motion(self, event):
    if self._drag is None:
      return
    node_id, x0, y0, moved = self._drag
    if not moved and abs(event.x - x0) + abs(event.y - y0) < 5:
      return
    self._drag[3] = True
    wx, wy = self.view.viewport.to_world(event.x, event.y)
    node = self.network.nodes[node_id]
    node.x, node.y = self.view.viewport.clamp_world(wx, wy)
    self.view.mark_moved()

  def _release(self, _event):
    if self._drag is not None and not self._drag[3]:
      node_id = self._drag[0]
      self.selected = None if self.selected == node_id else node_id
    self._drag = None

  def _hover(self, event):
    over_node = self.view.node_at(event.x, event.y)
    link = None if over_node else self.view.link_at(event.x, event.y)
    self.view.hover_link = link
    cursor = "fleur" if over_node else ("hand2" if link else "")
    if self.canvas.cget("cursor") != cursor:
      self.canvas.configure(cursor=cursor)

  # -- animation ---------------------------------------------------------

  def _frame(self):
    now = time.perf_counter()
    elapsed = min(0.1, now - self._last_time)
    self._last_time = now
    if not self.paused:
      self._budget += elapsed * self.settings.speed
      steps = 0
      while self._budget >= 1.0 and steps < MAX_STEPS_PER_FRAME:
        self.sim.step()
        self._demo_tick()
        self._budget -= 1.0
        steps += 1
      if steps == MAX_STEPS_PER_FRAME:
        # The machine cannot keep up; slow down instead of spiralling.
        self._budget = min(self._budget, 0.99)
    alpha = min(self._budget, 0.999)
    self.view.render(self.sim, self.sim.tick + alpha, self.sender, self.receiver, self.selected)

    self._frame_count += 1
    if self._frame_count % 4 == 0:
      self._refresh_panels()
    if self.sim.event_serial != self._story_serial:
      self._refresh_story()
    self.root.after(FRAME_MS, self._frame)

  def _demo_tick(self):
    """Keep a letter on the road until the user sends their own."""
    if not self.auto_demo or self.sim.active_foreground():
      return
    self._demo_wait -= 1
    if self._demo_wait > 0 or self.sender is None or self.receiver is None or self.sender == self.receiver:
      return
    text = self.tr.t(DEMO_KEYS[self._demo_index % len(DEMO_KEYS)])
    self._demo_index += 1
    self._demo_wait = DEMO_PAUSE_TICKS
    try:
      self.sim.send_message(self.sender, self.receiver, text)
    except SimulationError:
      self.auto_demo = False

  # -- panels ------------------------------------------------------------

  def _refresh_panels(self):
    tr = self.tr
    sim = self.sim
    flow = sim.foreground_flow()
    if flow is None:
      self.sidebar.show_progress(tr.t("progress_idle"), "")
    else:
      if flow.delivered:
        status = tr.t("progress_done", ticks=flow.trip_time())
      elif not flow.active:
        status = tr.t("progress_failed")
      else:
        status = tr.t("progress_moving", got=flow.received_count, total=flow.total)
      pair = f"{node_label(self.network, flow.src, tr)} → {node_label(self.network, flow.dst, tr)}"
      self.sidebar.show_progress(flow.progress_text(), f"{pair}   {status}")

    stats = sim.stats
    trip = stats.average_trip
    self.sidebar.show_counters({
      "st_step": str(sim.tick),
      "st_sent": str(stats.sent),
      "st_arrived": str(stats.delivered_packets),
      "st_lost": str(stats.dropped),
      "st_resent": str(stats.retransmits),
      "st_letters": str(stats.messages_delivered),
      "st_trip": tr.t("st_steps", n=round(trip)) if trip is not None else tr.t("st_none"),
    })
    self._set_text(self.inspector, self._inspector_text())
    status = tr.t("status_healing") if sim.healing else tr.t("status_settled")
    if self.routing_status.cget("text") != status:
      self.routing_status.configure(text=status)

  def _inspector_text(self):
    tr = self.tr
    node_id = self.selected
    if node_id is None or node_id not in self.network.nodes:
      return tr.t("inspect_hint")
    node = self.network.nodes[node_id]
    name = node_label(self.network, node_id, tr)
    lines = [tr.t("inspect_house" if node.is_house else "inspect_router", name=name)]
    links = [link for _, link in self.network.neighbors(node_id, only_up=False)]
    waiting = sum(len(self.sim.queues[(node_id, n)]) for n, _ in self.network.neighbors(node_id, only_up=False))
    lines.append(tr.t("inspect_cables", up=sum(1 for l in links if l.up), count=len(links))
                 + " · " + tr.t("inspect_waiting", count=waiting))
    lines.append(tr.t("inspect_knows"))
    lines.extend("  " + line for line in routing_report(self.sim, node_id, tr))
    return "\n".join(lines)

  def _refresh_story(self):
    self._story_serial = self.sim.event_serial
    lines = story_lines(self.sim.events, self.network, self.tr, limit=30)
    self._set_text(self.story, "\n".join(lines), follow_end=True)

  # -- language ----------------------------------------------------------

  def _paint_language_switch(self):
    for code, label in self._lang_labels.items():
      active = code == self.tr.lang
      label.configure(fg=theme.ACCENT_DARK if active else theme.INK_SOFT,
                      font=(theme.FAMILY, 10, "bold" if active else "normal"))

  def _on_language(self, lang, previous):
    self.settings.lang = lang
    save_settings(self.settings)
    self.root.title(self.tr.t("app_title"))
    for widget, key in self._translated:
      widget.configure(text=self.tr.t(key))
    self._paint_language_switch()
    self.sidebar.retranslate(previous)
    self.legend.refresh()
    self.view.refresh_labels()
    self._refresh_town_box()
    self._refresh_house_boxes()
    self._refresh_panels()
    self._refresh_story()

  def _close(self):
    save_settings(self.settings)
    self.root.destroy()

def _enable_crisp_text():
  if sys.platform != "win32":
    return
  try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
  except (AttributeError, OSError):
    pass

def launch(lang=None, scenario=None, town_file=None):
  _enable_crisp_text()
  settings = load_settings()
  if lang:
    settings.lang = lang
  root = tk.Tk()
  PacketVillageApp(root, settings, scenario=scenario, town_file=town_file)
  root.mainloop()
  return 0
