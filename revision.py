import os, argparse, logging, time, re
from genericpath import isdir
from aux_scripts.consistency_functions import *
from aux_scripts.conversion_functions import *
from aux_scripts.repair_constants import *
from aux_scripts.repair_functions import *
from aux_scripts.repair_prints import *
from aux_scripts.repair_criteria import CRITERIA, print_criteria
from collections import OrderedDict

#Usage: $python revision.py -f (FILENAME) -o (OBSERVATIONS) -stable -sync -async -bulk -benchmark (SAVE_PATH)
#Optional flags:
#-stable -> Performs repairs using stable state observations (default).
#-sync -> Performs repairs using synchronous observations.
#-async -> Performs repairs using asynchronous observations.
#-bulk -> Enables bulk revision (-f must be path of the directory with the models)
#-benchmark -> Enables benchmark mode
#Variables:
#FILENAME -> Path of file containing the BCF Boolean model written in .lp or .bnet format
#OBSERVATIONS -> Path of file containing observations written in lp. 
#SAVE_PATH -> Path of folder to save benchmark results to


#-----Configs-----
#Toggle debug modes
iftv_debug_toggled = False

#Model path
model_path = None

#Paths of encodings with observations
obsv_path = None

repair_save_path = None

#Flag that enables the revision of multiple models at once
bulk_enabled = False

#Flag that enables benchmark mode
# Note: Benchmark mode disables all prints, and produces an output file with
# four columns: the first is the name of the revised file, the second is
# whether it was inconsistent to begin with, 
# and if yes was it repaired successfully or not,
# the third is the time taken to revise it,
# and the fourth is only present in case of unsuccessful repairs, indicating
# which functions could not be repaired.
benchmark_enabled = False

benchmark_naming = False

#Benchmark save path
benchmakr_write_folder = "None"

#Mode flags 
toggle_stable_state = True
toggle_sync = False
toggle_async = False
parallel_mode = None

min_change_criteria = ["term-number", "regulators", "signs", "term-format"]

#Parser
parser = None
args = None

#Global logger (change logging.(LEVEL) to desired (LEVEL) )
logging.basicConfig(filename='revision.log',
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level=logging.DEBUG)
global_logger = logging.getLogger("global")



#-----Auxiliary Functions-----
#---Argument parser---
#Purpose: Parses the arguments of function repair
def parseArgs():
  logger = logging.getLogger("parser")

  global parser, args

  parser = argparse.ArgumentParser(description="Revise a Boolean logical model in the BCF written in .lp or .bnet format, given a set of observations written in .lp format.")
  requiredNamed = parser.add_argument_group("required arguments")
  requiredNamed.add_argument("-f", "--model_to_repair", help="Path of model to revise.", required=True)
  requiredNamed.add_argument("-o", "--observations", help="Path of observations from real-world model.", required=True)
  requiredNamed.add_argument("-s", "--save_path", help="Path to save repaired function to. If a directory is passed, a file with same name as the original funcion will be created there.", default=None)
  parser.add_argument("-stable", "--stable_state", action='store_true', help="Flag to check the consistency using stable state observations (default).")
  parser.add_argument("-sync", "--synchronous", action='store_true', help="Flag to check the consistency using synchronous observations (default is stable state).")
  parser.add_argument("-async", "--asynchronous", action='store_true', help="Flag to check the consistency using asynchronous observations (default is stable state).")
  parser.add_argument("-bulk", "--bulk", action='store_true', help="Enables the revision of multiple models at once. (Note: the path provided to -f must be the directory containing those models).")
  parser.add_argument("-benchmark", "--benchmark_save_folder", help="Enables benchmark mode, saving benchmark results at the specified path.")
  parser.add_argument("-benchmark_naming", "--benchmark_naming", action='store_true', help="Enables benchmark files to be saved with a more helpful name.")
  parser.add_argument("-t", "--timeout", type=int, default=3600, help="How many seconds to wait for each function repair.")
  parser.add_argument("-p", "--parallel_mode", type=str, default=None,
                      help="What to pass to clingo's --parallel-mode argument. " \
                      "The value 'auto' will choose the number of threads based on the number of available CPU cores.")
  parser.add_argument("-criteria", "--criteria", default="term-number,regulators,signs,term-format",
                      help="Comma separated list of the criteria to use to minimize changes, in order of priority. For the list of available criteria use --help-criteria. Default is %(default)s.")
  parser.add_argument("-help-criteria", "--help-criteria", action='store_true', help="Prints the available criteria to the console and exits.")
  args = parser.parse_args()

  logger.info(f"Received arguments: {args}")

  if args.help_criteria:
    print_criteria()
    exit(0)
  global model_path, obsv_path, benchmakr_write_folder
  global toggle_stable_state, toggle_sync, toggle_async
  global bulk_enabled, benchmark_enabled, benchmark_naming, parallel_mode
  global min_change_criteria

  model_path = args.model_to_repair
  obsv_path = args.observations

  logger.debug("Obtained model: " + model_path)
  logger.debug("Obtained observations: " + obsv_path)

  stable = args.stable_state
  synchronous = args.synchronous
  asynchronous = args.asynchronous
  bulk = args.bulk
  benchmark = args.benchmark_save_folder

  if args.criteria:
    custom_criteria = args.criteria.split(',')
    for x in custom_criteria:
      assert x in CRITERIA, f"Invalid criterion specified: {x}. Use --help-criteria to see available criteria."
    min_change_criteria = custom_criteria

  if args.parallel_mode:
    if args.parallel_mode == "auto":
      parallel_mode = f"{min(64, os.cpu_count())}"  # Automatically set to the number of CPU cores
    else:
      parallel_mode = args.parallel_mode
    logger.info(f"Parallel argument set to: --parallel-mode {parallel_mode}")
  if bulk:
    bulk_enabled = bulk  
  
  if benchmark:
    benchmark_enabled = True
    if isdir(benchmark):
      benchmakr_write_folder = benchmark
    else:
      logger.info("Specified save location is not a valid directory. Saving in model directory instead.")
      benchmakr_write_folder = os.path.dirname(model_path)

  if args.benchmark_naming: 
    benchmark_naming = True

  if not stable and not synchronous and not asynchronous:
    logger.info("Default mode: Stable State \U0001f6d1")
    return

  if stable:
    toggle_stable_state = True
    toggle_sync = False
    toggle_async = False
    logger.info("Mode used: Stable State \U0001f6d1")

  elif synchronous:
    toggle_stable_state = False
    toggle_sync = True
    toggle_async = False
    logger.info("Mode used: Synchronous \U0001f550")

  elif asynchronous:
    toggle_stable_state = False
    toggle_sync = False
    toggle_async = True
    logger.info("Mode used: Asynchronous \U0001f331")
  return


