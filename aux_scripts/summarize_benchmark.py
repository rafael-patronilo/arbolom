import argparse
from pathlib import Path
import pandas as pd
from collections import defaultdict
from repair_criteria import CRITERIA
import repair_constants as COLS

REPAIR_COLS = {
  'C. Node Variation', 
  'C. Missing Regulators', 
  'C. Extra Regulators', 
  'C. Changed Signs',
  'C. Missing Node Regulators',
  'C. Extra Node Regulators'
} | CRITERIA.keys()

OBSV_TYPES = ["obs.lp","1-20", "1-3", "5-20", "5-3"]
OBSV_COL = "Obsv. Type"

csv_folder : Path

output_file : Path | None = None

#---Argument parser---
def parseArgs():
  global parser, args

  parser = argparse.ArgumentParser(description="Summarize the .csv files originated from benchmark.py")
  requiredNamed = parser.add_argument_group("required arguments")
  requiredNamed.add_argument("-f", "--csv_folder", help="Path of folder with the .csv files", required=True)
  parser.add_argument("-o", "--output_file", action='append', help="Path of output file to save the summary table." \
  " Supports different extensions and can be specified multiple times. (default: None)", default=None)
  args = parser.parse_args()

  global csv_folder

  csv_folder = Path(args.csv_folder)

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
    csv[OBSV_COL] = o_type
    if not isinstance(csv, pd.DataFrame):
      print(f"Error reading {f}: {csv}")
      continue
    dfs.append(csv)
  print(f"Loaded {len(dfs)} CSV files")
  df = pd.concat(dfs, ignore_index=True)
  return df


def initSummaryTable(df : pd.DataFrame) -> pd.DataFrame:
  model_states = df[COLS.BCHMRK_MODEL_STATE].unique()
  time_fields = [col for col in df.columns if 'Time' in col]
  repair_fields = [col for col in df.columns if col in REPAIR_COLS]
  
  tuples = []
  for field in time_fields:
    tuples.append(('Global Times', field))
  for state in model_states:
    for field in time_fields:
      tuples.append((state, field))
  for field in repair_fields:
    tuples.append(('Repairs', field))

  summary = pd.DataFrame(
    float('nan'),
    index=pd.MultiIndex.from_tuples(tuples, names=['Group', 'Field']),
    columns=['Count', 'Mean', 'Std', 'Max', 'Min', 'Total']
  )
  for state in model_states:
    summary.loc[state, 'Count'] = 0
  return summary

def groupby_model(df : pd.DataFrame) -> pd.DataFrame:
  return df.groupby([COLS.BCHMRK_MODEL_NAME, OBSV_COL])

def calcModelStateCounts(df : pd.DataFrame, summary: pd.DataFrame):
  model_state_counter = defaultdict(lambda:0)
  for name, model_df in groupby_model(df):
    state = model_df[COLS.BCHMRK_MODEL_STATE].iloc[0]
    summary.loc[state, 'Count'] = summary.loc[state, 'Count'].iloc[0] + 1

  print("Number of models per state:")
  for state, count in model_state_counter.items():
    print(f"\t{state}\t:{count}")

def writeStatistics(df : pd.DataFrame, first_index : str, summary: pd.DataFrame):
  statistics = [
    ('Mean', df.mean()),
    ('Std', df.std()),
    ('Max', df.max()),
    ('Min', df.min()),
    ('Total', df.sum())
  ]
  for stat_name, stat_values in statistics:
    for field, val in stat_values.items():
      summary.loc[(first_index, field), stat_name] = val

def summarizeTimes(df : pd.DataFrame, summary: pd.DataFrame):
  time_cols = [col for col in df.columns if 'Time' in col and col != COLS.BCHMARK_COMPOUND_REPAIR_TIME]
  by_model = groupby_model(df).first()
  writeStatistics(by_model[time_cols], 'Global Times', summary)
  writeStatistics(df[[COLS.BCHMARK_COMPOUND_REPAIR_TIME]], 'Global Times', summary)
  for k, v in df.groupby([COLS.BCHMRK_MODEL_STATE]):
    by_model = groupby_model(v).first()
    writeStatistics(by_model[time_cols], k[0], summary)
    writeStatistics(v[[COLS.BCHMARK_COMPOUND_REPAIR_TIME]], k[0], summary)

def summarizeRepairs(df : pd.DataFrame, summary: pd.DataFrame):
  repair_cols = [col for col in df.columns if col in REPAIR_COLS]
  repairs = df[df[COLS.BCHMRK_COMPOUND_STATE] == 'repaired'][repair_cols]
  writeStatistics(repairs, 'Repairs', summary)

def writeTo(summary: pd.DataFrame, output_file: Path):
  if output_file.exists():
    print(f"Output file {output_file} already exists, delete first.")
    return
  match output_file.suffix.lower():
    case '.csv':
      summary.to_csv(output_file)
    case '.txt':
      output_file.write_text(summary.to_string(
        float_format=lambda x: str(int(x)) if x.is_integer() else str(x),
        na_rep='-'
      ))
    case '.xlsx':
      summary.to_excel(output_file)
    case '.json':
      summary.to_json(output_file)
    case '.tex':
      summary.to_latex(output_file)
    case '.html':
      summary.to_html(output_file)
    case '.pkl':
      summary.to_pickle(output_file)
    case '.xml':
      summary.to_xml(output_file)
    case other:
      print(f"Unsupported output file format: {other}."
            " Supported formats: .csv, .txt, .xlsx, .json, .tex, .html, .pkl, .xml")

def summarize(df: pd.DataFrame):
  summary = initSummaryTable(df)
  calcModelStateCounts(df, summary)
  summarizeTimes(df, summary)
  summarizeRepairs(df, summary)
  return summary

def main():
  parseArgs()
  df = loadFiles()
  summary = summarize(df)
  print("Summary table:")
  print(summary.to_string(
    float_format=lambda x: str(int(x)) if x.is_integer() else f'{x:.4f}',
    na_rep='-'
  ))
  
  for out_file in args.output_file:
    writeTo(summary, Path(out_file))

if __name__ == '__main__':
  main()
