"""Reliable delivery of one message between two houses.

A Flow holds both ends of a conversation. The sender side is a small
TCP-Reno-like machine:

* a congestion window that grows by one per acknowledged piece while
  below `ssthresh` (slow start) and by 1/cwnd above it,
* a retransmission timer whose length follows the measured round trip
  (Jacobson/Karels smoothing; ACKs echo the send time of the piece that
  triggered them, and without an echo Karn's rule skips resent pieces),
* go-back retransmission after a timeout,
* fast retransmit after three duplicate acknowledgements, with
  NewReno-style partial ACK handling while recovering.

The receiver side keeps out-of-order pieces and always answers with a
cumulative acknowledgement: "I have everything before piece N".
"""

from .packets import ACK, DATA, join_pieces, split_message

SENDING = "sending"
DONE = "done"
FAILED = "failed"

class TransportConfig:
  __slots__ = ("initial_rto", "min_rto", "max_rto", "initial_cwnd", "max_cwnd",
               "max_timeouts", "max_blind_timeouts", "dupack_threshold")

  def __init__(self, initial_rto=40, min_rto=8, max_rto=160, initial_cwnd=2, max_cwnd=16,
               max_timeouts=20, max_blind_timeouts=5, dupack_threshold=3):
    if not 1 <= min_rto <= initial_rto <= max_rto:
      raise ValueError("timeouts must satisfy 1 <= min <= initial <= max")
    if not 1 <= initial_cwnd <= max_cwnd:
      raise ValueError("initial window must be between 1 and the maximum window")
    if max_timeouts < 1 or max_blind_timeouts < 1 or dupack_threshold < 1:
      raise ValueError("timeout and dupack limits must be positive")
    self.initial_rto = initial_rto
    self.initial_cwnd = initial_cwnd
    self.min_rto = min_rto
    self.max_rto = max_rto
    self.max_cwnd = max_cwnd
    self.max_timeouts = max_timeouts
    self.max_blind_timeouts = max_blind_timeouts
    self.dupack_threshold = dupack_threshold

DEFAULT_TRANSPORT = TransportConfig()

