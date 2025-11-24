from dataclasses import dataclass

@dataclass(frozen=True)
class RepairCriterion:
    format_string: str
    description: str = ""
    
    def combine(self, other: 'RepairCriterion', description : str) -> 'RepairCriterion':
        """
        Combine two RepairCriterion instances into a new one, allowing the same priority to be assigned to both.
        """
        combined_format = "\n".join((self.format_string, other.format_string))
        return RepairCriterion(combined_format, description)

    def build(self, priority: int) -> str:
        """
        Build the ASP criterion with the given priority.
        """
        return self.format_string.format(p=priority)

# ASP basic optimization criteria (Combined criteria are built afterwards)
CRITERIA = {
    "extra-terms" : RepairCriterion(
        "#minimize{{1@{p}, N : extra_full_node(N)}}.", 
        "Optimize for the minimum number of added terms to the new formula."
    ),
    "missing-terms" : RepairCriterion(
        "#minimize{{1@{p}, N : missing_full_node(N)}}.",
        "Optimize for the minimum number of removed terms from the old formula."
    ),


    "extra-regulators" : RepairCriterion(
        "#minimize{{1@{p}, C : extra_regulator(C)}}.",
        "Optimize for the minimum number of added regulators in the new formula."
    ),
    "missing-regulators" : RepairCriterion(
        "#minimize{{1@{p}, C : missing_regulator(C)}}.",
        "Optimize for the minimum number of removed regulators from the old formula."
    ),


    #"sign-to-inhibitor" : RepairCriterion(
    #    "#minimize{{1@{p}, C : regulates(C,compound,0), inhibitor(C)}}.",
    #    "Optimize for the minimum number of activators changed to inhibitors."
    #),
    #"sign-to-activator" : RepairCriterion(
    #    "#minimize{{1@{p}, C : regulates(C,compound,1), activator(C)}}.",
    #    "Optimize for the minimum number of inhibitors changed to activators."
    #),
    "signs" : RepairCriterion(
        "#minimize{{1@{p}, C : sign_changed(C)}}."
    ),

    "term-missing-regulator" : RepairCriterion(
        "#minimize{{1@{p}, ID, R : missing_node_regulator(ID,R)}}.",
        "Optimize for the minimum number of missing regulators in each term of the new formula."
    ),
    "term-extra-regulator" : RepairCriterion(
        "#minimize{{1@{p}, ID, R : extra_node_regulator(ID,R)}}.",
        "Optimize for the minimum number of extra regulators in each term of the new formula."
    )
}

# Default criteria:
# 1-Optimize for the minimum changes to number of terms (highest priority by default)
CRITERIA["term-number"] = CRITERIA["extra-terms"].combine(
    CRITERIA["missing-terms"], 
    "Optimize for the minimum number of changes to the number of terms in the new formula. "
    "Combines 'extra-terms' and 'missing-terms'."
)
# 2-Optimize for the minimum changes to regulators (second highest priority by default)
CRITERIA["regulators"] = CRITERIA["extra-regulators"].combine(
    CRITERIA["missing-regulators"], 
    "Optimize for the minimum number of changes to regulators in the new formula. "
    "Combines 'extra-regulators' and 'missing-regulators'."
)
# 3-Optimize for the minimum changes to signs (third highest priority by default)
#CRITERIA["signs"] = CRITERIA["sign-to-inhibitor"].combine(
#    CRITERIA["sign-to-activator"],
#    "Optimize for the minimum number of changed regulator signs in the new formula. "
#    "Combines 'sign-to-inhibitor' and 'sign-to-activator'."
#)
# 4-Optimize for the minimum changes to term format (lowest priority by default)
CRITERIA["term-format"] = CRITERIA["term-missing-regulator"].combine(
    CRITERIA["term-extra-regulator"], 
    "Optimize for the minimum number of changes to the term format in the new formula. "
    "Combines 'term-missing-regulator' and 'term-extra-regulator'."
)

# Combine the term-number and term-format criteria into a single criterion
CRITERIA["terms"] = CRITERIA["term-number"].combine(
    CRITERIA["term-format"],
    "Optimize for the minimum number of changes to the terms, both number and format, in the new formula. "
    "Combines 'term-number' and 'term-format'."
)


def build_asp_change_criteria(criteria : list[str], toggle_stable_state, toggle_sync, toggle_async) -> str:
    asp_criteria = []
    for i, c in enumerate(criteria):
        priority = len(criteria) - i
        criterion = CRITERIA.get(c)
        if criterion is None:
            raise ValueError(f"Unknown criteria: {c}")
        asp_criteria.append(criterion.build(priority))
    return "\n".join(asp_criteria) + "\n"

def print_criteria(file = None):
    """
    Print the available criteria to the console or a file.
    """
    output = []
    for name, criterion in CRITERIA.items():
        output.append(f"{name}\n\t{criterion.description}")
    print("\n".join(output), file=file)