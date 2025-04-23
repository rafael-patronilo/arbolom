import argparse
from pathlib import Path
import pandas as pd
from collections import defaultdict

REPAIR_COLS = [
  'C. Node Variation', 
  'C. Missing Regulators', 
  'C. Extra Regulators', 
  'C. Changed Signs',
  'C. Missing Node Regulators',
  'C. Extra Node Regulators'
]

csv_folder : Path

#---Argument parser---
def parseArgs():
  global parser, args

  parser = argparse.ArgumentParser(description="Summarize the .csv files originated from benchmark.py")
  requiredNamed = parser.add_argument_group("required arguments")
  requiredNamed.add_argument("-f", "--csv_folder", help="Path of folder with the .csv files", required=True)
  args = parser.parse_args()

  global csv_folder

  csv_folder = Path(args.csv_folder)

def printModelStateCounts(df : pd.DataFrame):
  model_state_counter = defaultdict(lambda:0)

  for name, model_df in df.groupby('Model Name'):
    model_state_counter[model_df['Model State'].iloc[0]] += 1

  print("Number of models per state:")
  for state, count in model_state_counter.items():
    print(f"\t{state}\t:{count}")

def printStatistics(df : pd.DataFrame):
  print("Mean")
  print(df.mean())
  print("Std")
  print(df.std())
  print("Max")
  print(df.max())
  print("Min")
  print(df.min())

def printTimes(df : pd.DataFrame):
  time_cols = [col for col in df.columns if 'Time' in col]
  print("Global Times")
  printStatistics(df[time_cols])
  print()
  for k, v in df.groupby('Model State'):
    print(f"Times for state {k}")
    printStatistics(v[time_cols])
    print()

def printRepairs(df : pd.DataFrame):
  repairs = df[df['Compound State'] == 'repaired'][REPAIR_COLS]
  print("Repair statistics (repaired compounds only)")
  printStatistics(repairs)

def main():
  parseArgs()
  def read_csv(file):
    return pd.read_csv(file, sep=r',\s*', engine='python')
  df = pd.concat(map(read_csv, csv_folder.glob('*.csv')), ignore_index=True)
  printModelStateCounts(df)
  print('\n\n')
  printTimes(df)
  print('\n')
  printRepairs(df)

if __name__ == '__main__':
  main()
