"""Merge the .csv files produced by arbolom-benchmark (only works with the file
structure of the benchmark files in the project page).

Usage: arbolom-merge-csv -f (FOLDERNAME)
"""
import argparse
import glob
import os
import sys

import pandas as pd
from natsort import natsorted

OBSV_TYPES = ["obs.lp","1-20", "1-3", "5-20", "5-3"]


def build_parser():
  parser = argparse.ArgumentParser(description="Merge the .csv files originated from benchmark.py (only works if used with the file structure of the benchmark files in the project page)")
  requiredNamed = parser.add_argument_group("required arguments")
  requiredNamed.add_argument("-f", "--csv_folder", help="Path of folder with the .csv files", required=True)
  return parser


#Purpose: Merges the CSV files of each observation type in csv_folder into the
# sibling "Merged" folder
def merge_csv_files(csv_folder):
  csv_name = os.path.basename(os.path.dirname(os.path.dirname(csv_folder)))
  for o_type in OBSV_TYPES:
    files = [f for f in glob.glob(os.path.join(csv_folder, "*.csv")) if o_type in f]

    files = natsorted(files)

    if files:
      df = pd.concat(map(pd.read_csv, files), ignore_index=True)
      df.to_csv(os.path.join(os.path.dirname(csv_folder),"Merged", csv_name + "-" + o_type + "-" + os.path.basename(os.path.dirname(csv_folder)) + "-merged.csv"), index=False)


def main(argv=None):
  args = build_parser().parse_args(argv)
  merge_csv_files(args.csv_folder)
  print("Done! Saved in 'Merged' folder.")
  return 0


if __name__ == "__main__":
  sys.exit(main())
