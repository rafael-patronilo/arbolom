"""Command line interface to revise a model (ARBoLoM's original interface).

Usage: arbolom-revision -f (FILENAME) -o (OBSERVATIONS) -stable -sync -async -benchmark
       (or: python -m arbolom.scripts.revision ...)
Optional flags:
-stable -> Performs repairs using stable state observations (default).
-sync -> Performs repairs using synchronous observations.
-async -> Performs repairs using asynchronous observations.
-benchmark -> Enables benchmark mode
Variables:
FILENAME -> Path of file containing the BCF Boolean model written in .lp or .bnet format
OBSERVATIONS -> Path of file containing observations written in lp.

Note: Benchmark mode disables all prints, and outputs one CSV row per compound
with the name of the revised file, its final state, the revision, consistency
checking and repair times, followed by the statistics of the compound.
"""
import argparse
import logging
import sys

from arbolom.conversion import read_model
from arbolom.modes import UpdateMode
from arbolom.repair.criteria import CRITERIA, print_criteria
from arbolom.revision import DEFAULT_CRITERIA, ModelReviser, RevisionSettings, resolve_parallel_mode

LOG_FILE = 'revision.log'


#Purpose: Builds the argument parser of the revision command
def build_parser():
  parser = argparse.ArgumentParser(description="Revise a Boolean logical model in the BCF written in .lp or .bnet format, given a set of observations written in .lp format.")
  requiredNamed = parser.add_argument_group("required arguments")
  requiredNamed.add_argument("-f", "--model_to_repair", help="Path of model to revise.", required=True)
  requiredNamed.add_argument("-o", "--observations", help="Path of observations from real-world model.", required=True)
  requiredNamed.add_argument("-s", "--save_path", help="Path to save repaired function to. If a directory is passed, a file with same name as the original funcion will be created there.", default=None)
  parser.add_argument("-stable", "--stable_state", action='store_true', help="Flag to check the consistency using stable state observations (default).")
  parser.add_argument("-sync", "--synchronous", action='store_true', help="Flag to check the consistency using synchronous observations (default is stable state).")
  parser.add_argument("-async", "--asynchronous", action='store_true', help="Flag to check the consistency using asynchronous observations (default is stable state).")
  parser.add_argument("-bulk", "--bulk", action='store_true', help="Enables the revision of multiple models at once. (Note: the path provided to -f must be the directory containing those models).")
  parser.add_argument("-benchmark", "--benchmark_output", action='store_true', help="Enables benchmark mode, outputting benchmark results ato STDOUT.")
  parser.add_argument("-t", "--timeout", type=int, default=3600, help="How many seconds to wait for each function repair.")
  parser.add_argument("-p", "--parallel_mode", type=str, default=None,
                      help="What to pass to clingo's --parallel-mode argument. " \
                      "The value 'auto' will choose the number of threads based on the number of available CPU cores.")
  parser.add_argument("-criteria", "--criteria", default=",".join(DEFAULT_CRITERIA),
                      help="Comma separated list of the criteria to use to minimize changes, in order of priority. For the list of available criteria use --help-criteria. Default is %(default)s.")
  parser.add_argument("-disable-criteria", "--disable-criteria", default="",
                      help="Comma separated list of the criteria to disable. For the list of available criteria use --help-criteria. Default is %(default)s.")
  parser.add_argument("-help-criteria", "--help-criteria", action='store_true', help="Prints the available criteria to the console and exits.")
  parser.add_argument("--no-sanity-checks", action='store_true', help="Disables the validation of the change counts and of the consistency of the repaired model.")
  return parser


#Purpose: Converts the parsed arguments into RevisionSettings
def settings_from_args(args) -> RevisionSettings:
  logger = logging.getLogger("parser")

  min_change_criteria = list(DEFAULT_CRITERIA)
  disable_change_criteria = []
  if args.criteria:
    min_change_criteria = args.criteria.split(',')
    for x in min_change_criteria:
      assert x in CRITERIA, f"Invalid criterion specified: {x}. Use --help-criteria to see available criteria."
  if args.disable_criteria:
    disable_change_criteria = args.disable_criteria.split(',')
    for x in disable_change_criteria:
      assert x in CRITERIA, f"Invalid criterion specified: {x}. Use --help-criteria to see available criteria."

  parallel_mode = resolve_parallel_mode(args.parallel_mode)
  if parallel_mode:
    logger.info(f"Parallel argument set to: --parallel-mode {parallel_mode}")

  mode = UpdateMode.from_flags(args.stable_state, args.synchronous, args.asynchronous)
  if not (args.stable_state or args.synchronous or args.asynchronous):
    logger.info(f"Default mode: {mode.description}")
  else:
    logger.info(f"Mode used: {mode.description}")

  return RevisionSettings(
    mode=mode,
    min_change_criteria=min_change_criteria,
    disable_change_criteria=disable_change_criteria,
    timeout=args.timeout,
    parallel_mode=parallel_mode,
    quiet=args.benchmark_output,
    sanity_checks=not args.no_sanity_checks,
  )


def main(argv=None):
  logging.basicConfig(filename=LOG_FILE,
                      format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                      datefmt='%Y-%m-%d %H:%M:%S',
                      level=logging.DEBUG)
  global_logger = logging.getLogger("global")
  try:
    args = build_parser().parse_args(argv)
    logging.getLogger("parser").info(f"Received arguments: {args}")
    if args.help_criteria:
      print_criteria()
      return 0
    settings = settings_from_args(args)

    logging.getLogger("parser").debug("Obtained model: " + args.model_to_repair)
    logging.getLogger("parser").debug("Obtained observations: " + args.observations)

    # First, obtain the model in .lp format. If the obtained file has .bnet
    # extension, it is converted to .lp.
    model = read_model(args.model_to_repair)
    if model is None:
      return 1

    result = ModelReviser(settings).revise(model, args.observations, model_name=args.model_to_repair)

    if settings.quiet: # benchmark mode
      for row in result.benchmark_rows():
        print(row)
    return 0
  except Exception as e:
    global_logger.exception(f"An unexpected exception occurred during the revision process: {e}")
    raise


if __name__ == "__main__":
  sys.exit(main())
