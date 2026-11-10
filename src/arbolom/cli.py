"""Command line interface compatible with pymodrev's.

Given a model and a set of observations, it determines if the model is
consistent. If not, it computes the repairs that render it consistent, using
ARBoLoM's consistency checking and repair.

    arbolom -m model.bnet -obs obs1.lp sync -t r -f c

ARBoLoM's original command line tools are available as arbolom-revision,
arbolom-consistency, etc.
"""
import argparse
import logging
import os
import re
import sys

from pymodrev.network.exceptions import EdgeNotFoundError, PyModRevError
from pymodrev.network.observation_set import ObservationSet
from pymodrev.updaters.factory import get_updater, is_valid_updater_type

from arbolom.api import Configuration
from arbolom.bridge import SUPPORTED_UPDATERS, UnsupportedObservationsError
from arbolom.consistency import NoAnswerSetError
from arbolom.engine import RevisionEngine
from arbolom.formats import ARBOLOM_LP, MODREV_LP, model_format, read_model_file, read_observation_file, write_model_file
from arbolom.repair.criteria import CRITERIA, print_criteria
from arbolom.revision import DEFAULT_CRITERIA, RevisionSettings, resolve_parallel_mode

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
  arg_parser = argparse.ArgumentParser(
    description="""ARBoLoM - ASP-based Revision of Boolean Logical Models (pymodrev-compatible interface).
Given a model and a set of observations, it determines if the model is consistent.
If not, it computes the repairs, minimizing changes according to the given criteria, in order to render it consistent.""",
    formatter_class=argparse.RawTextHelpFormatter,
  )
  arg_parser.add_argument("-m", "--model",
    help="Input model file (.bnet, .lp, .ginml, .zginml)")
  arg_parser.add_argument("-obs", "--observations", nargs='+', action='extend',
    metavar=('OBS', 'UPDATER'),
    help=f"""List of observation files and updater pairs.
Each observation *must* be followed by its updater type ({', '.join(SUPPORTED_UPDATERS)}).
Example: -obs obs1.lp sync obs2.lp sync
Or: -obs obs1.lp sync -obs obs2.lp sync""")
  arg_parser.add_argument('-t', '--task', choices=['c', 'r', 'm'], default='r',
    help="""Specify the task to perform (default=r):
    c - check for consistency
    r - get repairs
    m - get repaired models""")
  arg_parser.add_argument("--exhaustive-search", action="store_true",
    help="Accepted for compatibility with pymodrev. ARBoLoM always searches for\n"
         "optimal repairs, within the timeout.")
  arg_parser.add_argument("-s", "--solutions", type=int, choices=[1,2,3,4], default=1,
    help="""Accepted for compatibility with pymodrev. ARBoLoM computes one optimal repair
per inconsistent node, which is reported as sub-optimal only if its search timed out.""")
  arg_parser.add_argument("-f", "--format", type=str, choices=['c', 'j', 'h'], default='h',
    help="""Specify output format (default=h):
    c - compact format
    j - json format
    h - human-readable format""")
  arg_parser.add_argument("--fixed-nodes", nargs='+', action='extend',
    help="""List of nodes ids not to repair.
Example: --fixed-nodes A B C""")
  arg_parser.add_argument("--fixed-edges", nargs='+', action='extend',
    help="""List of edges ids not to repair (their regulator can neither be removed nor change sign).
Example: --fixed-edges A,B C;D E:F""")
  arg_parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode")

  arbolom_args = arg_parser.add_argument_group("ARBoLoM options")
  arbolom_args.add_argument("--criteria", default=",".join(DEFAULT_CRITERIA),
    help="Comma separated list of the criteria to use to minimize changes, in order of priority.\n"
         "For the list of available criteria use --help-criteria. Default is %(default)s.")
  arbolom_args.add_argument("--disable-criteria", default="",
    help="Comma separated list of the criteria whose changes are forbidden.")
  arbolom_args.add_argument("--help-criteria", action='store_true',
    help="Prints the available criteria and exits.")
  arbolom_args.add_argument("--timeout", type=float, default=3600,
    help="Seconds available to repair all the functions of the model (default %(default)s).")
  arbolom_args.add_argument("-p", "--parallel-mode", type=str, default=None,
    help="What to pass to clingo's --parallel-mode argument.\n"
         "The value 'auto' chooses the number of threads based on the available CPU cores.")
  arbolom_args.add_argument("--no-sanity-checks", action='store_true',
    help="Disables the validation of the change counts and of the consistency of the repaired model.")
  return arg_parser


