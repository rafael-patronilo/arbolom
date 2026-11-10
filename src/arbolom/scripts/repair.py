"""Command line interface to repair a model given the inconsistencies found by
arbolom-consistency (the second step of a two-step revision; arbolom-revision
does both steps at once).

Usage: arbolom-repair -f (FILENAME) -i (INCONSISTENCIES) -stable -sync -async
Optional flags:
-stable -> Performs repairs using stable state observations (default).
-sync -> Performs repairs using synchronous observations.
-async -> Performs repairs using asynchronous observations.
Variables:
FILENAME -> Path of file containing Boolean model in the BCF format written in .lp or .bnet.
INCONSISTENCIES -> Path of file containing inconsistencies obtained from the consistency checking phase.

Examples:
  arbolom-repair -f simple_models/lp/corrupted/8/8-corrupted-f.lp -i simple_models/lp/corrupted/8/inconsistencies/8-corrupted-f-sync_inconsistency.lp -sync
  arbolom-repair -f real_models/lp/corrupted/SP_1cell/SP_1cell-corrupted-f.lp -i real_models/lp/corrupted/SP_1cell/inconsistencies/SP_1cell-corrupted-f-stable_inconsistency.lp
"""
import argparse
import logging
import sys
import time

from arbolom.conversion import read_model
from arbolom.lp_model import format_model_dict, model_to_dict
from arbolom.modes import UpdateMode
from arbolom.repair.criteria import print_criteria
from arbolom.revision import DEFAULT_CRITERIA, ModelReviser, RevisionSettings, resolve_parallel_mode


def build_parser():
  parser = argparse.ArgumentParser(description="Repair an inconsistent Boolean logical model in the BCF written in lp, given a set of observations and inconsistent compounds, both written in lp.")
  parser.add_argument("-f", "--model_to_repair", help="Path to model to repair.", required=True)
  parser.add_argument("-i", "--inconsistencies", help="Path to inconsistencies obtained from the consistency checking phase.", required=True)
  parser.add_argument("-stable", "--stable_state", action='store_true', help="Flag to repair using stable state observations (default).")
  parser.add_argument("-sync", "--synchronous", action='store_true', help="Flag to repair using synchronous observations (default is stable state).")
  parser.add_argument("-async", "--asynchronous", action='store_true', help="Flag to repair using asynchronous observations (default is stable state).")
  parser.add_argument("-t", "--timeout", type=int, default=3600, help="How many seconds to wait for the repairs.")
  parser.add_argument("-p", "--parallel_mode", type=str, default=None,
                      help="What to pass to clingo's --parallel-mode argument. " \
                      "The value 'auto' will choose the number of threads based on the number of available CPU cores.")
  parser.add_argument("-criteria", "--criteria", default=",".join(DEFAULT_CRITERIA),
                      help="Comma separated list of the criteria to use to minimize changes, in order of priority. " \
                      "For the list of available criteria use --help-criteria. Default is %(default)s.")
  parser.add_argument("-disable-criteria", "--disable-criteria", default="",
                      help="Comma separated list of the criteria to disable. Default is %(default)s.")
  parser.add_argument("-help-criteria", "--help-criteria", action='store_true', help="Prints the available criteria to the console and exits.")
  return parser


def main(argv=None):
  logging.basicConfig()
  logging.getLogger("global").setLevel(logging.INFO)
  args = build_parser().parse_args(argv)
  if args.help_criteria:
    print_criteria()
    return 0

  settings = RevisionSettings(
    mode=UpdateMode.from_flags(args.stable_state, args.synchronous, args.asynchronous),
    min_change_criteria=args.criteria.split(','),
    disable_change_criteria=args.disable_criteria.split(',') if args.disable_criteria else [],
    timeout=args.timeout,
    parallel_mode=resolve_parallel_mode(args.parallel_mode),
  )
  model = read_model(args.model_to_repair)
  if model is None:
    return 1
  with open(args.inconsistencies) as f:
    inconsistencies = f.read()

  start_time = time.monotonic()
  reviser = ModelReviser(settings)
  model_dict = model_to_dict(model)
  final_state = reviser.repair(model, inconsistencies, reviser.init_revision_stats(model), model_dict)
  print(f"Final model state: {final_state}")
  print(format_model_dict(model_dict))
  print(f"Total time taken: {time.monotonic()-start_time}s")
  return 0


if __name__ == "__main__":
  sys.exit(main())
