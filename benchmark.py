import os, argparse, logging
import subprocess
from aux_scripts.repair_constants import *
from aux_scripts.consistency_functions import *
from aux_scripts.conversion_functions import *
from aux_scripts.repair_functions import *
from aux_scripts.repair_prints import *
from aux_scripts.repair_criteria import CRITERIA, print_criteria
import shutil
import sys
from contextlib import contextmanager

#Usage: $python benchmark.py -f (CONFIG_FOLDER) -o (OBSERVATION_FOLDER) -m (MODEL_NAME) -s (SAVE_FOLDER) -stable -sync -async
#Optional flags:
#-stable -> Performs repairs using stable state observations (default).
#-sync -> Performs repairs using synchronous observations.
#-async -> Performs repairs using asynchronous observations.
#Variables:
#CONFIG_FOLDER -> Path of file containing the BCF Boolean model written in .lp or .bnet format.
#OBSERVATION_FOLDER -> Path of file containing observations written in lp. 
#MODEL_NAME -> The name of the model that will be benchmarked.
#INTERACTION_TYPE -> The interaction type to be considered (stable, sync or async).
#SAVE_FOLDER -> The folder where the results from benchmarking will be saved to.

#-----Configs-----
#Config folder path
config_path = None

#Paths of folder with observations
obsv_path = None

#Model name
model_name = None

#Paths of encodings with inconsistencies
obsv_path = None

#Folder where the benchmark results will be saved to
save_folder = None

# Skip first n observation/config pairs, useful for resuming interrupted benchmarks
skip_n_first = 0

#Mode flags 
toggle_stable_state = True
toggle_sync = False
toggle_async = False

#Parser
parser = None
args = None

min_change_criteria = ["term-number", "regulators", "signs", "term-format"]

common_revision_args = []

#Global logger (change logging.(LEVEL) to desired (LEVEL) )
logging.basicConfig()
global_logger = logging.getLogger("global")
global_logger.setLevel(logging.INFO)

#-----Auxiliary Functions-----
#---Argument parser---
#Purpose: Parses the arguments of function repair
def parseArgs():
  logger = logging.getLogger("parser")
  logger.setLevel(logging.INFO)

  global parser, args, common_revision_args

  parser = argparse.ArgumentParser(description="Benchmark the ARBoLoM tool using the benchmarking folder structure presented in the project's page. Extra arguments will be passedthrough to revision.py")
  requiredNamed = parser.add_argument_group("required arguments")
  requiredNamed.add_argument("-f", "--config_folder", help="Path of folder containing config folders.", required=True)
  requiredNamed.add_argument("-o", "--observations", help="Path of observations from real-world models.", required=True)
  requiredNamed.add_argument("-m", "--model_name", help="Name of the model to benchmark (doesn't need to be exact, just needs to be contained in it).", required=True)
  requiredNamed.add_argument("-s", "--save_folder", help="Path of folder to save benchmarks to.", required=True)
  parser.add_argument("-skip", "--skip-n-first", type=int, default=0, help="An optional number of first observation/config pairs to skip at the beginning of the benchmark. Intended to help resume interrupted benchmarks.")
  parser.add_argument("-stable", "--stable_state", action='store_true', help="Flag to benchmark using stable state observations (default).")
  parser.add_argument("-sync", "--synchronous", action='store_true', help="Flag to benchmark using synchronous observations (default is stable state).")
  parser.add_argument("-async", "--asynchronous", action='store_true', help="Flag to benchmark using asynchronous observations (default is stable state).")
  parser.add_argument("-criteria", "--criteria", default="term-number,regulators,signs,term-format",
      help="Comma separated list of the criteria to use to minimize changes, in order of priority. For the list of available criteria use --help-criteria. Default is %(default)s.")
  parser.add_argument("-help-criteria", "--help-criteria", action='store_true', help="Prints the available criteria to the console and exits.")
  args, common_revision_args = parser.parse_known_args(sys.argv[1:])

  if args.help_criteria:
    print_criteria()
    exit(0)

  global config_path, obsv_path, model_name, save_folder, skip_n_first
  global toggle_stable_state, toggle_sync, toggle_async, min_change_criteria

  config_path = args.config_folder
  obsv_path = args.observations
  save_folder = args.save_folder

  logger.debug("Obtained configs folder: " + config_path)
  logger.debug("Obtained observations folder: " + obsv_path)
  logger.debug("Obtained save folder: " + save_folder)

  model_name = args.model_name
  stable = args.stable_state
  synchronous = args.synchronous
  asynchronous = args.asynchronous

  if args.criteria:
    common_revision_args += ["--criteria", args.criteria]
    custom_criteria = args.criteria.split(',')
    for x in custom_criteria:
      assert x in CRITERIA, f"Invalid criterion specified: {x}. Use --help-criteria to see available criteria."
    min_change_criteria = custom_criteria

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

  skip_n_first = args.skip_n_first

  return


