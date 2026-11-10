"""Console output of the revision process."""
from pprint import pformat

#Purpose: Prints the start of the repair of a function
def print_func_repair_start(current_function):
  print(f"\033[1;32m ----{current_function} REPAIR START----\033[0;37;40m")

#Purpose: Prints the end of the repair of a function
def print_func_repair_end(current_function):
  print(f"\033[1;32m ----{current_function} REPAIR END----\033[0;37;40m")

#Purpose: Prints the initial iftv generation phase message
def print_iftv_start():
  print("\033[1;32m ----IFTV GENERATION START----\033[0;37;40m")

#Purpose: Prints the final iftv generation phase message
def print_iftv_end():
  print("\033[1;32m ----IFTV GENERATION END----\033[0;37;40m")

#Inputs: The inconsistent function, and the resulting answer set obtained from clingo
#Purpose: Prints the repairs in LP format
def log_repaired_lp(inconsistent_func, function_lp, criteria_costs, to_stdout=True, logger = None):
  if to_stdout:
    print("\033[1;32mRepairs: \033[0;37;40m")
    print(function_lp)

  log_changes(criteria_costs, to_stdout=to_stdout, logger=logger)

  if logger: logger.info(f"Repairs for function {inconsistent_func}:\n{function_lp}")

def log_changes(criteria_costs, to_stdout=True, logger = None):
  if to_stdout:
    print("\033[1;32mNumber of repairs per criteria: \033[0;37;40m")
    for crit, cost in criteria_costs:
      print(f"{crit} - {cost}")

  if logger: logger.info(f"Number of repairs per criteria:\n{pformat(criteria_costs)}")

#Inputs: The stats dictionary returned from clingo
def print_statistics(stats_dict, print_func = None):

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
