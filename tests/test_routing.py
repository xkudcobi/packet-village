import unittest

from packet_village.generator import random_town
from packet_village.routing import INFINITY, DistanceVectorRouting, shortest_costs
from packet_village.scenarios import SCENARIOS
from packet_village.topology import ROUTER, Network

def chain(*names, delay=1):
  net = Network()
  for i, name in enumerate(names):
    net.add_node(name, ROUTER, name, i * 10, 0)
  for a, b in zip(names, names[1:]):
    net.add_link(a, b, delay=delay)
  return net

class DijkstraTest(unittest.TestCase):
  def test_weighted_costs(self):
    net = chain("A", "B", "C")
    net.add_link("A", "C", delay=5)
    self.assertEqual(shortest_costs(net, "A"), {"A": 0, "B": 1, "C": 2})

  def test_ignores_cut_cables(self):
    net = chain("A", "B", "C")
    net.link("B", "C").up = False
    self.assertEqual(shortest_costs(net, "A"), {"A": 0, "B": 1})

  def test_unknown_source(self):
    self.assertEqual(shortest_costs(chain("A"), "Z"), {})

class DistanceVectorTest(unittest.TestCase):
  def test_starts_knowing_only_itself(self):
    routing = DistanceVectorRouting(chain("A", "B"))
    self.assertIsNone(routing.next_hop("A", "B"))
    self.assertEqual(routing.cost("A", "A"), 0)

  def test_news_travels_one_hop_per_round(self):
    routing = DistanceVectorRouting(chain("A", "B", "C", "D"))
    routing.exchange()
    self.assertEqual(routing.next_hop("A", "B"), "B")
    self.assertIsNone(routing.next_hop("A", "D"))
    routing.exchange()
    routing.exchange()
    self.assertEqual(routing.next_hop("A", "D"), "B")
    self.assertEqual(routing.cost("A", "D"), 3)

  def test_converges_to_dijkstra_on_every_builtin_town(self):
    for scenario in SCENARIOS:
      with self.subTest(scenario=scenario.key):
        routing = DistanceVectorRouting(scenario.build())
        routing.converge()
        self.assertTrue(routing.matches())
        self.assertEqual(routing.exchange(), 0)

  def test_converges_on_random_towns(self):
    for seed in range(15):
      routing = DistanceVectorRouting(random_town(seed=seed))
      routing.converge()
      self.assertTrue(routing.matches(), f"seed {seed}")

  def test_heals_after_a_cut(self):
    net = chain("A", "B", "C", "D")
    net.add_link("A", "D", delay=10)
    routing = DistanceVectorRouting(net)
    routing.converge()
    self.assertEqual(routing.next_hop("A", "D"), "B")
    net.link("C", "D").up = False
    routing.link_changed("C", "D")
    # The ends notice immediately.
    self.assertIsNone(routing.next_hop("C", "D"))
    routing.converge()
    self.assertTrue(routing.matches())
    self.assertEqual(routing.next_hop("A", "D"), "D")
    self.assertEqual(routing.path("C", "D"), (["C", "B", "A", "D"], True))

  def test_link_changed_ignores_working_cable(self):
    net = chain("A", "B")
    routing = DistanceVectorRouting(net)
    routing.converge()
    routing.link_changed("A", "B")
    self.assertEqual(routing.next_hop("A", "B"), "B")

  def test_partition_forgets_unreachable_nodes(self):
    net = chain("A", "B", "C")
    routing = DistanceVectorRouting(net)
    routing.converge()
    net.link("B", "C").up = False
    routing.link_changed("B", "C")
    rounds = routing.converge()
    # Poisoned reverse stops A and B from counting to infinity forever.
    self.assertLess(rounds, INFINITY)
    self.assertIsNone(routing.next_hop("A", "C"))
    self.assertEqual(routing.path("A", "C"), (["A"], False))

  def test_repair_is_picked_up(self):
    net = chain("A", "B", "C")
    routing = DistanceVectorRouting(net)
    net.link("B", "C").up = False
    routing.converge()
    self.assertIsNone(routing.next_hop("A", "C"))
    net.link("B", "C").up = True
    routing.converge()
    self.assertEqual(routing.next_hop("A", "C"), "B")

  def test_sync_nodes_after_editing(self):
    net = chain("A", "B")
    routing = DistanceVectorRouting(net)
    routing.converge()
    net.add_node("C", ROUTER, "C", 30, 0)
    net.add_link("B", "C")
    net.remove_node("A")
    routing.sync_nodes()
    self.assertNotIn("A", routing.tables)
    self.assertNotIn("A", routing.tables["B"])
    routing.converge()
    self.assertTrue(routing.matches())

  def test_path_to_self(self):
    routing = DistanceVectorRouting(chain("A", "B"))
    self.assertEqual(routing.path("A", "A"), (["A"], True))

  def test_equal_cost_choice_is_stable(self):
    net = Network()
    for name in "SXYT":
      net.add_node(name, ROUTER, name, 0, 0)
    for a, b in (("S", "X"), ("S", "Y"), ("X", "T"), ("Y", "T")):
      net.add_link(a, b, delay=2)
    routing = DistanceVectorRouting(net)
    routing.converge()
    first = routing.next_hop("S", "T")
    for _ in range(10):
      routing.exchange()
      self.assertEqual(routing.next_hop("S", "T"), first)

if __name__ == "__main__":
  unittest.main()
