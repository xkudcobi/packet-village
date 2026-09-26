"""Turns engine events and node ids into sentences for people.

The engine records events as (tick, key, params) with raw ids, so the
story can be re-told in another language at any time.
"""

from .topology import ROUTER

def node_label(network, node_id, tr):
  node = network.nodes.get(node_id)
  if node is None:
    return tr.t("unknown_place")
  if node.kind == ROUTER:
    return tr.t("router_label", tag=node.name)
  return node.name

def describe_event(event, network, tr):
  _, key, params = event
  words = {}
  for name, value in params.items():
    if name in ("src", "dst", "a", "b", "node"):
      words[name] = node_label(network, value, tr)
    else:
      words[name] = value
  if "seq" in params:
    words["num"] = params["seq"] + 1
  return tr.t(key, **words)

def story_lines(events, network, tr, limit=40):
  """The most recent events, oldest first, as '[step] sentence' lines."""
  recent = list(events)[-limit:]
  return [f"[{event[0]}] {describe_event(event, network, tr)}" for event in recent]

def route_text(network, nodes, tr):
  return " → ".join(node_label(network, node_id, tr) for node_id in nodes)

def routing_report(sim, node_id, tr):
  """Lines describing what one node knows about reaching every house."""
  network = sim.network
  lines = []
  for dest in network.houses():
    if dest == node_id:
      continue
    hop = sim.routing.next_hop(node_id, dest)
    if hop is None:
      lines.append(tr.t("inspect_noroute", dest=node_label(network, dest, tr)))
    else:
      lines.append(tr.t(
        "inspect_route",
        dest=node_label(network, dest, tr),
        hop=node_label(network, hop, tr),
        cost=sim.routing.cost(node_id, dest),
      ))
  return lines