#---Model reading-related functions---
#Purpose: reads models from the specified model_path (either in .bnet or .lp
# format), and returns them in a list. Each element of the list is a tuple,
#with the model in string format in the first position and the model's path
#in the second position
def readModels():
  logger = logging.getLogger("readModels")

  input_model_list = [model_path]
  output_model_list = []

  if bulk_enabled:
    input_model_list = [os.path.join(model_path, f) for f in os.listdir(model_path)
    if os.path.isfile(os.path.join(model_path,f)) and os.path.splitext(f)[1] == ".lp" or
    os.path.splitext(f)[1] == ".bnet"]
  
  for current_model_path in input_model_list:
    split_path = os.path.splitext(current_model_path)
    model_extension = split_path[1]

    if model_extension != ".bnet" and model_extension != ".lp":
      logger.error("Unrecognized model format. Only models written in "
      +".bnet or .lp format are accepted.")
      return None

    model_file = open(current_model_path, 'r')
    output_model = model_file.readlines()

    if model_extension == ".bnet":
      output_model = convertModelToLP(output_model,logger)
    
    else: output_model = "".join(output_model)
      
    logger.debug("obtained model: \n" + output_model)
    output_model_list.append((output_model,current_model_path))
  
  return output_model_list

def getModelCompounds(model):
  return re.findall(r'compound\((.+?)\).',model)

def getCompoundRegulatorNumber(model, compound):
  return len(re.findall(fr'regulates\((.+?), ?{compound}, ?(0|1)\).',model))

def getCompoundTermNumber(model, compound):
  return re.search(fr'function\({compound},(.+?)\).',model).group(1)



#-----Benchmarking Functions-----
#Input: model - the model being revised
#Purpose: Initializes and returns the map containing the statistics of each 
# function's changes after being repaired
def initRevisionStatsMap(model):
  revision_stats_map = OrderedDict()
  all_compounds = sorted(getModelCompounds(model))

  for compound in all_compounds:
    regulator_number = getCompoundRegulatorNumber(model, compound)
    node_number = getCompoundTermNumber(model, compound)

    revision_stats_map[compound] = OrderedDict()
    revision_stats_map[compound][FINAL_STATE] = "consistent"
    revision_stats_map[compound][ORIGINAL_REGULATOR_NUMBER] = regulator_number
    revision_stats_map[compound][ORIGINAL_NODE_NUMBER] = node_number
    revision_stats_map[compound][BCHMARK_COMPOUND_REPAIR_TIME] = 0.0
    for crit in min_change_criteria:
      revision_stats_map[compound][crit] = 0

  return revision_stats_map

