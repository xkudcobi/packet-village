"""Saving towns to JSON files and loading them back safely."""

import json

from .topology import Network, TopologyError

FORMAT_NAME = "packet-village-town"
FORMAT_VERSION = 1

class TownFileError(Exception):
  """A problem with a town file; `key` names the message to show."""

  def __init__(self, key, **params):
    super().__init__(f"{key} {params}" if params else key)
    self.key = key
    self.params = params

def town_to_json(network, title=None):
  data = {"format": FORMAT_NAME, "version": FORMAT_VERSION}
  if title:
    data["title"] = str(title)
  data.update(network.to_dict())
  return json.dumps(data, ensure_ascii=False, indent=2)

def town_from_json(text):
  """Parse and validate; returns (network, title)."""
  try:
    data = json.loads(text)
  except json.JSONDecodeError as exc:
    raise TownFileError("err_file_json", line=exc.lineno) from exc
  if not isinstance(data, dict) or data.get("format") != FORMAT_NAME:
    raise TownFileError("err_file_format")
  version = data.get("version")
  if not isinstance(version, int) or version < 1:
    raise TownFileError("err_file_format")
  if version > FORMAT_VERSION:
    raise TownFileError("err_file_version", version=version)
  if not isinstance(data.get("nodes"), list) or not isinstance(data.get("links"), list):
    raise TownFileError("err_file_town", detail="nodes/links")
  try:
    network = Network.from_dict(data)
  except TopologyError as exc:
    raise TownFileError("err_file_town", detail=str(exc)) from exc
  if len(network.houses()) < 2:
    raise TownFileError("err_file_empty")
  title = data.get("title")
  return network, (str(title) if title else None)

def save_town(network, path, title=None):
  try:
    with open(path, "w", encoding="utf-8") as handle:
      handle.write(town_to_json(network, title))
  except OSError as exc:
    raise TownFileError("err_file_write", detail=exc.strerror or str(exc)) from exc

def load_town(path):
  try:
    with open(path, "r", encoding="utf-8") as handle:
      text = handle.read()
  except UnicodeDecodeError as exc:
    raise TownFileError("err_file_format") from exc
  except OSError as exc:
    raise TownFileError("err_file_read", detail=exc.strerror or str(exc)) from exc
  return town_from_json(text)
