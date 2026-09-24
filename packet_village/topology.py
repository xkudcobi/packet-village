"""The town map: houses, post offices and the cables that join them.

Everything here is plain data plus a few graph helpers. It knows nothing
about packets, timing or drawing, so it can be tested on its own.
"""

from collections import deque

HOUSE = "house"
ROUTER = "router"
NODE_KINDS = (HOUSE, ROUTER)

MAX_DELAY = 60
MAX_INTERVAL = 20

class TopologyError(ValueError):
  """Raised when an edit would leave the map in an impossible state."""

def link_key(a, b):
  """Cables are two-way; both orientations share one key."""
  return (a, b) if a <= b else (b, a)

class Node:
  __slots__ = ("id", "kind", "name", "x", "y")

  def __init__(self, node_id, kind, name, x, y):
    if not isinstance(node_id, str) or not node_id:
      raise TopologyError("node id must be a non-empty string")
    if kind not in NODE_KINDS:
      raise TopologyError(f"unknown node kind: {kind!r}")
    self.id = node_id
    self.kind = kind
    self.name = str(name)
    self.x = float(x)
    self.y = float(y)

  @property
  def is_house(self):
    return self.kind == HOUSE

  def to_dict(self):
    return {
      "id": self.id,
      "kind": self.kind,
      "name": self.name,
      "x": round(self.x, 1),
      "y": round(self.y, 1),
    }

class Link:
  """A two-way cable.

  delay    -- ticks a packet needs to travel from one end to the other
  interval -- ticks between two packets entering the cable (its width)
  loss     -- chance that a packet gets garbled on the way (0..1)
  """

  __slots__ = ("a", "b", "delay", "interval", "loss", "up")

  def __init__(self, a, b, delay=4, interval=1, loss=0.0, up=True):
    if a == b:
      raise TopologyError("a cable needs two different ends")
    delay = int(delay)
    interval = int(interval)
    loss = float(loss)
    if not 1 <= delay <= MAX_DELAY:
      raise TopologyError(f"delay must be between 1 and {MAX_DELAY}")
    if not 1 <= interval <= MAX_INTERVAL:
      raise TopologyError(f"interval must be between 1 and {MAX_INTERVAL}")
    if not 0.0 <= loss < 1.0:
      raise TopologyError("loss must be in [0, 1)")
    self.a = a
    self.b = b
    self.delay = delay
    self.interval = interval
    self.loss = loss
    self.up = bool(up)

  @property
  def key(self):
    return link_key(self.a, self.b)

  def other(self, node_id):
    if node_id == self.a:
      return self.b
    if node_id == self.b:
      return self.a
    raise TopologyError(f"{node_id!r} is not an end of this cable")

  def to_dict(self):
    data = {"a": self.a, "b": self.b, "delay": self.delay, "interval": self.interval}
    if self.loss:
      data["loss"] = self.loss
    if not self.up:
      data["up"] = False
    return data

class Network:
  """Nodes and cables with an adjacency index kept in sync."""

  def __init__(self):
    self.nodes = {}
    self.links = {}
    self._adj = {}

  # -- editing -----------------------------------------------------------

  def add_node(self, node_id, kind, name, x, y):
    if node_id in self.nodes:
      raise TopologyError(f"duplicate node id: {node_id!r}")
    node = Node(node_id, kind, name, x, y)
    self.nodes[node_id] = node
    self._adj[node_id] = {}
    return node

  def remove_node(self, node_id):
    if node_id not in self.nodes:
      raise TopologyError(f"unknown node: {node_id!r}")
    for neighbor in list(self._adj[node_id]):
      self.remove_link(node_id, neighbor)
    del self._adj[node_id]
    del self.nodes[node_id]

  def add_link(self, a, b, delay=4, interval=1, loss=0.0, up=True):
    for end in (a, b):
      if end not in self.nodes:
        raise TopologyError(f"unknown node: {end!r}")
    key = link_key(a, b)
    if key in self.links:
      raise TopologyError(f"cable {a}-{b} already exists")
    link = Link(key[0], key[1], delay, interval, loss, up)
    self.links[key] = link
    self._adj[a][b] = link
    self._adj[b][a] = link
    return link

  def remove_link(self, a, b):
    key = link_key(a, b)
    if key not in self.links:
      raise TopologyError(f"no cable between {a!r} and {b!r}")
    del self.links[key]
    del self._adj[a][b]
    del self._adj[b][a]

  # -- queries -----------------------------------------------------------

  def link(self, a, b):
    return self.links.get(link_key(a, b))

  def neighbors(self, node_id, only_up=True):
    """Yield (neighbor_id, link) pairs in a stable order."""
    for neighbor, link in self._adj[node_id].items():
      if link.up or not only_up:
        yield neighbor, link

  def degree(self, node_id, only_up=False):
    return sum(1 for _ in self.neighbors(node_id, only_up))

  def houses(self):
    return [n.id for n in self.nodes.values() if n.kind == HOUSE]

  def routers(self):
    return [n.id for n in self.nodes.values() if n.kind == ROUTER]

  def reachable_from(self, start):
    """Every node reachable from start over working cables (BFS)."""
    if start not in self.nodes:
      return set()
    seen = {start}
    todo = deque([start])
    while todo:
      current = todo.popleft()
      for neighbor, _ in self.neighbors(current):
        if neighbor not in seen:
          seen.add(neighbor)
          todo.append(neighbor)
    return seen

  def is_connected(self, a, b):
    return b in self.reachable_from(a)

  # -- serialisation -----------------------------------------------------

  def to_dict(self):
    return {
      "nodes": [n.to_dict() for n in self.nodes.values()],
      "links": [l.to_dict() for l in self.links.values()],
    }

  @classmethod
  def from_dict(cls, data):
    if not isinstance(data, dict):
      raise TopologyError("town data must be an object")
    net = cls()
    try:
      for raw in data["nodes"]:
        net.add_node(raw["id"], raw["kind"], raw.get("name", raw["id"]), raw["x"], raw["y"])
      for raw in data["links"]:
        net.add_link(
          raw["a"], raw["b"],
          delay=raw.get("delay", 4),
          interval=raw.get("interval", 1),
          loss=raw.get("loss", 0.0),
          up=raw.get("up", True),
        )
    except (KeyError, TypeError, ValueError) as exc:
      if isinstance(exc, TopologyError):
        raise
      raise TopologyError(f"malformed town data: {exc}") from exc
    return net

  def copy(self):
    return Network.from_dict(self.to_dict())