def _split_criteria(arg_parser, value):
  criteria = [c for c in value.split(',') if c] if value else []
  for c in criteria:
    if c not in CRITERIA:
      arg_parser.error(f"Invalid criterion specified: {c}. Use --help-criteria to see available criteria.")
  return criteria


def main(argv=None):
  arg_parser = build_parser()
  args = arg_parser.parse_args(argv)

  if args.help_criteria:
    print_criteria()
    return 0
  if not args.model or not args.observations:
    arg_parser.error("the following arguments are required: -m/--model, -obs/--observations")

  config = Configuration(
    task=args.task, format=args.format, solutions=args.solutions, debug=args.debug,
    force_optimum=args.exhaustive_search, fixed_nodes=args.fixed_nodes or [],
    fixed_edges=args.fixed_edges or [], input_filename=args.model,
  )
  settings = RevisionSettings(
    min_change_criteria=_split_criteria(arg_parser, args.criteria) or list(DEFAULT_CRITERIA),
    disable_change_criteria=_split_criteria(arg_parser, args.disable_criteria),
    timeout=args.timeout,
    parallel_mode=resolve_parallel_mode(args.parallel_mode),
    quiet=True,
    sanity_checks=not args.no_sanity_checks,
  )

  if config.debug:
    logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s: %(message)s')

  # Observations
  observation_set = ObservationSet()
  obs_args = args.observations
  if len(obs_args) % 2 != 0:
    arg_parser.error("Expected an even number of arguments for -obs (pairs of obs_file and updater_name)")
  for i in range(0, len(obs_args), 2):
    obs_path, updater_name = obs_args[i], obs_args[i+1]
    try:
      if not is_valid_updater_type(updater_name):
        raise Exception(f"Updater '{updater_name}' not found in updaters directory")
      observation_set.add_observation(read_observation_file(obs_path, get_updater(updater_name)))
    except Exception as e:
      arg_parser.error(str(e))

  # Model, with the nodes and edges not to repair
  try:
    network = read_model_file(config.input_filename, strict=True)
    for node_id in config.fixed_nodes:
      node = network.get_node(node_id)
      if not node:
        raise ValueError(f'ERROR: Node {node_id} not found in the network.')
      node.is_fixed = True
    for edge_id in config.fixed_edges:
      nodes = re.split('[,;:]', edge_id)
      if len(nodes) != 2:
        raise ValueError(f'ERROR: Edge {edge_id} incorrectly defined.')
      network.get_edge(nodes[0], nodes[1]).is_fixed = True
  except (ValueError, EdgeNotFoundError, PyModRevError) as e:
    logger.error(str(e))
    return 1

  engine = RevisionEngine(settings)
  try:
    # Check consistency
    consistency = engine.check_consistency(network, observation_set)
    if config.task == 'c' or consistency.consistent:
      print(consistency.to_str(config.format))
      return 0

    # Model revision
    outcome = engine.repair(network, observation_set, consistency)
  except (UnsupportedObservationsError, NoAnswerSetError) as e:
    logger.error(str(e))
    return 1

  if not outcome.possible:
    logger.warning(f"It was not possible to repair the model (final state: {outcome.final_state}).")

  if config.task == 'r':
    print(outcome.to_str(config.format))
  else:
    repaired_models = outcome.repaired_models()
    if not repaired_models:
      logger.info("No repaired models to generate.")
    else:
      lp_format = ARBOLOM_LP if model_format(config.input_filename) == ARBOLOM_LP else MODREV_LP
      padding = len(str(len(repaired_models)))
      prefix, ext = os.path.splitext(config.input_filename)
      for i, repaired in enumerate(repaired_models):
        filename = f"{prefix}_{str(i+1).zfill(padding)}{ext}"
        write_model_file(repaired, filename, lp_format)
        print(f"Repaired model: {filename}")
  return 0


if __name__ == '__main__':
  sys.exit(main())
