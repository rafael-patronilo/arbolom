"""Command line interface to check the consistency of a model.

Usage: arbolom-consistency -f (FILENAME) -o (OBSERVATIONS) -stable -sync -async -s (SAVE_DIRECTORY)

Optional flags:
-stable -> Performs consistency checking using stable state observations (default).
-sync -> Performs consistency checking using synchronous observations.
-async -> Performs consistency checking using asynchronous observations.
-s -> Path of directory to save inconsistencies, when they exist (default is the
      "inconsistencies" folder next to the model)

Variables:
FILENAME -> Path of file containing Boolean model in the BCF format written in lp.
OBSERVATIONS -> Path of file containing observations written in lp.

Attention:
 File FILENAME must be in the BCF format and follow the conventions of the
 .lp files in the lp_models folder (results will be unpredictable otherwise).
Observations should also follow the conventions of the files in the
 obsv folder, inside lp_models.
"""
import argparse
import logging
import os
import sys

from arbolom.consistency import consistency_check, is_consistent
from arbolom.modes import UpdateMode


def build_parser():
  parser = argparse.ArgumentParser(description=
    "Check the consistency of a Boolean logical model in the BCF written in " +
    " lp, given a set of observations in lp.")
  parser.add_argument("-f", "--model_to_check", required=True, help=
    "Path to model to check the consistency of.")
  parser.add_argument("-o", "--observations_to_use", required=True, help=
    "Path to observations used to check the consistency of the model.")
  parser.add_argument("-stable", "--stable_state", action='store_true', help=
    "Flag to check the consistency using stable state observations (default).")
  parser.add_argument("-sync", "--synchronous", action='store_true', help=
    "Flag to check the consistency using synchronous observations (default is stable state).")
  parser.add_argument("-async", "--asynchronous", action='store_true', help=
    "Flag to check the consistency using asynchronous observations (default is stable state).")
  parser.add_argument("-s", "--save_directory", help=
    "Path of directory to save inconsistent functions to (if they exist).")
  return parser


#Inputs: LP - the inconsistencies (and curated observations) in LP format
#Purpose: Stores inconsistency atoms in a separate file
# (to be used by repairs later on). Returns the path of the file.
def save_inconsistencies_to_file(LP, model_path, write_folder, mode: UpdateMode):
  logger = logging.getLogger("saveIncst")
  logger.setLevel(logging.INFO)

  filename = os.path.basename(model_path)
  suffix = {UpdateMode.STABLE: "stable", UpdateMode.SYNC: "sync", UpdateMode.ASYNC: "async"}[mode]
  filename = filename.replace(".lp", f"-{suffix}_inconsistency.lp")

  logger.debug("Filename: " + str(filename))

  if not os.path.exists(write_folder):
    os.makedirs(write_folder)
    logger.info("Created directory: " + str(write_folder))

  write_fullpath = os.path.join(write_folder, filename)

  logger.debug("Full path: " + str(write_fullpath))

  with open(write_fullpath, 'w') as f:
    f.write(LP)

  logger.info("Saved to: " + str(write_fullpath))
  return write_fullpath


def main(argv=None):
  logging.basicConfig()
  logging.getLogger("global").setLevel(logging.INFO)
  logger = logging.getLogger("parser")
  logger.setLevel(logging.INFO)

  args = build_parser().parse_args(argv)
  model_path = args.model_to_check
  obsv_path = args.observations_to_use
  write_folder = args.save_directory or os.path.join(os.path.dirname(model_path), "inconsistencies")
  logger.debug("Obtained model: " + model_path)
  logger.debug("Obtained observations: " + obsv_path)

  mode = UpdateMode.from_flags(args.stable_state, args.synchronous, args.asynchronous)
  logger.info(f"Mode used: {mode.description}")

  atoms = consistency_check(model_path, obsv_path, mode, path_mode=True)
  result = is_consistent(atoms, mode, print_inconsistencies=True)
  if result: save_inconsistencies_to_file(result, model_path, write_folder, mode)
  return 0


if __name__ == "__main__":
  sys.exit(main())