#-----Benchmark functions-----
def getObsvList():

  obsv_path_list = []

  #For each file system entity inside the Observations folder
  for obsv_model in os.listdir(obsv_path):

    #If it is a folder containing the name of the model passed as argument
    if os.path.isdir(os.path.join(obsv_path, obsv_model)) and model_name in obsv_model:

      #For each folder containing the observations for the interaction types inside the folder with the name of the model
      for interaction_type in os.listdir(os.path.join(obsv_path, obsv_model)):
        #If the folder name matches the chosen interaction type
        if toggle_stable_state and "stable" == interaction_type or \
          toggle_sync and "sync" == interaction_type or \
          toggle_async and "async" == interaction_type:

          #Then place all the paths for the observations within inside the list
          for obsv in os.listdir(os.path.join(obsv_path, obsv_model,interaction_type)):
            obsv_path_list.append(os.path.join(obsv_path, obsv_model,interaction_type,obsv))
          return obsv_path_list

def getConfigsList():

  configs_path_list = []
  exact_model_name = None

  #For each file system entity inside the Configurations folder
  for config_folder in os.listdir(config_path):
    #If it is a folder
    if os.path.isdir(os.path.join(config_path, config_folder)):

      #For each model folder within that folder
      for model_folder in os.listdir(os.path.join(config_path, config_folder)):
        #If it matches the name of the model passed as an argument, add it to the list
        if model_name in model_folder:
          if exact_model_name is None:
            exact_model_name = model_folder
          elif model_folder != exact_model_name:
            if model_folder == model_name:
              exact_model_name = model_folder
              configs_path_list.clear()
            else:
              continue
          configs_path_list.append(os.path.join(config_path, config_folder, model_folder))
  global_logger.info(f"Model search term '{model_name}' solved to '{exact_model_name}'")
  return configs_path_list

def get_models(model_path):
  input_model_list = [os.path.join(model_path, f) for f in os.listdir(model_path)
    if os.path.isfile(os.path.join(model_path,f)) and os.path.splitext(f)[1] == ".lp" or
    os.path.splitext(f)[1] == ".bnet"]
  return input_model_list

def benchmark_filename(config_dir, obsv_file, snapshot):
  filename = None
  filename = os.path.split(os.path.split(config_dir)[0])[1] + "-" + os.path.basename(os.path.normpath(obsv_file))
  if toggle_stable_state:
    filename += "-stable_benchmark"
  elif toggle_sync:
    filename += "-sync_benchmark"
  else:
    filename += "-async_benchmark"

  if snapshot:
    filename += '-snapshot'
  
  filename += '.csv'
  
  save_path = None
  save_path = os.path.join(save_folder, filename)
  return save_path

def error_row(model_path, error_type):
  return (f"{model_path},{error_type},NaN,NaN,NaN,N/A,N/A,NaN,NaN,NaN," + 
          ",".join(["NaN" for _ in min_change_criteria]) + "\n"
  )

