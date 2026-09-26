import unittest

from packet_village.topology import HOUSE, ROUTER, Link, Network, TopologyError, link_key

def small_line():
  net = Network()
  net.add_node("a", HOUSE, "Ada", 0, 0)
  net.add_node("R", ROUTER, "R", 50, 0)
  net.add_node("b", HOUSE, "Bora", 100, 0)
  net.add_link("a", "R", delay=2)
  net.add_link("R", "b", delay=3)
  return net

class LinkKeyTest(unittest.TestCase):
  def test_order_does_not_matter(self):
    self.assertEqual(link_key("x", "y"), link_key("y", "x"))

class NetworkEditingTest(unittest.TestCase):
  def test_nodes_and_links_are_indexed(self):
    net = small_line()
    self.assertEqual(net.houses(), ["a", "b"])
    self.assertEqual(net.routers(), ["R"])
    self.assertEqual(sorted(n for n, _ in net.neighbors("R")), ["a", "b"])
    self.assertIs(net.link("b", "R"), net.link("R", "b"))

  def test_duplicate_node_is_rejected(self):
    net = small_line()
    with self.assertRaises(TopologyError):
      net.add_node("a", HOUSE, "Again", 1, 1)

  def test_link_to_unknown_node_is_rejected(self):
    net = small_line()
    with self.assertRaises(TopologyError):
      net.add_link("a", "nowhere")

  def test_duplicate_link_is_rejected_either_way(self):
    net = small_line()
    with self.assertRaises(TopologyError):
      net.add_link("R", "a")

  def test_bad_link_values(self):
    with self.assertRaises(TopologyError):
      Link("a", "a")
    with self.assertRaises(TopologyError):
      Link("a", "b", delay=0)
    with self.assertRaises(TopologyError):
      Link("a", "b", interval=0)
    with self.assertRaises(TopologyError):
      Link("a", "b", loss=1.0)

  def test_bad_node_kind(self):
    net = Network()
    with self.assertRaises(TopologyError):
      net.add_node("x", "castle", "X", 0, 0)

  def test_remove_node_removes_its_cables(self):
    net = small_line()
    net.remove_node("R")
    self.assertEqual(net.links, {})
    self.assertEqual(list(net.neighbors("a")), [])

  def test_remove_missing_link(self):
    net = small_line()
    with self.assertRaises(TopologyError):
      net.remove_link("a", "b")

  def test_other_end(self):
    link = small_line().link("a", "R")
    self.assertEqual(link.other("a"), "R")
    with self.assertRaises(TopologyError):
      link.other("b")

class ReachabilityTest(unittest.TestCase):
  def test_cut_cable_splits_the_town(self):
    net = small_line()
    self.assertTrue(net.is_connected("a", "b"))
    net.link("R", "b").up = False
    self.assertFalse(net.is_connected("a", "b"))
    self.assertEqual(net.reachable_from("a"), {"a", "R"})
    self.assertEqual(net.degree("R", only_up=True), 1)
    self.assertEqual(net.degree("R"), 2)

  def test_unknown_start(self):
    self.assertEqual(small_line().reachable_from("zzz"), set())

class SerialisationTest(unittest.TestCase):
  def test_round_trip_keeps_everything(self):
    net = small_line()
    net.link("a", "R").up = False
    net.link("R", "b").loss = 0.25
    copy = Network.from_dict(net.to_dict())
    self.assertEqual(copy.to_dict(), net.to_dict())
    self.assertFalse(copy.link("a", "R").up)
    self.assertEqual(copy.link("R", "b").loss, 0.25)

  def test_copy_is_independent(self):
    net = small_line()
    copy = net.copy()
    copy.nodes["a"].x = 999
    self.assertEqual(net.nodes["a"].x, 0)

  def test_malformed_data(self):
    for bad in (None, [], {"nodes": []}, {"nodes": [{"id": "a"}], "links": []},
                {"nodes": [{"id": "a", "kind": "house", "x": "left", "y": 0}], "links": []}):
      with self.assertRaises(TopologyError):
        Network.from_dict(bad)

if __name__ == "__main__":
  unittest.main()
