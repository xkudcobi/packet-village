"""The simulation: one place that owns every moving part of the town.

Time advances in whole ticks. During a tick the engine

1. lets the post offices swap route news (every few ticks),
2. lands envelopes that finished crossing a cable,
3. asks every conversation whether it wants to send or resend something,
4. pushes the next waiting envelope into each free cable,
5. maybe starts some background chatter between random houses.

The user interface never changes this state directly; it calls the
methods below and reads the results.
"""

import random
from collections import deque

from .packets import ACK, DATA, PacketFactory
from .routing import DistanceVectorRouting
from .topology import HOUSE
from .transport import FAILED, SENDING, Flow

DROP_REASONS = ("queue", "noise", "no_route", "ttl", "cut")

# Characters used for background chatter; nobody reads these letters.
_CHATTER_ALPHABET = "abcdefghijklmnopqrstuvwxyz"

class SimulationError(Exception):
  """A user-facing problem; `key` names the message in the string table."""

  def __init__(self, key, **params):
    super().__init__(key)
    self.key = key
    self.params = params

class SimConfig:
  __slots__ = ("queue_size", "chunk_size", "routing_interval", "chatter",
               "noise", "ttl", "max_background")

  def __init__(self, queue_size=8, chunk_size=3, routing_interval=3, chatter=0.0,
               noise=0.0, ttl=32, max_background=8):
    self.queue_size = queue_size
    self.chunk_size = chunk_size
    self.routing_interval = routing_interval
    self.chatter = chatter
    self.noise = noise
    self.ttl = ttl
    self.max_background = max_background

class Stats:
  __slots__ = ("sent", "retransmits", "delivered_packets", "trip_total",
               "messages_started", "messages_delivered", "messages_failed",
               "message_time_total", "drops")

  def __init__(self):
    self.reset()

  def reset(self):
    self.sent = 0
    self.retransmits = 0
    self.delivered_packets = 0
    self.trip_total = 0
    self.messages_started = 0
    self.messages_delivered = 0
    self.messages_failed = 0
    self.message_time_total = 0
    self.drops = {reason: 0 for reason in DROP_REASONS}

  @property
  def dropped(self):
    return sum(self.drops.values())

  @property
  def average_trip(self):
    return self.trip_total / self.delivered_packets if self.delivered_packets else None

  @property
  def average_message_time(self):
    return self.message_time_total / self.messages_delivered if self.messages_delivered else None

class Transit:
  """An envelope currently travelling along one direction of a cable."""

  __slots__ = ("packet", "depart", "arrive")

  def __init__(self, packet, depart, arrive):
    self.packet = packet
    self.depart = depart
    self.arrive = arrive

