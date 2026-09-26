"""User preferences that survive a restart, kept in a small JSON file."""

import json
import os
from pathlib import Path

from .i18n import normalize_language
from .scenarios import DEFAULT_SCENARIO, scenario_keys

# name -> (default, minimum, maximum, type)
LIMITS = {
  "speed": (10.0, 1.0, 40.0, float),
  "chatter": (0.25, 0.0, 1.0, float),
  "noise": (0.0, 0.0, 0.1, float),
  "queue_size": (8, 1, 24, int),
  "chunk_size": (3, 1, 12, int),
}

def default_path():
  override = os.environ.get("PACKET_VILLAGE_SETTINGS")
  if override:
    return Path(override)
  return Path.home() / ".packet_village.json"

def clamp_setting(name, value):
  default, low, high, kind = LIMITS[name]
  try:
    value = kind(value)
  except (TypeError, ValueError):
    return default
  if value != value:  # NaN
    return default
  return min(max(value, low), high)

class Settings:
  def __init__(self, **values):
    self.lang = normalize_language(values.get("lang"))
    scenario = values.get("scenario")
    self.scenario = scenario if scenario in scenario_keys() else DEFAULT_SCENARIO
    for name, (default, _, _, _) in LIMITS.items():
      setattr(self, name, clamp_setting(name, values[name]) if name in values else default)

  def update(self, name, value):
    if name not in LIMITS:
      raise KeyError(name)
    setattr(self, name, clamp_setting(name, value))
    return getattr(self, name)

  def to_dict(self):
    data = {name: getattr(self, name) for name in LIMITS}
    data["lang"] = self.lang
    data["scenario"] = self.scenario
    return data

def load_settings(path=None):
  """Read preferences; a missing or broken file simply gives defaults."""
  path = Path(path) if path else default_path()
  try:
    data = json.loads(path.read_text(encoding="utf-8"))
  except (OSError, ValueError):
    return Settings()
  if not isinstance(data, dict):
    return Settings()
  return Settings(**data)

def save_settings(settings, path=None):
  """Write preferences; returns False instead of crashing on a read-only home."""
  path = Path(path) if path else default_path()
  try:
    path.write_text(json.dumps(settings.to_dict(), indent=2), encoding="utf-8")
  except OSError:
    return False
  return True
