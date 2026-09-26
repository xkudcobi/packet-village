import string
import unittest

from packet_village.engine import Simulation
from packet_village.i18n import Translator, detect_language, normalize_language
from packet_village.narrate import describe_event, node_label, routing_report, story_lines
from packet_village.scenarios import SCENARIOS, build_village
from packet_village.strings import EN, TR

def placeholders(template):
  return {name for _, name, _, _ in string.Formatter().parse(template) if name}

class TableTest(unittest.TestCase):
  def test_same_keys_in_both_languages(self):
    self.assertEqual(set(EN), set(TR))

  def test_same_placeholders(self):
    for key in EN:
      with self.subTest(key=key):
        self.assertEqual(placeholders(EN[key]), placeholders(TR[key]))

  def test_no_empty_strings(self):
    for table in (EN, TR):
      for key, value in table.items():
        self.assertTrue(value.strip(), key)

  def test_every_scenario_has_text(self):
    for scenario in SCENARIOS:
      self.assertIn(scenario.title_key, EN)
      self.assertIn(scenario.blurb_key, EN)

class LanguageDetectionTest(unittest.TestCase):
  def test_normalize(self):
    self.assertEqual(normalize_language("tr_TR.UTF-8"), "tr")
    self.assertEqual(normalize_language("Turkish_Turkey"), "tr")
    self.assertEqual(normalize_language("EN-us"), "en")
    self.assertIsNone(normalize_language("de_DE"))
    self.assertIsNone(normalize_language(None))

  def test_environment_wins(self):
    self.assertEqual(detect_language({"LANG": "tr_TR.UTF-8"}, "linux"), "tr")
    self.assertEqual(detect_language({"LC_ALL": "en_GB.UTF-8", "LANG": "tr_TR"}, "linux"), "en")
    self.assertEqual(detect_language({"LANGUAGE": "tr:en"}, "linux"), "tr")

  def test_unknown_locale_means_english(self):
    self.assertEqual(detect_language({"LANG": "de_DE.UTF-8"}, "linux"), "en")

  def test_c_locale_is_skipped(self):
    self.assertIn(detect_language({"LANG": "C"}, "linux"), ("en", "tr"))

class TranslatorTest(unittest.TestCase):
  def test_lookup_and_format(self):
    tr = Translator("tr")
    self.assertEqual(tr.t("router_label", tag="B"), "Postane B")
    self.assertEqual(Translator("en").t("router_label", tag="B"), "Post B")

  def test_missing_key_and_params_do_not_crash(self):
    tr = Translator("en")
    self.assertEqual(tr.t("no_such_key"), "no_such_key")
    self.assertEqual(tr.t("router_label"), "Post {tag}")
    self.assertEqual(tr.t("router_label", wrong=1), "Post {tag}")

  def test_listeners_hear_changes(self):
    tr = Translator("en")
    heard = []
    tr.subscribe(lambda new, old: heard.append((new, old)))
    self.assertTrue(tr.set_language("tr"))
    self.assertFalse(tr.set_language("tr"))
    self.assertFalse(tr.set_language("fr"))
    self.assertEqual(tr.toggle(), "en")
    self.assertEqual(heard, [("tr", "en"), ("en", "tr")])

class NarrationTest(unittest.TestCase):
  def test_labels(self):
    net = build_village()
    self.assertEqual(node_label(net, "A", Translator("tr")), "Postane A")
    self.assertEqual(node_label(net, "ada", Translator("tr")), "Ada")
    self.assertEqual(node_label(net, "ghost", Translator("en")), "somewhere")

  def test_events_read_well_in_both_languages(self):
    net = build_village()
    event = (5, "ev_drop_queue", {"flow": 1, "seq": 2, "node": "B"})
    self.assertEqual(describe_event(event, net, Translator("en")),
                     "Envelope 3 was thrown away at Post B: the shelf was full.")
    self.assertIn("Postane B", describe_event(event, net, Translator("tr")))

  def test_every_engine_event_can_be_told(self):
    sim = Simulation(build_village(), seed=3)
    sim.send_message("ada", "elif", "story time")
    sim.set_link_up("A", "D", False)
    sim.run(300)
    sim.set_link_up("A", "D", True)
    for lang in ("en", "tr"):
      lines = story_lines(sim.events, sim.network, Translator(lang))
      self.assertTrue(lines)
      for line in lines:
        self.assertNotIn("{", line)

  def test_routing_report(self):
    sim = Simulation(build_village())
    lines = routing_report(sim, "A", Translator("en"))
    self.assertEqual(len(lines), 6)
    self.assertTrue(any(line.startswith("Ada: via Ada") for line in lines))

if __name__ == "__main__":
  unittest.main()
