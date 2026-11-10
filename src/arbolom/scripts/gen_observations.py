"""Command line interface to generate time-series observations for a model.

Usage: arbolom-gen-observations -f (FILENAME) -async -e (NUMBER OF EXPERIMENTS) -t (TIME STEPS) -s (SAVE_DIRECTORY)

Optional flags:
-async ->  Produces observations using the asynchronous mode.
-s -> Path of directory to save generated observations (default is the directory of the model)

Variables:
FILENAME ->  Path of file containing Boolean model in the BCF format written in lp.
NUMBER OF EXPERIMENTS ->  The number of experiments (sets of observations) to generate.
TIME STEPS ->  The number of time steps to consider in each experiment.
SAVE_DIRECTORY -> Path of directory to save generated observations to.

Attention:
 Input file must be in the BCF format and follow the conventions of the
 .lp files in the lp_models folder (results will be unpredictable otherwise)
"""
import argparse
import logging
import os
import sys

from arbolom.modes import UpdateMode
from arbolom.observation_generation import generate_observations, save_observations_to_file

DEFAULT_EXPERIMENTS = "2"
DEFAULT_TIME_STEPS = "5"


def build_parser():
  parser = argparse.ArgumentParser(description=
    "Generate observations for a Boolean logical model in the BCF written in lp.")
  parser.add_argument("-f", "--model_to_observe", required=True, help=
    "Path to model to generate observations for.")
  parser.add_argument("-async", "--asynchronous", action='store_true', help=
    "Flag to generate asynchronous observations (default is synchronous).")
  parser.add_argument("-e", "--experiments_number", default=DEFAULT_EXPERIMENTS, help=
    "Number of experiments (sets of observations) to generate (default is " +
    DEFAULT_EXPERIMENTS + ").")
  parser.add_argument("-t", "--time_steps", default=DEFAULT_TIME_STEPS, help=
    "Number of time steps to consider in each experiment (default is " +
    DEFAULT_TIME_STEPS + ").")
  parser.add_argument("-s", "--save_directory", help=
    "Path of directory to save generated observations to.")
  return parser


def main(argv=None):
  logging.basicConfig()
  logging.getLogger("global").setLevel(logging.INFO)
  logger = logging.getLogger("parser")
  logger.setLevel(logging.INFO)

  args = build_parser().parse_args(argv)
  model_path = args.model_to_observe
  mode = UpdateMode.ASYNC if args.asynchronous else UpdateMode.SYNC
  logger.info(f"Mode used: {mode.description}")
  write_folder = args.save_directory or os.path.dirname(model_path)

  atoms = generate_observations(model_path, mode, args.experiments_number, args.time_steps)
  print("Clingo finished solving ✔️")

  filename = os.path.basename(model_path).replace(".lp", f"-{mode.value}-obs.lp")
  save_observations_to_file(atoms, os.path.join(write_folder, filename))
  return 0


if __name__ == "__main__":
  sys.exit(main())
