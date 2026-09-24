"""How each post office learns which way to send an envelope.

Every node runs a small distance-vector protocol: it only knows what its
direct neighbours told it during the previous exchange. When a cable is
cut, the ends notice at once, but everybody else has to hear the news
second hand, round after round. That slow healing is what the town shows
on screen, and it is also why the protocol uses poisoned reverse: a node
never advertises a route back to the neighbour it learned it from.

A plain Dijkstra is included as the ground truth the protocol should
converge to; tests and the "is the map settled?" check both use it.
"""

import heapq

# Any cost at or above this counts as "unreachable". Keeping it small
# bounds how long a count-to-infinity episode can last.
INFINITY = 64

class DistanceVectorRouting:
  def __init__(self, network):
    self.network = network
    self.tables = {}
    self.rounds = 0
    self.last_changes = 0
    self.reset()

  def reset(self):
    """Forget everything: every node only knows how to reach itself."""
    self.tables = {node_id: {node_id: (0, node_id)} for node_id in self.network.nodes}
    self.rounds = 0
    self.last_changes = 0

  # TODO: carry route updates as real packets on the cables, so that a
  # congested or noisy town also slows down how fast the map heals.
  def exchange(self):
    """Run one synchronous round; return how many entries changed."""
    old = self.tables
    new = {}
    changes = 0
    for node_id in self.network.nodes:
      current = old.get(node_id, {})
      table = {node_id: (0, node_id)}
      for neighbor, link in self.network.neighbors(node_id):
        vector = old.get(neighbor)
        if not vector:
          continue
        for dest, (cost, hop) in vector.items():
          # Poisoned reverse: the neighbour routes through us, so for us
          # that advertisement is worthless.
          if dest == node_id or hop == node_id:
            continue
          total = cost + link.delay
          if total >= INFINITY:
            continue
          best = table.get(dest)
          if best is None or total < best[0]:
            table[dest] = (total, neighbor)
          elif total == best[0] and current.get(dest, (0, None))[1] == neighbor:
            # Equal cost: stick with the old choice to avoid flapping.
            table[dest] = (total, neighbor)
      if table != current:
        for dest in table.keys() | current.keys():
          if table.get(dest) != current.get(dest):
            changes += 1
      new[node_id] = table
    self.tables = new
    self.rounds += 1
    self.last_changes = changes
    return changes

  def converge(self, max_rounds=500):
    """Exchange until nothing changes; return the number of rounds used."""
    for used in range(1, max_rounds + 1):
      if self.exchange() == 0:
        return used
    return max_rounds

  def link_changed(self, a, b):
    """The two ends of a cable notice a cut immediately."""
    link = self.network.link(a, b)
    if link is not None and link.up:
      return
    for here, there in ((a, b), (b, a)):
      table = self.tables.get(here)
      if table is None:
        continue
      stale = [dest for dest, (_, hop) in table.items() if hop == there and dest != here]
      for dest in stale:
        del table[dest]

  def sync_nodes(self):
    """Adopt added nodes and forget removed ones."""
    nodes = self.network.nodes
    for node_id in list(self.tables):
      if node_id not in nodes:
        del self.tables[node_id]
    for node_id in nodes:
      self.tables.setdefault(node_id, {node_id: (0, node_id)})
    for table in self.tables.values():
      for dest in [d for d, (_, hop) in table.items() if d not in nodes or hop not in nodes]:
        del table[dest]

  # -- lookups -----------------------------------------------------------

  def next_hop(self, node_id, dest):
    if node_id == dest:
      return None
    entry = self.tables.get(node_id, {}).get(dest)
    return entry[1] if entry else None

  def cost(self, node_id, dest):
    entry = self.tables.get(node_id, {}).get(dest)
    return entry[0] if entry else None

  def path(self, src, dst, limit=128):
    """Follow next hops from src; return (nodes, reached_destination)."""
    nodes = [src]
    seen = {src}
    current = src
    while current != dst and len(nodes) < limit:
      hop = self.next_hop(current, dst)
      if hop is None or hop in seen:
        return nodes, False
      nodes.append(hop)
      seen.add(hop)
      current = hop
    return nodes, current == dst

  def matches(self):
    """True when every table agrees with Dijkstra on the current map."""
    for node_id in self.network.nodes:
      expected = shortest_costs(self.network, node_id)
      table = self.tables.get(node_id, {})
      if {d: c for d, c in expected.items() if c < INFINITY} != {d: c for d, (c, _) in table.items()}:
        return False
    return True

def shortest_costs(network, source):
  """Dijkstra over working cables, weighted by cable delay."""
  if source not in network.nodes:
    return {}
  dist = {source: 0}
  heap = [(0, source)]
  while heap:
    cost, node_id = heapq.heappop(heap)
    if cost > dist[node_id]:
      continue
    for neighbor, link in network.neighbors(node_id):
      total = cost + link.delay
      if total < dist.get(neighbor, float("inf")):
        dist[neighbor] = total
        heapq.heappush(heap, (total, neighbor))
  return dist
