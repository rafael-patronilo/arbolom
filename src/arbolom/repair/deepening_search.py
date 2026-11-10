"""Repair of a single inconsistent function by iterative deepening on the
number of nodes (terms): functions with the original number of nodes are tried
first, then with one node more or less, and so on. Used when "term-number" is
the most important change minimization criterion."""
import time

import clingo

from arbolom.modes import UpdateMode
from arbolom.printing import print_statistics
from arbolom.repair.criteria import build_asp_change_criteria, build_asp_disable_constraints
from arbolom.repair.preprocessing import determine_start_nodes_and_limit
from arbolom.resources import DEEPENING_SEARCH_REPAIR_ENCODINGS


#Inputs:
# repair_timeout - seconds available for this function, either a number or a
#   (soft, hard) tuple: after the soft timeout the best repair found so far is
#   returned; if none was found yet, the search continues for at most `hard`
#   more seconds until the first repair is found
# func - the name of the inconsistent function
# model - the model to revise
# incst - the inconsistencies obtained from consistency checking
# upo - unique positive observations that are obtained from process_previous_observations
# mode - the UpdateMode of the observations
# min_change_criteria - change minimization criteria, excluding term-number (handled by the deepening itself)
# disable_change_criteria - criteria whose changes are forbidden
# path_mode - flag that enables loading the model and inconsistencies from a file, instead of a string
# parallel_mode - value for clingo's --parallel-mode argument (None to disable)
# cost_bounds - costs of a previously found repair ([term-number] + costs of min_change_criteria);
#   only repairs at least as good are searched for
#Purpose: Generates a function that is compatible with previously given observations, based on the obtained inconsistencies
def generate_functions(
    repair_timeout, func, model, incst, upo,
    mode: UpdateMode,
    min_change_criteria, disable_change_criteria, path_mode = False, logger=None,
    parallel_mode=None, cost_bounds=None):
  if logger:
    logger.warning("Some changes are still being ported to this version. ")
    logger.debug("Calculating repairs...")

  if isinstance(repair_timeout, tuple):
    soft_timeout, hard_timeout = repair_timeout
  else:
    soft_timeout, hard_timeout = repair_timeout, 0
  soft_deadline = time.monotonic() + soft_timeout
  hard_deadline = soft_deadline + hard_timeout

  # The first cost bound is the term-number cost, i.e. the node variation; the
  # remaining ones bound the clingo optimization at that same variation
  max_variation = None
  clingo_bounds = None
  if cost_bounds:
    max_variation = cost_bounds[0]
    clingo_bounds = list(cost_bounds[1:])

  upo_program = ""
  if upo : upo_program = upo[0]
  starting_node_number, max_node_limit = determine_start_nodes_and_limit(func,model,upo,path_mode)

  def solve(node_number, variation, have_candidate):
    now = time.monotonic()
    soft_left = max(0.0, soft_deadline - now)
    # The hard timeout is waited for after the soft one. Once a candidate exists there
    # is no point in waiting past the soft timeout
    hard_left = 0.0 if have_candidate else max(0.0, hard_deadline - now - soft_left)
    bounds = clingo_bounds if variation == max_variation else None
    return generate_functions_clingo(node_number, (soft_left, hard_left),
                                     func, model, incst, upo_program,
                                     mode,
                                     min_change_criteria, disable_change_criteria, path_mode, logger,
                                     parallel_mode=parallel_mode, cost_bounds=bounds)

  def make_return_tuple(result, function, variation):
    if function is None: return result, [], None
    # The term-number cost counts added or removed terms, so the sign of the variation is dropped
    return result, function[0], [abs(variation)] + list(function[1])

  current_variation = 0
  while True:
    if max_variation is not None and current_variation > max_variation:
      if logger: logger.info("... Done. No solution within the given cost bounds")
      return "no_solution", [], None

    if current_variation == 0:
      candidates = [(starting_node_number, 0)]
    else:
      candidates = []
      if starting_node_number + current_variation <= max_node_limit:
        candidates.append((starting_node_number + current_variation, current_variation))
      if starting_node_number - current_variation > 0:
        candidates.append((starting_node_number - current_variation, -current_variation))
      if not candidates:
        if logger: logger.info("... Done. No solution")
        return "no_solution", [], None

    best, best_variation = None, 0
    timed_out = False
    for node_number, variation in candidates:
      if logger: logger.info(f"Trying to find a solution with {node_number} nodes "
                             f"(original is {starting_node_number}, max is {max_node_limit})...")
      completed, function = solve(node_number, current_variation, best is not None)
      # On equal costs the later candidate (fewer nodes) is preferred
      if function is not None and (best is None or tuple(function[1]) <= tuple(best[1])):
        best, best_variation = function, variation
      if not completed:
        timed_out = True
        break

    if timed_out:
      if logger: logger.warning("Timed out; if there is a function it will be suboptimal")
      return make_return_tuple('timeout', best, best_variation)
    elif best is not None:
      if logger: logger.info("... Done.")
      return make_return_tuple("repaired", best, best_variation)
    else:
      if logger: logger.info(f"No solutions with a node variation of {current_variation}.")
      current_variation += 1

