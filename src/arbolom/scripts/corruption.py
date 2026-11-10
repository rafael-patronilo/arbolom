"""Command line interface to corrupt .bnet models.

Usage: arbolom-corruption -f (FILENAME) -op (OPERATIONS) -(O)p (PROBABILITY) -s (SAVE_DIRECTORY) -lp -bulk (INSTANCE_NO)

Optional flags:
-op -> Specify which corruptions to apply (default applies all corruptions).
-(O)p -> Probability (0.0 to 1.0) of corruption O taking place (default is 0.2).
-s -> Path of directory to save corrupted file (default is the directory of the original file).
-lp -> Converts the output to .lp directly.
-bulk -> Allows multiple corrupted instances to be created at once.
-seed -> Seed of the random number generator, to replicate results.

Variables:
FILENAME -> Path of the .bnet file to corrupt.
OPERATIONS -> A string with one (or more) specific characters, denoting which
 corruptions to apply. These characters are 'f','e','r' and 'a'. 'fera'
 would be the full string, representing that (f)unction change, (e)dge flip,
 edge (r)emove and edge (a)dd will all be applied.
O -> A character that can take one of four possible values:
 'f','e','r' and 'a' (followed by 'p'). -fp would change the probability of
 function change to occur, -ep of edge removal, etc.
PROBABILITY -> A float from 0.0 to 1.0 denoting the probability of a given
 corruption to occur. For example, -ap 0.5 would change the add edge
 operation's probability to 50%.
SAVE_DIRECTORY -> Path of directory to save corrupted model to.

Attention:
 Input files must be in the BCF format and follow the conventions of
 the .bnet files in the simple_models folder
 (results will be unpredictable otherwise)
"""
import argparse
import glob
import logging
import os
import sys

from arbolom.corruption import CorruptionSettings, ModelCorruptor, save_corrupted_model


def build_parser():
  parser = argparse.ArgumentParser(description=
    "Corrupt a Boolean logical model written in the BCF format.")
  parser.add_argument("-f",
    "--file_to_corrupt", required=True, help="Path to file to be corrupted.")
  parser.add_argument("-op",
    "--operations", help="Corruptions to apply.")
  parser.add_argument("-fp",
    "--f_probability", help="Probability of applying function change.",
    type=float)
  parser.add_argument("-ep",
    "--e_probability", help="Probability of applying edge flip.",
    type=float)
  parser.add_argument("-rp",
    "--r_probability", help="Probability of applying edge remove.",
    type=float)
  parser.add_argument("-ap",
    "--a_probability", help="Probability of applying edge add.",
    type=float)
  parser.add_argument("-s",
    "--save_directory", help="Path of directory to save converted model to.")
  parser.add_argument("-bulk",
    "--bulk", help="Make several corrupted instances at once (must specify a number).", type=int)
  parser.add_argument("-lp",
    "--logic_program", action='store_true',
    help="Converts the corrupted model directly to the logic program format.")
  parser.add_argument("-seed", "--seed", type=int, default=None,
    help="Seed of the random number generator (random by default; the seed used is logged).")
  return parser


#Purpose: Converts the operations and probabilities arguments into CorruptionSettings
def settings_from_args(args) -> CorruptionSettings:
  logger = logging.getLogger("parser")
  logger.setLevel(logging.INFO)
  settings = CorruptionSettings()
  operations = args.operations
  if operations:
    for op in "fera":
      enabled = op in operations
      setattr(settings, f"{op}_toggle", enabled)
      probability = getattr(args, f"{op}_probability")
      if enabled and probability:
        setattr(settings, f"{op}_chance", probability)
    logger.debug("Obtained operations: " + operations)

  for op in "fera":
    logger.debug(f"Corruption {op.upper()}: {getattr(settings, f'{op}_toggle')} with chance {getattr(settings, f'{op}_chance')}")
  return settings


def main(argv=None):
  logging.basicConfig()
  global_logger = logging.getLogger("global")
  global_logger.setLevel(logging.INFO)
  logger = logging.getLogger("parser")

  args = build_parser().parse_args(argv)
  filepath = args.file_to_corrupt
  if os.path.splitext(filepath)[1] != ".bnet":
    logger.error("Unrecognized model format. Only models written in "
    +".bnet format are accepted.")
    return 1
  write_folder = args.save_directory or os.path.dirname(filepath)
  instance_number = args.bulk or 1

  corruptor = ModelCorruptor(settings_from_args(args), seed=args.seed)

  for fname in glob.glob(filepath):
    with open(fname, 'r') as f:
      global_logger.info("Reading file: " + fname)
      original_lines = [line.strip() for line in f.readlines()]

    for _ in range(0, instance_number):
      final_dict, ops = corruptor.corrupt(original_lines)
      save_corrupted_model(final_dict, os.path.basename(fname), write_folder, ops=ops,
                           convert_to_lp=args.logic_program, log_path=instance_number < 10)
  return 0


if __name__ == "__main__":
  sys.exit(main())
