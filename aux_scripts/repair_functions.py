import math
import time, clingo
from aux_scripts.repair_criteria import build_asp_change_criteria
from aux_scripts.repair_prints import printStatistics
from aux_scripts import deepening_search
from aux_scripts.common import clingo_logger
from collections import defaultdict
from dataclasses import dataclass

#Path of the encodings to obtain inconsistent functions
inconsistent_functions_path = "encodings/repairs/auxiliary/inconsistent_functions.lp"

#Paths of the encodings to obtain the observations that happen before positive observations
previous_observations_sync_path = "encodings/repairs/auxiliary/previous_observations_sync.lp"
previous_observations_async_path = "encodings/repairs/auxiliary/previous_observations_async.lp"

OPTIONAL_REPAIR_PREDICATES = [('fixed', 2), ('fixed', 3), ('unique_positive_observation', 2)]
#Paths of the encodings that generating functions
repair_encoding_stable_path = "encodings/repairs/repairs_stable.lp"
repair_encoding_sync_path = "encodings/repairs/repairs_sync.lp"
repair_encoding_async_path = "encodings/repairs/repairs_async.lp"

#Timeout for function repair
# repair_timeout = 3600


#-----Functions that solve LPs with clingo-----
#Input:
# model - the model that is being revised
# inconsistencies - the inconsistencies obtained from consistency checking
# debug_mode - flag that enables extra clingo output (must remove logger in clingo.Control to see)
#Purpose: Obtains the inconsistent functions from the consistency checking phase
def generateInconsistentFunctions(model, inconsistencies, debug_mode=False, path_mode=False, enable_prints=False):
  clingo_args = ["0"]
  if debug_mode:
    clingo_args.append("--output-debug=text")

  ctl = clingo.Control(arguments=clingo_args, logger= lambda a,b: None)

  if path_mode:
    ctl.load(model)
    ctl.load(inconsistencies)
  else:
    ctl.add("base", [], program=model)
    ctl.add("base", [], program=inconsistencies)
    
  ctl.load(inconsistent_functions_path)

  if enable_prints: print("Starting iftv generation \u23F1")
  ctl.ground([("base", [])])
  iftv = []

  with ctl.solve(yield_=True) as handle:
    for model in handle:
      iftv.append(str(model).split(" "))

  if enable_prints: print("Finished iftv generation \U0001F3C1")
  if enable_prints: printStatistics(ctl.statistics)
  return iftv

