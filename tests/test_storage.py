import json
import os
import tempfile
import unittest

from packet_village.scenarios import build_village
from packet_village.storage import (FORMAT_NAME, FORMAT_VERSION, TownFileError, load_town,
                                    save_town, town_from_json, town_to_json)

class JsonTest(unittest.TestCase):
  def test_round_trip(self):
    net = build_village()
    net.link("A", "B").up = False
    loaded, title = town_from_json(town_to_json(net, title="Köyüm"))
    self.assertEqual(title, "Köyüm")
    self.assertEqual(loaded.to_dict(), net.to_dict())

  def test_title_is_optional(self):
    _, title = town_from_json(town_to_json(build_village()))
    self.assertIsNone(title)

  def assertFileError(self, text, key):
    with self.assertRaises(TownFileError) as caught:
      town_from_json(text)
    self.assertEqual(caught.exception.key, key)
    return caught.exception

  def test_broken_json_reports_the_line(self):
    error = self.assertFileError('{\n  "format": \n}', "err_file_json")
    self.assertEqual(error.params["line"], 3)

  def test_wrong_format(self):
    self.assertFileError("[]", "err_file_format")
    self.assertFileError('{"format": "spreadsheet"}', "err_file_format")
    self.assertFileError(json.dumps({"format": FORMAT_NAME, "version": "one"}), "err_file_format")

  def test_newer_version(self):
    data = {"format": FORMAT_NAME, "version": FORMAT_VERSION + 1, "nodes": [], "links": []}
    self.assertFileError(json.dumps(data), "err_file_version")

  def test_nonsense_town(self):
    data = json.loads(town_to_json(build_village()))
    data["links"].append({"a": "A", "b": "ghost"})
    self.assertFileError(json.dumps(data), "err_file_town")
    self.assertFileError(json.dumps({"format": FORMAT_NAME, "version": 1, "nodes": {}}),
                         "err_file_town")

  def test_too_few_houses(self):
    data = json.loads(town_to_json(build_village()))
    data["nodes"] = [n for n in data["nodes"] if n["kind"] == "router" or n["id"] == "ada"]
    data["links"] = [l for l in data["links"] if l["a"] not in ("deniz", "leyla", "mert", "kerem", "elif")
                     and l["b"] not in ("deniz", "leyla", "mert", "kerem", "elif")]
    self.assertFileError(json.dumps(data), "err_file_empty")

class FileTest(unittest.TestCase):
  def test_save_and_load(self):
    with tempfile.TemporaryDirectory() as folder:
      path = os.path.join(folder, "town.json")
      save_town(build_village(), path, title="Test")
      network, title = load_town(path)
      self.assertEqual(title, "Test")
      self.assertEqual(len(network.houses()), 6)

  def test_missing_file(self):
    with self.assertRaises(TownFileError) as caught:
      load_town(os.path.join(tempfile.gettempdir(), "definitely", "not", "here.json"))
    self.assertEqual(caught.exception.key, "err_file_read")

  def test_binary_file(self):
    with tempfile.TemporaryDirectory() as folder:
      path = os.path.join(folder, "picture.json")
      with open(path, "wb") as handle:
        handle.write(b"\xff\xfe\x00\x81garbage")
      with self.assertRaises(TownFileError) as caught:
        load_town(path)
      self.assertEqual(caught.exception.key, "err_file_format")

  def test_unwritable_path(self):
    with tempfile.TemporaryDirectory() as folder:
      with self.assertRaises(TownFileError) as caught:
        save_town(build_village(), folder)  # a directory, not a file
      self.assertEqual(caught.exception.key, "err_file_write")

if __name__ == "__main__":
  unittest.main()
