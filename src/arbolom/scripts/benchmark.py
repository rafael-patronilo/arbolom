"""Benchmark ARBoLoM using the benchmarking folder structure presented in the
project's page.

Usage: arbolom-benchmark -f (CONFIG_FOLDER) -o (OBSERVATION_FOLDER) -m (MODEL_NAME) -s (SAVE_FOLDER) -stable -sync -async
Optional flags:
-stable -> Performs repairs using stable state observations (default).
-sync -> Performs repairs using synchronous observations.
-async -> Performs repairs using asynchronous observations.
-skip -> Number of first observation/config pairs to skip (to resume interrupted benchmarks).
Variables:
CONFIG_FOLDER -> Path of folder containing the config folders (with the corrupted models).
OBSERVATION_FOLDER -> Path of folder containing the observations.
MODEL_NAME -> The name of the model that will be benchmarked.
SAVE_FOLDER -> The folder where the results from benchmarking will be saved to.
Extra arguments are passed through to arbolom-revision.
"""
import argparse
import logging
import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field

from arbolom.constants import (BCHMARK_COMPOUND_REPAIR_TIME, BCHMARK_ORIGINAL_NODE_NO,
                               BCHMARK_ORIGINAL_REGULATOR_NO, BCHMRK_COMPOUND_NAME,
                               BCHMRK_COMPOUND_STATE, BCHMRK_MODEL_CONSISTENCY_TIME,
                               BCHMRK_MODEL_NAME, BCHMRK_MODEL_REPAIR_TIME,
                               BCHMRK_MODEL_REVISION_TIME, BCHMRK_MODEL_STATE)
from arbolom.modes import UpdateMode
from arbolom.repair.criteria import CRITERIA, print_criteria
from arbolom.revision import DEFAULT_CRITERIA

global_logger = logging.getLogger("global")


@dataclass
class BenchmarkSettings:
  config_path: str
  obsv_path: str
  model_name: str
  save_folder: str
  # Skip first n observation/config pairs, useful for resuming interrupted benchmarks
  skip_n_first: int = 0
  mode: UpdateMode = UpdateMode.STABLE
  min_change_criteria: list[str] = field(default_factory=lambda: list(DEFAULT_CRITERIA))
  # Extra arguments passed through to the revision command
  common_revision_args: list[str] = field(default_factory=list)


#-----Argument parser-----
def build_parser():
  parser = argparse.ArgumentParser(description="Benchmark the ARBoLoM tool using the benchmarking folder structure presented in the project's page. Extra arguments will be passed through to arbolom-revision")
  requiredNamed = parser.add_argument_group("required arguments")
  requiredNamed.add_argument("-f", "--config_folder", help="Path of folder containing config folders.", required=True)
  requiredNamed.add_argument("-o", "--observations", help="Path of observations from real-world models.", required=True)
  requiredNamed.add_argument("-m", "--model_name", help="Name of the model to benchmark (doesn't need to be exact, just needs to be contained in it).", required=True)
  requiredNamed.add_argument("-s", "--save_folder", help="Path of folder to save benchmarks to.", required=True)
  parser.add_argument("-skip", "--skip-n-first", type=int, default=0, help="An optional number of first observation/config pairs to skip at the beginning of the benchmark. Intended to help resume interrupted benchmarks.")
  parser.add_argument("-stable", "--stable_state", action='store_true', help="Flag to benchmark using stable state observations (default).")
  parser.add_argument("-sync", "--synchronous", action='store_true', help="Flag to benchmark using synchronous observations (default is stable state).")
  parser.add_argument("-async", "--asynchronous", action='store_true', help="Flag to benchmark using asynchronous observations (default is stable state).")
  parser.add_argument("-criteria", "--criteria", default=",".join(DEFAULT_CRITERIA),
      help="Comma separated list of the criteria to use to minimize changes, in order of priority. For the list of available criteria use --help-criteria. Default is %(default)s.")
  parser.add_argument("-help-criteria", "--help-criteria", action='store_true', help="Prints the available criteria to the console and exits.")
  return parser


