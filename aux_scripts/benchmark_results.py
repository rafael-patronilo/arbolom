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

OBSV_TYPES = ["obs.lp","1-20", "1-3", "5-20", "5-3"]

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

  for name, model_df in df.groupby(['Model Name', 'Obsv. Type']):
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
  time_cols = [col for col in df.columns if 'Time' in col and col != "C. Repair Time"]
  by_model = df.groupby(['Model Name', 'Obsv. Type']).first()
  print("Global Times")
  printStatistics(by_model[time_cols])
  printStatistics(df['C. Repair Time'])
  print()
  for k, v in df.groupby(['Model State']):
    by_model = v.groupby(['Model Name', 'Obsv. Type']).first()
    print(f"Times for state {k}")
    printStatistics(by_model[time_cols])
    print("C. Repair Time")
    printStatistics(v['C. Repair Time'])
    print()

def printRepairs(df : pd.DataFrame):
  repairs = df[df['Compound State'] == 'repaired'][REPAIR_COLS]
  print("Repair statistics (repaired compounds only)")
  printStatistics(repairs)

def loadFiles() -> pd.DataFrame:
  dfs = []
  csvs = csv_folder.glob("*.csv")
  if not csvs:
    print(f"No CSV files found in {csv_folder}")
    return
  
  for f in csvs:
    o_type = None
    for o_type_cand in OBSV_TYPES:
      if o_type_cand in f.name:
        o_type = o_type_cand
        break
    if o_type is None:
      print(f"Skipping {f}: no observation type found")
      continue
    csv = pd.read_csv(f, sep=r',\s*', engine='python')
    csv['Obsv. Type'] = o_type
    if not isinstance(csv, pd.DataFrame):
      print(f"Error reading {f}: {csv}")
      continue
    dfs.append(csv)
  print(f"Loaded {len(dfs)} CSV files")
  df = pd.concat(dfs, ignore_index=True)
  return df

def main():
  parseArgs()
  df = loadFiles()
  printModelStateCounts(df)
  print('\n\n')
  printTimes(df)
  print('\n')
  printRepairs(df)

if __name__ == '__main__':
  main()