#Inputs:
# node_number - number of nodes to consider in the search
# timeouts - (soft, hard) tuple in seconds: after `soft` seconds the search stops
#   if a model was found; otherwise it waits at most `hard` more seconds for the first model
# func - the name of the inconsistent function
# model - the model to revise
# incst - the inconsistencies obtained from consistency checking
# upo_program - the processed unique positive observations
# mode - the UpdateMode of the observations
# path_mode - flag that enables loading the model and inconsistencies from a file, instead of a string
# parallel_mode - value for clingo's --parallel-mode argument (None to disable)
# cost_bounds - upper bounds (inclusive) for the optimization costs
#Purpose: Calls clingo to solve the repair encoding. Returns (completed, result), where
# completed is True if the search finished (so result is optimal, or None if there is
# no solution) and result is either None or an (atoms, costs) tuple.
def generate_functions_clingo(
    node_number, timeouts, func, model, incst,
    upo_program,
    mode: UpdateMode,
    min_change_criteria, disable_change_criteria,
    path_mode = False, logger=None, parallel_mode=None, cost_bounds=None):
  soft_timeout, hard_timeout = (max(0.0, t) for t in timeouts) # negative means "no timeout" to clingo
  clingo_args = ["0", f"-c compound={func}", f"-c node_number={node_number}"]
  if cost_bounds: clingo_args.append(f"--opt-mode=opt,{','.join(map(str, cost_bounds))}")
  else: clingo_args.append("--opt-mode=opt")
  if parallel_mode:
    clingo_args.append("--parallel-mode")
    clingo_args.append(parallel_mode)
  if logger: logger.debug(f"Starting clingo with args {clingo_args}")

  ctl = clingo.Control(arguments=clingo_args, logger= lambda a,b: None)

  ctl.add("base", [], program=upo_program)

  if path_mode:
    ctl.load(model)
    ctl.load(incst)
  else:
    ctl.add("base", [], program=model)
    ctl.add("base", [], program=incst)

  ctl.load(DEEPENING_SEARCH_REPAIR_ENCODINGS[mode])

  asp_min_criteria = build_asp_change_criteria(min_change_criteria)
  ctl.add("base", [], program=asp_min_criteria)
  asp_disable_changes = build_asp_disable_constraints(disable_change_criteria)
  ctl.add("base", [], program=asp_disable_changes)

  ctl.ground([("base", [])])
  function = []
  costs = None
  stop_at_next_model = False
  stopped_early = False

  def on_model(m):
    nonlocal function, costs, stopped_early
    function = str(m).split(" ")
    costs = m.cost
    if stop_at_next_model:
      stopped_early = True
      return False

  with ctl.solve(on_model=on_model, async_=True) as handle:
    finished = handle.wait(soft_timeout)
    if not finished and not function:
      if logger: logger.debug(f"No solution yet, waiting at most {hard_timeout} seconds for any solution")
      stop_at_next_model = True
      finished = handle.wait(hard_timeout)
    if not finished:
      handle.cancel()

  if logger: print_statistics(ctl.statistics, logger.debug)

  completed = finished and not stopped_early
  if not function: return completed, None
  else: return completed, (function, costs)
