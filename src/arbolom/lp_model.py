"""Manipulation of models in ARBoLoM's LP format.

A model dict maps each compound to a dict with its final "state", its
"regulators" (regulates/3 atoms), its "function" (function/2 atom) and its
"terms" (term/3 atoms).
"""
import re
from collections import OrderedDict, defaultdict

from arbolom.common import parse_atom


def get_model_compounds(model):
  return re.findall(r'compound\((.+?)\).',model)

def get_compound_regulator_number(model, compound):
  return len(re.findall(fr'regulates\((.+?), ?{compound}, ?(0|1)\).',model))

def get_compound_term_number(model, compound):
  return re.search(fr'function\({compound},(.+?)\).',model).group(1)


def model_to_dict(model):
  if isinstance(model, str):
    model = model.split("\n")
  original_functions = OrderedDict()
  def function_container():
    return {"state": "consistent", "regulators" : [], "function" : "", "terms" : []}
  for atom in model:
    predicate, terms = parse_atom(atom)
    if predicate == "compound":
      original_functions.setdefault(terms[0], function_container())
    elif predicate == "regulates":
      original_functions.setdefault(terms[1], function_container())["regulators"].append(atom)
    elif predicate == "function":
      original_functions.setdefault(terms[0], function_container())["function"] = atom
    elif predicate == "term":
      original_functions.setdefault(terms[0], function_container())["terms"].append(atom)
    elif predicate == "fixed":
      pass # constraint on the repairs (fixed regulators), not part of the functions
    else: assert predicate is None, f"Unknown predicate {predicate}: {atom}"
  return original_functions

def format_function_dict(compound, function_dict) -> str:
  sb = []
  compound_state = function_dict.get("state")
  if compound_state:
    sb.append(f"%Compound {compound}'s final state is {compound_state}")
  sb.append(f"%Regulators of {compound}")
  for regulator_atom in function_dict["regulators"]:
    sb.append(regulator_atom)
  sb.append("")
  sb.append(f"%Regulatory function of {compound}")
  sb.append(function_dict["function"])
  for term_atom in function_dict["terms"]:
    sb.append(term_atom)
  sb.append("")
  return '\n'.join(sb)

def format_model_dict(model_dict):
  compound_sb = ["%Compounds"]
  main_sb = []

  for compound, function_dict in model_dict.items():
    compound_sb.append(f"compound({compound}). % state = {function_dict.get("state")}")
    main_sb.append(format_function_dict(compound, function_dict))
  return '\n'.join(compound_sb) + '\n' + '\n'.join(main_sb)


def repair_model_dict(model_dict, compound, repairs, compound_state) -> dict:
  function_dict = {"state": compound_state, "regulators" : [], "function" : "", "terms" : []}

  unordered_nodes = defaultdict(list)

  for atom in repairs:
    predicate, terms = parse_atom(atom)
    if predicate == "regulator_activator":
      function_dict["regulators"].append(f"regulates({terms[0]}, {compound}, 0).")
    elif predicate == "regulator_inhibitor":
      function_dict["regulators"].append(f"regulates({terms[0]}, {compound}, 1).")
    elif predicate == "node_regulator":
      node_id = int(terms[0])
      unordered_nodes[node_id].append(terms[1])
  function_dict["function"] = f"function({compound}, {len(unordered_nodes)})."
  for i, regs in enumerate(sorted(unordered_nodes.items())):
    for reg in regs[1]:
      function_dict["terms"].append(f"term({compound}, {i+1}, {reg}).")
  model_dict[compound] = function_dict
  return function_dict
