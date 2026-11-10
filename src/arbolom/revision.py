"""Revision of a model: consistency checking followed by the repair of every
inconsistent function.

The configuration that used to live in module-level globals of revision.py
(update mode toggles, criteria, timeout, benchmark mode, ...) is held by
RevisionSettings, and the revision steps are methods of ModelReviser.
"""
import logging
import os
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field

from arbolom.constants import (BCHMARK_COMPOUND_REPAIR_TIME, FINAL_STATE,
                               ORIGINAL_NODE_NUMBER, ORIGINAL_REGULATOR_NUMBER)
from arbolom.consistency import consistency_check, is_consistent
from arbolom.lp_model import (format_function_dict, format_model_dict,
                              get_compound_regulator_number, get_compound_term_number,
                              get_model_compounds, model_to_dict, repair_model_dict)
from arbolom.modes import UpdateMode
from arbolom.printing import log_repaired_lp, print_func_repair_end, print_func_repair_start
from arbolom.repair.criteria import CRITERIA
from arbolom.repair.preprocessing import (generate_inconsistent_functions, generate_previous_observations,
                                          process_inconsistent_functions, process_previous_observations)
from arbolom.repair.sanity import repair_count_sanity_check
from arbolom.repair.search import generate_functions

DEFAULT_CRITERIA = ("term-number", "regulators", "signs", "term-format")

#Final states of a repaired function
REPAIRED = "repaired"
SUBOPTIMALLY_REPAIRED = "suboptimally repaired (timed out)"
TIMED_OUT = "inconsistent (timed out)"
NO_SOLUTION = "inconsistent (no solution)"


def resolve_parallel_mode(parallel_mode):
  """Value to pass to clingo's --parallel-mode ('auto' uses the available CPU cores)."""
  if parallel_mode == "auto":
    return f"{min(64, os.cpu_count() or 1)}"
  return parallel_mode or None


@dataclass
class RevisionSettings:
  """Configuration of a revision.

  mode - the UpdateMode of the observations
  min_change_criteria - change minimization criteria, in order of priority
  disable_change_criteria - criteria whose changes are forbidden
  timeout - seconds available to repair all the functions of a model
  parallel_mode - value for clingo's --parallel-mode argument (None to disable)
  quiet - disables all prints to stdout (benchmark mode)
  sanity_checks - validates the change counts of each repair and the
    consistency of the repaired model (raising on mismatches)
  """
  mode: UpdateMode = UpdateMode.STABLE
  min_change_criteria: list[str] = field(default_factory=lambda: list(DEFAULT_CRITERIA))
  disable_change_criteria: list[str] = field(default_factory=list)
  timeout: float = 3600
  parallel_mode: str | None = None
  quiet: bool = False
  sanity_checks: bool = True

  def __post_init__(self):
    for criterion in [*self.min_change_criteria, *self.disable_change_criteria]:
      if criterion not in CRITERIA:
        raise ValueError(f"Invalid criterion specified: {criterion}. Use --help-criteria to see available criteria.")


@dataclass
class FunctionRepair:
  """Outcome of the repair of one inconsistent function."""
  compound: str
  state: str
  atoms: list[str]
  costs: list | None
  repair_time: float

  @property
  def repaired(self) -> bool:
    return bool(self.atoms)


@dataclass
class RevisionResult:
  """Outcome of ModelReviser.revise()."""
  model_name: str | None
  final_state: str
  revision_time: float
  consistency_time: float
  repair_time: float
  stats: OrderedDict
  model_dict: OrderedDict
  inconsistencies: str | None
  function_repairs: dict[str, FunctionRepair]

  @property
  def resulting_model(self) -> str:
    return format_model_dict(self.model_dict)

  #Purpose: Returns the rows of the benchmark output (one per compound) with
  # the results obtained from the model's revision
  def benchmark_rows(self) -> list[str]:
    rows = []
    for func in self.stats:
      row = (str(self.model_name),
        self.final_state, str(self.revision_time),
        str(self.consistency_time), str(self.repair_time),
        func, *map(str, self.stats[func].values())
      )
      rows.append(",".join(row))
    return rows


