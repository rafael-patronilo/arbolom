"""Corruption of Boolean models in the .bnet format, used to create "wrong"
versions of models for benchmarking.

The corruptions are (f)unction change, (e)dge sign flip, edge (r)emove and
edge (a)dd, each applied with a given probability.
"""
import logging
import os
import random
import re
import sys
from dataclasses import dataclass

from arbolom.common import get_all_compounds, get_all_literals, get_regulators_of, uniquify
from arbolom.conversion import convert_model_to_lp


#-----Auxiliary functions-----

#Inputs: Receives a list of implicants.
#Purpose:  Returns a list of its prime implicants.
def primes_only(implicants):
  logger = logging.getLogger("primes_only")
  logger.setLevel(logging.INFO)

  original = [i for i in implicants if(i != '')]
  orig_len = len(original)
  copy = [set(i.strip("()").split('&')) for i in implicants]
  logger.debug("Processed input" + str(copy))

  output = []
  changed_input = []

  for i in range(0, orig_len):
    #if i has already been marked as a non-prime or
    #is already in the output, go to the next implicant
    if(copy[i]=='' or original[i] in output): continue

    for j in range(i+1, orig_len):
      #if j has already been marked as a non-prime, go to the next implicant
      if(copy[j]==''): continue

      #if j absorbs i, then j is not a prime implicant
      if copy[i].issubset(copy[j]):
        changed_input.append(original[j])
        copy[j] = ''

      #if j is absorbed by i, then i is not a prime implicant
      elif copy[j].issubset(copy[i]):
        changed_input.append(original[i])
        copy[i] = ''
        break; #leave inner loop if i has absorbed another implicant

    #if i has not absorbed any other implicant, it is a prime so add it to output
    if(copy[i] != ''):
      output.append(original[i])

  return (changed_input, output)


#Input: A list of prime implicants, a list of literals that should be present
# in the prime implicants.
#Purpose: If there are literals missing from the list of prime implicants,
# add a new implicant with them.
def check_literals(implicants, literals):
  logger = logging.getLogger("check_literals")
  logger.setLevel(logging.INFO)
  output = implicants.copy()

  imp_literals = get_all_literals(implicants)
  missing_literals_implicant = None

  logger.debug("Received implicants: " + str(implicants))
  for l in literals:
    if l not in imp_literals:
      logger.debug("Found literal not in primes: " + l)

      if not missing_literals_implicant:
        missing_literals_implicant = l

      else:
        missing_literals_implicant += '&' + l

  if(missing_literals_implicant):
    output.append(missing_literals_implicant)

  return output


def get_unremovable_compounds_map(func_dict):
  logger = logging.getLogger("get_unremovables_map")
  logger.setLevel(logging.INFO)
  uc_map = {}

  all_compounds = get_all_compounds(func_dict)

  for compound in all_compounds:
    if compound in func_dict.keys():
      logger.debug(f"Skipped {compound} because it has a function")
      continue
    else:
      uc_map[compound] = 0

      for c in all_compounds:
        if c in func_dict.keys():
          if compound in get_regulators_of(c, func_dict[c]):
            uc_map[compound] += 1

      logger.debug(f"{compound} added to uc map with value {uc_map[compound]}")
  return uc_map


#Input: func_dict - a dictionary with all the regulatory functions
#Purpose: Writes the dictionary using the .bnet format.
def function_dict_to_bnet(func_dict):
  result = ""
  for function in func_dict.items():
    implicants = ''

    for i in function[1]:
      is_conjunction = '&' in i

      if i == function[1][-1]: #If it is the last prime implicant
        if is_conjunction:
          implicants += "(" + i + ")"
        else:
          implicants += i

      else:
        if is_conjunction:
          implicants += "(" + i + ") | "

        else:
          implicants += i + " | "

    result += function[0] + ", " + implicants + '\n'
  return result


@dataclass
class CorruptionSettings:
  """Which corruptions to apply (toggles) and with which probability (0.0 to 1.0)."""
  f_toggle: bool = True #Function Change
  e_toggle: bool = True #Edge Sign Flip
  r_toggle: bool = True #Edge Remove
  a_toggle: bool = True #Edge Add
  f_chance: float = 0.2
  e_chance: float = 0.2
  r_chance: float = 0.2
  a_chance: float = 0.2