@contextmanager
def deffered_output_file(path, resume_mode : bool, header_line : str):
  if not resume_mode and os.path.exists(path):
    raise FileExistsError(f"{path} unexpectedly already exists. "
                          "Please delete first or use --skip to enable resuming from a snapshot file")
  file = None
  class DefferedOutputFile:
    def write(self, data : str):
      nonlocal file
      if not file:
        if resume_mode and os.path.exists(path):
          global_logger.warning(f"File {path} already exists, opening in append mode")
          file = open(path, "a")
        else:
          file = open(path, "x")
          file.write(header_line)
          global_logger.debug(f"File {path} created")
      file.write(data)
  try: yield DefferedOutputFile()
  finally:
    if file: file.close()

def main():
  global global_logger
  global toggle_stable_state, toggle_sync, toggle_async
  global min_change_criteria, skip_n_first
  parseArgs()
  skip_mode = (skip_n_first != 0)

  interaction_mode = None
  if toggle_stable_state: interaction_mode = "stable"
  elif toggle_sync: interaction_mode = "sync"
  elif toggle_async: interaction_mode = "async"

  benchmark_header = (BCHMRK_MODEL_NAME, 
    BCHMRK_MODEL_STATE, BCHMRK_MODEL_REVISION_TIME,
    BCHMRK_MODEL_CONSISTENCY_TIME, BCHMRK_MODEL_REPAIR_TIME,
    BCHMRK_COMPOUND_NAME, BCHMRK_COMPOUND_STATE,
    BCHMARK_ORIGINAL_REGULATOR_NO,
    BCHMARK_ORIGINAL_NODE_NO,
    BCHMARK_COMPOUND_REPAIR_TIME,
    *min_change_criteria
  )
  header_line = ",".join(benchmark_header) + "\n"

  configs_list = getConfigsList()
  obsv_list = getObsvList()

  global_logger.debug(f"Obtained config models: {configs_list}")
  global_logger.debug(f"Obtained observations: {obsv_list}")

  current_observations = None
  current_config_directory = None
  current_obs_number = 0
  current_config_number = 0
  test_number = 1
  for obsv in obsv_list:
    current_observations = obsv
    current_obs_number += 1

    for config in configs_list:
      current_config_number += 1
      global_logger.info(f"Starting config {config}")
      current_config_directory = config
      model_paths = get_models(current_config_directory)
      save_filename = benchmark_filename(current_config_directory, obsv, snapshot=True)
      
      with deffered_output_file(save_filename, skip_mode, header_line) as save_file:
        for model_index, model_path in enumerate(model_paths):
          test_id = (f"Test {test_number} - "
            f"Obsv({current_obs_number}/{len(obsv_list)}) || "
            f"Config({current_config_number}/{len(configs_list)}) || "
            f"Model({model_index+1}/{len(model_paths)})"
          )
          if skip_n_first > 0:
            skip_n_first -= 1
            global_logger.info(f"Skipping: {test_id}")
            test_number += 1
            continue
          result = subprocess.run(['python', 'revision.py',
            '-f', model_path,
            '-o', current_observations,
            f'-{interaction_mode}', '-benchmark'] + common_revision_args,
            capture_output=True, text=True
          )
          if result.returncode < 0:
            global_logger.error(f"Revision process was killed with code {result.returncode} (Out of memory?)")
            save_file.write(error_row(model_path, "killed (out of memory?)"))
          elif result.returncode != 0:
            global_logger.error(f"Revision process returned {result.returncode}"
                                f"\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}")
            save_file.write(error_row(model_path, "error"))
          elif result.stderr:
            global_logger.error(f"Revision process had an error"
                                f"\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}")
            save_file.write(error_row(model_path, "error"))
          else:
            save_file.write(result.stdout)
          global_logger.info(f"Current progress: {test_id}")
          test_number += 1
      final_filename = benchmark_filename(current_config_directory, obsv, snapshot=False)
      if not os.path.exists(save_filename):
        assert skip_mode
        global_logger.info("All tests skipped for current config")
      elif os.path.exists(final_filename):
        raise FileExistsError(f"Cannot overwrite {final_filename}, results kept as {save_filename}")
      else:
        shutil.move(save_filename, final_filename)
        global_logger.info(f"Saved config results to {final_filename}")
    current_config_number = 0
    
  global_logger.info("Done!")

if __name__ == "__main__":
  main()