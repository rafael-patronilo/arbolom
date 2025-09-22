import argparse, logging, time
from aux_scripts.repair_functions import *
from aux_scripts.repair_prints import *
from aux_scripts.repair_criteria import *
import os
import revision

#Usage: $python repair.py -f (FILENAME) -i (INCONSISTENCIES) -stable -sync -async
#Optional flags:
#-stable -> Performs repairs using stable state observations (default).
#-sync -> Performs repairs using synchronous observations.
#-async -> Performs repairs using asynchronous observations.
#Variables:
#FILENAME -> Path of file containing Boolean model in the BCF format written in lp.
#INCONSISTENCIES -> Path of file containing inconsistencies obtained from the consistency checking phase.


#-----Testing shortcuts----
'''
#3 variables
python .\repair.py -f simple_models/lp/corrupted/3/3-corrupted-f.lp -i simple_models/lp/corrupted/3/inconsistencies/3-corrupted-f-stable_inconsistency.lp -stable
python .\repair.py -f simple_models/lp/corrupted/3/3-corrupted-f.lp -i simple_models/lp/corrupted/3/inconsistencies/3-corrupted-f-sync_inconsistency.lp -sync
python .\repair.py -f simple_models/lp/corrupted/3/3-corrupted-f.lp -i simple_models/lp/corrupted/3/inconsistencies/3-corrupted-f-async_inconsistency.lp -async

#5 variables
python .\repair.py -f simple_models/lp/corrupted/8/8-corrupted-f.lp -i simple_models/lp/corrupted/8/inconsistencies/8-corrupted-f-stable_inconsistency.lp -stable
python .\repair.py -f simple_models/lp/corrupted/8/8-corrupted-f.lp -i simple_models/lp/corrupted/8/inconsistencies/8-corrupted-f-sync_inconsistency.lp -sync
python .\repair.py -f simple_models/lp/corrupted/8/8-corrupted-f.lp -i simple_models/lp/corrupted/8/inconsistencies/8-corrupted-f-async_inconsistency.lp -async

#6 variables
python .\repair.py -f real_models/lp/corrupted/boolean_cell_cycle/boolean_cell_cycle-corrupted-f.lp -i real_models/lp/corrupted/boolean_cell_cycle/inconsistencies/boolean_cell_cycle-corrupted-f-stable_inconsistency.lp
python .\repair.py -f real_models/lp/corrupted/boolean_cell_cycle/boolean_cell_cycle-corrupted-f.lp -i real_models/lp/corrupted/boolean_cell_cycle/inconsistencies/boolean_cell_cycle-corrupted-f-sync_inconsistency.lp -sync
python .\repair.py -f real_models/lp/corrupted/boolean_cell_cycle/boolean_cell_cycle-corrupted-f.lp -i real_models/lp/corrupted/boolean_cell_cycle/inconsistencies/boolean_cell_cycle-corrupted-f-async_inconsistency.lp -async

#7 variables
python .\repair.py -i simple_models/lp/corrupted/11/inconsistencies/11-corrupted-f2-stable_inconsistency.lp -f simple_models/lp/corrupted/11/11-corrupted-f2.lp -stable
python .\repair.py -f simple_models/lp/corrupted/11/11-corrupted-f.lp -i simple_models/lp/corrupted/11/inconsistencies/11-corrupted-f-sync_inconsistency.lp -sync
python .\repair.py -f simple_models/lp/corrupted/11/11-corrupted-f.lp -i simple_models/lp/corrupted/11/inconsistencies/11-corrupted-f-async_inconsistency.lp -async

#8 variables
python .\repair.py -f real_models/lp/corrupted/SP_1cell/SP_1cell-corrupted-f.lp -i real_models/lp/corrupted/SP_1cell/inconsistencies/SP_1cell-corrupted-f-stable_inconsistency.lp
python .\repair.py -f real_models/lp/corrupted/SP_1cell/SP_1cell-corrupted-f.lp -i real_models/lp/corrupted/SP_1cell/inconsistencies/SP_1cell-corrupted-f-sync_inconsistency.lp -sync
python .\repair.py -f real_models/lp/corrupted/SP_1cell/SP_1cell-corrupted-f.lp -i real_models/lp/corrupted/SP_1cell/inconsistencies/SP_1cell-corrupted-f-async_inconsistency.lp -async

#Extra
python .\repair.py -f simple_models/lp/corrupted/6/6-corrupted-fe.lp -i simple_models/lp/corrupted/6/inconsistencies/6-corrupted-fe-stable_inconsistency.lp -stable
python .\repair.py -f simple_models/lp/corrupted/6/6-corrupted-fe.lp -i simple_models/lp/corrupted/6/inconsistencies/6-corrupted-fe-sync_inconsistency.lp -sync
python .\repair.py -f simple_models/lp/corrupted/6/6-corrupted-fe.lp -i simple_models/lp/corrupted/6/inconsistencies/6-corrupted-fe-async_inconsistency.lp -async

#Total of 30 variables, with functions of varying variable number
.\repair.py -f simple_models/lp/corrupted/13/13-corrupted-fera.lp -i simple_models/lp/corrupted/13/inconsistencies/13-corrupted-fera-sync_inconsistency.lp -sync

#Real world model with 40 variables
.\repair.py -f real_models/lp/corrupted/TCRsig40/TCRsig40-corrupted-fera.lp -i real_models/lp/corrupted/TCRsig40/inconsistencies/TCRsig40-corrupted-fera-sync_inconsistency.lp -sync

#NO SOLUTIONS
#6 variables
python .\repair.py -f real_models/lp/corrupted/boolean_cell_cycle/boolean_cell_cycle-corrupted-f.lp -i testing/impossible_inconsistencies/boolean_cell_cycle-corrupted-f-sync_inconsistency.lp -sync 

#8 variables
python .\repair.py -f real_models/lp/corrupted/SP_1cell/SP_1cell-corrupted-f.lp -i testing/impossible_inconsistencies/SP_1cell-corrupted-f-sync_inconsistency.lp -sync
'''


