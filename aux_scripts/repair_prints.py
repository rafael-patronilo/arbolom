from pprint import pformat

#Purpose: Prints the initial node generation phase message
def printFuncRepairStart(current_function):
  print(f"\033[1;32m ----{current_function} REPAIR START----\033[0;37;40m")

#Purpose: Prints the initial node generation phase message
def printFuncRepairEnd(current_function):
  print(f"\033[1;32m ----{current_function} REPAIR END----\033[0;37;40m")

#Purpose: Prints the initial iftv generation phase message
def printIFTVStart():
  print("\033[1;32m ----IFTV GENERATION START----\033[0;37;40m")

#Purpose: Prints the final iftv generation phase message
def printIFTVEnd():
  print("\033[1;32m ----IFTV GENERATION END----\033[0;37;40m")

#Inputs: The inconsistent function, and the resulting answer set obtained from clingo
#Purpose: Prints the repairs in LP format
def logRepairedLP(inconsistent_func, repairs, criteria_costs, to_stdout=True, logger = None):
  activators = ""
  inhibitors = ""

  node_max_ID = 1
  node_ID_map = {} 
  nodes = {}
  
  if repairs:
    for atom in repairs:
      if len(atom) == 0:
        continue
      try: arguments = atom.split(')')[0].split('(')[1].split(',')
      except Exception as e:
        if logger: logger.error(f"Error parsing atom {atom}:", exc_info=e)
        continue

      if "regulator_activator" in atom:
        activators += f"regulates({arguments[0]}, {inconsistent_func}, 0).\n"
      elif "regulator_inhibitor" in atom:
        inhibitors += f"regulates({arguments[0]}, {inconsistent_func}, 1).\n"
      elif "node_regulator" in atom:
        unsorted_node_ID = arguments[0]
        regulator = arguments[1]

        #Makes sure nodes are outputted using ordered IDs
        if unsorted_node_ID not in node_ID_map.keys():
          node_ID_map[unsorted_node_ID] = node_max_ID
          node_max_ID += 1

        node_ID = node_ID_map[unsorted_node_ID]

        if node_ID in nodes:
          nodes[node_ID].append(regulator)
        else:
          nodes[node_ID] = [regulator]

    repairs = f"%Regulators of {inconsistent_func}\n" + activators + inhibitors +"\n"
    repairs += f"%Regulatory function of {inconsistent_func}\nfunction({inconsistent_func}, {len(nodes.keys())}).\n"

    for node_ID in nodes.keys():
      regulators = nodes[node_ID]

      for reg in regulators:
        repairs += f"term({inconsistent_func}, {node_ID}, {reg}).\n"
    
    if to_stdout: 
      print("\033[1;32mRepairs: \033[0;37;40m")
      print(repairs)

    logChanges(criteria_costs, to_stdout=to_stdout, logger=logger)

    if logger: logger.info(f"Repairs for function {inconsistent_func}:\n{repairs}")

def logChanges(criteria_costs, to_stdout=True, logger = None):
  if to_stdout:
    print("\033[1;32mNumber of repairs per criteria: \033[0;37;40m")
    for crit, cost in criteria_costs:
      print(f"{crit} - {cost}")

  if logger: logger.info(f"Number of repairs per criteria:\n{pformat(criteria_costs)}")

#Inputs: The stats dictionary returned from clingo
def printStatistics(stats_dict, print_func = None):
  
  times = stats_dict["summary"]["times"]
  output = (
    "\n<Statistics>\n"
    "Total: "+str(times["total"]) + "s (Solving: "+str(times["solve"])+"s)\n"
    "CPU Time: "+str(times["cpu"])+"s\n"
    "\n")
  if print_func:
    print_func(output)
  else:
    print(output)