import math
import time, clingo
from aux_scripts.repair_constants import CHANGED_SIGNS, EXTRA_NODE_REGULATORS, EXTRA_REGULATORS, MISSING_NODE_REGULATORS, MISSING_REGULATORS
from aux_scripts.repair_criteria import build_asp_change_criteria
from aux_scripts.repair_prints import printStatistics

#Path of the encodings to obtain inconsistent functions
inconsistent_functions_path = "encodings/repairs/auxiliary/inconsistent_functions.lp"

#Paths of the encodings to obtain the observations that happen before positive observations
previous_observations_sync_path = "encodings/repairs/auxiliary/previous_observations_sync.lp"
previous_observations_async_path = "encodings/repairs/auxiliary/previous_observations_async.lp"

#Paths of the encodings that generating functions
repair_encoding_stable_path = "encodings/repairs/repairs_stable.lp"
repair_encoding_sync_path = "encodings/repairs/repairs_sync.lp"
repair_encoding_async_path = "encodings/repairs/repairs_async.lp"

#Timeout for function repair
repair_timeout = 3600


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
def generateFunctions(func, model, incst, upo, min_change_criteria,
                      toggle_stable_state, toggle_sync, toggle_async, 
                      path_mode = False, logger=None):
  if logger: logger.debug("Calculating repairs...")

  #current_variation = 0
  #final_variation = 0
  function = []
  upo_program = ""
  if upo : upo_program = upo[0]

  _, max_node_limit = determineStartNodesAndLimit(func,model,upo,path_mode)
  if logger: 
    logger.debug(f"Trying to find a solution with at most ({max_node_limit}) nodes...")
    if math.isinf(max_node_limit): logger.error("Node limit is infinite")
  timeout_start = time.time()
  function, costs = generateFunctionsClingo(max_node_limit, timeout_start, func, model, incst, upo_program, min_change_criteria,
                                     toggle_stable_state, toggle_sync, toggle_async, path_mode, logger)
  if function == "timed_out": 
    if logger: logger.debug(f"No solutions.")
    return function, None
  elif function:
    if logger: logger.debug("... Done.")
    assert costs is not None
    return function, costs
  else:
    if logger: logger.debug(f"No solutions.")
    return "no_solution", None

#Inputs:
# function_above - the function with original number of nodes + variation
# function_below - the function with original number of nodes - variation
#Purpose: Compare the two functions and return the one with the least changes,
#according to the optimization criteria (regulators, signs, format)
def compareAndGetBestFunction(function_above, function_below, variation):

  if not function_above and not function_below: return None, 0
  if function_above and not function_below: return function_above, variation
  if function_below and not function_above: return function_below, -variation

  func_above_stat_map = getFuncStatMap(function_above)
  func_below_stat_map = getFuncStatMap(function_below)

  if func_above_stat_map[MISSING_REGULATORS] + func_above_stat_map[EXTRA_REGULATORS] < \
    func_below_stat_map[MISSING_REGULATORS] + func_below_stat_map[EXTRA_REGULATORS]:
    return function_above, variation

  elif func_above_stat_map[MISSING_REGULATORS] + func_above_stat_map[EXTRA_REGULATORS] > \
    func_below_stat_map[MISSING_REGULATORS] + func_below_stat_map[EXTRA_REGULATORS]:
    return function_below, -variation

  elif func_above_stat_map[CHANGED_SIGNS] < func_below_stat_map[CHANGED_SIGNS]:
    return function_above, variation
  
  elif func_above_stat_map[CHANGED_SIGNS] > func_below_stat_map[CHANGED_SIGNS]:
    return function_below, -variation

  elif func_above_stat_map[MISSING_NODE_REGULATORS] + func_above_stat_map[EXTRA_NODE_REGULATORS] < \
    func_below_stat_map[MISSING_NODE_REGULATORS] + func_below_stat_map[EXTRA_NODE_REGULATORS]:
    return function_above, variation
  
  elif func_above_stat_map[MISSING_NODE_REGULATORS] + func_above_stat_map[EXTRA_NODE_REGULATORS] > \
    func_below_stat_map[MISSING_NODE_REGULATORS] + func_below_stat_map[EXTRA_NODE_REGULATORS]:
    return function_below, -variation
  
  else: return function_below, -variation

#Inputs:
# function - The repaired function obtained from clingo.
#Purpose: Organize the differencecs between the original function and the
#given function in a map.
def getFuncStatMap(function):
  stat_map = {}

  stat_map[MISSING_REGULATORS] = 0
  stat_map[EXTRA_REGULATORS] = 0
  stat_map[CHANGED_SIGNS] = 0
  stat_map[MISSING_NODE_REGULATORS] = 0
  stat_map[EXTRA_NODE_REGULATORS] = 0

  for atom in function:
    if "missing_regulator" in atom:
      stat_map[MISSING_REGULATORS] += 1
    
    elif "extra_regulator" in atom:
      stat_map[EXTRA_REGULATORS] += 1

    elif "sign_changed" in atom:
      stat_map[CHANGED_SIGNS] += 1
      
    elif "missing_node_regulator" in atom:
      stat_map[MISSING_NODE_REGULATORS] += 1
      
    elif "extra_node_regulator" in atom:
      stat_map[EXTRA_NODE_REGULATORS] += 1

  return stat_map

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
def generateFunctionsClingo(node_number, timeout_start, func, model,
                             incst, upo_program, min_change_criteria,
                             toggle_stable_state, toggle_sync, toggle_async, 
                             path_mode = False, logger=None):
  no_timeout = True
  clingo_args = ["0", f"-c compound={func}", f"-c max_node_number={node_number}"]
      
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
  if logger: logger.debug(f"Change minimization criteria:\n{asp_min_criteria}")
  ctl.add("base", [], program=asp_min_criteria)

  ctl.ground([("base", [])])
  function = []
  costs = None

  def on_model(m):
    nonlocal function, costs
    function = str(m).split(" ")
    costs = m.cost

  with ctl.solve(on_model=on_model, async_=True) as handle:
    no_timeout = handle.wait(repair_timeout - (time.time() - timeout_start))
    handle.cancel()

  if not no_timeout:
    function = "timed_out" 
  
  if logger: logger.debug(ctl.statistics)
  return function, costs

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

  if logger: logger.debug("Calculating previous observations...")

  with ctl.solve(yield_=True) as handle:
    for model in handle:
      functions = str(model).split(" ")

  if logger: logger.debug("... Done.")

  if logger: printStatistics(ctl.statistics, print_func=logger.debug)

  if not functions[0]: #If there are no previous observations
    if logger: logger.warning("No previous observations found.")
    return []

  return functions

#Inputs: 
# -prev_obs, a string containing all previous observations
#Purpose: Returns a tuple with all unique positive observations,
# and the total number of unique positive observations
def processPreviousObservations(prev_obs, logger=None):

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
  if logger: logger.debug(f"Python code time for unique positive observations: {end - start}s\n")
  total_upos = len(uniques_map.values())
  return (output, total_upos)