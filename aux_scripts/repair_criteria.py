from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class RepairCriterion:
    name : str
    optimize_format_string: str
    disable_constraints: Optional[str] = None
    description: str = ""
    
    def combine(self, other: 'RepairCriterion', name : str, description : str) -> 'RepairCriterion':
        """
        Combine two RepairCriterion instances into a new one, allowing the same priority to be assigned to both.
        """
        combined_optimize_format = "\n".join((self.optimize_format_string, other.optimize_format_string))
        if self.disable_constraints and other.disable_constraints:
            combined_disable_constraints = "\n".join((self.disable_constraints, other.disable_constraints))
        else:
            combined_disable_constraints = None

        return RepairCriterion(combined_optimize_format, combined_disable_constraints, description)

    def build_optimize_statement(self, priority: int) -> str:
        """
        Build the ASP criterion with the given priority.
        """
        return self.optimize_format_string.format(p=priority)
    
    def build_disable_statement(self) -> Optional[str]:
        """
        Build the ASP statement to disable this criterion, if a disable format string is provided.
        """
        if not self.disable_constraints:
            raise ValueError(f"Criterion {self.name} cannot be disabled.")
        return self.disable_constraints
    
    @classmethod
    def from_expression(
        cls, name : str, variables : list[str], expression : str, 
        description : str
    ):
        optimize_format_string = f"#minimize{{1@{{p}}, {', '.join(variables)} : {expression}}}."
        disable_constraints = f":- {expression}."
        return cls(name, optimize_format_string, disable_constraints,
                    description=description)

CRITERIA : dict[str, RepairCriterion] = {}

def register_criterion(criterion: RepairCriterion):
    if criterion.name in CRITERIA:
        raise ValueError(f"Criterion with name '{criterion.name}' already exists.")
    CRITERIA[criterion.name] = criterion


# ASP basic optimization criteria (Combined criteria are built afterwards)
register_criterion( RepairCriterion.from_expression(
    "extra-terms",
    ["N"],
    "node_ID(N), function(compound, TERM_NO), N > TERM_NO",
    "Optimize for the minimum number of added terms to the new formula."
))
register_criterion(RepairCriterion.from_expression(
    "missing-terms",
    ["N"],
    "available_node_ID(N), not node_ID(N), function(compound, TERM_NO), N <= TERM_NO",
    "Optimize for the minimum number of removed terms from the old formula."
))


register_criterion(RepairCriterion.from_expression(
    "extra-regulators",
    ["C"],
    "not regulates(C,compound,_), node_regulator(_,C)",
    "Optimize for the minimum number of added regulators in the new formula."
))
register_criterion(RepairCriterion.from_expression(
    "missing-regulators",
    ["C"],
    "regulates(C,compound,_), not node_regulator(_,C)",
    "Optimize for the minimum number of removed regulators from the old formula."
))


register_criterion(RepairCriterion.from_expression(
    "sign-to-inhibitor",
    ["C"],
    "regulates(C,compound,0), inhibitor(C), node_regulator(_, C)",
    "Optimize for the minimum number of activators changed to inhibitors."
))
register_criterion(RepairCriterion.from_expression(
    "sign-to-activator",
    ["C"],
    "regulates(C,compound,1), activator(C), node_regulator(_, C)",
    "Optimize for the minimum number of inhibitors changed to activators."
))


register_criterion(RepairCriterion.from_expression(
    "term-missing-regulator",
    ["ID", "R"],
    "term(compound, ID, R), node_ID(ID), not node_regulator(ID, R)",
    "Optimize for the minimum number of missing regulators in each term of the new formula."
))
register_criterion(RepairCriterion.from_expression(
    "term-extra-regulator",
    ["ID", "R"],
    "node_regulator(ID, R), term(compound, ID, _), not term(compound, ID, R)",
    "Optimize for the minimum number of extra regulators in each term of the new formula."
))


# Default criteria:
# 1-Optimize for the minimum changes to number of terms (highest priority by default)
register_criterion(CRITERIA["extra-terms"].combine(
    CRITERIA["missing-terms"], 
    "term-number",
    "Optimize for the minimum number of changes to the number of terms in the new formula. "
    "Combines 'extra-terms' and 'missing-terms'."
))
# 2-Optimize for the minimum changes to regulators (second highest priority by default)
register_criterion(CRITERIA["extra-regulators"].combine(
    CRITERIA["missing-regulators"], 
    "regulators",
    "Optimize for the minimum number of changes to regulators in the new formula. "
    "Combines 'extra-regulators' and 'missing-regulators'."
))
# 3-Optimize for the minimum changes to signs (third highest priority by default)
register_criterion(CRITERIA["sign-to-inhibitor"].combine(
    CRITERIA["sign-to-activator"],
    "signs",
    "Optimize for the minimum number of changed regulator signs in the new formula. "
    "Combines 'sign-to-inhibitor' and 'sign-to-activator'."
))
# 4-Optimize for the minimum changes to term format (lowest priority by default)
register_criterion(CRITERIA["term-missing-regulator"].combine(
    CRITERIA["term-extra-regulator"], 
    "term-format",
    "Optimize for the minimum number of changes to the term format in the new formula. "
    "Combines 'term-missing-regulator' and 'term-extra-regulator'."
))

# Combine the term-number and term-format criteria into a single criterion
register_criterion(CRITERIA["term-number"].combine(
    CRITERIA["term-format"],
    "terms",
    "Optimize for the minimum number of changes to the terms, both number and format, in the new formula. "
    "Combines 'term-number' and 'term-format'."
))


def build_asp_change_criteria(criteria : list[str], toggle_stable_state, toggle_sync, toggle_async) -> str:
    asp_criteria = []
    for i, c in enumerate(criteria):
        priority = len(criteria) - i
        criterion = CRITERIA.get(c)
        if criterion is None:
            raise ValueError(f"Unknown criteria: {c}")
        asp_criteria.append(criterion.build_optimize_statement(priority))
    return "\n".join(asp_criteria) + "\n"

def build_asp_disable_constraints(criteria : list[str]) -> str:
    asp_constraints = []
    for c in criteria:
        criterion = CRITERIA.get(c)
        if criterion is None:
            raise ValueError(f"Unknown criteria: {c}")
        disable_statement = criterion.build_disable_statement()
        if disable_statement:
            asp_constraints.append(disable_statement)
    return "\n".join(asp_constraints) + "\n"

def print_criteria(file = None):
    """
    Print the available criteria to the console or a file.
    """
    output = []
    for name, criterion in CRITERIA.items():
        output.append(f"{name}\n\t{criterion.description}")
    print("\n".join(output), file=file)