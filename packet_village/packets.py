"""Envelopes (packets) and the helpers that cut a message into them."""

DATA = "data"
ACK = "ack"

class Packet:
  """One envelope on its way through town.

  For DATA packets `seq` is the index of the piece of the message; for ACK
  packets it is the next piece the receiver is still waiting for, and
  `echo` repeats the send time of the piece that triggered it, so the
  sender can time the round trip even for pieces it had to resend.
  """

  __slots__ = ("pid", "flow_id", "kind", "seq", "chunk", "src", "dst",
               "ttl", "born", "hops", "resent", "background", "echo")

  def __init__(self, pid, flow_id, kind, seq, chunk, src, dst, ttl, born,
               resent=False, background=False, echo=None):
    self.pid = pid
    self.flow_id = flow_id
    self.kind = kind
    self.seq = seq
    self.chunk = chunk
    self.src = src
    self.dst = dst
    self.ttl = ttl
    self.born = born
    self.hops = 0
    self.resent = resent
    self.background = background
    self.echo = echo

  def __repr__(self):
    return f"<Packet {self.pid} {self.kind} flow={self.flow_id} seq={self.seq} {self.src}->{self.dst}>"

class PacketFactory:
  """Hands out packets with unique ids."""

  def __init__(self, ttl=32):
    self.ttl = ttl
    self._next_id = 1

  def make(self, kind, flow_id, seq, chunk, src, dst, born, resent=False, background=False,
           echo=None):
    packet = Packet(self._next_id, flow_id, kind, seq, chunk, src, dst,
                    self.ttl, born, resent, background, echo)
    self._next_id += 1
    return packet

def split_message(text, size):
  """Cut text into pieces of at most `size` characters."""
  if size < 1:
    raise ValueError("piece size must be at least 1")
  return [text[i:i + size] for i in range(0, len(text), size)]

def join_pieces(pieces, width, gap="·"):
  """Glue received pieces back together, showing missing ones as gaps.

  `pieces` holds either the received text or None. A missing piece is
  drawn as `width` gap marks, except the last one, which may be shorter
  than the others and so only gets a single mark.
  """
  last = len(pieces) - 1
  out = []
  for index, piece in enumerate(pieces):
    if piece is not None:
      out.append(piece)
    else:
      out.append(gap * (1 if index == last else max(1, width)))
  return "".join(out)
