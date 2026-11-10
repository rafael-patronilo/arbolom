"""Repair of a single inconsistent function with a single clingo call,
bounded by the maximum number of nodes (terms)."""
import math

import clingo

from arbolom.common import clingo_logger
from arbolom.modes import UpdateMode
from arbolom.repair import deepening_search
from arbolom.repair.criteria import build_asp_change_criteria, build_asp_disable_constraints
from arbolom.repair.preprocessing import determine_start_nodes_and_limit
from arbolom.resources import REPAIR_ENCODINGS

OPTIONAL_REPAIR_PREDICATES = [('fixed', 2), ('fixed', 3), ('unique_positive_observation', 2)]


#Inputs:
# func - the name of the inconsistent function
# model - the model to revise
# incst - the inconsistencies obtained from consistency checking
# upo - unique positive observations that are obtained from process_previous_observations
# min_change_criteria - list of the change minimization criteria (term-number,regulators,signs,term-format) in order of priority.
# disable_change_criteria - criteria whose changes are forbidden
# repair_timeout - seconds available for this function, either a number or a (soft, hard) tuple
# mode - the UpdateMode of the observations
# parallel_mode - value for clingo's --parallel-mode argument (None to disable)
# path_mode - flag that enables loading the model and inconsistencies from a file, instead of a string
# cost_bounds - costs of a previously found repair; only repairs at least as good are searched for
#Purpose: Generates a function that is compatible with previously given observations, based on the obtained inconsistencies.
# Returns (result, atoms, costs) where result is one of "repaired", "timeout" or "no_solution".
def generate_functions(
    func, model, incst, upo, min_change_criteria, disable_change_criteria,
    repair_timeout, mode: UpdateMode,
    parallel_mode=None, path_mode = False, logger=None, cost_bounds = None):
  if logger: logger.debug("Calculating repairs...")

  if min_change_criteria[0] == 'term-number':
    if logger: logger.info("Switching to former version to take advantage of deepening search")
    return deepening_search.generate_functions(
      repair_timeout, func, model, incst, upo, mode,
      min_change_criteria[1:], disable_change_criteria, path_mode, logger,
      parallel_mode=parallel_mode, cost_bounds=cost_bounds)
  function = []
  upo_program = ""
  if upo : upo_program = upo[0]

  _, max_node_limit = determine_start_nodes_and_limit(func, model, upo, path_mode)
  if logger:
    logger.debug(f"Trying to find a solution with at most ({max_node_limit}) nodes...")
    if math.isinf(max_node_limit): logger.error("Node limit is infinite")

  optimal, function, costs = generate_functions_clingo(
    max_node_limit, repair_timeout, func,
    model, incst, upo_program, min_change_criteria, disable_change_criteria,
    mode, parallel_mode, path_mode, logger,
    cost_bounds=cost_bounds
  )
  if not optimal:
    if logger: logger.warning(f"Search timed out. If a solution was found, it will be suboptimal.")
    result = "timeout"
  elif function:
    if logger: logger.info("... Done.")
    result = "repaired"
  else:
    if logger: logger.error(f"No solutions.")
    result = "no_solution"
  if function:
    assert costs is not None
  return result, function, costs

#Inputs:
# node_number - maximum number of nodes to consider in the search
# repair_timeout - seconds available, either a number or a (soft, hard) tuple
# (remaining inputs as in generate_functions; upo_program is the processed unique positive observations)
#Purpose: Calls clingo to solve the repair encoding
def generate_functions_clingo(node_number,
                             repair_timeout, func, model,
                             incst, upo_program, min_change_criteria, disable_change_criteria,
                             mode: UpdateMode,
                             parallel_mode=None,
                             path_mode = False, logger=None,
                             cost_bounds=None):
  no_timeout = True
  clingo_args = ["0", f"-c compound={func}", f"-c max_node_number={node_number}"]
  if cost_bounds: clingo_args.append(f"--opt-mode=opt,{','.join(map(str,cost_bounds))}")
  else: clingo_args.append("--opt-mode=opt")
  if parallel_mode:
    clingo_args.append(f"--parallel-mode")
    clingo_args.append(parallel_mode)

  if isinstance(repair_timeout, tuple):
    soft_timeout, hard_timeout = repair_timeout
  else:
    soft_timeout = repair_timeout
    hard_timeout = 0
  # clingo treats a negative timeout as "no timeout"
  soft_timeout, hard_timeout = max(0.0, soft_timeout), max(0.0, hard_timeout)
  if logger: logger.debug(f"Starting clingo with args {clingo_args}")
  ctl = clingo.Control(arguments=clingo_args, logger=clingo_logger(logger, optional_predicates=OPTIONAL_REPAIR_PREDICATES))

  ctl.add("base", [], program=upo_program)

  if path_mode:
    ctl.load(model)
    ctl.load(incst)
  else:
    ctl.add("base", [], program=model)
    ctl.add("base", [], program=incst)

  ctl.load(REPAIR_ENCODINGS[mode])

  asp_min_criteria = build_asp_change_criteria(min_change_criteria)
  if logger: logger.debug(f"Change minimization criteria:\n{asp_min_criteria}")
  ctl.add("base", [], program=asp_min_criteria)
  asp_disable_changes = build_asp_disable_constraints(disable_change_criteria)
  ctl.add("base", [], program=asp_disable_changes)

  ctl.ground([("base", [])])
  function = []
  cancelling = False
  costs = None

  def on_model(m):
    nonlocal function, costs, cancelling
    function = str(m).split(" ")
    costs = m.cost
    if logger: logger.debug(f"New model. Costs: {costs}")
    if cancelling:
      if logger: logger.debug(f"Soft timeout passed, interrupting")
      return False

  with ctl.solve(on_model=on_model, async_=True) as handle:
    if logger: logger.debug(f"Waiting at most {soft_timeout} seconds for optimal solution")
    no_timeout = handle.wait(soft_timeout)
    if not no_timeout:
      if logger: logger.debug("Soft timeout reached; Checking if there is a suboptimal solution...")
      if not function:
        if logger: logger.debug(f"No solution, waiting at most {hard_timeout} seconds for any solution")
        cancelling = True
        if handle.wait(hard_timeout) and not function:
          if logger: logger.debug("Search space exhausted: there is no solution")
          no_timeout = True
      elif logger: logger.debug("Suboptimal solution already found, interrupting")
      handle.cancel()

  if logger: logger.debug(ctl.statistics)
  return no_timeout, function, costs
