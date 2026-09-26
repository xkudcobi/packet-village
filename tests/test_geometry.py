import unittest

from packet_village.geometry import Viewport, mix_color, point_segment_distance, unit_and_normal

class GeometryTest(unittest.TestCase):
  def test_point_segment_distance(self):
    self.assertAlmostEqual(point_segment_distance(5, 3, 0, 0, 10, 0), 3)
    self.assertAlmostEqual(point_segment_distance(-3, 4, 0, 0, 10, 0), 5)
    self.assertAlmostEqual(point_segment_distance(1, 1, 0, 0, 0, 0), 2 ** 0.5)

  def test_unit_and_normal(self):
    ux, uy, nx, ny, length = unit_and_normal(0, 0, 3, 4)
    self.assertAlmostEqual(length, 5)
    self.assertAlmostEqual(ux * nx + uy * ny, 0)
    self.assertEqual(unit_and_normal(1, 1, 1, 1), (0.0, 0.0, 0.0, 0.0, 0.0))

  def test_mix_color(self):
    self.assertEqual(mix_color("#000000", "#ffffff", 0), "#000000")
    self.assertEqual(mix_color("#000000", "#ffffff", 1), "#ffffff")
    self.assertEqual(mix_color("#000000", "#ff0000", 0.5), "#800000")
    self.assertEqual(mix_color("#000000", "#ffffff", 7), "#ffffff")

  def test_viewport_round_trip(self):
    vp = Viewport(1000, 500, margin=10)
    vp.fit(620, 800)
    self.assertAlmostEqual(vp.scale, 0.6)
    sx, sy = vp.to_screen(250, 100)
    wx, wy = vp.to_world(sx, sy)
    self.assertAlmostEqual(wx, 250)
    self.assertAlmostEqual(wy, 100)
    self.assertEqual(vp.clamp_world(-5, 900), (20, 480))

  def test_tiny_canvas_does_not_divide_by_zero(self):
    vp = Viewport(1000, 640)
    vp.fit(0, 0)
    self.assertGreater(vp.scale, 0)

if __name__ == "__main__":
  unittest.main()