#Inputs: 
# -benchmark_array - the array containing the benchmark results
# -model_name - the full path of the model being revised
# -final_state - the final state of the revised model
# -revision_time - the time taken to fully revise the model
# -consistency_time - the time spent on consistency checking
# -repair_time - the time spent on repairs
# -model_revision_stats - the map containing the changes done to each repaired
#   function
#Purpose: Fills the benchmark array with the results obtained from the model's
# revision
def fillBenchmarkArray(benchmark_array, model_name, final_state, 
  revision_time, consistency_time, repair_time, model_revision_stats):

  for func in model_revision_stats:
    benchmark_array.append(
      (model_name, 
      final_state, revision_time,
      consistency_time, repair_time,
      func, *model_revision_stats[func].values()
      )
    )

#Inputs: 
# -func - the name of the compound whose function is being repaired
# -func_state - the final state of the function after repairs
# -node_variation - how much the final node number varied in comparison to the
#   original number
# -repairs - the atoms obtained from function repair
# -revision_stats - the map containing 
# -repair_time - the time spent on repairs
# -model_revision_stats - the map containing the changes done to each repaired
#   function
#Purpose: updates the map with the results from function repair
def processFunctionRepairStats(func, func_state, criteria_costs, repairs, repair_time, revision_stats):
  revision_stats[func][FINAL_STATE] = func_state
  revision_stats[func][BCHMARK_COMPOUND_REPAIR_TIME] = repair_time

  for crit, cost in criteria_costs:
      revision_stats[func][crit] = cost

#Input: array - the array containing the lines with benchmark results
#  to write on the output file
#Purpose: Saves the results from benchmarking in the specified save_path
def saveBenchmark(array, snapshot=False):
  logger = logging.getLogger("saveBenchmark")

  filename = None
  if benchmark_naming:
    filename = os.path.split(os.path.split(model_path)[0])[1] + "-" + os.path.basename(os.path.normpath(obsv_path))
  else:
    filename = os.path.basename(os.path.normpath(model_path)) + "-" + os.path.basename(os.path.normpath(obsv_path))


  if toggle_stable_state:
    filename += "-stable_benchmark"
  elif toggle_sync:
    filename += "-sync_benchmark"
  else:
    filename += "-async_benchmark"

  snapshot_filename = filename + '-snapshot.csv'
  if snapshot:
    filename = snapshot_filename
  else:
    filename += '.csv'
  
  save_path = None
  if benchmakr_write_folder:
    save_path = os.path.join(benchmakr_write_folder, filename)
  else:
    save_path = os.path.join(os.path.dirname(model_path), filename)
    if bulk_enabled:
      save_path = os.path.join(model_path, filename)

  logger.debug("Save path: " + str(save_path))

  f = open(save_path, 'w')

  for line in array:
    for column_idx in range(0,len(line)):
      f.write(str(line[column_idx]))

      if (column_idx != len(line)-1):
        f.write(",\t")
       
    f.write("\n")
  f.close()
  if not snapshot and os.path.exists(snapshot_filename):
    os.remove(snapshot_filename)
  logger.info("Saved benchmark to: " + str(save_path))



#-----Revision Functions-----
#Inputs: 
# -model - the model whose consistency is being checked
# -obsv - the observations from the original model
#Purpose: returns the inconsistencies found in the model
def checkConsistency(model, obsv):
  logger = logging.getLogger("checkConsistency")

  atoms = consistencyCheck(model,obsv,
    toggle_stable_state,toggle_sync,toggle_async)

  inconsistencies = isConsistent(atoms, toggle_stable_state, 
    toggle_sync, toggle_async, print_consistent=not benchmark_enabled)

  
  if inconsistencies is None:
    logger.debug("No inconsistencies found")
  else:
    logger.debug("Inconsistencies found")
  return inconsistencies 

