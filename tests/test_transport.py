import unittest

from packet_village.packets import ACK, DATA, PacketFactory, join_pieces, split_message
from packet_village.transport import DONE, FAILED, SENDING, Flow, TransportConfig

def make_flow(text="abcdefghij", size=1, **config):
  return Flow(1, "src", "dst", text, size, 0, PacketFactory(), TransportConfig(**config))

def sent(flow, now):
  out = []
  flow.packets_due(now, out)
  return out

class SplittingTest(unittest.TestCase):
  def test_split(self):
    self.assertEqual(split_message("hello", 2), ["he", "ll", "o"])
    self.assertEqual(split_message("", 3), [])
    with self.assertRaises(ValueError):
      split_message("x", 0)

  def test_join_with_gaps(self):
    self.assertEqual(join_pieces(["he", None, "o"], 2, gap="_"), "he__o")
    self.assertEqual(join_pieces(["he", "ll", None], 2, gap="_"), "hell_")
    self.assertEqual(join_pieces([], 2), "")

  def test_unicode_survives(self):
    pieces = split_message("çğıİöşü", 3)
    self.assertEqual("".join(pieces), "çğıİöşü")

class ConfigTest(unittest.TestCase):
  def test_invalid_configs(self):
    with self.assertRaises(ValueError):
      TransportConfig(min_rto=50, initial_rto=40)
    with self.assertRaises(ValueError):
      TransportConfig(initial_cwnd=0)
    with self.assertRaises(ValueError):
      TransportConfig(max_timeouts=0)

  def test_flow_rejects_bad_input(self):
    with self.assertRaises(ValueError):
      Flow(1, "a", "a", "hi", 1, 0, PacketFactory())
    with self.assertRaises(ValueError):
      Flow(1, "a", "b", "", 1, 0, PacketFactory())

class SenderTest(unittest.TestCase):
  def test_initial_window(self):
    flow = make_flow(initial_cwnd=2)
    packets = sent(flow, 0)
    self.assertEqual([p.seq for p in packets], [0, 1])
    self.assertTrue(all(p.kind == DATA and not p.resent for p in packets))
    self.assertEqual(sent(flow, 1), [])

  def test_slow_start_grows_window(self):
    flow = make_flow(initial_cwnd=1)
    sent(flow, 0)
    flow.on_ack(1, 5, [])
    self.assertEqual(flow.cwnd, 2.0)
    self.assertEqual([p.seq for p in sent(flow, 5)], [1, 2])
    flow.on_ack(3, 10, [])
    self.assertEqual(flow.cwnd, 4.0)

  def test_congestion_avoidance_grows_slowly(self):
    flow = make_flow(initial_cwnd=4)
    flow.ssthresh = 4.0
    sent(flow, 0)
    flow.on_ack(1, 5, [])
    self.assertAlmostEqual(flow.cwnd, 4.25)

  def test_window_is_capped(self):
    flow = make_flow("x" * 100, initial_cwnd=2, max_cwnd=4)
    now = 0
    while flow.state == SENDING and now < 400:
      for packet in sent(flow, now):
        flow.on_data(packet.seq, packet.chunk, now)
      flow.on_ack(flow.next_expected, now, [])
      self.assertLessEqual(flow.cwnd, 4.0)
      now += 1
    self.assertEqual(flow.state, DONE)

  def test_three_duplicate_acks_trigger_fast_retransmit(self):
    flow = make_flow(initial_cwnd=6)
    sent(flow, 0)
    out = []
    flow.on_ack(0, 3, out)
    flow.on_ack(0, 3, out)
    self.assertEqual(out, [])
    flow.on_ack(0, 4, out)
    self.assertEqual(len(out), 1)
    self.assertEqual(out[0].seq, 0)
    self.assertTrue(out[0].resent)
    self.assertTrue(flow.in_recovery)
    self.assertEqual(flow.cwnd, 3.0)
    # A fourth duplicate does not resend again.
    flow.on_ack(0, 5, out)
    self.assertEqual(len(out), 1)

  def test_partial_ack_resends_next_hole(self):
    flow = make_flow(initial_cwnd=6)
    sent(flow, 0)
    out = []
    for _ in range(3):
      flow.on_ack(0, 3, out)
    out.clear()
    flow.on_ack(2, 8, out)
    self.assertEqual([p.seq for p in out], [2])
    self.assertTrue(flow.in_recovery)
    flow.on_ack(6, 12, out)
    self.assertFalse(flow.in_recovery)

  def test_timeout_backs_off_and_resets_window(self):
    flow = make_flow(initial_cwnd=4, initial_rto=10)
    sent(flow, 0)
    self.assertEqual(sent(flow, 9), [])
    again = sent(flow, 10)
    self.assertEqual([p.seq for p in again], [0])
    self.assertTrue(again[0].resent)
    self.assertEqual(flow.cwnd, 1.0)
    self.assertEqual(flow.ssthresh, 2.0)
    self.assertEqual(flow.rto, 20)
    self.assertEqual(flow.retransmissions, 1)

  def test_gives_up_after_too_many_timeouts(self):
    flow = make_flow(initial_rto=10, max_rto=40, max_timeouts=3)
    now = 0
    while flow.state == SENDING:
      sent(flow, now)
      now += 1
      self.assertLess(now, 1000)
    self.assertEqual(flow.state, FAILED)
    self.assertFalse(flow.active)
    self.assertEqual(sent(flow, now + 100), [])

  def test_gives_up_sooner_without_a_route(self):
    def ticks_until_failure(route_known):
      flow = make_flow(initial_rto=10, max_rto=40, max_timeouts=6, max_blind_timeouts=2)
      now = 0
      while flow.state == SENDING:
        flow.packets_due(now, [], route_known)
        now += 1
      return now, flow.retransmissions

    blind_time, blind_tries = ticks_until_failure(False)
    patient_time, patient_tries = ticks_until_failure(True)
    self.assertEqual(blind_tries, 2)
    self.assertEqual(patient_tries, 6)
    self.assertLess(blind_time, patient_time)

  def test_rtt_estimate_sets_timeout(self):
    flow = make_flow(initial_rto=40, min_rto=2)
    sent(flow, 0)
    flow.on_ack(1, 10, [])
    self.assertEqual(flow.srtt, 10.0)
    self.assertEqual(flow.rto, 30)

  def test_karn_rule_skips_resent_samples(self):
    flow = make_flow(initial_cwnd=1, initial_rto=10)
    sent(flow, 0)
    sent(flow, 10)  # timeout, piece 0 resent
    flow.on_ack(1, 12, [])
    self.assertIsNone(flow.srtt)

  def test_timeout_goes_back_to_the_hole(self):
    flow = make_flow(initial_cwnd=4, initial_rto=10)
    sent(flow, 0)
    sent(flow, 10)
    self.assertEqual(flow.next_seq, 1)
    # Piece 0 is acknowledged, the window reopens and piece 1 goes again.
    out = []
    flow.on_ack(1, 14, out, echo=10)
    again = sent(flow, 14)
    self.assertEqual(again[0].seq, 1)
    self.assertTrue(again[0].resent)

  def test_ack_beyond_go_back_point_skips_ahead(self):
    flow = make_flow(initial_cwnd=4, initial_rto=10)
    sent(flow, 0)
    sent(flow, 10)
    flow.on_ack(4, 13, [], echo=10)
    self.assertEqual(flow.base, 4)
    self.assertEqual(flow.next_seq, 4)
    self.assertEqual([p.seq for p in sent(flow, 13)][0], 4)

  def test_echo_gives_a_sample_even_for_resent_pieces(self):
    flow = make_flow(initial_cwnd=1, initial_rto=10, min_rto=2)
    sent(flow, 0)
    sent(flow, 10)
    flow.on_ack(1, 16, [], echo=10)
    self.assertEqual(flow.srtt, 6.0)
    self.assertLess(flow.rto, 20)

  def test_stale_and_bogus_acks_are_ignored(self):
    flow = make_flow(initial_cwnd=2)
    sent(flow, 0)
    flow.on_ack(2, 5, [])
    base = flow.base
    flow.on_ack(1, 6, [])
    flow.on_ack(999, 6, [])
    self.assertEqual(flow.base, base)