#Inputs:
# func - the name of the inconsistent function
# model - the model to revise
# incst - the inconsistencies obtained from consistency checking
# upo - unique positive observations that are obtained from processPreviousObservations
# min_change_criteria - list of the change minimization criteria (term-number,regulators,signs,term-format) in order of priority.
# toggle_stable_state - flag that enables stable state interaction
# toggle_sync - flag that enables synchronous interaction
# toggle_async - flag that enables asynchronous interaction
# path_mode - flag that enables loading the model and inconsistencies from a file, instead of a string
# enable_prints - enables additional prints
#Purpose: Generates a function that is compatible with previously given observations, based on the obtained inconsistencies
def generateFunctions(func, model, incst, upo, min_change_criteria, repair_timeout,
                      toggle_stable_state, toggle_sync, toggle_async, 
                      parallel_mode=None, path_mode = False, logger=None, cost_bounds = None):
  if logger: logger.debug("Calculating repairs...")

  if min_change_criteria[0] == 'term-number':
    if logger: logger.info("Switching to former version to take advantage of deepening search")
    return deepening_search.generateFunctions(
      repair_timeout, func, model, incst, upo, toggle_stable_state, toggle_sync, toggle_async, 
      min_change_criteria[1:], path_mode, logger)
  function = []
  upo_program = ""
  if upo : upo_program = upo[0]

  _, max_node_limit = determineStartNodesAndLimit(func, model, upo, path_mode)
  if logger: 
    logger.debug(f"Trying to find a solution with at most ({max_node_limit}) nodes...")
    if math.isinf(max_node_limit): logger.error("Node limit is infinite")
  
  optimal, function, costs = generateFunctionsClingo(max_node_limit, repair_timeout, func,
                                    model, incst, upo_program, min_change_criteria,
                                    toggle_stable_state, toggle_sync, toggle_async, 
                                    parallel_mode, path_mode, logger,
                                    cost_bounds=cost_bounds)
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
# node_number - number of nodes to consider in the search
# timeout_start - time when the timeout counter was started
# func - the name of the inconsistent function
# model - the model to revise
# incst - the inconsistencies obtained from consistency checking
# upo_program - the processed unique positive observations
# min_change_criteria - list of the change minimization criteria (term-number,regulators,signs,term-format) in order of priority.
# toggle_stable_state - flag that enables stable state interaction
# toggle_sync - flag that enables synchronous interaction
# toggle_async - flag that enables asynchronous interaction
# path_mode - flag that enables loading the model and inconsistencies from a file, instead of a string
# enable_prints - enables additional prints
#Purpose: Calls clingo to solve the repair encoding
def generateFunctionsClingo(node_number,
                             repair_timeout, func, model,
                             incst, upo_program, min_change_criteria,
                             toggle_stable_state, toggle_sync, toggle_async, 
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
  if logger: logger.debug(f"Starting clingo with args {clingo_args}")
  ctl = clingo.Control(arguments=clingo_args, logger=clingo_logger(logger, optional_predicates=OPTIONAL_REPAIR_PREDICATES))

  ctl.add("base", [], program=upo_program)

  if path_mode:
    ctl.load(model)
    ctl.load(incst) 
  else: 
    ctl.add("base", [], program=model)
    ctl.add("base", [], program=incst)

  if toggle_stable_state:
    ctl.load(repair_encoding_stable_path)
  elif toggle_sync:
    ctl.load(repair_encoding_sync_path)
  elif toggle_async:
    ctl.load(repair_encoding_async_path)
  
  asp_min_criteria = build_asp_change_criteria(min_change_criteria, toggle_stable_state, toggle_sync, toggle_async)
  if logger: logger.debug(f"Change minimization criteria:\n{asp_min_criteria}")
  ctl.add("base", [], program=asp_min_criteria)

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
        handle.wait(hard_timeout)
      elif logger: logger.debug("Suboptimal solution already found, interrupting")
      handle.cancel()
  
  if logger: logger.debug(ctl.statistics)
  return no_timeout, function, costs

#Inputs:
# func - the inconsistent function
# model - the model being revised
# upo - unique positive observations that are obtained from processPreviousObservations
# path mode - flag that enables loading the model and inconsistencies from a file, instead of a string
#Purpose: Determines how many nodes were in the inconsistent function, as well
#as what the maximum number of nodes to consider should be
def determineStartNodesAndLimit(func,model,upo,path_mode):
  node_limit = None

  if not upo:
    node_limit = 0
  else: node_limit = upo[1]

  if path_mode:
    f = open(model, "r")
    lines = f.readlines()
    for line in lines:
      if f"function({func}" in line:
        original_nodes = int(line.split(',')[1].split(')')[0])
        break
    f.close()
  else:
    original_nodes = int(model.split(f"function({func},")[1].split(')')[0])
  
  return original_nodes, node_limit



#-----Functions that process output from clingo-----
#Input: The inconsistent functions obtained from clingo
#Purpose: Creates an array containing the name of all the inconsistent functions 
def getInconsistentFunctionsArray(inconsistent_functions):
  result = []

  for incst_func in inconsistent_functions:      
    var_name = incst_func[0].split(')')[0].split('(')[1]
    result.append(var_name)

  return result

#Input: The generated inconsistent functions output from clingo
#Purpose: Processes clingo's inconsistent functions output by creating an array with them
def processInconsistentFunctions(inconsistent_functions, enable_prints=False):
  if not inconsistent_functions:
    print("processInconsistentFunctions: No answers sets could be found	\u2755 there must be something wrong with the encoding...")

  elif inconsistent_functions[0]:

    i_f_array = getInconsistentFunctionsArray(inconsistent_functions)

    if enable_prints:
      total_iftvs = len(i_f_array)
      if(total_iftvs < 100):
        print("<Resulting inconsistent functions>")
        print(str(i_f_array),end="\n\n")
      else:
        print("Too many iftvs to print...!")
      print(f"Total iftvs: {total_iftvs}\n")

    return i_f_array

  else: 
    print("processInconsistentFunctions: No inconsistent functions could be found \u274C")



#-----Python implementation of unique positive observation determination-----
#Inputs: 
# func- the compound that has the inconsistent function
# inconsistencies - the inconsistencies obtained from consistency checking
# toggle_stable_state - flag that enables stable state interaction
# toggle_sync - flag that enables synchronous interaction
# toggle_async - flag that enables asynchronous interaction
# path_mode - flag that enables loading the inconsistencies from a file, instead of a string
#Purpose: Returns observations that happen in the timestep before
# positive observations (the observations are contained in inconsistencies)
def generatePreviousObservations(func, inconsistencies, toggle_sync, toggle_async, path_mode=False, logger=None):
  clingo_args = ["0", f"-c compound={func}"]
  
  ctl = clingo.Control(arguments=clingo_args, logger=clingo_logger(logger))

  if path_mode:
    ctl.load(inconsistencies)
  else:
    ctl.add("base", [], program=inconsistencies)

  if toggle_sync:
    ctl.load(previous_observations_sync_path)
  elif toggle_async:
    ctl.load(previous_observations_async_path)
  else: 
    return []
  
  ctl.ground([("base", [])])
  functions = []

  if logger: logger.debug("Calculating previous positive observations...")

  with ctl.solve(yield_=True) as handle:
    for model in handle:
      functions = str(model).split(" ")

  if logger: logger.debug("... Done.")

  if logger: printStatistics(ctl.statistics, print_func=logger.debug)

  if not functions[0]: #If there are no previous observations
    if logger: logger.debug("No previous positive observations found.")
    return []

  return functions


#Inputs: 
# -prev_obs, a string containing all previous observations
#Purpose: Returns a tuple with all unique positive observations,
# and the total number of unique positive observations
def processPreviousObservations(prev_obs, logger=None):
  if not prev_obs:
    return ("",0)
  start = time.monotonic()
  observations = defaultdict(list)
  compounds = set()
  
  for previous_obsv in prev_obs:
    arguments = previous_obsv.split(')')[0].split('(')[1].split(',')
    experiment = arguments[0]
    timestep = str(int(arguments[1]) + 1)
    compound = arguments[2]
    state = arguments[3]
    observations[(experiment, timestep)].append((compound, state))
    compounds.add(compound)
  
  @dataclass(frozen=False) # We will need to write to the field state_key
  class Unique:
    obs_id : tuple[str, str]
    state_key : frozenset[tuple[str,str]]
  
  uniques = {}
  for obs_id, state in observations.items():
    value = Unique(obs_id, frozenset(state))
    uniques[value.state_key] = value
  if logger: logger.debug(f"Reduced from {len(observations)} to {len(uniques)} just excluding exact matches")
  
  uniques = uniques.values()
  # input upos for repair should include all unique obs, to keep the information of which compounds should be irrelevant
  upos = "\n".join([f"unique_positive_observation({','.join(unique.obs_id)})." for unique in uniques])
  
  # But for max node limit we can exclude irrelevant compounds
  # We do this by "fusing" states where the only difference is a compound
  if logger: logger.debug(f"Compounds present: {' '.join(compounds)}")
  old_len = len(uniques) + 1
  while old_len > len(uniques):
    old_len = len(uniques)
    if logger: logger.debug(f"Cycling all compounds to attempt simplification")
    for c in compounds:
      new_uniques = {}
      for unique in uniques:
        new_state_key = frozenset(x for x in unique.state_key if x[0] != c)
        present = new_uniques.get(new_state_key)
        if present:
          if present.state_key != unique.state_key:    # means this compound is not relevant for this conjoint, therefore
            present.state_key = new_state_key          # exclude irrelevant compound from state key
        else: new_uniques[new_state_key] = unique
      if len(new_uniques) < len(uniques):
        if logger: logger.debug(f"New reduction using compound {c}: {len(uniques)} to {len(new_uniques)}")
        uniques = new_uniques.values()
  
  end = time.monotonic()
  if logger: logger.debug(f"Finished upo counting in {end-start}s; Final count {len(uniques)}")
  
  return (upos, len(uniques))

def repair_count_sanity_check(func, orig_model, repaired_model, repair_counts, logger):
  if isinstance(orig_model, str):
    orig_model = [line for line in orig_model.split('\n') if not line.startswith("%") and not line.isspace()]
  else: assert isinstance(orig_model, list)
  if isinstance(repaired_model, str): repaired_model = repaired_model.split()
  else: assert isinstance(repaired_model, list)
  orig_terms = []
  orig_signs = {}
  for atom in orig_model:
    if atom.startswith("function"):
      f, n = [x.strip() for x in atom.split(')')[0].split('(')[1].split(',')]
      n = int(n)
      if f == func and n > len(orig_terms): orig_terms.extend([set() for _ in range(n - len(orig_terms))])
    elif atom.startswith("regulates"):
      r, f, s = [x.strip() for x in atom.split(')')[0].split('(')[1].split(',')]
      if f == func:
        orig_signs[r] = '+' if s == '0' else '-'
    elif atom.startswith("term"):
      f, t, r = [x.strip() for x in atom.split(')')[0].split('(')[1].split(',')]
      t = int(t)
      if f == func:
        if len(orig_terms) < t: orig_terms.extend([set() for _ in range(t - len(orig_terms))])
        orig_terms[t-1].add(r)
  
  new_terms = []
  new_signs = {}
  for atom in repaired_model:
    if atom.startswith("node_regulator"):
      t, r = [x.strip() for x in atom.split(')')[0].split('(')[1].split(',')]
      t = int(t)
      if len(new_terms) < t: new_terms.extend([set() for _ in range(t - len(new_terms))])
      new_terms[t-1].add(r)
    elif atom.startswith("activator") or atom.startswith("regulator_activator"):
      r = atom.split(')')[0].split('(')[1].strip()
      assert r not in new_signs
      new_signs[r] = '+'
    elif atom.startswith("inhibitor") or atom.startswith("regulator_inhibitor"):
      r = atom.split(')')[0].split('(')[1].strip()
      assert r not in new_signs
      new_signs[r] = '-'
  
  orig_regulators = {r for term in orig_terms for r in term}
  new_regulators = {r for term in new_terms for r in term}
  common_regulators = orig_regulators & new_regulators
  
  if logger:
    logger.debug("Processed functions:"
                  f"\n{orig_regulators = }\n{new_regulators = }\n"
                  f"\n{orig_signs = }\n{new_signs = }\n"
                  f"\n{orig_terms = }\n{new_terms = }")
  
  real_counts = {
    "extra-terms" : max(0, len(new_terms) - len(orig_terms)),
    "missing-terms" : max(0, len(orig_terms) - len(new_terms)),
    "extra-regulators" : len(new_regulators - orig_regulators),
    "missing-regulators" : len(orig_regulators - new_regulators),
    "sign-to-inhibitor" : sum(1 for r in common_regulators if new_signs[r] == '-' and orig_signs[r] == '+'),
    "sign-to-activator" : sum(1 for r in common_regulators if new_signs[r] == '+' and orig_signs[r] == '-'),
    "term-extra-regulator" : sum(len(new_term - orig_term) for new_term, orig_term in zip(new_terms, orig_terms)),
    "term-missing-regulator" : sum(len(orig_term - new_term) for new_term, orig_term in zip(new_terms, orig_terms))
  }
  real_counts["term-number"] = real_counts["extra-terms"] + real_counts["missing-terms"]
  real_counts["regulators"] = real_counts["extra-regulators"] + real_counts["missing-regulators"]
  real_counts["signs"] = real_counts["sign-to-inhibitor"] + real_counts["sign-to-activator"]
  real_counts["term-format"] = real_counts["term-missing-regulator"] + real_counts["term-extra-regulator"]
  real_counts["terms"] = real_counts["term-number"] + real_counts["term-format"]
  
  for crit, count in repair_counts:
    real_c = real_counts.get(crit)
    if real_c is None:
      if logger: logger.warning(f"Could not validate count for criterion {crit}")
    else:
      assert count == real_c, f"Criterion {crit} differs: expected {real_c} got {count}"
  if logger: logger.info("Repair counts are correct")