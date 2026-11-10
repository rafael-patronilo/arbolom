"""Generation of time-series observations from a model in LP format."""
import logging
import os
import re

import clingo

from arbolom.modes import UpdateMode
from arbolom.resources import OBSERVATION_GENERATION_ENCODINGS


#Inputs:
# model_path - path of the model (in LP format) to generate observations for
# mode - UpdateMode.SYNC or UpdateMode.ASYNC
# experiments_number - the number of experiments (sets of observations) to generate
# time_steps - the number of time steps to consider in each experiment
#Purpose: Returns the atoms of the generated observations
def generate_observations(model_path, mode: UpdateMode = UpdateMode.SYNC, experiments_number=2, time_steps=5):
  if mode not in OBSERVATION_GENERATION_ENCODINGS:
    raise ValueError(f"Observations can only be generated for the modes {[m.value for m in OBSERVATION_GENERATION_ENCODINGS]}")
  ctl = clingo.Control(arguments=["0", f"-c e={experiments_number}", f"-c t={time_steps}"])

  ctl.load(model_path)
  ctl.load(OBSERVATION_GENERATION_ENCODINGS[mode])

  ctl.ground([("base", [])])
  atoms = []
  with ctl.solve(yield_=True) as handle:
    for model in handle:
      atoms = (str(model).split(" "))
  return atoms


#Inputs: atoms - generated observation atoms, path - file to save them to
#Purpose: Saves generated observations to file, grouped by experiment.
def save_observations_to_file(atoms, path):
  logger = logging.getLogger("saveToFile")
  logger.setLevel(logging.INFO)

  experiments_observations = {}

  for atom in atoms:
    if "experiment" in atom:
      exp_num = ''.join(d for d in atom if d.isdigit())
      experiments_observations[exp_num] = [atom]

    elif "observation" in atom:
      terms = re.search(r'\((.*)\)', atom).group(1)
      terms = terms.split(',')
      experiments_observations[terms[0]] += [atom]

  if os.path.dirname(path) and not os.path.exists(os.path.dirname(path)):
    os.makedirs(os.path.dirname(path))
    logger.info("Created directory: " + os.path.dirname(path))

  with open(path, 'w') as f:
    for item in experiments_observations.items():
      sorted_atoms = sorted(item[1])
      for atom in sorted_atoms:
        f.write(atom+".\n")
      f.write("\n")
  logger.info("Saved to: " + path)