class ReceiverTest(unittest.TestCase):
  def test_out_of_order_reassembly(self):
    flow = make_flow("abcdef", size=2)
    self.assertEqual(flow.on_data(1, "cd", 1), 0)
    self.assertEqual(flow.progress_text(gap="_"), "__cd_")
    self.assertEqual(flow.on_data(0, "ab", 2), 2)
    self.assertFalse(flow.delivered)
    self.assertEqual(flow.on_data(2, "ef", 3), 3)
    self.assertTrue(flow.delivered)
    self.assertEqual(flow.progress_text(), "abcdef")
    self.assertEqual(flow.trip_time(), 3)

  def test_duplicates_and_out_of_range_are_harmless(self):
    flow = make_flow("abcd", size=2)
    flow.on_data(0, "ab", 1)
    self.assertEqual(flow.on_data(0, "XX", 2), 1)
    self.assertEqual(flow.on_data(7, "zz", 2), 1)
    self.assertEqual(flow.received_count, 1)
    self.assertEqual(flow.progress_text(gap="_"), "ab_")

  def test_ack_packet_goes_back(self):
    flow = make_flow()
    ack = flow.make_ack(3, 9)
    self.assertEqual((ack.kind, ack.seq, ack.src, ack.dst), (ACK, 3, "dst", "src"))

class LossyChannelTest(unittest.TestCase):
  def test_delivers_everything_despite_heavy_loss(self):
    """Drive a flow over a fake channel that drops every third packet."""
    import random
    rng = random.Random(4)
    text = "The quick brown fox jumps over the lazy dog, twice over."
    flow = Flow(1, "s", "d", text, 3, 0, PacketFactory(), TransportConfig(initial_rto=12, min_rto=4))
    in_flight = []  # (arrival tick, packet)
    now = 0
    while flow.state == SENDING and now < 5000:
      out = []
      flow.packets_due(now, out)
      for packet in out:
        if rng.random() > 0.33:
          in_flight.append((now + 3, packet))
      landed = [p for t, p in in_flight if t <= now]
      in_flight = [(t, p) for t, p in in_flight if t > now]
      for packet in landed:
        if packet.kind == DATA:
          ack = flow.make_ack(flow.on_data(packet.seq, packet.chunk, now), now)
          if rng.random() > 0.33:
            in_flight.append((now + 3, ack))
        else:
          replies = []
          flow.on_ack(packet.seq, now, replies)
          for reply in replies:
            in_flight.append((now + 3, reply))
      now += 1
    self.assertEqual(flow.state, DONE)
    self.assertEqual(flow.progress_text(), text)
    self.assertGreater(flow.retransmissions, 0)

if __name__ == "__main__":
  unittest.main()