#-----Configs-----
#Command-line usage
cmd_enabled = True

#Toggle debug modes
iftv_debug_toggled = False

#Model path
model_path = "simple_models/lp/corrupted/8/8-corrupted-f.lp"

#Paths of encodings with inconsistencies
incst_path = "simple_models/lp/corrupted/8/inconsistencies/8-corrupted-f-sync_inconsistency.lp"

#Mode flags 
toggle_stable_state = True
toggle_sync = False
toggle_async = False

parallel_mode = None

min_change_criteria = ["term-number", "regulators", "signs", "term-format"]

#Parser (will only be used if command-line usage is enabled above)
parser = None
args = None

#Global logger (change logging.(LEVEL) to desired (LEVEL) )
logging.basicConfig()
global_logger = logging.getLogger("global")
global_logger.setLevel(logging.DEBUG)



#-----Auxiliary Functions-----
#---Argument parser---
#Purpose: Parses the arguments of function repair
def parseArgs():
  logger = logging.getLogger("parser")
  logger.setLevel(logging.INFO)

  global parser, args #TODO add criteria order arg

  parser = argparse.ArgumentParser(description="Repair an inconsistent Boolean logical model in the BCF written in lp, given a set of observations and inconsistent compounds, both written in lp.")
  parser.add_argument("-f", "--model_to_repair", help="Path to model to check the consistency of.", required=True)
  parser.add_argument("-i", "--inconsistencies", help="Path to inconsistencies obtained from the consistency checking phase.", required=True)
  parser.add_argument("-stable", "--stable_state", action='store_true', help="Flag to check the consistency using stable state observations (default).")
  parser.add_argument("-sync", "--synchronous", action='store_true', help="Flag to check the consistency using synchronous observations (default is stable state).")
  parser.add_argument("-async", "--asynchronous", action='store_true', help="Flag to check the consistency using asynchronous observations (default is stable state).")
  parser.add_argument("-p", "--parallel_mode", type=str, default=None,
                      help="What to pass to clingo's --parallel-mode argument. " \
                      "The value 'auto' will choose the number of threads based on the number of available CPU cores.")
  parser.add_argument("-criteria", "--criteria", default="term-number,regulators,signs,term-format",
                      help="Comma separated list of the criteria to use to minimize changes, in order of priority. " \
                      "For the list of available criteria use --help-criteria. Default is %(default)s.")
  args = parser.parse_args()

  global model_path, incst_path, toggle_stable_state, toggle_sync, toggle_async
  global min_change_criteria, parallel_mode

  model_path = args.model_to_repair
  incst_path = args.inconsistencies

  logger.debug("Obtained model: " + model_path)
  logger.debug("Obtained inconsistencies: " + incst_path)


  stable = args.stable_state
  synchronous = args.synchronous
  asynchronous = args.asynchronous

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

  if args.criteria:
    custom_criteria = args.criteria.split(',')
    for x in custom_criteria:
      assert x in CRITERIA, f"Invalid criterion specified: {x}. Use --help-criteria to see available criteria."
    min_change_criteria = custom_criteria
  if args.parallel_mode:
    if args.parallel_mode == "auto":
      parallel_mode = f"{min(64, os.cpu_count() or 1)}"  # Automatically set to the number of CPU cores
    else:
      parallel_mode = args.parallel_mode
  
  return


