"""Command line entry point: opens the window, or runs a letter in the terminal."""

import argparse
import sys

from .engine import SimConfig, Simulation, SimulationError
from .i18n import LANGUAGES, Translator, normalize_language
from .narrate import node_label, route_text, story_lines
from .scenarios import DEFAULT_SCENARIO, SCENARIOS, get_scenario, scenario_keys
from .storage import TownFileError, load_town

def _peek_language(argv):
  """Find --lang before argparse runs, so the help text is translated too."""
  for index, arg in enumerate(argv):
    if arg == "--lang" and index + 1 < len(argv):
      return normalize_language(argv[index + 1])
    if arg.startswith("--lang="):
      return normalize_language(arg.split("=", 1)[1])
  return None

def _formatter_for(tr):
  class TranslatedFormatter(argparse.HelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
      super().add_usage(usage, actions, groups, prefix or tr.t("cli_usage"))

  return TranslatedFormatter

def build_parser(tr):
  parser = argparse.ArgumentParser(prog="packet-village", description=tr.t("cli_description"),
                                   formatter_class=_formatter_for(tr), add_help=False)
  parser._optionals.title = tr.t("cli_options")
  parser.add_argument("-h", "--help", action="help", help=tr.t("cli_help_help"))
  parser.add_argument("--lang", choices=LANGUAGES, help=tr.t("cli_help_lang"))
  parser.add_argument("--headless", action="store_true", help=tr.t("cli_help_headless"))
  parser.add_argument("--list", action="store_true", help=tr.t("cli_help_list"))
  parser.add_argument("--scenario", default=None, help=tr.t("cli_help_scenario"))
  parser.add_argument("--file", default=None, help=tr.t("cli_help_file"))
  parser.add_argument("--from", dest="sender", default=None, help=tr.t("cli_help_from"))
  parser.add_argument("--to", dest="receiver", default=None, help=tr.t("cli_help_to"))
  parser.add_argument("--message", default=None, help=tr.t("cli_help_message"))
  parser.add_argument("--ticks", type=int, default=3000, help=tr.t("cli_help_ticks"))
  parser.add_argument("--seed", type=int, default=None, help=tr.t("cli_help_seed"))
  parser.add_argument("--cut", action="append", default=[], help=tr.t("cli_help_cut"))
  parser.add_argument("--chatter", type=float, default=0.0, help=tr.t("cli_help_chatter"))
  parser.add_argument("--noise", type=float, default=0.0, help=tr.t("cli_help_noise"))
  return parser

class CliError(Exception):
  pass

def find_house(network, name):
  wanted = name.strip().casefold()
  for node in network.nodes.values():
    if node.is_house and (node.id.casefold() == wanted or node.name.casefold() == wanted):
      return node.id
  return None

def _resolve_node(network, spec):
  if spec in network.nodes:
    return spec
  return find_house(network, spec)

def run_headless(args, tr, out=print):
  """Send one letter through the chosen town and narrate it. Returns exit code."""
  if args.file:
    try:
      network, title = load_town(args.file)
    except TownFileError as exc:
      raise CliError(tr.t(exc.key, **exc.params)) from exc
    town_name = title or tr.t("sc_loaded")
    sender, receiver = network.houses()[0], network.houses()[-1]
  else:
    key = args.scenario or DEFAULT_SCENARIO
    scenario = get_scenario(key)
    if scenario is None:
      raise CliError(tr.t("cli_unknown_scenario", name=key, names=", ".join(scenario_keys())))
    network = scenario.build()
    town_name = tr.t(scenario.title_key)
    sender, receiver = scenario.sender, scenario.receiver

  house_names = ", ".join(network.nodes[h].name for h in network.houses())
  for role, value in (("sender", args.sender), ("receiver", args.receiver)):
    if value is None:
      continue
    found = find_house(network, value)
    if found is None:
      raise CliError(tr.t("cli_unknown_house", name=value, names=house_names))
    if role == "sender":
      sender = found
    else:
      receiver = found

  config = SimConfig(chatter=min(max(args.chatter, 0.0), 1.0),
                     noise=min(max(args.noise, 0.0), 0.9))
  sim = Simulation(network, config, seed=args.seed)

  for spec in args.cut:
    ends = spec.split("-")
    nodes = [_resolve_node(network, e) for e in ends] if len(ends) == 2 else []
    if len(nodes) != 2 or None in nodes or network.link(*nodes) is None:
      raise CliError(tr.t("cli_bad_cut", spec=spec))
    sim.set_link_up(nodes[0], nodes[1], False)
  if args.cut:
    sim.routing.converge()

  text = args.message or tr.t("demo_1")
  out(tr.t("cli_town", name=town_name))
  out(tr.t("cli_letter", src=node_label(network, sender, tr),
           dst=node_label(network, receiver, tr), text=text))
  path, reached = sim.routing.path(sender, receiver)
  if reached:
    out(tr.t("cli_route", path=route_text(network, path, tr)))
  else:
    out(tr.t("cli_no_route", src=node_label(network, sender, tr), dst=node_label(network, receiver, tr)))

  try:
    flow = sim.send_message(sender, receiver, text)
  except SimulationError as exc:
    raise CliError(tr.t(exc.key, **exc.params)) from exc

  last_shown = None
  for _ in range(max(1, args.ticks)):
    sim.step()
    shown = flow.progress_text()
    if shown != last_shown:
      out(tr.t("cli_progress", tick=sim.tick, text=shown))
      last_shown = shown
    if flow.delivered or not flow.active:
      break

  out("")
  out(tr.t("cli_story"))
  for line in story_lines(sim.events, network, tr, limit=25):
    out("  " + line)
  out("")
  stats = sim.stats
  out(tr.t("cli_summary", sent=stats.sent, resent=stats.retransmits, lost=stats.dropped))
  if flow.delivered:
    out(tr.t("cli_result_delivered", ticks=flow.trip_time()))
    return 0
  if not flow.active:
    out(tr.t("cli_result_failed"))
    return 2
  out(tr.t("cli_result_timeout", ticks=sim.tick))
  return 3

def list_scenarios(tr, out=print):
  out(tr.t("cli_list_header"))
  for scenario in SCENARIOS:
    out(f"  {scenario.key:<10} {tr.t(scenario.title_key)} - {tr.t(scenario.blurb_key)}")

def main(argv=None):
  argv = sys.argv[1:] if argv is None else argv
  tr = Translator(_peek_language(argv))
  _make_stdout_friendly()
  args = build_parser(tr).parse_args(argv)
  if args.lang:
    tr.set_language(args.lang)

  if args.list:
    list_scenarios(tr)
    return 0
  if args.headless:
    try:
      return run_headless(args, tr)
    except CliError as exc:
      print(exc, file=sys.stderr)
      return 1

  try:
    from .ui.app import launch
  except ImportError:
    print(tr.t("cli_gui_missing"), file=sys.stderr)
    return 1
  return launch(lang=args.lang, scenario=args.scenario, town_file=args.file)

def _make_stdout_friendly():
  # Pipes on Windows often default to a code page without "ğ" or "→";
  # switch those to UTF-8 and never crash on an unprintable character.
  for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
      continue
    try:
      "ğİ→·".encode(stream.encoding or "ascii")
      reconfigure(errors="replace")
    except UnicodeEncodeError:
      reconfigure(encoding="utf-8", errors="replace")
    except (LookupError, ValueError, OSError):
      pass
