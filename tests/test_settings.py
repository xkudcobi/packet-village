import os
import tempfile
import unittest

from packet_village.settings import LIMITS, Settings, clamp_setting, load_settings, save_settings

class SettingsTest(unittest.TestCase):
  def test_defaults(self):
    settings = Settings()
    self.assertIsNone(settings.lang)
    self.assertEqual(settings.scenario, "village")
    for name, (default, _, _, _) in LIMITS.items():
      self.assertEqual(getattr(settings, name), default)

  def test_values_are_clamped_and_typed(self):
    self.assertEqual(clamp_setting("speed", 1000), 40.0)
    self.assertEqual(clamp_setting("queue_size", "5"), 5)
    self.assertEqual(clamp_setting("queue_size", -3), 1)
    self.assertEqual(clamp_setting("chatter", "lots"), 0.25)
    self.assertEqual(clamp_setting("noise", float("nan")), 0.0)

  def test_unknown_values_fall_back(self):
    settings = Settings(lang="klingon", scenario="atlantis", speed=None, extra=1)
    self.assertIsNone(settings.lang)
    self.assertEqual(settings.scenario, "village")
    self.assertEqual(settings.speed, 10.0)

  def test_update(self):
    settings = Settings()
    self.assertEqual(settings.update("chunk_size", 99), 12)
    with self.assertRaises(KeyError):
      settings.update("colour", "red")

  def test_file_round_trip(self):
    with tempfile.TemporaryDirectory() as folder:
      path = os.path.join(folder, "prefs.json")
      settings = Settings(lang="tr_TR", scenario="ring", speed=22)
      self.assertTrue(save_settings(settings, path))
      loaded = load_settings(path)
      self.assertEqual(loaded.lang, "tr")
      self.assertEqual(loaded.scenario, "ring")
      self.assertEqual(loaded.speed, 22.0)

  def test_broken_or_missing_file_gives_defaults(self):
    with tempfile.TemporaryDirectory() as folder:
      path = os.path.join(folder, "prefs.json")
      self.assertEqual(load_settings(path).to_dict(), Settings().to_dict())
      with open(path, "w", encoding="utf-8") as handle:
        handle.write("{not json")
      self.assertEqual(load_settings(path).to_dict(), Settings().to_dict())
      with open(path, "w", encoding="utf-8") as handle:
        handle.write("[1, 2]")
      self.assertEqual(load_settings(path).to_dict(), Settings().to_dict())

  def test_save_failure_is_reported_not_raised(self):
    with tempfile.TemporaryDirectory() as folder:
      self.assertFalse(save_settings(Settings(), folder))

if __name__ == "__main__":
  unittest.main()
