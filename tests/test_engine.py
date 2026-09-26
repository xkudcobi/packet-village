import unittest

from packet_village.engine import SimConfig, Simulation, SimulationError
from packet_village.scenarios import build_bridges, build_grid, build_ring, build_village
from packet_village.topology import HOUSE, ROUTER, Network

def run_until_done(sim, flow, limit=4000):
  for _ in range(limit):
    sim.step()
    if flow.delivered or not flow.active:
      return
  raise AssertionError("flow did not finish in time")

def two_houses_one_router():
  net = Network()
  net.add_node("a", HOUSE, "Ada", 0, 0)
  net.add_node("R", ROUTER, "R", 50, 0)
  net.add_node("b", HOUSE, "Bora", 100, 0)
  net.add_link("a", "R", delay=2)
  net.add_link("R", "b", delay=2)
  return net

class DeliveryTest(unittest.TestCase):
  def test_letter_arrives_intact(self):
    sim = Simulation(build_village(), seed=1)
    text = "Merhaba! Çiçekler açtı, güneş doğdu."
    flow = sim.send_message("ada", "elif", text)
    run_until_done(sim, flow)
    self.assertTrue(flow.delivered)
    self.assertEqual(flow.progress_text(), text)
    self.assertEqual(sim.stats.messages_delivered, 1)
    self.assertEqual(sim.stats.dropped, 0)
    keys = [e[1] for e in sim.events]
    self.assertIn("ev_sent", keys)
    self.assertIn("ev_delivered", keys)

  def test_every_builtin_town_delivers(self):
    for build, src, dst in ((build_village, "ada", "elif"), (build_bridges, "can", "oya"),
                            (build_ring, "arda", "emre"), (build_grid, "ada", "zeynep")):
      with self.subTest(town=build.__name__):
        sim = Simulation(build(), seed=5)
        flow = sim.send_message(src, dst, "a letter for the test suite")
        run_until_done(sim, flow)
        self.assertTrue(flow.delivered)

  def test_trip_time_is_at_least_the_path_delay(self):
    sim = Simulation(two_houses_one_router())
    flow = sim.send_message("a", "b", "x")
    run_until_done(sim, flow)
    self.assertGreaterEqual(flow.trip_time(), 4)

  def test_sender_finishes_after_final_ack(self):
    sim = Simulation(two_houses_one_router())
    flow = sim.send_message("a", "b", "hello there")
    for _ in range(300):
      sim.step()
    self.assertNotIn(flow.flow_id, sim.flows)
    self.assertIn(flow, sim.finished)

class DisruptionTest(unittest.TestCase):
  def test_cut_cable_mid_flight_still_delivers(self):
    sim = Simulation(build_ring(), seed=2)
    flow = sim.send_message("arda", "emre", "going round the ring, the long way if needed")
    for _ in range(15):
      sim.step()
    path, reached = sim.routing.path("arda", "emre")
    self.assertTrue(reached)
    sim.set_link_up(path[1], path[2], False)
    self.assertTrue(sim.healing)
    run_until_done(sim, flow)
    self.assertTrue(flow.delivered)
    self.assertIn("ev_cut", [e[1] for e in sim.events])
    self.assertIn("ev_settled", [e[1] for e in sim.events])
    self.assertFalse(sim.healing)

  def test_cut_drops_everything_on_the_cable(self):
    sim = Simulation(two_houses_one_router())
    sim.send_message("a", "b", "abcdefghijklmnop")
    sim.step()
    sim.step()
    on_cable = len(sim.transits[("a", "R")]) + len(sim.queues[("a", "R")])
    self.assertGreater(on_cable, 0)
    sim.set_link_up("a", "R", False)
    self.assertEqual(sim.stats.drops["cut"], on_cable)
    self.assertEqual(len(sim.transits[("a", "R")]), 0)
    self.assertGreaterEqual(len(sim.drop_marks), 1)

  def test_partitioned_town_gives_up(self):
    sim = Simulation(two_houses_one_router())
    sim.set_link_up("R", "b", False)
    flow = sim.send_message("a", "b", "nobody will read this")
    run_until_done(sim, flow, limit=10000)
    self.assertFalse(flow.delivered)
    self.assertEqual(sim.stats.messages_failed, 1)
    self.assertGreater(sim.stats.drops["no_route"], 0)
    self.assertIn("ev_failed", [e[1] for e in sim.events])

  def test_repair_lets_a_stalled_letter_through(self):
    sim = Simulation(two_houses_one_router())
    sim.set_link_up("R", "b", False)
    flow = sim.send_message("a", "b", "wait for me")
    sim.run(60)
    self.assertEqual(sim.repair_all(), 1)
    run_until_done(sim, flow)
    self.assertTrue(flow.delivered)

  def test_full_shelves_drop_but_letter_recovers(self):
    config = SimConfig(queue_size=2, chunk_size=1)
    net = build_bridges()
    sim = Simulation(net, config, seed=3)
    flow = sim.send_message("can", "oya", "a long letter that will not fit on tiny shelves")
    run_until_done(sim, flow, limit=20000)
    self.assertTrue(flow.delivered)
    self.assertGreater(sim.stats.drops["queue"], 0)
    self.assertGreater(sim.stats.retransmits, 0)

  def test_stormy_weather_is_survived(self):
    sim = Simulation(build_village(), SimConfig(noise=0.08), seed=8)
    flow = sim.send_message("ada", "elif", "rain, rain, go away")
    run_until_done(sim, flow, limit=20000)
    self.assertTrue(flow.delivered)
    self.assertGreater(sim.stats.drops["noise"], 0)

  def test_background_chatter_runs_and_stays_bounded(self):
    sim = Simulation(build_grid(), SimConfig(chatter=1.0, max_background=5), seed=9)
    sim.run(600)
    self.assertGreater(sim.stats.messages_started, 5)
    self.assertLessEqual(sum(1 for f in sim.flows.values() if f.background), 5)
    self.assertIsNone(sim.foreground_flow())

