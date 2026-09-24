"""Small 2D helpers shared by the drawing code and its hit testing."""

import math

def point_segment_distance(px, py, ax, ay, bx, by):
  dx = bx - ax
  dy = by - ay
  length_sq = dx * dx + dy * dy
  if length_sq == 0:
    return math.hypot(px - ax, py - ay)
  t = ((px - ax) * dx + (py - ay) * dy) / length_sq
  t = min(1.0, max(0.0, t))
  return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

def unit_and_normal(ax, ay, bx, by):
  """Direction a->b as a unit vector, plus its right-hand normal."""
  dx = bx - ax
  dy = by - ay
  length = math.hypot(dx, dy)
  if length == 0:
    return 0.0, 0.0, 0.0, 0.0, 0.0
  ux = dx / length
  uy = dy / length
  return ux, uy, -uy, ux, length

def mix_color(first, second, amount):
  """Blend two '#rrggbb' colours; amount 0 gives first, 1 gives second."""
  amount = min(1.0, max(0.0, amount))
  a = int(first[1:], 16)
  b = int(second[1:], 16)
  out = 0
  for shift in (16, 8, 0):
    ca = (a >> shift) & 0xFF
    cb = (b >> shift) & 0xFF
    out |= int(round(ca + (cb - ca) * amount)) << shift
  return f"#{out:06x}"

class Viewport:
  """Maps the fixed-size world onto a canvas of any size, keeping aspect."""

  def __init__(self, world_width, world_height, margin=24):
    self.world_width = world_width
    self.world_height = world_height
    self.margin = margin
    self.scale = 1.0
    self.offset_x = 0.0
    self.offset_y = 0.0

  def fit(self, width, height):
    usable_w = max(1, width - 2 * self.margin)
    usable_h = max(1, height - 2 * self.margin)
    self.scale = min(usable_w / self.world_width, usable_h / self.world_height)
    self.offset_x = (width - self.world_width * self.scale) / 2
    self.offset_y = (height - self.world_height * self.scale) / 2

  def to_screen(self, x, y):
    return self.offset_x + x * self.scale, self.offset_y + y * self.scale

  def to_world(self, sx, sy):
    return (sx - self.offset_x) / self.scale, (sy - self.offset_y) / self.scale

  def clamp_world(self, x, y, pad=20):
    return (min(max(x, pad), self.world_width - pad),
            min(max(y, pad), self.world_height - pad))
