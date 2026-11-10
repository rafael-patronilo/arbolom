"""Consistency checking of a model against observations."""
import clingo

from arbolom.modes import UpdateMode
from arbolom.resources import CONSISTENCY_ENCODINGS


#Inputs:
# model - the model, as an LP program (or a path, if path_mode is set)
# obsv - the observations, as a path (or an LP program, if obsv_path_mode is unset)
# mode - the UpdateMode to check consistency with
#Purpose: Returns the atoms of the optimal answer set of the consistency encoding
def consistency_check(model, obsv, mode: UpdateMode, path_mode=False, obsv_path_mode=True):
  ctl = clingo.Control(arguments=["0"])

  if path_mode:
    ctl.load(model)
  else:
    ctl.add("base",[], program=model)

  if obsv_path_mode:
    ctl.load(obsv)
  else:
    ctl.add("base", [], program=obsv)

  ctl.load(CONSISTENCY_ENCODINGS[mode])

  ctl.ground([("base", [])])
  atoms = []
  with ctl.solve(yield_=True) as handle:
    for model in handle:
      atoms = (str(model).split(" "))
  return atoms

class NoAnswerSetError(Exception):
  """The consistency checking program has no answer set, so consistency cannot be decided."""

#Inputs: atoms is a list of atoms obtained from solving with clingo.
#Purpose: Returns None if the model is consistent, otherwise the inconsistencies
# followed by the curated observations (in LP format). Raises NoAnswerSetError if
# consistency checking had no answer set.
def is_consistent(atoms, mode: UpdateMode, print_inconsistencies=False, print_consistent=True):
  if not atoms:
    if mode is UpdateMode.ASYNC:
      reason = ("In asynchronous mode at most one compound may change its state per time step, "
        "but the observations contain a time step in which several compounds change. "
        "Check that the observations are asynchronous (e.g. that synchronous observations "
        "were not used with the asynchronous mode).")
    else:
      reason = ("This is not expected for this update mode; check the model and observation files.")
    raise NoAnswerSetError("Consistency checking found no answer set, so the consistency "
      "of the model cannot be decided. " + reason)
  else:
    consistent = True
    inconsistent_LP = ""
    observations_LP = ""

    for atom in atoms:
      if "inconsistent" in atom:
        consistent = False
        inconsistent_LP += atom + ".\n"
      else:
        observations_LP += atom + ".\n"

    if not consistent:
      if print_inconsistencies:
        if mode is UpdateMode.STABLE:
          print("Model is not consistent ❌ Inconsistent (experiment, compound, value): ")
        elif mode is UpdateMode.SYNC:
          print("Model is not consistent ❌ Inconsistent (experiment, timestep, compound, value): ")
        else:
          print("Model is not consistent ❌ Inconsistent (experiment, timestep, compound, value/other compound updated at the same time): ")
        print(inconsistent_LP)

      return inconsistent_LP + "\n" + observations_LP

    else:
      if print_consistent: print("The model is consistent with the observations ✔️")
      return None
