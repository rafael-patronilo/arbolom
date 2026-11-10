import time, clingo
from aux_scripts.repair_prints import printStatistics
from aux_scripts.repair_criteria import build_asp_change_criteria, build_asp_disable_constraints

#Path of the encodings to obtain inconsistent functions
inconsistent_functions_path = "encodings/repairs/auxiliary/inconsistent_functions.lp"

#Paths of the encodings to obtain the observations that happen before positive observations
previous_observations_sync_path = "encodings/repairs/auxiliary/previous_observations_sync.lp"
previous_observations_async_path = "encodings/repairs/auxiliary/previous_observations_async.lp"

#Paths of the encodings that generating functions
repair_encoding_stable_path = "encodings/repairs/deepening_search/repairs_stable.lp"
repair_encoding_sync_path = "encodings/repairs/deepening_search/repairs_sync.lp"
repair_encoding_async_path = "encodings/repairs/deepening_search/repairs_async.lp"


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
# repair_timeout - seconds available for this function, either a number or a
#   (soft, hard) tuple: after the soft timeout the best repair found so far is
#   returned; if none was found yet, the search continues for at most `hard`
#   more seconds until the first repair is found
# func - the name of the inconsistent function
# model - the model to revise
# incst - the inconsistencies obtained from consistency checking
# upo - unique positive observations that are obtained from processPreviousObservations
# toggle_stable_state - flag that enables stable state interaction
# toggle_sync - flag that enables synchronous interaction
# toggle_async - flag that enables asynchronous interaction
# min_change_criteria - change minimization criteria, excluding term-number (handled by the deepening itself)
# disable_change_criteria - criteria whose changes are forbidden
# path_mode - flag that enables loading the model and inconsistencies from a file, instead of a string
# parallel_mode - value for clingo's --parallel-mode argument (None to disable)
# cost_bounds - costs of a previously found repair ([term-number] + costs of min_change_criteria);
#   only repairs at least as good are searched for
#Purpose: Generates a function that is compatible with previously given observations, based on the obtained inconsistencies
def generateFunctions(
    repair_timeout, func, model, incst, upo, 
    toggle_stable_state, toggle_sync, toggle_async, 
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
  starting_node_number, max_node_limit = determineStartNodesAndLimit(func,model,upo,path_mode)

  def solve(node_number, variation, have_candidate):
    now = time.monotonic()
    soft_left = max(0.0, soft_deadline - now)
    # The hard timeout is waited for after the soft one. Once a candidate exists there
    # is no point in waiting past the soft timeout
    hard_left = 0.0 if have_candidate else max(0.0, hard_deadline - now - soft_left)
    bounds = clingo_bounds if variation == max_variation else None
    return generateFunctionsClingo(node_number, (soft_left, hard_left),
                                   func, model, incst, upo_program,
                                   toggle_stable_state, toggle_sync, toggle_async,
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
# toggle_stable_state - flag that enables stable state interaction
# toggle_sync - flag that enables synchronous interaction
# toggle_async - flag that enables asynchronous interaction
# path_mode - flag that enables loading the model and inconsistencies from a file, instead of a string
# parallel_mode - value for clingo's --parallel-mode argument (None to disable)
# cost_bounds - upper bounds (inclusive) for the optimization costs
#Purpose: Calls clingo to solve the repair encoding. Returns (completed, result), where
# completed is True if the search finished (so result is optimal, or None if there is
# no solution) and result is either None or an (atoms, costs) tuple.
def generateFunctionsClingo(
    node_number, timeouts, func, model, incst, 
    upo_program, 
    toggle_stable_state, toggle_sync, toggle_async,
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

  if toggle_stable_state:
    ctl.load(repair_encoding_stable_path)
  elif toggle_sync:
    ctl.load(repair_encoding_sync_path)
  elif toggle_async:
    ctl.load(repair_encoding_async_path)

  asp_min_criteria = build_asp_change_criteria(min_change_criteria, toggle_stable_state, toggle_sync, toggle_async)
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
  
  if logger: printStatistics(ctl.statistics, logger.debug)
  
  completed = finished and not stopped_early
  if not function: return completed, None
  else: return completed, (function, costs)

#Inputs:
# func - the inconsistent function
# model - the model being revised
# upo - unique positive observations that are obtained from processPreviousObservations
# path mode - flag that enables loading the model and inconsistencies from a file, instead of a string
#Purpose: Determines how many nodes were in the inconsistent function, as well
#as what the maximum number of nodes to consider should be
def determineStartNodesAndLimit(func,model,upo,path_mode):
  node_limit = None

  if not upo: node_limit = 0
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
def generatePreviousObservations(func, inconsistencies, toggle_sync, toggle_async, path_mode=False, enable_prints=False):
  clingo_args = ["0", f"-c compound={func}"]
  
  ctl = clingo.Control(arguments=clingo_args)

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

  if enable_prints: print("Calculating previous observations...")

  with ctl.solve(yield_=True) as handle:
    for model in handle:
      functions = str(model).split(" ")

  if enable_prints: print("... Done.")

  if enable_prints: printStatistics(ctl.statistics)

  if not functions[0]: #If there are no previous observations
    return []

  return functions

#Inputs: 
# -prev_obs, a string containing all previous observations
#Purpose: Returns a tuple with all unique positive observations,
# and the total number of unique positive observations
def processPreviousObservations(prev_obs, enable_prints=False):

  if not prev_obs:
    return ""
    
  uniques_map = {}

  output = ""

  current_experiment = ""
  current_timestep = ""
  current_state_key = "0"

  start = time.time()
  for previous_obsv in prev_obs:
    arguments = previous_obsv.split(')')[0].split('(')[1].split(',')
    experiment = arguments[0]
    timestep = arguments[1]
    compound = arguments[2]
    state = arguments[3]

    #First iteration
    if not current_experiment:
      current_experiment = experiment
      current_timestep = timestep

    #If we're still looking at the same experiment and timestep
    if current_experiment + current_timestep == experiment + timestep:

      #If the compound is active, it will be a part of this timestep's 
      # state key
      if state == "1":
        current_state_key += compound

    else: #We are looking at a different experiment or timestep

      #Save previous timestep's state in the map, if it didn't exist yet
      sorted_state = "".join(sorted(current_state_key))

      if sorted_state not in uniques_map:
          uniques_map[sorted_state] = current_experiment + ","+ str(int(current_timestep) + 1)
   
      current_experiment = experiment
      current_timestep = timestep
      current_state_key = "0"

      if state == "1":
        current_state_key += compound

  #End of loop, last timestep's state must be saved
  sorted_state = "".join(sorted(current_state_key))

  if sorted_state not in uniques_map:
    uniques_map[sorted_state] = current_experiment + ","+ str(int(current_timestep) + 1)

  #Print result in LP format
  for value in uniques_map.values():
    output += "unique_positive_observation(" + value + ").\n"

  end = time.time()
  if enable_prints: print(f"Python code time for unique positive observations: {end - start}s\n")
  total_upos = len(uniques_map.values())
  return (output, total_upos)