def repair(model, inconsistencies): 
  incst_funcs = generateInconsistentFunctions(model, inconsistencies)
  i_f_array = processInconsistentFunctions(incst_funcs)
  final_state = "repaired"

  timed_out_functions = False
  suboptimal_repairs = False
  unrepairable_functions = False

  if i_f_array:
    for func in i_f_array:
      printFuncRepairStart(func)
      func_logger = logging.getLogger(func)
      func_logger.info(f"Beginning repairs for function {func}")
      prev_obs = generatePreviousObservations(func, inconsistencies, 
        toggle_sync, toggle_async, logger = func_logger)
      upo = processPreviousObservations(prev_obs, logger = func_logger)
      
      result, functions, costs = generateFunctions(func, model, inconsistencies, upo, min_change_criteria, args.timeout,
        toggle_stable_state, toggle_sync, toggle_async, parallel_mode=parallel_mode, logger = func_logger)
      

      if result == "timeout": 
        if functions:
          suboptimal_repairs = True
        else:
          timed_out_functions = True
      elif result == "no_solution": 
        unrepairable_functions = True
      
      if functions:
        assert costs is not None
        criteria_costs = list(zip(min_change_criteria, costs))
        printFuncRepairEnd(func)
        print(f"Repair costs:\n" + "\n".join([f"\t{x[0]}: {x[1]}" for x in criteria_costs]))
      
    
  if timed_out_functions and unrepairable_functions:
    final_state = "still inconsistent (timed out functions and functions without existing solutions)"
  elif timed_out_functions:
    final_state = "still inconsistent (timed out functions)"
  elif unrepairable_functions:
    final_state = "still inconsistent (functions without existing solutions)"
  elif suboptimal_repairs:
    final_state = "suboptimally repaired (functions timed out before finding optimal repair)"

  print(f"Final function state: {final_state}")


#-----Main-----
if cmd_enabled:
  parseArgs()

  start_time = time.time()
  revision.repair(model_path, incst_path, )
  printIFTVStart()

  incst_funcs = generateInconsistentFunctions(model_path, incst_path, 
    iftv_debug_toggled, True, True)
  i_f_array = processInconsistentFunctions(incst_funcs, True)
  printIFTVEnd()

  if i_f_array:
    for func in i_f_array:

      printFuncRepairStart(func)
      
      prev_obs = generatePreviousObservations(func, incst_path, toggle_sync,
        toggle_async, True, True)
      upo = processPreviousObservations(prev_obs)
      
      functions, node_variation = generateFunctions(func, model_path, incst_path, upo,
        toggle_stable_state, toggle_sync, toggle_async, True, True)

      logRepairedLP(func, functions, node_variation)
      
      printFuncRepairEnd(func)

  end_time = time.time()
  print(f"Total time taken: {end_time-start_time}s", )
  