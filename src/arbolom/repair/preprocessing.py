"""Steps that prepare the repair of each function: finding the inconsistent
functions, the observations preceding their positive observations and the
resulting node limits."""
import time
from collections import defaultdict
from dataclasses import dataclass

import clingo

from arbolom.common import clingo_logger
from arbolom.modes import UpdateMode
from arbolom.printing import print_statistics
from arbolom.resources import INCONSISTENT_FUNCTIONS_ENCODING, PREVIOUS_OBSERVATIONS_ENCODINGS


#-----Functions that solve LPs with clingo-----
#Input:
# model - the model that is being revised
# inconsistencies - the inconsistencies obtained from consistency checking
# debug_mode - flag that enables extra clingo output (must remove logger in clingo.Control to see)
#Purpose: Obtains the inconsistent functions from the consistency checking phase
def generate_inconsistent_functions(model, inconsistencies, debug_mode=False, path_mode=False, enable_prints=False):
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

  ctl.load(INCONSISTENT_FUNCTIONS_ENCODING)

  if enable_prints: print("Starting iftv generation ⏱")
  ctl.ground([("base", [])])
  iftv = []

  with ctl.solve(yield_=True) as handle:
    for model in handle:
      iftv.append(str(model).split(" "))

  if enable_prints: print("Finished iftv generation \U0001F3C1")
  if enable_prints: print_statistics(ctl.statistics)
  return iftv


#Inputs:
# func - the inconsistent function
# model - the model being revised
# upo - unique positive observations that are obtained from process_previous_observations
# path mode - flag that enables loading the model and inconsistencies from a file, instead of a string
#Purpose: Determines how many nodes were in the inconsistent function, as well
#as what the maximum number of nodes to consider should be
def determine_start_nodes_and_limit(func,model,upo,path_mode):
  node_limit = None

  if not upo:
    node_limit = 0
  else: node_limit = upo[1]

  if path_mode:
    with open(model, "r") as f:
      for line in f.readlines():
        if f"function({func}" in line:
          original_nodes = int(line.split(',')[1].split(')')[0])
          break
  else:
    original_nodes = int(model.split(f"function({func},")[1].split(')')[0])

  return original_nodes, node_limit



#-----Functions that process output from clingo-----
#Input: The inconsistent functions obtained from clingo
#Purpose: Creates an array containing the name of all the inconsistent functions
def get_inconsistent_functions_array(inconsistent_functions):
  result = []

  for incst_func in inconsistent_functions:
    var_name = incst_func[0].split(')')[0].split('(')[1]
    result.append(var_name)

  return result

#Input: The generated inconsistent functions output from clingo
#Purpose: Processes clingo's inconsistent functions output by creating an array with them
def process_inconsistent_functions(inconsistent_functions, enable_prints=False):
  if not inconsistent_functions:
    print("process_inconsistent_functions: No answers sets could be found	❕ there must be something wrong with the encoding...")

  elif inconsistent_functions[0]:

    i_f_array = get_inconsistent_functions_array(inconsistent_functions)

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
    print("process_inconsistent_functions: No inconsistent functions could be found ❌")



#-----Python implementation of unique positive observation determination-----
#Inputs:
# func- the compound that has the inconsistent function
# inconsistencies - the inconsistencies obtained from consistency checking
# mode - the UpdateMode of the observations
# path_mode - flag that enables loading the inconsistencies from a file, instead of a string
#Purpose: Returns the states that are the input of the function for its
# positive observations (the observations are contained in inconsistencies):
# previous_observation(E,T,C,S) atoms for the timestep before each positive
# observation in time-series modes, and previous_observation(E,C,S) atoms for
# each experiment where the compound is active in stable state mode
def generate_previous_observations(func, inconsistencies, mode: UpdateMode, path_mode=False, logger=None):
  clingo_args = ["0", f"-c compound={func}"]

  ctl = clingo.Control(arguments=clingo_args, logger=clingo_logger(logger))

  if path_mode:
    ctl.load(inconsistencies)
  else:
    ctl.add("base", [], program=inconsistencies)

  ctl.load(PREVIOUS_OBSERVATIONS_ENCODINGS[mode])

  ctl.ground([("base", [])])
  functions = []

  if logger: logger.debug("Calculating previous positive observations...")

  with ctl.solve(yield_=True) as handle:
    for model in handle:
      functions = str(model).split(" ")

  if logger: logger.debug("... Done.")

  if logger: print_statistics(ctl.statistics, print_func=logger.debug)

  if not functions[0]: #If there are no previous observations
    if logger: logger.debug("No previous positive observations found.")
    return []

  return functions


#Inputs:
# -prev_obs, the atoms obtained from generate_previous_observations
#Purpose: Returns a tuple with all unique positive observations,
# and the total number of unique positive observations.
# Positive observations are identified by (experiment, timestep) in time-series
# modes and by experiment in stable state mode; observations from different
# experiments with the same state are counted once.
def process_previous_observations(prev_obs, logger=None):
  if not prev_obs:
    return ("",0)
  start = time.monotonic()
  observations = defaultdict(list)
  compounds = set()

  for previous_obsv in prev_obs:
    arguments = previous_obsv.split(')')[0].split('(')[1].split(',')
    if len(arguments) == 4: # previous_observation(E,T,C,S) in time-series modes
      experiment, timestep, compound, state = arguments
      obs_id = (experiment, str(int(timestep) + 1))
    else: # previous_observation(E,C,S) in stable state mode
      experiment, compound, state = arguments
      obs_id = (experiment,)
    observations[obs_id].append((compound, state))
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