#Purpose: Parses the arguments of the benchmark (sys.argv[1:] by default).
# Returns None if the program should exit (e.g. --help-criteria)
def parse_args(argv=None) -> BenchmarkSettings | None:
  logger = logging.getLogger("parser")
  logger.setLevel(logging.INFO)

  if argv is None:
    argv = sys.argv[1:]
  args, common_revision_args = build_parser().parse_known_args(argv)

  if args.help_criteria:
    print_criteria()
    return None

  logger.debug("Obtained configs folder: " + args.config_folder)
  logger.debug("Obtained observations folder: " + args.observations)
  logger.debug("Obtained save folder: " + args.save_folder)

  min_change_criteria = list(DEFAULT_CRITERIA)
  if args.criteria:
    common_revision_args += ["--criteria", args.criteria]
    min_change_criteria = args.criteria.split(',')
    for x in min_change_criteria:
      assert x in CRITERIA, f"Invalid criterion specified: {x}. Use --help-criteria to see available criteria."

  mode = UpdateMode.from_flags(args.stable_state, args.synchronous, args.asynchronous)
  logger.info(f"Mode used: {mode.description}")

  return BenchmarkSettings(
    config_path=args.config_folder,
    obsv_path=args.observations,
    model_name=args.model_name,
    save_folder=args.save_folder,
    skip_n_first=args.skip_n_first,
    mode=mode,
    min_change_criteria=min_change_criteria,
    common_revision_args=common_revision_args,
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


def get_models(model_path):
  input_model_list = [os.path.join(model_path, f) for f in sorted(os.listdir(model_path))
    if os.path.isfile(os.path.join(model_path,f)) and os.path.splitext(f)[1] in (".lp", ".bnet")]
  return input_model_list


class BenchmarkRunner:
  """Revises every corrupted model of every config against every observation
  file, in a separate process each, writing one CSV file per (config, observation)."""

  def __init__(self, settings: BenchmarkSettings):
    self.settings = settings

  def get_obsv_list(self):
    s = self.settings
    obsv_path_list = []

    #For each file system entity inside the Observations folder
    for obsv_model in sorted(os.listdir(s.obsv_path)):

      #If it is a folder containing the name of the model passed as argument
      if os.path.isdir(os.path.join(s.obsv_path, obsv_model)) and s.model_name in obsv_model:

        #For each folder containing the observations for the interaction types inside the folder with the name of the model
        for interaction_type in sorted(os.listdir(os.path.join(s.obsv_path, obsv_model))):
          #If the folder name matches the chosen interaction type
          if s.mode.value == interaction_type:

            #Then place all the paths for the observations within inside the list
            for obsv in sorted(os.listdir(os.path.join(s.obsv_path, obsv_model,interaction_type))):
              obsv_path_list.append(os.path.join(s.obsv_path, obsv_model,interaction_type,obsv))
            return obsv_path_list
    global_logger.error(f"No observations found for model '{s.model_name}' in {s.obsv_path}")
    return obsv_path_list

  def get_configs_list(self):
    s = self.settings
    configs_path_list = []
    exact_model_name = None

    #For each file system entity inside the Configurations folder
    for config_folder in sorted(os.listdir(s.config_path)):
      #If it is a folder
      if os.path.isdir(os.path.join(s.config_path, config_folder)):

        #For each model folder within that folder
        for model_folder in sorted(os.listdir(os.path.join(s.config_path, config_folder))):
          #If it matches the name of the model passed as an argument, add it to the list
          if s.model_name in model_folder:
            if exact_model_name is None:
              exact_model_name = model_folder
            elif model_folder != exact_model_name:
              if model_folder == s.model_name:
                exact_model_name = model_folder
                configs_path_list.clear()
              else:
                continue
            configs_path_list.append(os.path.join(s.config_path, config_folder, model_folder))
    global_logger.info(f"Model search term '{s.model_name}' solved to '{exact_model_name}'")
    return configs_path_list

  def benchmark_filename(self, config_dir, obsv_file, snapshot):
    filename = os.path.split(os.path.split(config_dir)[0])[1] + "-" + os.path.basename(os.path.normpath(obsv_file))
    filename += f"-{self.settings.mode.value}_benchmark"

    if snapshot:
      filename += '-snapshot'

    filename += '.csv'

    return os.path.join(self.settings.save_folder, filename)

  def error_row(self, model_path, error_type):
    return (f"{model_path},{error_type},NaN,NaN,NaN,N/A,N/A,NaN,NaN,NaN," +
            ",".join(["NaN" for _ in self.settings.min_change_criteria]) + "\n"
    )

  def header_line(self):
    benchmark_header = (BCHMRK_MODEL_NAME,
      BCHMRK_MODEL_STATE, BCHMRK_MODEL_REVISION_TIME,
      BCHMRK_MODEL_CONSISTENCY_TIME, BCHMRK_MODEL_REPAIR_TIME,
      BCHMRK_COMPOUND_NAME, BCHMRK_COMPOUND_STATE,
      BCHMARK_ORIGINAL_REGULATOR_NO,
      BCHMARK_ORIGINAL_NODE_NO,
      BCHMARK_COMPOUND_REPAIR_TIME,
      *self.settings.min_change_criteria
    )
    return ",".join(benchmark_header) + "\n"

  def revision_command(self, model_path, observations):
    s = self.settings
    return [sys.executable, '-m', 'arbolom.scripts.revision',
            '-f', model_path,
            '-o', observations,
            f'-{s.mode.value}', '-benchmark'] + s.common_revision_args

  def run(self):
    s = self.settings
    skip_n_first = s.skip_n_first
    skip_mode = (skip_n_first != 0)
    header_line = self.header_line()

    configs_list = self.get_configs_list()
    obsv_list = self.get_obsv_list()

    global_logger.debug(f"Obtained config models: {configs_list}")
    global_logger.debug(f"Obtained observations: {obsv_list}")

    current_obs_number = 0
    current_config_number = 0
    test_number = 1
    for obsv in obsv_list:
      current_obs_number += 1

      for config in configs_list:
        current_config_number += 1
        global_logger.info(f"Starting config {config}")
        model_paths = get_models(config)
        save_filename = self.benchmark_filename(config, obsv, snapshot=True)

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
            result = subprocess.run(self.revision_command(model_path, obsv),
              capture_output=True, text=True
            )
            if result.returncode < 0:
              global_logger.error(f"Revision process was killed with code {result.returncode} (Out of memory?)")
              save_file.write(self.error_row(model_path, "killed (out of memory?)"))
            elif result.returncode != 0:
              global_logger.error(f"Revision process returned {result.returncode}"
                                  f"\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}")
              save_file.write(self.error_row(model_path, "error"))
            elif result.stderr:
              global_logger.error(f"Revision process had an error"
                                  f"\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}")
              save_file.write(self.error_row(model_path, "error"))
            else:
              save_file.write(result.stdout)
            global_logger.info(f"Current progress: {test_id}")
            test_number += 1
        final_filename = self.benchmark_filename(config, obsv, snapshot=False)
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


def main(argv=None):
  logging.basicConfig()
  global_logger.setLevel(logging.INFO)
  settings = parse_args(argv)
  if settings is None:
    return 0
  BenchmarkRunner(settings).run()
  return 0


if __name__ == "__main__":
  sys.exit(main())
