"""Conversion of Boolean models from the .bnet format to ARBoLoM's LP format."""
import logging
import os

from arbolom.common import get_all_compounds, get_all_literals, get_regulators_of


def get_function_dict(lines, logger):
  func_dict = {}
  all_regulators = set()
  for regfun in lines:
    if regfun == '': #ignore blank lines
      continue
    else:
      full = [c.strip() for c in regfun.split(',')]
      if logger : logger.debug("Read function: "+str(full))

      implicants = [i.replace(" ", "").strip("()") for i in full[1].split('|')]

      #If we are dealing with an input compound, then it will be regulated
      #by itself
      if not implicants[0]:
        implicants = [full[0]]
      else:
        regulators = get_regulators_of(full[0], implicants)
        for r in regulators:
          all_regulators.add(r)

      if logger : logger.debug("Implicants of "+full[0]+": "+str(implicants))

      #The LP format stores one sign per regulator, so a regulator appearing both
      #negated and non-negated in a function cannot be represented faithfully
      literals = get_all_literals(implicants)
      dual_regulators = sorted({l[1:] for l in literals if l.startswith('!') and l[1:] in literals})
      if dual_regulators:
        (logger or logging.getLogger("conversion")).warning(
          f"Function of {full[0]} uses {', '.join(dual_regulators)} both as activator and inhibitor. "
          "The LP format supports a single sign per regulator, so terms containing them "
          "will always evaluate to false and the converted function will not match the original.")

      #each compound is a key; the value is the corresponding
      # list of prime implicants
      func_dict[full[0]] = implicants

  #Add missing input compounds (compounds that appear only as regulators of
  #other compounds )
  for r in all_regulators:
    if r not in func_dict.keys():
      func_dict[r] = [r]

  return func_dict

#Inputs: string is the LP being built, compounds is a list of strings
# representing the compounds.
#Purpose: Adds predicates representing compounds to LP.
def add_compounds_to_result(string, compounds):
  string += "%Compounds\n"
  for c in compounds:
    string += "compound(" + c + ").\n"
  string +="\n"
  return string

#Inputs: string is the LP being built, item is a tuple where the first element
# is the compound of the regulatory function,
# and the second element is a list of its implicants.
#Purpose: Adds the predicates representing the regulators of each compound to LP.
def add_regulators_to_result(string, item):
  if item[1][0]: #if there exist any regulators
    string += "%Regulators of " + item[0] + "\n"
    all_literals = get_all_literals(item[1])

    for l in all_literals:
      if(l[0]=='!'):
        string += "regulates(" + l[1:] + ", " + item[0] + ", " + "1).\n"

      else:
        string += "regulates(" + l + ", " + item[0] + ", " + "0).\n"
    string += "\n"
  return string

#Inputs: string is the LP being built, item is a tuple where the first element
# is the compound of the regulatory function,
# and the second element is a list of its implicants.
#Purpose: Adds regulators of each compound to LP.
def add_function_to_result(string, item):
  if item[1][0]: #if there exist any regulators
    string += "%Regulatory function of " + item[0] + "\n"
    num_terms = len(item[1])
    string += "function(" + item[0] + ", " + str(num_terms) + ").\n"

    for idx, i in enumerate(item[1]):
      regulators = get_regulators_of(item[0],[i])

      for r in regulators:
        string += "term(" + item[0] + ", " + str(idx+1) + ", " + r + ").\n"

    string +="\n"
  return string

#Inputs: func_dict, maps each compound to the list of implicants of its function
#Purpose: Writes the function dictionary in .lp format
def function_dict_to_lp(func_dict, logger=None):
  result = ""

  all_compounds = get_all_compounds(func_dict, True)
  if logger: logger.debug("All compounds: " + str(all_compounds))

  if len(all_compounds) == len(list(func_dict.keys())):
    #If all compounds are present in the map keys,
    # then the original order is preserved for convenience
    result = add_compounds_to_result(result, list(func_dict.keys()))
  else:
    result = add_compounds_to_result(result, all_compounds)

  for function in func_dict.items():
    result = add_regulators_to_result(result,function)
    result = add_function_to_result(result,function)

  return result

#Inputs: model, an array containing the model in which each element is a string
#containg a line of the .bnet model representation
#Purpose: Converts the .bnet model into a string in .lp format
def convert_model_to_lp(model, logger):
  lines = [line.strip() for line in model]
  func_dict = get_function_dict(lines, logger)
  return function_dict_to_lp(func_dict, logger)


#Input: model_path - path of a model in .bnet or .lp format
#Purpose: Reads a model, converting it to .lp format if needed.
# Returns None if the format is not recognized.
def read_model(model_path, logger=None):
  logger = logger or logging.getLogger("readModels")
  model_extension = os.path.splitext(model_path)[1]

  if model_extension != ".bnet" and model_extension != ".lp":
    logger.error("Unrecognized model format. Only models written in "
    +".bnet or .lp format are accepted.")
    return None

  with open(model_path, 'r') as model_file:
    output_model = model_file.readlines()

  if model_extension == ".bnet":
    output_model = convert_model_to_lp(output_model,logger)
  else: output_model = "".join(output_model)

  logger.debug("obtained model: \n" + output_model)
  return output_model