#Inputs: 
# -model - the model being repaired
# -inconsistencies - the inconsistencies obtained from consistency checking
# -revision_stats - the map containing the changes done to each repaired
# function
#Purpose: attempts to repair the model and returns its final state
def repair(model, inconsistencies, revision_stats): 
  incst_funcs = generateInconsistentFunctions(model, inconsistencies)
  i_f_array = processInconsistentFunctions(incst_funcs)
  final_state = "repaired"

  timed_out_functions = []
  suboptimal_repairs = []
  unrepairable_functions = []

  if i_f_array:
    for func in i_f_array:
      func_state = "repaired"
      if not benchmark_enabled: printFuncRepairStart(func)
      func_logger = logging.getLogger(func)
      func_logger.info(f"Beginning repairs for function {func}")
      prev_obs = generatePreviousObservations(func, inconsistencies, 
        toggle_sync, toggle_async, logger = func_logger)
      upo = processPreviousObservations(prev_obs, logger = func_logger)
      
      compound_repair_start = time.monotonic()
      result, functions, costs = generateFunctions(func, model, inconsistencies, upo, min_change_criteria, args.timeout,
        toggle_stable_state, toggle_sync, toggle_async, parallel_mode=parallel_mode, logger = func_logger)
      compound_repair_end = time.monotonic()
      

      if result == "timeout": 
        if functions:
          func_state = "suboptimally repaired (timed out)"
          suboptimal_repairs.append(func)
        else:
          func_state = "inconsistent (timed out)"
          timed_out_functions.append(func)
      elif result == "no_solution": 
        unrepairable_functions.append(func)
        func_state = "inconsistent (no solution)"
      if functions:
        assert costs is not None
      func_logger.info(f"Completed repairing of {func}, final state: {func_state}")
      if not benchmark_enabled: print(f"Completed repairing of {func}, final state: {func_state}")

      if costs is None:
        costs = [float('nan')] * len(min_change_criteria)
      criteria_costs = list(zip(min_change_criteria, costs))

      processFunctionRepairStats(func, func_state, criteria_costs, functions, compound_repair_end - compound_repair_start, revision_stats)

      logRepairedLP(func, functions, criteria_costs, to_stdout=not benchmark_enabled, logger=func_logger)
      if not benchmark_enabled: printFuncRepairEnd(func)
    
  if timed_out_functions and unrepairable_functions:
    final_state = "still inconsistent (timed out functions and functions without existing solutions)"
  elif timed_out_functions:
    final_state = "still inconsistent (timed out functions)"
  elif unrepairable_functions:
    final_state = "still inconsistent (functions without existing solutions)"
  elif suboptimal_repairs:
    final_state = "suboptimally repaired (functions timed out before finding optimal repair)"

  return final_state



def main():
  global global_logger, model_path, obsv_path, repair_save_path
  parseArgs()
  # First, obtain the model in .lp model. If the obtained file has .bnet
  # extension, it must be converted to .lp.
  models = readModels()
  benchmark_array = [(BCHMRK_MODEL_NAME, 
    BCHMRK_MODEL_STATE, BCHMRK_MODEL_REVISION_TIME,
    BCHMRK_MODEL_CONSISTENCY_TIME, BCHMRK_MODEL_REPAIR_TIME,
    BCHMRK_COMPOUND_NAME, BCHMRK_COMPOUND_STATE,
    BCHMARK_ORIGINAL_REGULATOR_NO,
    BCHMARK_ORIGINAL_NODE_NO,
    BCHMARK_COMPOUND_REPAIR_TIME,
    *min_change_criteria
    )]

  for model in models:
    final_state = "consistent"
    total_revision_time = 0
    total_consistency_time = 0
    total_repair_time = 0

    revision_start_time = time.monotonic()
    model_revision_stats = initRevisionStatsMap(model[0])

    if bulk_enabled and not benchmark_enabled: print("Currently revising model ", model[1])
    global_logger.info(f"Currently revising model {model[1]}")

    consistency_start_time = time.monotonic()
    inconsistencies = checkConsistency(model[0], obsv_path)
    consistency_end_time = time.monotonic()

    total_consistency_time = consistency_end_time - consistency_start_time

    # Second, check the consistency of the .lp model using the provided observations
    # and time step. If the model is consistent, print a message saying so.
    if inconsistencies:
      if not benchmark_enabled: print("Inconsistent model! \nRepairing...")
      global_logger.info(f"Currently revising model {model[1]}")

      # Third, if it is not, proceed with the repairs and print out the necessary ones.
      repair_start_time = time.monotonic()
      final_state = repair(model[0], inconsistencies, model_revision_stats)
      repair_end_time = time.monotonic()

      total_repair_time = repair_end_time - repair_start_time
      
      if not benchmark_enabled and "repaired" in final_state: print(f"Applying the above repairs to model {model[1]} will render it consistent!\n")

    revision_end_time = time.monotonic()
    total_revision_time = revision_end_time - revision_start_time

    if benchmark_enabled:
      fillBenchmarkArray(benchmark_array, model[1], final_state,
        total_revision_time, 
        total_consistency_time,
        total_repair_time, model_revision_stats)
      saveBenchmark(benchmark_array, snapshot=True)

  if benchmark_enabled:
    saveBenchmark(benchmark_array)
  else:
    global_logger.info("Benchmarking disabled, not saving.")

if __name__ == "__main__":
  try:
    main()
  except Exception as e:
    global_logger.exception(f"An unexpected exception occurred during the revision process: {e}")
    raise e