class ApiTest(unittest.TestCase):
  def test_send_errors(self):
    sim = Simulation(build_village())
    for args, key in ((("ada", "ada", "hi"), "err_same_house"),
                      (("ada", "nobody", "hi"), "err_unknown_house"),
                      (("ada", "elif", "   "), "err_empty_message")):
      with self.assertRaises(SimulationError) as caught:
        sim.send_message(*args)
      self.assertEqual(caught.exception.key, key)

  def test_toggle_link(self):
    sim = Simulation(build_village())
    self.assertFalse(sim.toggle_link("A", "B"))
    self.assertTrue(sim.toggle_link("B", "A"))
    with self.assertRaises(SimulationError):
      sim.toggle_link("A", "E")
    self.assertEqual(sim.link_version, 2)

  def test_setting_same_state_is_a_no_op(self):
    sim = Simulation(build_village())
    sim.set_link_up("A", "B", True)
    self.assertEqual(sim.link_version, 0)
    self.assertEqual(len(sim.events), 0)

  def test_same_seed_same_story(self):
    def story(seed):
      sim = Simulation(build_grid(), SimConfig(chatter=0.8, noise=0.05), seed=seed)
      sim.send_message("ada", "zeynep", "determinism matters")
      sim.run(400)
      return [(e[0], e[1]) for e in sim.events], sim.stats.sent

    self.assertEqual(story(11), story(11))

  def test_iter_transits_and_load(self):
    sim = Simulation(two_houses_one_router())
    sim.send_message("a", "b", "abcdefghijklmnopqrstuvwxyz")
    sim.run(3)
    moving = list(sim.iter_transits())
    self.assertTrue(moving)
    for a, b, packet, progress in moving:
      self.assertIsNotNone(sim.network.link(a, b))
      self.assertGreaterEqual(progress, 0.0)
      self.assertLessEqual(progress, 1.0)
    self.assertGreaterEqual(sim.node_load("a"), 0.0)
    self.assertLessEqual(sim.node_load("a"), 1.0)

  def test_stats_add_up(self):
    sim = Simulation(build_village(), SimConfig(noise=0.1, chatter=0.5), seed=4)
    sim.send_message("ada", "elif", "counting envelopes")
    sim.run(800)
    stats = sim.stats
    self.assertGreaterEqual(stats.sent, stats.retransmits)
    self.assertGreater(stats.delivered_packets, 0)
    self.assertIsNotNone(stats.average_trip)
    stats.reset()
    self.assertEqual(stats.dropped, 0)
    self.assertIsNone(stats.average_trip)
    self.assertIsNone(stats.average_message_time)

  def test_ttl_expiry_is_counted(self):
    net = two_houses_one_router()
    sim = Simulation(net, SimConfig(ttl=2))
    flow = sim.send_message("a", "b", "short life")
    sim.run(50)
    self.assertFalse(flow.delivered)
    self.assertGreater(sim.stats.drops["ttl"], 0)

if __name__ == "__main__":
  unittest.main()
