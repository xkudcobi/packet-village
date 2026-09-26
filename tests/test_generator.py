import unittest

from packet_village.generator import HOUSE_NAMES, random_town
from packet_village.scenarios import WORLD_HEIGHT, WORLD_WIDTH

class RandomTownTest(unittest.TestCase):
  def test_always_connected(self):
    for seed in range(40):
      net = random_town(seed=seed)
      first = next(iter(net.nodes))
      self.assertEqual(net.reachable_from(first), set(net.nodes), f"seed {seed}")

  def test_counts_and_names(self):
    net = random_town(seed=7, routers=5, houses=6)
    self.assertEqual(len(net.routers()), 5)
    self.assertEqual(len(net.houses()), 6)
    names = [net.nodes[h].name for h in net.houses()]
    self.assertEqual(len(set(names)), 6)
    self.assertTrue(all(name in HOUSE_NAMES for name in names))

  def test_same_seed_same_town(self):
    self.assertEqual(random_town(seed=3).to_dict(), random_town(seed=3).to_dict())
    self.assertNotEqual(random_town(seed=3).to_dict(), random_town(seed=4).to_dict())

  def test_everything_stays_on_the_map(self):
    for seed in range(20):
      for node in random_town(seed=seed).nodes.values():
        self.assertTrue(0 <= node.x <= WORLD_WIDTH)
        self.assertTrue(0 <= node.y <= WORLD_HEIGHT)

  def test_every_house_has_one_cable(self):
    net = random_town(seed=12)
    for house in net.houses():
      self.assertEqual(net.degree(house), 1)

  def test_crowded_town_still_builds(self):
    net = random_town(seed=1, routers=16, houses=20)
    self.assertEqual(len(net.nodes), 36)

  def test_bad_sizes(self):
    with self.assertRaises(ValueError):
      random_town(routers=1)
    with self.assertRaises(ValueError):
      random_town(houses=len(HOUSE_NAMES) + 1)

if __name__ == "__main__":
  unittest.main()
