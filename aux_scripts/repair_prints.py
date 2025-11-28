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
def logRepairedLP(inconsistent_func, function_lp, criteria_costs, to_stdout=True, logger = None):
  if to_stdout: 
    print("\033[1;32mRepairs: \033[0;37;40m")
    print(function_lp)

  logChanges(criteria_costs, to_stdout=to_stdout, logger=logger)

  if logger: logger.info(f"Repairs for function {inconsistent_func}:\n{function_lp}")

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