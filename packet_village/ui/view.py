"""Draws the town and everything moving through it on a Tk canvas.

Canvas items are created once and then only moved or recoloured. Moving
envelopes come from two sprite pools that grow when needed and hide
their spare items, so a busy town does not allocate new items per frame.
"""

import tkinter as tk

from ..packets import DATA
from ..geometry import Viewport, mix_color, point_segment_distance, unit_and_normal
from ..narrate import node_label
from ..scenarios import WORLD_HEIGHT, WORLD_WIDTH
from ..topology import ROUTER
from . import theme

NODE_RADIUS = 17
LANE_OFFSET = 6
QUEUE_SPACING = 11
PUFF_TICKS = 10
LOAD_STEPS = 8

HOUSE_SHAPE = ((0, -19), (-17, -4), (-13, -4), (-13, 14), (13, 14), (13, -4), (17, -4))

def _is_letter(packet):
  return packet.kind == DATA and not packet.background

def _envelope_half(packet):
  return max(12, len(packet.chunk) * 4.5 + 6)

class TownView:
  def __init__(self, canvas, tr):
    self.canvas = canvas
    self.tr = tr
    self.viewport = Viewport(WORLD_WIDTH, WORLD_HEIGHT)
    self.network = None
    self.screen = {}
    self.geometry_dirty = True
    self.geometry_version = 0
    self.hover_link = None
    self.show_way = True
    self._link_items = {}
    self._link_marks = {}
    self._link_style = {}
    self._node_shapes = {}
    self._node_letters = {}
    self._node_labels = {}
    self._node_fill = {}
    self._arrows = {}
    self._arrow_signature = None
    self._envelopes = []
    self._envelopes_shown = 0
    self._dots = []
    self._dots_shown = 0
    self._puffs = []
    self._puffs_shown = 0
    self._rings = {}
    canvas.bind("<Configure>", self._on_resize, add="+")

  # -- building ----------------------------------------------------------

  def rebuild(self, network):
    """Throw away all items and create the ones for a new town."""
    c = self.canvas
    c.delete("all")
    self.network = network
    self._link_items.clear()
    self._link_marks.clear()
    self._link_style.clear()
    self._node_shapes.clear()
    self._node_letters.clear()
    self._node_labels.clear()
    self._node_fill.clear()
    self._arrows.clear()
    self._arrow_signature = None
    self._envelopes = []
    self._dots = []
    self._puffs = []
    self._envelopes_shown = self._dots_shown = self._puffs_shown = 0
    self.hover_link = None

    for key in network.links:
      self._link_items[key] = c.create_line(0, 0, 0, 0, fill=theme.CABLE, width=4,
                                            capstyle=tk.ROUND, tags=("cable",))
      self._link_marks[key] = c.create_text(0, 0, text="✂", fill=theme.CABLE_CUT,
                                            font=(theme.FAMILY, 14, "bold"), state=tk.HIDDEN,
                                            tags=("cable",))
    for node_id in network.nodes:
      self._arrows[node_id] = c.create_line(0, 0, 0, 0, fill=theme.WAY_ARROW, width=3,
                                            arrow=tk.LAST, arrowshape=(10, 12, 5),
                                            state=tk.HIDDEN, tags=("way",))
    for node in network.nodes.values():
      if node.kind == ROUTER:
        shape = c.create_oval(0, 0, 0, 0, fill=theme.ROUTER_CALM, outline=theme.ROUTER_EDGE,
                              width=2, tags=("node",))
        self._node_letters[node.id] = c.create_text(0, 0, text=node.name, fill="white",
                                                    font=theme.FONT_BOLD, tags=("node",))
      else:
        shape = c.create_polygon(0, 0, 0, 0, 0, 0, fill=theme.HOUSE_WALL, outline=theme.HOUSE_EDGE,
                                 width=2, joinstyle=tk.ROUND, tags=("node",))
        self._node_letters[node.id] = c.create_rectangle(0, 0, 0, 0, fill=theme.HOUSE_ROOF,
                                                         outline="", tags=("node",))
      self._node_shapes[node.id] = shape
      self._node_labels[node.id] = c.create_text(0, 0, text="", fill=theme.INK,
                                                 font=theme.FONT_LABEL, tags=("node",))
    for role, colour, dash in (("from", theme.SENDER_RING, ()), ("to", theme.RECEIVER_RING, ()),
                               ("select", theme.SELECT_RING, (4, 3))):
      self._rings[role] = c.create_oval(0, 0, 0, 0, outline=colour, width=3, dash=dash,
                                        state=tk.HIDDEN, tags=("ring",))
    self.refresh_labels()
    self.geometry_dirty = True

  def refresh_labels(self):
    """Re-read node names, e.g. after the language changed."""
    if self.network is None:
      return
    for node_id, item in self._node_labels.items():
      self.canvas.itemconfigure(item, text=node_label(self.network, node_id, self.tr))

  # -- geometry ----------------------------------------------------------

  def _on_resize(self, event):
    self.viewport.fit(event.width, event.height)
    self.geometry_dirty = True

  def mark_moved(self):
    self.geometry_dirty = True

  def _layout(self):
    c = self.canvas
    vp = self.viewport
    self.screen = {nid: vp.to_screen(n.x, n.y) for nid, n in self.network.nodes.items()}
    for node_id, (x, y) in self.screen.items():
      node = self.network.nodes[node_id]
      if node.kind == ROUTER:
        c.coords(self._node_shapes[node_id], x - NODE_RADIUS, y - NODE_RADIUS,
                 x + NODE_RADIUS, y + NODE_RADIUS)
        c.coords(self._node_letters[node_id], x, y)
      else:
        points = []
        for dx, dy in HOUSE_SHAPE:
          points.extend((x + dx, y + dy))
        c.coords(self._node_shapes[node_id], *points)
        # A small roof tile doubles as the chimney.
        c.coords(self._node_letters[node_id], x + 6, y - 16, x + 10, y - 8)
      c.coords(self._node_labels[node_id], x, y + NODE_RADIUS + 10)
    for key, item in self._link_items.items():
      ax, ay = self.screen[key[0]]
      bx, by = self.screen[key[1]]
      c.coords(item, ax, ay, bx, by)
      c.coords(self._link_marks[key], (ax + bx) / 2, (ay + by) / 2)
    self.geometry_dirty = False
    self.geometry_version += 1

  # -- hit testing -------------------------------------------------------

  def node_at(self, sx, sy):
    best = None
    best_distance = NODE_RADIUS + 6
    for node_id, (x, y) in self.screen.items():
      d = ((x - sx) ** 2 + (y - sy) ** 2) ** 0.5
      if d <= best_distance:
        best, best_distance = node_id, d
    return best

  def link_at(self, sx, sy, tolerance=8):
    best = None
    best_distance = tolerance
    for key in self._link_items:
      ax, ay = self.screen[key[0]]
      bx, by = self.screen[key[1]]
      d = point_segment_distance(sx, sy, ax, ay, bx, by)
      if d <= best_distance:
        best, best_distance = key, d
    return best

  # -- per-frame drawing -------------------------------------------------

  def render(self, sim, now, sender=None, receiver=None, selected=None):
    if self.network is None:
      return
    if self.geometry_dirty:
      self._layout()
    self._style_links()
    self._style_nodes(sim)
    self._draw_traffic(sim, now)
    self._draw_way(sim, receiver)
    self._draw_rings(sender, receiver, selected)
    self._draw_puffs(sim, now)

  def _style_links(self):
    c = self.canvas
    for key, link in self.network.links.items():
      style = (link.up, key == self.hover_link)
      if self._link_style.get(key) == style:
        continue
      self._link_style[key] = style
      item = self._link_items[key]
      if link.up:
        width = {1: 5, 2: 3}.get(link.interval, 2)
        colour = theme.CABLE_HOVER if style[1] else theme.CABLE
        c.itemconfigure(item, fill=colour, width=width + (2 if style[1] else 0), dash=())
        c.itemconfigure(self._link_marks[key], state=tk.HIDDEN)
      else:
        c.itemconfigure(item, fill=theme.CABLE_HOVER if style[1] else theme.CABLE_CUT,
                        width=3, dash=(7, 6))
        c.itemconfigure(self._link_marks[key], state=tk.NORMAL)

  def _style_nodes(self, sim):
    c = self.canvas
    for node_id, node in self.network.nodes.items():
      if node.kind != ROUTER:
        continue
      level = round(sim.node_load(node_id) * LOAD_STEPS)
      if self._node_fill.get(node_id) != level:
        self._node_fill[node_id] = level
        colour = mix_color(theme.ROUTER_CALM, theme.ROUTER_BUSY, level / LOAD_STEPS)
        c.itemconfigure(self._node_shapes[node_id], fill=colour)

  def _draw_traffic(self, sim, now):
    screen = self.screen
    env_used = 0
    dot_used = 0
    grown = False
    for (a, b), lane in sim.transits.items():
      if not lane:
        continue
      ax, ay = screen[a]
      bx, by = screen[b]
      ux, uy, nx, ny, length = unit_and_normal(ax, ay, bx, by)
      start = NODE_RADIUS
      span = max(0.0, length - 2 * NODE_RADIUS)
      ox = nx * LANE_OFFSET
      oy = ny * LANE_OFFSET
      for transit in lane:
        duration = transit.arrive - transit.depart
        p = (now - transit.depart) / duration if duration > 0 else 1.0
        p = 0.0 if p < 0 else (1.0 if p > 1 else p)
        d = start + span * p
        env_used, dot_used, g = self._place(transit.packet, ax + ux * d + ox, ay + uy * d + oy,
                                            env_used, dot_used)
        grown = grown or g
    for (a, b), queue in sim.queues.items():
      if not queue:
        continue
      ax, ay = screen[a]
      bx, by = screen[b]
      ux, uy, nx, ny, length = unit_and_normal(ax, ay, bx, by)
      limit = length * 0.5
      ox = nx * (LANE_OFFSET + 6)
      oy = ny * (LANE_OFFSET + 6)
      d = NODE_RADIUS + 4
      for packet in queue:
        # Envelopes wait in a line, each one as long as its label.
        half = _envelope_half(packet) if _is_letter(packet) else QUEUE_SPACING / 2
        d += half
        if d > limit:
          break
        env_used, dot_used, g = self._place(packet, ax + ux * d + ox, ay + uy * d + oy,
                                            env_used, dot_used)
        grown = grown or g
        d += half + 2
    self._envelopes_shown = self._hide_rest(self._envelopes, env_used, self._envelopes_shown, 2)
    self._dots_shown = self._hide_rest(self._dots, dot_used, self._dots_shown, 1)
    if grown:
      self.canvas.tag_raise("node")
      self.canvas.tag_raise("ring")

  def _place(self, packet, x, y, env_used, dot_used):
    c = self.canvas
    grown = False
    if _is_letter(packet):
      if env_used == len(self._envelopes):
        rect = c.create_rectangle(0, 0, 0, 0, outline=theme.ENVELOPE_EDGE, width=1.5,
                                  fill=theme.ENVELOPE, tags=("packet",))
        text = c.create_text(0, 0, text="", fill=theme.INK, font=theme.FONT_ENVELOPE, tags=("packet",))
        self._envelopes.append([rect, text, True, None])
        grown = True
      sprite = self._envelopes[env_used]
      half = _envelope_half(packet)
      c.coords(sprite[0], x - half, y - 9, x + half, y + 9)
      c.coords(sprite[1], x, y)
      if not sprite[2]:
        c.itemconfigure(sprite[0], state=tk.NORMAL)
        c.itemconfigure(sprite[1], state=tk.NORMAL)
        sprite[2] = True
      look = (packet.chunk, packet.resent)
      if sprite[3] != look:
        sprite[3] = look
        c.itemconfigure(sprite[0], fill=theme.ENVELOPE_RESENT if packet.resent else theme.ENVELOPE)
        c.itemconfigure(sprite[1], text=packet.chunk.replace(" ", "·"))
      return env_used + 1, dot_used, grown

    if dot_used == len(self._dots):
      oval = c.create_oval(0, 0, 0, 0, outline="", fill=theme.BACKGROUND_DOT, tags=("packet",))
      self._dots.append([oval, True, None])
      grown = True
    sprite = self._dots[dot_used]
    if packet.background:
      colour = theme.BACKGROUND_DOT if packet.kind == DATA else theme.BACKGROUND_ACK
      r = 3.5 if packet.kind == DATA else 2.5
    else:
      colour = theme.ACK_DOT
      r = 4.5
    c.coords(sprite[0], x - r, y - r, x + r, y + r)
    if not sprite[1]:
      c.itemconfigure(sprite[0], state=tk.NORMAL)
      sprite[1] = True
    if sprite[2] != colour:
      sprite[2] = colour
      c.itemconfigure(sprite[0], fill=colour)
    return env_used, dot_used + 1, grown

  def _hide_rest(self, pool, used, shown, parts):
    c = self.canvas
    for index in range(used, min(shown, len(pool))):
      sprite = pool[index]
      if sprite[parts]:
        for part in range(parts):
          c.itemconfigure(sprite[part], state=tk.HIDDEN)
        sprite[parts] = False
    return used

  def _draw_way(self, sim, receiver):
    signature = (self.show_way, receiver, self.geometry_version, sim.routing.rounds, id(sim),
                 sim.link_version)
    if signature == self._arrow_signature:
      return
    self._arrow_signature = signature
    c = self.canvas
    for node_id, item in self._arrows.items():
      hop = None
      if self.show_way and receiver is not None and node_id != receiver:
        hop = sim.routing.next_hop(node_id, receiver)
      if hop is None or hop not in self.screen:
        c.itemconfigure(item, state=tk.HIDDEN)
        continue
      ax, ay = self.screen[node_id]
      bx, by = self.screen[hop]
      ux, uy, nx, ny, length = unit_and_normal(ax, ay, bx, by)
      begin = NODE_RADIUS + 3
      end = min(length * 0.45, NODE_RADIUS + 44)
      if end <= begin:
        c.itemconfigure(item, state=tk.HIDDEN)
        continue
      c.coords(item, ax + ux * begin - nx * 10, ay + uy * begin - ny * 10,
               ax + ux * end - nx * 10, ay + uy * end - ny * 10)
      c.itemconfigure(item, state=tk.NORMAL)

  def _draw_rings(self, sender, receiver, selected):
    c = self.canvas
    for role, node_id, radius in (("from", sender, NODE_RADIUS + 7),
                                  ("to", receiver, NODE_RADIUS + 7),
                                  ("select", selected, NODE_RADIUS + 12)):
      item = self._rings[role]
      if node_id is None or node_id not in self.screen:
        c.itemconfigure(item, state=tk.HIDDEN)
        continue
      x, y = self.screen[node_id]
      c.coords(item, x - radius, y - radius, x + radius, y + radius)
      c.itemconfigure(item, state=tk.NORMAL)

  def _draw_puffs(self, sim, now):
    c = self.canvas
    vp = self.viewport
    used = 0
    for tick, x, y, _reason in reversed(sim.drop_marks):
      age = now - tick
      if age > PUFF_TICKS:
        break
      if used == len(self._puffs):
        self._puffs.append([c.create_oval(0, 0, 0, 0, outline=theme.DROP_PUFF, width=2,
                                          tags=("ring",)), True])
      sprite = self._puffs[used]
      sx, sy = vp.to_screen(x, y)
      r = 5 + max(0.0, age) * 2.4
      c.coords(sprite[0], sx - r, sy - r, sx + r, sy + r)
      if not sprite[1]:
        c.itemconfigure(sprite[0], state=tk.NORMAL)
        sprite[1] = True
      used += 1
    self._puffs_shown = self._hide_rest(self._puffs, used, self._puffs_shown, 1)

