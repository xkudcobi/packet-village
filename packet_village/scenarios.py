"""Hand-made towns that ship with the program.

Coordinates live in a 1000 x 640 world; the window scales it to fit.
"""

import math

from .topology import HOUSE, ROUTER, Network

WORLD_WIDTH = 1000
WORLD_HEIGHT = 640

class Scenario:
  __slots__ = ("key", "title_key", "blurb_key", "build", "sender", "receiver", "chatter")

  def __init__(self, key, build, sender, receiver, chatter=0.2):
    self.key = key
    self.title_key = "sc_" + key
    self.blurb_key = "sc_" + key + "_blurb"
    self.build = build
    self.sender = sender
    self.receiver = receiver
    self.chatter = chatter

def _house(net, name, x, y, router, delay=2):
  node_id = name.lower()
  net.add_node(node_id, HOUSE, name, x, y)
  net.add_link(node_id, router, delay=delay, interval=1)

def _router(net, tag, x, y):
  net.add_node(tag, ROUTER, tag, x, y)

def build_village():
  net = Network()
  for tag, x, y in (("A", 290, 210), ("B", 510, 130), ("C", 730, 220),
                    ("D", 400, 420), ("E", 660, 440)):
    _router(net, tag, x, y)
  for a, b, delay in (("A", "B", 4), ("B", "C", 4), ("A", "D", 4),
                      ("D", "E", 5), ("C", "E", 4), ("B", "D", 6)):
    net.add_link(a, b, delay=delay)
  _house(net, "Ada", 110, 120, "A")
  _house(net, "Deniz", 120, 330, "A")
  _house(net, "Leyla", 510, 30, "B")
  _house(net, "Mert", 900, 130, "C")
  _house(net, "Kerem", 330, 570, "D")
  _house(net, "Elif", 860, 540, "E")
  return net

def build_bridges():
  net = Network()
  for tag, x, y in (("A", 200, 220), ("B", 360, 330), ("C", 640, 330),
                    ("D", 800, 220), ("E", 500, 560)):
    _router(net, tag, x, y)
  net.add_link("A", "B", delay=3)
  net.add_link("C", "D", delay=3)
  # The bridge is short but only lets one envelope in every three steps.
  net.add_link("B", "C", delay=4, interval=3)
  # The detour through the valley is wide but long.
  net.add_link("A", "E", delay=10)
  net.add_link("E", "D", delay=10)
  _house(net, "Can", 70, 120, "A")
  _house(net, "Ece", 90, 360, "A")
  _house(net, "Ada", 300, 470, "B")
  _house(net, "Nil", 700, 470, "C")
  _house(net, "Oya", 930, 120, "D")
  _house(net, "Umut", 920, 360, "D")
  return net

def build_ring():
  net = Network()
  names = ("Arda", "Mina", "Ozan", "Defne", "Emre", "Selin", "Toprak", "Yaren")
  cx, cy, radius = WORLD_WIDTH / 2, WORLD_HEIGHT / 2, 200
  count = len(names)
  tags = [chr(ord("A") + i) for i in range(count)]
  for i, tag in enumerate(tags):
    angle = -math.pi / 2 + 2 * math.pi * i / count
    _router(net, tag, cx + radius * math.cos(angle) * 1.35, cy + radius * math.sin(angle))
  for i, tag in enumerate(tags):
    net.add_link(tag, tags[(i + 1) % count], delay=4)
  for i, name in enumerate(names):
    angle = -math.pi / 2 + 2 * math.pi * i / count
    x = cx + (radius + 95) * math.cos(angle) * 1.35
    y = cy + (radius + 95) * math.sin(angle)
    _house(net, name, min(max(x, 40), WORLD_WIDTH - 40), min(max(y, 30), WORLD_HEIGHT - 30), tags[i])
  return net

def build_grid():
  net = Network()
  cols, rows = 4, 3
  x0, y0, dx, dy = 230, 150, 180, 170
  for r in range(rows):
    for c in range(cols):
      _router(net, chr(ord("A") + r * cols + c), x0 + c * dx, y0 + r * dy)

  def tag(r, c):
    return chr(ord("A") + r * cols + c)

  for r in range(rows):
    for c in range(cols):
      if c + 1 < cols:
        net.add_link(tag(r, c), tag(r, c + 1), delay=3)
      if r + 1 < rows:
        net.add_link(tag(r, c), tag(r + 1, c), delay=3)
  _house(net, "Ada", 80, 90, tag(0, 0))
  _house(net, "Can", 80, 330, tag(1, 0))
  _house(net, "Ece", 80, 560, tag(2, 0))
  _house(net, "Mert", 500, 40, tag(0, 1))
  _house(net, "Nil", 590, 600, tag(2, 2))
  _house(net, "Oya", 930, 90, tag(0, 3))
  _house(net, "Umut", 930, 330, tag(1, 3))
  _house(net, "Zeynep", 930, 560, tag(2, 3))
  return net

SCENARIOS = (
  Scenario("village", build_village, "ada", "elif", chatter=0.25),
  Scenario("bridges", build_bridges, "can", "oya", chatter=0.45),
  Scenario("ring", build_ring, "arda", "emre", chatter=0.2),
  Scenario("grid", build_grid, "ada", "zeynep", chatter=0.6),
)

DEFAULT_SCENARIO = "village"

def get_scenario(key):
  for scenario in SCENARIOS:
    if scenario.key == key:
      return scenario
  return None

def scenario_keys():
  return [s.key for s in SCENARIOS]
