import os
import tempfile
import unittest

from packet_village.cli import CliError, build_parser, find_house, list_scenarios, run_headless
from packet_village.i18n import Translator
from packet_village.scenarios import build_village
from packet_village.storage import save_town

def headless(*argv, lang="en"):
  tr = Translator(lang)
  args = build_parser(tr).parse_args(["--headless", *argv])
  lines = []
  code = run_headless(args, tr, out=lines.append)
  return code, lines

class HeadlessTest(unittest.TestCase):
  def test_default_letter_is_delivered(self):
    code, lines = headless("--seed", "1")
    self.assertEqual(code, 0)
    self.assertEqual(lines[0], "Town: Little village")
    self.assertTrue(lines[-1].startswith("Delivered after"))

  def test_turkish_output(self):
    code, lines = headless("--seed", "1", "--scenario", "ring", lang="tr")
    self.assertEqual(code, 0)
    self.assertEqual(lines[0], "Kasaba: Yuvarlak kasaba")
    self.assertTrue(lines[-1].endswith("teslim edildi."))

  def test_custom_houses_and_message(self):
    code, lines = headless("--from", "MERT", "--to", "kerem", "--message", "hi!")
    self.assertEqual(code, 0)
    self.assertIn('"hi!"', lines[1])
    self.assertTrue(any(line.endswith("hi!") for line in lines))

  def test_cut_forces_a_detour(self):
    code, lines = headless("--cut", "A-D", "--cut", "B-D")
    self.assertEqual(code, 0)
    self.assertIn("Post B", lines[2])

  def test_cutting_off_the_receiver_fails(self):
    code, lines = headless("--cut", "E-elif", "--ticks", "20000")
    self.assertEqual(code, 2)
    self.assertTrue(any("no way" in line for line in lines))

  def test_timeout(self):
    code, _ = headless("--ticks", "3")
    self.assertEqual(code, 3)

  def test_errors(self):
    for argv in (("--scenario", "atlantis"), ("--from", "Gandalf"), ("--cut", "A"),
                 ("--cut", "A-C"), ("--file", "/no/such/town.json")):
      with self.subTest(argv=argv):
        with self.assertRaises(CliError):
          headless(*argv)

  def test_town_file(self):
    with tempfile.TemporaryDirectory() as folder:
      path = os.path.join(folder, "mine.json")
      save_town(build_village(), path, title="My village")
      code, lines = headless("--file", path)
      self.assertEqual(code, 0)
      self.assertEqual(lines[0], "Town: My village")

  def test_list(self):
    lines = []
    list_scenarios(Translator("tr"), out=lines.append)
    self.assertEqual(lines[0], "Hazır kasabalar:")
    self.assertEqual(len(lines), 5)

  def test_find_house(self):
    net = build_village()
    self.assertEqual(find_house(net, " Elif "), "elif")
    self.assertIsNone(find_house(net, "A"))

if __name__ == "__main__":
  unittest.main()
