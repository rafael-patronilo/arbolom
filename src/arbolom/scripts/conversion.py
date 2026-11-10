"""Command line interface to convert .bnet models to ARBoLoM's LP format.

Usage: arbolom-conversion -f (FILENAME) -s (SAVE_DIRECTORY)

Optional flags:
-s -> Path of directory to save converted file (default is the directory of the original file)

Variables:
FILENAME -> Path of file containing Boolean model in the BCF format to convert to ASP
            (glob patterns are accepted).
SAVE_DIRECTORY -> Path of directory to save converted model to.

Attention:
 Input files must be in the BCF format and follow the conventions of
 the .bnet files in the simple_models folder (results will be unpredictable otherwise)
"""
import argparse
import glob
import logging
import os
import sys

from arbolom.conversion import convert_model_to_lp


def build_parser():
  parser = argparse.ArgumentParser(description=
    "Convert a Boolean logical model written in the BCF format to a logic program.")
  parser.add_argument("-f", "--file_to_convert", required=True, help=
    "Path to file to be converted.")
  parser.add_argument("-s", "--save_directory", help=
    "Path of directory to save converted model to.")
  return parser


#Inputs: lp - the converted model, filename - name of the original .bnet file
#Purpose: Saves a converted model to an LP file. Returns the path of the file.
def save_lp_to_file(lp, filename, write_folder):
  logger = logging.getLogger("saveLP")
  logger.setLevel(logging.INFO)

  current_path = os.path.join(write_folder, filename.replace(".bnet", '.lp'))
  logger.debug("Filename: " + str(filename))
  logger.debug("Path: " + str(write_folder))

  if os.path.dirname(current_path) and not os.path.exists(os.path.dirname(current_path)):
    os.makedirs(os.path.dirname(current_path))
    logger.info("Created directory: " + str(current_path))

  with open(current_path, 'w') as f:
    f.write(lp)
  logger.info("Saved to: " + str(current_path))
  return current_path


def main(argv=None):
  logging.basicConfig()
  global_logger = logging.getLogger("global")
  global_logger.setLevel(logging.INFO)

  args = build_parser().parse_args(argv)
  filepath = args.file_to_convert
  read_folder = os.path.dirname(filepath)
  write_folder = args.save_directory or read_folder
  logging.getLogger("parser").info("Obtained file: " + filepath)

  for fname in glob.glob(filepath):
    global_logger.debug("Reading file: " + fname)
    with open(fname, 'r') as f:
      lp = convert_model_to_lp(f.readlines(), global_logger)
    save_lp_to_file(lp, os.path.basename(fname), write_folder)
  return 0


if __name__ == "__main__":
  sys.exit(main())