class Simulation:
  def __init__(self, network, config=None, seed=None, warm=True):
    self.network = network
    self.config = config or SimConfig()
    self.rng = random.Random(seed)
    self.routing = DistanceVectorRouting(network)
    self.factory = PacketFactory(self.config.ttl)
    self.tick = 0
    self.flows = {}
    self.finished = deque(maxlen=32)
    self.last_foreground = None
    self.stats = Stats()
    self.events = deque(maxlen=200)
    self.event_serial = 0
    self.drop_marks = deque(maxlen=96)
    self.queues = {}
    self.transits = {}
    self.busy_until = {}
    self._next_flow_id = 1
    self.link_version = 0
    self._healing_since = None
    self._scratch = []
    for link in network.links.values():
      for direction in ((link.a, link.b), (link.b, link.a)):
        self.queues[direction] = deque()
        self.transits[direction] = deque()
        self.busy_until[direction] = 0
    if warm:
      # Start with a settled map so the first letter does not wander blind.
      self.routing.converge()

  # -- public actions ----------------------------------------------------

  def send_message(self, src, dst, text, background=False):
    nodes = self.network.nodes
    if src not in nodes or dst not in nodes:
      raise SimulationError("err_unknown_house")
    if src == dst:
      raise SimulationError("err_same_house")
    if not text or not text.strip():
      raise SimulationError("err_empty_message")
    flow = Flow(self._next_flow_id, src, dst, text, self.config.chunk_size,
                self.tick, self.factory, background=background)
    self._next_flow_id += 1
    self.flows[flow.flow_id] = flow
    self.stats.messages_started += 1
    if not background:
      self.last_foreground = flow
      self._event("ev_sent", flow=flow.flow_id, src=src, dst=dst, pieces=flow.total)
    return flow

  def set_link_up(self, a, b, up):
    link = self.network.link(a, b)
    if link is None:
      raise SimulationError("err_no_cable")
    if link.up == bool(up):
      return
    link.up = bool(up)
    self.link_version += 1
    if up:
      self._event("ev_repair", a=link.a, b=link.b)
    else:
      lost = 0
      for direction in ((link.a, link.b), (link.b, link.a)):
        start, end = self.network.nodes[direction[0]], self.network.nodes[direction[1]]
        for transit in self.transits[direction]:
          p = self._progress(transit, self.tick)
          self._mark(start.x + (end.x - start.x) * p, start.y + (end.y - start.y) * p, "cut")
        lost += len(self.queues[direction]) + len(self.transits[direction])
        self.queues[direction].clear()
        self.transits[direction].clear()
        self.busy_until[direction] = self.tick
      self.stats.drops["cut"] += lost
      self.routing.link_changed(link.a, link.b)
      self._event("ev_cut", a=link.a, b=link.b, lost=lost)
    self._healing_since = self.routing.rounds

  def toggle_link(self, a, b):
    link = self.network.link(a, b)
    if link is None:
      raise SimulationError("err_no_cable")
    self.set_link_up(a, b, not link.up)
    return link.up

  def repair_all(self):
    repaired = 0
    for link in self.network.links.values():
      if not link.up:
        self.set_link_up(link.a, link.b, True)
        repaired += 1
    return repaired

  def reset_stats(self):
    self.stats.reset()

  # -- time --------------------------------------------------------------

  def run(self, ticks):
    for _ in range(ticks):
      self.step()

  def step(self):
    self.tick += 1
    now = self.tick
    if now % self.config.routing_interval == 0:
      changes = self.routing.exchange()
      if self._healing_since is not None and changes == 0:
        self._event("ev_settled", rounds=self.routing.rounds - self._healing_since)
        self._healing_since = None

    self._land_arrivals(now)
    self._run_flows(now)
    self._start_transmissions(now)
    if self.config.chatter > 0:
      self._maybe_chatter()

  def _land_arrivals(self, now):
    nodes = self.network.nodes
    noise = self.config.noise
    for (a, b), lane in self.transits.items():
      if not lane or lane[0].arrive > now:
        continue
      loss = min(0.95, self.network.link(a, b).loss + noise)
      while lane and lane[0].arrive <= now:
        packet = lane.popleft().packet
        if loss and self.rng.random() < loss:
          node = nodes[b]
          self._drop(packet, "noise", b, node.x, node.y)
        else:
          self._arrive(packet, b)

  def _run_flows(self, now):
    out = self._scratch
    finished = None
    routing = self.routing
    for flow in self.flows.values():
      out.clear()
      flow.packets_due(now, out, routing.next_hop(flow.src, flow.dst) is not None)
      if out:
        self._inject(flow, out)
      if flow.state != SENDING:
        finished = finished or []
        finished.append(flow)
    if finished:
      for flow in finished:
        self._retire(flow)

  def _start_transmissions(self, now):
    for direction, queue in self.queues.items():
      if not queue or self.busy_until[direction] > now:
        continue
      link = self.network.link(*direction)
      packet = queue.popleft()
      self.transits[direction].append(Transit(packet, now, now + link.delay))
      self.busy_until[direction] = now + link.interval

  # -- packet handling ---------------------------------------------------

  def _inject(self, flow, packets):
    for packet in packets:
      self.stats.sent += 1
      if packet.resent:
        self.stats.retransmits += 1
        if not flow.background:
          self._event("ev_resend", flow=flow.flow_id, seq=packet.seq)
      self._forward(packet, flow.src)

  def _arrive(self, packet, node_id):
    packet.hops += 1
    if packet.dst == node_id:
      self._deliver(packet, node_id)
    else:
      self._forward(packet, node_id)

  def _forward(self, packet, node_id):
    node = self.network.nodes[node_id]
    packet.ttl -= 1
    if packet.ttl <= 0:
      self._drop(packet, "ttl", node_id, node.x, node.y)
      return
    hop = self.routing.next_hop(node_id, packet.dst)
    queue = self.queues.get((node_id, hop)) if hop is not None else None
    if queue is None or not self.network.link(node_id, hop).up:
      self._drop(packet, "no_route", node_id, node.x, node.y)
      return
    if len(queue) >= self.config.queue_size:
      self._drop(packet, "queue", node_id, node.x, node.y)
      return
    queue.append(packet)

  def _deliver(self, packet, node_id):
    flow = self.flows.get(packet.flow_id)
    if flow is None:
      return
    now = self.tick
    if packet.kind == DATA:
      self.stats.delivered_packets += 1
      self.stats.trip_total += now - packet.born
      was_delivered = flow.delivered
      ack_no = flow.on_data(packet.seq, packet.chunk, now)
      if flow.delivered and not was_delivered:
        self.stats.messages_delivered += 1
        self.stats.message_time_total += flow.trip_time()
        if not flow.background:
          self._event("ev_delivered", flow=flow.flow_id, src=flow.src, dst=flow.dst,
                      ticks=flow.trip_time())
      self._forward(flow.make_ack(ack_no, now, echo=packet.born), node_id)
    elif packet.kind == ACK:
      out = []
      flow.on_ack(packet.seq, now, out, echo=packet.echo)
      if out:
        self._inject(flow, out)

  def _drop(self, packet, reason, node_id, x, y):
    self.stats.drops[reason] += 1
    self._mark(x, y, reason)
    if not packet.background and packet.kind == DATA:
      self._event("ev_drop_" + reason, flow=packet.flow_id, seq=packet.seq, node=node_id)

  def _retire(self, flow):
    del self.flows[flow.flow_id]
    self.finished.append(flow)
    if flow.state == FAILED and not flow.delivered:
      self.stats.messages_failed += 1
      if not flow.background:
        self._event("ev_failed", flow=flow.flow_id, src=flow.src, dst=flow.dst)

  def _maybe_chatter(self):
    background = sum(1 for f in self.flows.values() if f.background)
    if background >= self.config.max_background:
      return
    if self.rng.random() >= self.config.chatter * 0.12:
      return
    houses = [n.id for n in self.network.nodes.values() if n.kind == HOUSE]
    if len(houses) < 2:
      return
    src, dst = self.rng.sample(houses, 2)
    length = self.rng.randint(6, 24)
    text = "".join(self.rng.choice(_CHATTER_ALPHABET) for _ in range(length))
    self.send_message(src, dst, text, background=True)

  # -- bookkeeping -------------------------------------------------------

  def _event(self, key, **params):
    self.events.append((self.tick, key, params))
    self.event_serial += 1

  def _mark(self, x, y, reason):
    self.drop_marks.append((self.tick, x, y, reason))

  @staticmethod
  def _progress(transit, now):
    span = transit.arrive - transit.depart
    if span <= 0:
      return 1.0
    return min(1.0, max(0.0, (now - transit.depart) / span))

  # -- read-only views for the interface ----------------------------------

  def iter_transits(self, now=None):
    """Yield (from_id, to_id, packet, progress) for every moving envelope."""
    now = self.tick if now is None else now
    for (a, b), lane in self.transits.items():
      for transit in lane:
        yield a, b, transit.packet, self._progress(transit, now)

  def node_load(self, node_id):
    """How full this node's outgoing shelves are, between 0 and 1."""
    waiting = 0
    shelves = 0
    for neighbor, _ in self.network.neighbors(node_id, only_up=False):
      waiting += len(self.queues[(node_id, neighbor)])
      shelves += 1
    if not shelves:
      return 0.0
    return min(1.0, waiting / (shelves * max(1, self.config.queue_size)))

  def foreground_flow(self):
    return self.last_foreground

  def active_foreground(self):
    return [f for f in self.flows.values() if not f.background]

  @property
  def healing(self):
    return self._healing_since is not None