class ModelCorruptor:
  """Applies random corruptions to models.

  The random number generator is seeded with `seed` (a random seed is drawn
  and logged when not given, so that results can be replicated).
  """

  def __init__(self, settings: CorruptionSettings | None = None, seed: int | None = None):
    self.settings = settings if settings is not None else CorruptionSettings()
    if seed is None:
      seed = random.randrange(sys.maxsize)
    self.seed = seed
    self.rng = random.Random(seed)
    logging.getLogger("global").info("Seed: "+ str(seed))

  #-----Model corruption operations-----
  #Inputs: Receives a list of implicants as input, and the chance to change
  # that list of implicants (0.0-1.0).
  #Purpose: Changes the regulatory function of a compound by creating a new one
  # using the same literals.
  def func_change(self, implicants, chance):
    logger = logging.getLogger("func_change")
    logger.setLevel(logging.INFO)
    rng = self.rng

    output = None
    changed = False
    literals = get_all_literals(implicants)

    logger.debug("Length of literals: "+ str(len(literals)))
    roll = rng.random()
    if(len(literals) > 1 and roll <= chance):
      changed = True

      num_implicants = rng.randint(1, 2*len(literals))
      if(num_implicants > len(literals)+1):
        logger.debug("Max implicants initial: " + str(num_implicants))
        num_implicants = round(num_implicants /2)+1

      logger.debug("Number of max implicants set: "+ str(num_implicants))

      output = [None]*num_implicants
      filled_clauses = {}

      for l in literals:
        logger.debug("Looking at literal "+l)
        has_been_used = False

        for i in range(0, num_implicants):
          roll = rng.random()

          if(roll <=0.5
             #Literal has not been used yet and we're on the last possible
             # implicant that it can be used in
             or (i==num_implicants-1 and not has_been_used)
             #We're on the last literal and there is a clause that does not have
             # any literals in it yet
             or (l==literals[-1] and i not in filled_clauses)):
            logger.debug("Adding it to clause "+ str(i+1))
            has_been_used = True
            filled_clauses[i] = True

            if(output[i] == None):
              output[i] = l

            else:
              output[i] += "&"+l

            logger.debug("Updated implicants: "+ str(output))

      output = check_literals(primes_only(output)[1], literals)

    return (changed, output)


  #Inputs: A dictionary containing all the regulatory functions and the chance
  #that a new regulator will be added to the regulatory function of a compound.
  #Purpose: Add more regulators to the regulatory function of a compound.
  #Detail: For each compound, make a loop with
  # each other compound that is not its regulator,
  # then roll the dice (input chance) and see if it is added as
  # regulator (50% chance of being activator / inhibitor) or not.
  # If it is added as a regulator, then roll the dice to see if it is added as
  # an OR clause or added to one of the existing AND clauses (50% chance).
  # If it is added to one of the existing AND clauses, for each clause there's
  # a 50% chance it will be included there.
  def edge_add(self, func_dict, chance):
    logger = logging.getLogger("edge_add")
    logger.setLevel(logging.INFO)
    rng = self.rng

    all_compounds = get_all_compounds(func_dict)
    changed = set()

    #original keys are copied to preserve key ordering
    final_dict = dict.fromkeys(func_dict.keys(),[])

    for c in all_compounds:
      c_implicants = func_dict.get(c,[])
      c_regulators = get_regulators_of(c,c_implicants)

      logger.debug("Regulators of "+c+" are: "+str(c_regulators))

      #Edges to be added need to come from compounds that are not regulators of c already
      potential_edges = [compound for compound in all_compounds if compound not in c_regulators]

      for e in potential_edges:
        roll = rng.random()
        if(roll <= chance/len(potential_edges)):
          logger.debug("Adding "+e+" as regulator of "+ c)
          changed.add(c)

          roll = rng.random()
          if(roll <=0.5): #Roll to see if e is activator or inhibitor
            logger.debug(e + " is going to be an inhibitor")
            e = '!'+e

          or_clause = True
          roll = rng.random()
          if(roll <=0.5):
            or_clause = False

          if(or_clause or not c_implicants):
            logger.debug("Adding "+e+ " as new prime implicant")
            c_implicants.append(e)

          else:
            logger.debug("Adding "+e+" to existing prime implicant(s)")
            has_been_added = False

            for implicant in range (0, len(c_implicants)):
              roll = rng.random()

              if(roll <=0.5 or (not has_been_added and implicant==len(c_implicants)-1)):
                logger.debug("Adding it to implicant "+c_implicants[implicant])
                c_implicants[implicant]+='&'+e
                has_been_added = True

          logger.debug("Updated implicants: " + str(c_implicants))

      final_dict[c] = c_implicants

    logger.debug("Final dict: " + str(final_dict))

    return (changed, final_dict)


  #Inputs: A dictionary containing all the regulatory functions, and the chance of removing an edge (regulator).
  #Purpose: For all literals in a regulatory function, roll the die and see
  # if the respective edge is removed or not.
  def edge_remove(self, func_dict, chance):
    logger = logging.getLogger("edge_remove")
    logger.setLevel(logging.INFO)
    rng = self.rng

    #original keys are copied to preserve key ordering
    final_dict = dict.fromkeys(func_dict.keys(),[])
    changed = set()

    unremovable_compounds = get_unremovable_compounds_map(func_dict)

    for c in func_dict.keys():
      c_implicants = func_dict.get(c,[])
      literals = get_all_literals(c_implicants)
      output = c_implicants.copy()

      logger.debug(f"Currently removing regulators of {c}")
      for l in literals:
        compound = l
        if l[0] == '!':
          compound = l[1:]

        if compound in unremovable_compounds:
          if unremovable_compounds[compound] <= 1:
            logger.debug(f"Skipped {compound} because map value was {unremovable_compounds[compound]}")
            final_dict[c] = output
            continue

        roll = rng.random()
        logger.debug("Rolled: " + str(roll))

        if(roll <= chance):
          logger.debug("Removing " + l)

          if compound in unremovable_compounds:
            unremovable_compounds[compound] -= 1
            logger.debug("Decreased unremovable map counter for {compound}, now at {unremovable_compounds[compound]} ")

          changed.add(c)

          logger.debug(f"Implicants before: {output}")

          for i in range(0, len(output)): #For each implicant
            #Start by seeing if literal to remove is one of the middle terms in
            # the conjunction
            replaced = output[i].replace("&" + l + "&", '&')
            if replaced == output[i]:
              #If it wasn't, then check if the literal to remove is the last term
              # of a conjunction
              replaced = re.sub(r'&{}\b'.format(l), '', output[i])
              if replaced == output[i]:
                #If it wasn't, then check to see if it is the first term of
                # a conjunction
                replaced = output[i].replace(l + "&", '')
                if replaced == output[i]:
                  #If it is neither, then the literal occurs alone and can
                  # be removed without leaving behind a trailing '&'
                  if replaced == output[i] == l:
                    replaced = ''
            output[i] = replaced

          output = primes_only(output)[1]
          logger.debug(f"Implicants after: {output}")
      final_dict[c] = output
    return (changed, final_dict)


  #Inputs: A list of implicants, and the chance of changing an edge's sign.
  #Purpose: A (repeated) literal in an implicant represents a signed edge.
  # For all literals, roll the die and see if the sign of the respective
  # edge changes or not.
  def edge_flip(self, implicants, chance):
    logger = logging.getLogger("edge_flip")
    logger.setLevel(logging.INFO)
    rng = self.rng

    output = implicants.copy()
    changed_input = []

    literals = get_all_literals(implicants)

    for l in literals:
      roll = rng.random()
      logger.debug("Rolled: " + str(roll))

      if(roll <= chance):
        logger.debug("Changing sign of " + l)
        changed_input.append(l)
        negated = l.count('!')
        logger.debug("Negated yes/no? " + str(negated))

        if(negated%2 != 0): #if the literal is negated
          output = [re.sub(r'\b{}\b'.format('!'+l), l , i) for i in output]

        else:
          output = [re.sub(r'\b{}\b'.format(l), '!'+l , i) for i in output]

        logger.debug("Changed a sign: " + str(output))

    return (changed_input, output)


  #Inputs: original_lines - the lines of a .bnet model
  #Purpose: Returns a corrupted function dictionary, and a string with the
  # operations that changed the model (e.g. 'fea')
  def corrupt(self, original_lines):
    global_logger = logging.getLogger("global")
    s = self.settings

    lines = original_lines.copy()
    func_dict = {}
    final_dict = {}

    f_effect = False
    e_effect = False
    r_effect = False
    a_effect = False

    for regfun in lines:
      full = [c.strip() for c in regfun.split(',')]
      global_logger.debug("Read function: "+str(full))

      implicants = [i.replace(" ", "").strip("()") for i in full[1].split('|')]
      global_logger.debug("Implicants of "+full[0]+": "+str(implicants))

      #each compound is a key; the value is the corresponding list of prime implicants
      func_dict[full[0]] = implicants

      if(s.f_toggle):
        change = self.func_change(implicants, s.f_chance)

        if(change[0]):
          global_logger.debug("("+full[0]+") " + "Changed reg func to " + str(change[1]))
          implicants = change[1]
          f_effect = True

        else:
          global_logger.debug("("+full[0]+") " + "No changes to reg func")

      if(s.e_toggle):
        flipped_implicants = self.edge_flip(implicants, s.e_chance)

        if(len(flipped_implicants[0]) > 0):
          global_logger.debug("("+full[0]+") " + "Flipped literals " +
            str(flipped_implicants[0]) +
            ". New implicants: "+str(flipped_implicants[1]))
          implicants = flipped_implicants[1]
          e_effect = True

        else:
          global_logger.debug("("+full[0]+") " + "No signs flipped")

      final_dict[full[0]] = implicants #Update final corrupted model

    if(s.r_toggle):
        removed_edges = self.edge_remove(final_dict, s.r_chance)

        if(removed_edges[0]):
          global_logger.debug("Removed edges from compound(s)" +
          str(removed_edges[0]) +
          ". New functions: "+str(removed_edges[1]))
          final_dict = removed_edges[1]
          r_effect = True

        else:
          global_logger.debug("No edges removed")

    if(s.a_toggle):
      added_edges = self.edge_add(final_dict, s.a_chance)

      if(added_edges[0]):
        global_logger.debug("Added new regulators to compound(s) " +
        str(added_edges[0]) +
        ". New functions: "+str(added_edges[1]))
        final_dict = added_edges[1]
        a_effect = True

      else:
        global_logger.debug("No edges added")

    #Operations that changed the model
    ops = ''
    if(f_effect):
      ops += 'f'
    if(e_effect):
      ops += 'e'
    if(r_effect):
      ops += 'r'
    if(a_effect):
      ops += 'a'

    return final_dict, ops


#Input: func_dict is a dictionary with all the regulatory functions, filename
# the name of the original model, write_folder the folder where the file will
# be stored, ops the operations that were applied.
#Purpose: Stores the contents of the dictionary into a file using the
# .bnet format (or .lp, if convert_to_lp is set). Returns the path of the file.
def save_corrupted_model(func_dict, filename, write_folder, ops='', convert_to_lp=False, log_path=True):
  logger = logging.getLogger("saveLP")
  logger.setLevel(logging.INFO)

  file_extension = ".lp" if convert_to_lp else ".bnet"

  current_path = uniquify(os.path.join(write_folder,
  filename.replace(".bnet", '') + "-corrupted" + "-" + ops + file_extension))

  if os.path.dirname(current_path) and not os.path.exists(os.path.dirname(current_path)):
    os.makedirs(os.path.dirname(current_path))
    logger.info("Created directory: " + str(os.path.dirname(current_path)))

  result = function_dict_to_bnet(func_dict)
  if convert_to_lp:
      result = convert_model_to_lp(result.split('\n'),logger)

  with open(current_path, 'w') as f:
    f.write(result)
  if log_path: logger.info("Saved to: " + str(current_path))
  return current_path
