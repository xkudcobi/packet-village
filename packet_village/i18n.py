"""Language selection and lookup on top of the string tables."""

import locale
import os
import sys

from .strings import TABLES

LANGUAGES = ("en", "tr")
DEFAULT_LANGUAGE = "en"

def normalize_language(value):
  """Map things like 'tr_TR.UTF-8' or 'Turkish_Turkey' to 'tr'/'en'."""
  if not value:
    return None
  value = str(value).strip().lower()
  if value.startswith("tr") or value.startswith("turkish"):
    return "tr"
  if value.startswith("en") or value.startswith("english"):
    return "en"
  return None

def _windows_ui_language():
  try:
    import ctypes
    lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
  except (ImportError, AttributeError, OSError):
    return None
  # The low ten bits are the primary language; 0x1F is Turkish.
  return "tr" if lang_id & 0x3FF == 0x1F else "en"

def detect_language(environ=None, platform=None):
  """Pick a language from the environment, falling back to English.

  Any recognised locale decides; an unrecognised one (say de_DE) means
  English, since that is the only other language we have.
  """
  environ = os.environ if environ is None else environ
  platform = sys.platform if platform is None else platform
  for name in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
    raw = environ.get(name)
    if raw:
      if raw in ("C", "POSIX"):
        continue
      return normalize_language(raw.split(":")[0]) or DEFAULT_LANGUAGE
  try:
    found = normalize_language(locale.getlocale()[0])
  except (ValueError, TypeError):
    found = None
  if found:
    return found
  if platform == "win32":
    return _windows_ui_language() or DEFAULT_LANGUAGE
  return DEFAULT_LANGUAGE

class Translator:
  """Looks sentences up in the active language and tells listeners on change."""

  def __init__(self, lang=None):
    self.lang = normalize_language(lang) or detect_language()
    self._listeners = []

  def t(self, key, **params):
    table = TABLES[self.lang]
    template = table.get(key)
    if template is None:
      template = TABLES[DEFAULT_LANGUAGE].get(key, key)
    if not params:
      return template
    try:
      return template.format(**params)
    except (KeyError, IndexError, ValueError):
      return template

  def set_language(self, lang):
    lang = normalize_language(lang)
    if lang is None or lang == self.lang:
      return False
    previous, self.lang = self.lang, lang
    for listener in list(self._listeners):
      listener(lang, previous)
    return True

  def toggle(self):
    self.set_language("en" if self.lang == "tr" else "tr")
    return self.lang

  def subscribe(self, listener):
    self._listeners.append(listener)