class Legend:
  """A thin strip under the map that explains the little shapes."""

  def __init__(self, canvas, tr):
    self.canvas = canvas
    self.tr = tr
    c = canvas
    self._texts = []
    x = 12
    y = 13
    c.create_rectangle(x, y - 7, x + 22, y + 7, fill=theme.ENVELOPE, outline=theme.ENVELOPE_EDGE, width=1.5)
    c.create_text(x + 11, y, text="ab", font=theme.FONT_TINY, fill=theme.INK)
    self._texts.append(("legend_data", c.create_text(x + 30, y, anchor=tk.W, font=theme.FONT_SMALL,
                                                     fill=theme.INK_SOFT)))
    self._samples = [
      c.create_oval(0, 0, 0, 0, fill=theme.ACK_DOT, outline=""),
      c.create_oval(0, 0, 0, 0, fill=theme.BACKGROUND_DOT, outline=""),
      c.create_line(0, 0, 0, 0, fill=theme.CABLE_CUT, width=3, dash=(5, 4)),
    ]
    for key in ("legend_ack", "legend_other", "legend_cut"):
      self._texts.append((key, c.create_text(0, y, anchor=tk.W, font=theme.FONT_SMALL,
                                             fill=theme.INK_SOFT)))
    self.refresh()

  def refresh(self):
    c = self.canvas
    y = 13
    for key, item in self._texts:
      c.itemconfigure(item, text=self.tr.t(key))
    # Lay the entries out one after another, whatever their text length.
    x = c.bbox(self._texts[0][1])[2] + 24
    for sample, (_, text_item) in zip(self._samples, self._texts[1:]):
      if c.type(sample) == "line":
        c.coords(sample, x, y, x + 22, y)
        text_x = x + 30
      else:
        c.coords(sample, x + 2, y - 5, x + 12, y + 5)
        text_x = x + 18
      c.coords(text_item, text_x, y)
      x = c.bbox(text_item)[2] + 24