#Inputs:
# -func - the name of the compound whose function is being repaired
# -func_state - the final state of the function after repairs
# -criteria_costs - the (criterion, cost) pairs of the repair
# -repairs - the atoms obtained from function repair
# -repair_time - the time spent on repairs
# -revision_stats - the map containing the changes done to each repaired function
#Purpose: updates the map with the results from function repair
def process_function_repair_stats(func, func_state, criteria_costs, repairs, repair_time, revision_stats):
  revision_stats[func][FINAL_STATE] = func_state
  revision_stats[func][BCHMARK_COMPOUND_REPAIR_TIME] = repair_time

  for crit, cost in criteria_costs:
      revision_stats[func][crit] = cost


class ModelReviser:
  """Checks the consistency of models and repairs their inconsistent functions."""

  def __init__(self, settings: RevisionSettings | None = None):
    self.settings = settings if settings is not None else RevisionSettings()

  #Input: model - the model being revised
  #Purpose: Initializes and returns the map containing the statistics of each
  # function's changes after being repaired
  def init_revision_stats(self, model):
    revision_stats_map = OrderedDict()
    all_compounds = sorted(get_model_compounds(model))

    for compound in all_compounds:
      regulator_number = get_compound_regulator_number(model, compound)
      node_number = get_compound_term_number(model, compound)

      revision_stats_map[compound] = OrderedDict()
      revision_stats_map[compound][FINAL_STATE] = "consistent"
      revision_stats_map[compound][ORIGINAL_REGULATOR_NUMBER] = regulator_number
      revision_stats_map[compound][ORIGINAL_NODE_NUMBER] = node_number
      revision_stats_map[compound][BCHMARK_COMPOUND_REPAIR_TIME] = 0.0
      for crit in self.settings.min_change_criteria:
        revision_stats_map[compound][crit] = 0

    return revision_stats_map

  #Inputs:
  # -model - the model whose consistency is being checked
  # -obsv - the observations (a path, or an LP program if observations_are_path is unset)
  #Purpose: returns the inconsistencies found in the model (None if consistent)
  def check_consistency(self, model, obsv, observations_are_path=True):
    logger = logging.getLogger("checkConsistency")

    atoms = consistency_check(model, obsv, self.settings.mode, obsv_path_mode=observations_are_path)

    inconsistencies = is_consistent(atoms, self.settings.mode, print_consistent=not self.settings.quiet)

    if inconsistencies is None:
      logger.debug("No inconsistencies found")
    else:
      logger.debug("Inconsistencies found")
    return inconsistencies

  def _record_repair(self, func, func_state, functions, costs, repair_time,
                     revision_stats, model_dict, function_repairs, func_logger):
    s = self.settings
    criteria_costs = list(zip(s.min_change_criteria, costs))
    process_function_repair_stats(func, func_state, criteria_costs, functions, repair_time, revision_stats)
    if function_repairs is not None:
      function_repairs[func] = FunctionRepair(func, func_state, list(functions), costs, repair_time)
    if functions:
      function_dict = repair_model_dict(model_dict, func, functions, func_state)
      if len(function_dict["terms"]) == 0: func_logger.warning("Unexpected empty term list (Empty functions are considered a mistake)")
      if len(function_dict["regulators"]) == 0: func_logger.warning("Unexpected empty regulator list (Empty functions are considered a mistake)")
      log_repaired_lp(func, format_function_dict(func, function_dict), criteria_costs, to_stdout=not s.quiet, logger=func_logger)
    return criteria_costs

  def recover_timeouts(self, model, inconsistencies, revision_stats, to_recover, timeout_end, model_dict,
                       function_repairs=None):
    s = self.settings
    time_left = timeout_end - time.monotonic()
    if time_left <= 0:
      logging.info(f"No time left, suboptimally repaired functions won't be recovered")
      return [x[0] for x in to_recover]
    to_recover = deque(to_recover)

    logging.info(f"{time_left}s left and there's suboptimally repaired functions, attempting to recover in remaining time")
    while len(to_recover) > 0 and time_left > 0:
      model_timeout = time_left / len(to_recover)
      func, upo, old_costs, orig_repair_time = to_recover.popleft()
      func_logger = logging.getLogger(func)
      func_logger.info(f"Attempting to recover {func}")
      compound_repair_start = time.monotonic()
      result, functions, costs = generate_functions(func, model, inconsistencies, upo,
        s.min_change_criteria, s.disable_change_criteria, (model_timeout, 0),
        s.mode, parallel_mode=s.parallel_mode, logger = func_logger, cost_bounds=old_costs)
      repair_time = time.monotonic() - compound_repair_start + orig_repair_time
      func_state = None
      if result == "repaired":
        func_logger.info(f"Successful recovery - reached optimal repairs for {func}")
        func_state = REPAIRED
      else:
        if functions and costs and tuple(costs) < tuple(old_costs):
          func_logger.warning(f"Unsuccessful recovery - reached better non optimal repairs for {func}")
          func_state = SUBOPTIMALLY_REPAIRED
          to_recover.append((func, upo, costs, repair_time)) # try again later
        else:
          func_logger.warning(f"Unsuccessful recovery - no improvement for {func}")
          to_recover.append((func, upo, old_costs, repair_time)) # try again later
      if func_state: # means there was an improvement
        self._record_repair(func, func_state, functions, costs, repair_time,
                            revision_stats, model_dict, function_repairs, func_logger)
      else:
        revision_stats[func][BCHMARK_COMPOUND_REPAIR_TIME] = repair_time
        if function_repairs is not None and func in function_repairs:
          function_repairs[func].repair_time = repair_time
      time_left = timeout_end - time.monotonic()
    if len(to_recover) == 0:
      logging.info("Recovery successful for all functions")
    else: logging.warning("Run out of time, no further recovery attempts will be made")
    return [x[0] for x in to_recover]

  #Inputs:
  # -model - the model being repaired
  # -inconsistencies - the inconsistencies obtained from consistency checking
  # -revision_stats - the map containing the changes done to each repaired function
  # -model_dict - the model dict that is updated with the repaired functions
  # -function_repairs - optional dict, filled with the FunctionRepair of each inconsistent function
  # -skip_functions - inconsistent functions that must not be repaired (they are reported as without solution)
  #Purpose: attempts to repair the model and returns its final state
  def repair(self, model, inconsistencies, revision_stats, model_dict, function_repairs=None,
             skip_functions=()):
    s = self.settings
    incst_funcs = generate_inconsistent_functions(model, inconsistencies)
    i_f_array = process_inconsistent_functions(incst_funcs)
    final_state = "repaired"

    timed_out_functions = []
    to_recover = []
    unrepairable_functions = []

    timeout_end = time.monotonic() + s.timeout

    if i_f_array:
      for i, func in enumerate(i_f_array):
        func_logger = logging.getLogger(func)
        if func in skip_functions:
          func_logger.warning(f"Function {func} is inconsistent but cannot be repaired (fixed)")
          unrepairable_functions.append(func)
          self._record_repair(func, NO_SOLUTION, [], [float('nan')] * len(s.min_change_criteria), 0.0,
                              revision_stats, model_dict, function_repairs, func_logger)
          continue
        hard_timeout = timeout_end - time.monotonic()
        soft_timeout = hard_timeout / (len(i_f_array) - i)
        hard_timeout = max(0, hard_timeout - soft_timeout)
        func_state = REPAIRED
        if not s.quiet: print_func_repair_start(func)
        func_logger.info(f"Beginning repairs for function {func}")
        prev_obs = generate_previous_observations(func, inconsistencies, s.mode, logger = func_logger)
        upo = process_previous_observations(prev_obs, logger = func_logger)

        compound_repair_start = time.monotonic()
        result, functions, costs = generate_functions(
          func, model, inconsistencies,
          upo, s.min_change_criteria, s.disable_change_criteria, (soft_timeout, hard_timeout),
          s.mode, parallel_mode=s.parallel_mode, logger = func_logger)
        compound_repair_end = time.monotonic()
        repair_time = compound_repair_end - compound_repair_start

        if result == "timeout":
          if functions:
            func_state = SUBOPTIMALLY_REPAIRED
            to_recover.append((func, upo, costs, repair_time))
          else:
            func_state = TIMED_OUT
            timed_out_functions.append(func)
        elif result == "no_solution":
          unrepairable_functions.append(func)
          func_state = NO_SOLUTION
        elif result == "repaired":
          assert functions
        else: raise Exception(f"Unexpected result {result}")
        if functions:
          assert costs is not None
        func_logger.info(f"Completed repairing of {func}, final state: {func_state}")
        if not s.quiet: print(f"Completed repairing of {func}, final state: {func_state}")

        if costs is None:
          costs = [float('nan')] * len(s.min_change_criteria)
        criteria_costs = self._record_repair(func, func_state, functions, costs, repair_time,
                                             revision_stats, model_dict, function_repairs, func_logger)
        if not s.quiet: print_func_repair_end(func)
        if s.sanity_checks and functions:
          func_logger.info("Counting repairs to confirm ASP optimization counts. You can disable this with the sanity_checks setting")
          repair_count_sanity_check(func, model, functions, criteria_costs, func_logger)
    if to_recover:
      if not s.quiet: print("Now going back to recover timed out repairs")
      suboptimal_repairs = self.recover_timeouts(model, inconsistencies, revision_stats, to_recover,
                                                 timeout_end, model_dict, function_repairs)
    else:
      suboptimal_repairs = []
    if timed_out_functions and unrepairable_functions:
      final_state = "still inconsistent (timed out functions and functions without existing solutions)"
    elif timed_out_functions:
      final_state = "still inconsistent (timed out functions)"
    elif unrepairable_functions:
      final_state = "still inconsistent (functions without existing solutions)"
    elif suboptimal_repairs:
      final_state = "suboptimally repaired (functions timed out before finding optimal repair)"

    return final_state

  #Inputs:
  # -model - the model to revise, in LP format
  # -obsv - the observations (a path, or an LP program if observations_are_path is unset)
  # -model_name - name used in prints, logs and benchmark rows
  # -skip_functions - inconsistent functions that must not be repaired
  #Purpose: checks the consistency of the model and, if inconsistent, repairs it
  def revise(self, model, obsv, model_name=None, observations_are_path=True, skip_functions=()) -> RevisionResult:
    s = self.settings
    global_logger = logging.getLogger("global")

    final_state = "consistent"
    total_repair_time = 0
    function_repairs = {}

    revision_start_time = time.monotonic()
    model_revision_stats = self.init_revision_stats(model)

    if not s.quiet: print("Currently revising model ", model_name)
    global_logger.info(f"Currently revising model {model_name}")

    model_dict = model_to_dict(model)

    # First, check the consistency of the .lp model using the provided observations.
    consistency_start_time = time.monotonic()
    inconsistencies = self.check_consistency(model, obsv, observations_are_path)
    consistency_end_time = time.monotonic()

    total_consistency_time = consistency_end_time - consistency_start_time
    global_logger.info(f"Consistency checking finished in {total_consistency_time}s - Consistent: {not inconsistencies}")

    if inconsistencies:
      if not s.quiet: print("Inconsistent model! \nRepairing...")
      global_logger.info(f"Currently repairing model {model_name}")

      # Second, if it is not consistent, proceed with the repairs.
      repair_start_time = time.monotonic()
      final_state = self.repair(model, inconsistencies, model_revision_stats, model_dict, function_repairs,
                                skip_functions=skip_functions)
      repair_end_time = time.monotonic()

      total_repair_time = repair_end_time - repair_start_time
      global_logger.info(f"Repair finished in {total_repair_time}s - Final state: {final_state}")
      if not s.quiet:
        print(f"Repair finished - Final state: {final_state}")
        if "repaired" in final_state:
          print(f"Applying the above repairs to model {model_name} will render it consistent!\n")

    revision_end_time = time.monotonic()
    total_revision_time = revision_end_time - revision_start_time
    resulting_model = format_model_dict(model_dict)
    global_logger.info(f"Revision finished in {total_revision_time}s - Final state: {final_state} - Resulting model:\n{resulting_model}")
    if s.sanity_checks and 'repaired' in final_state:
      remaining = self.check_consistency(resulting_model, obsv, observations_are_path)
      if remaining:
        raise Exception(f"State {final_state} is wrong: {len(remaining)} inconsistencies found in new repaired model.")

    return RevisionResult(
      model_name=model_name,
      final_state=final_state,
      revision_time=total_revision_time,
      consistency_time=total_consistency_time,
      repair_time=total_repair_time,
      stats=model_revision_stats,
      model_dict=model_dict,
      inconsistencies=inconsistencies,
      function_repairs=function_repairs,
    )
