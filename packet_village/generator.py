"""Builds a fresh, always-connected random town.

Post offices are scattered with a minimum spacing, tied together by a
minimum spanning tree (so nobody is cut off from the start) and then given
a few extra short cables so there is usually more than one way around.
Houses hang off the post offices, pushed outwards where there is room.
"""

import math
import random

from .geometry import point_segment_distance
from .scenarios import WORLD_HEIGHT, WORLD_WIDTH
from .topology import HOUSE, ROUTER, Network

HOUSE_NAMES = (
  "Ada", "Arda", "Aslı", "Baran", "Berk", "Can", "Cem", "Defne", "Deniz",
  "Ece", "Elif", "Emre", "Eren", "Ilgın", "Kaan", "Kerem", "Leyla", "Mert",
  "Mina", "Nil", "Oya", "Ozan", "Selin", "Sena", "Toprak", "Umut", "Yaren",
  "Zeynep",
)

MARGIN_X = 130
MARGIN_Y = 100

def _distance(p, q):
  return math.hypot(p[0] - q[0], p[1] - q[1])

def _scatter(rng, count, min_gap):
  points = []
  gap = min_gap
  attempts = 0
  while len(points) < count:
    candidate = (rng.uniform(MARGIN_X, WORLD_WIDTH - MARGIN_X),
                 rng.uniform(MARGIN_Y, WORLD_HEIGHT - MARGIN_Y))
    if all(_distance(candidate, p) >= gap for p in points):
      points.append(candidate)
    attempts += 1
    if attempts % 400 == 0:
      # The world is crowded; relax the spacing a little and keep going.
      gap *= 0.85
  return points

def _spanning_tree(points):
  """Prim's algorithm on the complete euclidean graph; returns index pairs."""
  count = len(points)
  if count < 2:
    return []
  in_tree = [False] * count
  best = [math.inf] * count
  parent = [-1] * count
  best[0] = 0.0
  edges = []
  for _ in range(count):
    current = min((i for i in range(count) if not in_tree[i]), key=lambda i: best[i])
    in_tree[current] = True
    if parent[current] >= 0:
      edges.append((parent[current], current))
    for other in range(count):
      if not in_tree[other]:
        d = _distance(points[current], points[other])
        if d < best[other]:
          best[other] = d
          parent[other] = current
  return edges

def _cable_delay(p, q):
  return max(2, round(_distance(p, q) / 45))

def random_town(seed=None, routers=7, houses=8):
  if routers < 2 or houses < 2:
    raise ValueError("a town needs at least two post offices and two houses")
  if houses > len(HOUSE_NAMES):
    raise ValueError(f"at most {len(HOUSE_NAMES)} houses are supported")
  rng = random.Random(seed)
  net = Network()
  points = _scatter(rng, routers, min_gap=170)
  tags = [chr(ord("A") + i) for i in range(routers)]
  for tag, (x, y) in zip(tags, points):
    net.add_node(tag, ROUTER, tag, x, y)

  tree = _spanning_tree(points)
  for i, j in tree:
    net.add_link(tags[i], tags[j], delay=_cable_delay(points[i], points[j]))

  # Extra cables: link each post office to its nearest unconnected
  # neighbour when that is not much longer than a typical tree edge.
  lengths = sorted(_distance(points[i], points[j]) for i, j in tree)
  typical = lengths[len(lengths) // 2]
  for i in rng.sample(range(routers), routers):
    if net.degree(tags[i]) >= 4:
      continue
    options = sorted(
      (j for j in range(routers) if j != i and net.link(tags[i], tags[j]) is None),
      key=lambda j: _distance(points[i], points[j]),
    )
    for j in options[:1]:
      if _distance(points[i], points[j]) < typical * 1.7 and net.degree(tags[j]) < 4 and rng.random() < 0.75:
        interval = 2 if rng.random() < 0.2 else 1
        net.add_link(tags[i], tags[j], delay=_cable_delay(points[i], points[j]), interval=interval)

  centre = (WORLD_WIDTH / 2, WORLD_HEIGHT / 2)
  cables = [(net.nodes[l.a].x, net.nodes[l.a].y, net.nodes[l.b].x, net.nodes[l.b].y)
            for l in net.links.values()]
  names = rng.sample(HOUSE_NAMES, houses)
  placed = list(points)
  load = [0] * routers
  for name in names:
    # Spread houses over the post offices, least crowded first.
    lowest = min(load)
    index = rng.choice([i for i in range(routers) if load[i] == lowest])
    load[index] += 1
    position = _place_house(rng, points[index], centre, placed, cables)
    placed.append(position)
    node_id = name.lower()
    net.add_node(node_id, HOUSE, name, *position)
    net.add_link(node_id, tags[index], delay=2)
  return net

def _place_house(rng, anchor, centre, placed, cables):
  """Pick a spot near anchor that keeps clear of other nodes and cables."""
  outward = math.atan2(anchor[1] - centre[1], anchor[0] - centre[0])
  best = None
  best_score = -math.inf
  for attempt in range(40):
    angle = outward + rng.uniform(-math.pi, math.pi) * min(1.0, 0.3 + attempt / 30)
    reach = rng.uniform(85, 120)
    x = min(max(anchor[0] + reach * math.cos(angle), 40), WORLD_WIDTH - 40)
    y = min(max(anchor[1] + reach * math.sin(angle), 30), WORLD_HEIGHT - 30)
    node_gap = min(_distance((x, y), p) for p in placed)
    cable_gap = min((point_segment_distance(x, y, *c) for c in cables), default=math.inf)
    if node_gap >= 80 and cable_gap >= 45:
      return (x, y)
    # Otherwise remember the least cramped spot, weighting cables higher.
    score = min(node_gap / 80, cable_gap / 45)
    if score > best_score:
      best, best_score = (x, y), score
  return best