class Flow:
  def __init__(self, flow_id, src, dst, text, chunk_size, started, factory,
               config=DEFAULT_TRANSPORT, background=False):
    if src == dst:
      raise ValueError("sender and receiver must differ")
    self.chunks = split_message(text, chunk_size)
    if not self.chunks:
      raise ValueError("cannot send an empty message")
    self.flow_id = flow_id
    self.src = src
    self.dst = dst
    self.text = text
    self.chunk_size = chunk_size
    self.started = started
    self.factory = factory
    self.config = config
    self.background = background
    self.total = len(self.chunks)
    self.state = SENDING
    self.finished_at = None

    # sender side
    self.base = 0
    self.next_seq = 0
    self.cwnd = float(config.initial_cwnd)
    self.ssthresh = float(config.max_cwnd)
    self.dup_acks = 0
    self.in_recovery = False
    self.recover = -1
    self.sent_at = {}
    self.resent_seqs = set()
    self.timer_start = None
    self.rto = config.initial_rto
    self.srtt = None
    self.rttvar = None
    self.timeouts_in_row = 0
    self.transmissions = 0
    self.retransmissions = 0

    # receiver side
    self.received = [None] * self.total
    self.received_count = 0
    self.next_expected = 0
    self.delivered_at = None

  # -- sender ------------------------------------------------------------

  @property
  def outstanding(self):
    return self.next_seq - self.base

  def packets_due(self, now, out, route_known=True):
    """Append every packet the sender wants to send at `now` to out.

    `route_known` tells whether the sending house currently knows any way
    to the receiver. Without one, the sender gives up much sooner; with
    one, lost pieces are simply bad luck and worth retrying.
    """
    if self.state != SENDING:
      return
    if (self.timer_start is not None and self.base < self.next_seq
        and now - self.timer_start >= self.rto):
      self._on_timeout(now, out, route_known)
      if self.state != SENDING:
        return
    window = max(1, int(self.cwnd))
    while self.next_seq < self.total and self.next_seq - self.base < window:
      out.append(self._transmit(self.next_seq, now))
      self.next_seq += 1

  def on_ack(self, ack_no, now, out, echo=None):
    """Handle a cumulative acknowledgement; may queue a retransmission."""
    if self.state != SENDING or ack_no < self.base or ack_no > self.total:
      return
    if ack_no > self.base:
      self._on_new_ack(ack_no, now, out, echo)
    elif self.base < self.next_seq:
      self.dup_acks += 1
      if self.dup_acks == self.config.dupack_threshold and not self.in_recovery:
        self.ssthresh = max(self.cwnd / 2.0, 2.0)
        self.cwnd = self.ssthresh
        self.in_recovery = True
        self.recover = self.next_seq - 1
        out.append(self._transmit(self.base, now))
        self.timer_start = now

  def _on_new_ack(self, ack_no, now, out, echo):
    newly = ack_no - self.base
    sample_seq = ack_no - 1
    if echo is not None:
      self._update_rtt(now - echo)
    elif sample_seq not in self.resent_seqs and sample_seq in self.sent_at:
      # Karn's rule: a resent piece gives an ambiguous round-trip sample.
      self._update_rtt(now - self.sent_at[sample_seq])
    for seq in range(self.base, ack_no):
      self.sent_at.pop(seq, None)
      self.resent_seqs.discard(seq)
    self.base = ack_no
    # After a go-back the receiver may already hold pieces we meant to resend.
    self.next_seq = max(self.next_seq, ack_no)
    self.dup_acks = 0
    self.timeouts_in_row = 0

    if self.in_recovery:
      if ack_no > self.recover:
        self.in_recovery = False
        self.cwnd = self.ssthresh
      elif self.base < self.total:
        # Partial ACK: the next hole was lost too, resend it right away.
        out.append(self._transmit(self.base, now))
    else:
      for _ in range(newly):
        if self.cwnd < self.ssthresh:
          self.cwnd += 1.0
        else:
          self.cwnd += 1.0 / self.cwnd
      self.cwnd = min(self.cwnd, float(self.config.max_cwnd))

    if self.base >= self.total:
      self.state = DONE
      self.finished_at = now
      self.timer_start = None
    else:
      self.timer_start = now if self.base < self.next_seq else None

  def _on_timeout(self, now, out, route_known=True):
    self.timeouts_in_row += 1
    limit = self.config.max_timeouts if route_known else self.config.max_blind_timeouts
    if self.timeouts_in_row > limit:
      self.state = FAILED
      self.finished_at = now
      self.timer_start = None
      return
    self.ssthresh = max(self.cwnd / 2.0, 2.0)
    self.cwnd = 1.0
    self.dup_acks = 0
    self.in_recovery = False
    self.rto = min(self.rto * 2, self.config.max_rto)
    # Go back: everything after the hole is sent again as the window
    # reopens; the receiver quietly ignores pieces it already has.
    # TODO: selective acknowledgements would let the sender skip the
    # pieces the receiver is already holding instead of resending them.
    self.next_seq = self.base + 1
    out.append(self._transmit(self.base, now))
    self.timer_start = now

  def _transmit(self, seq, now):
    resent = seq in self.sent_at
    if resent:
      self.resent_seqs.add(seq)
      self.retransmissions += 1
    self.sent_at[seq] = now
    self.transmissions += 1
    if self.timer_start is None:
      self.timer_start = now
    return self.factory.make(DATA, self.flow_id, seq, self.chunks[seq], self.src,
                             self.dst, now, resent=resent, background=self.background)

  def _update_rtt(self, sample):
    sample = max(1, sample)
    if self.srtt is None:
      self.srtt = float(sample)
      self.rttvar = sample / 2.0
    else:
      self.rttvar = 0.75 * self.rttvar + 0.25 * abs(self.srtt - sample)
      self.srtt = 0.875 * self.srtt + 0.125 * sample
    rto = self.srtt + max(1.0, 4.0 * self.rttvar)
    self.rto = int(min(max(rto, self.config.min_rto), self.config.max_rto))

  # -- receiver ----------------------------------------------------------

  def on_data(self, seq, chunk, now):
    """Store a piece; return the cumulative ACK number to send back."""
    if 0 <= seq < self.total and self.received[seq] is None:
      self.received[seq] = chunk
      self.received_count += 1
      while self.next_expected < self.total and self.received[self.next_expected] is not None:
        self.next_expected += 1
      if self.received_count == self.total and self.delivered_at is None:
        self.delivered_at = now
    return self.next_expected

  def make_ack(self, ack_no, now, echo=None):
    return self.factory.make(ACK, self.flow_id, ack_no, "", self.dst, self.src, now,
                             background=self.background, echo=echo)

  # -- reporting ---------------------------------------------------------

  @property
  def delivered(self):
    return self.delivered_at is not None

  @property
  def active(self):
    return self.state == SENDING

  def progress_text(self, gap="·"):
    return join_pieces(self.received, self.chunk_size, gap)

  def trip_time(self):
    return None if self.delivered_at is None else self.delivered_at - self.started
