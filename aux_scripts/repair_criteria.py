

# Optimization criteria
# 1-Optimize for the minimum changes to number of terms (highest priority by default)
TERM_NUMBER = (
    "#minimize{{1@{p}, N : extra_full_node(N)}}.\n"
    "#minimize{{1@{p}, N : missing_full_node(N)}}."
)

# 2-Optimize for the minimum changes to regulators
REGULATORS = (
    "#minimize{{1@{p}, C : missing_regulator(C)}}.\n"
    "#minimize{{1@{p}, C : extra_regulator(C)}}."
)

# 3-Optimize for the minimum changes to regulator signs 
SIGN_CHANGES = "#minimize{{1@{p}, C : sign_changed(C)}}."

#4-Optimize for minimum changes to original node format
TERM_FORMAT = (
    "#minimize{{1@{p}, N,C : missing_node_regulator(N,C)}}.\n"
    "#minimize{{1@{p}, N,C : extra_node_regulator(N,C)}}."
)

def build_asp_change_criteria(criteria : list[str], toggle_stable_state, toggle_sync, toggle_async) -> str:
    if not toggle_sync or toggle_stable_state or toggle_async:
        raise NotImplementedError("Mode not implemented yet")
    asp_criteria = []
    for i, c in enumerate(criteria):
        priority = len(criteria) - i
        match c:
            case "term-number":
                asp_criteria.append(TERM_NUMBER.format(p=priority))
            case "regulators":
                asp_criteria.append(REGULATORS.format(p=priority))
            case "signs":
                asp_criteria.append(SIGN_CHANGES.format(p=priority))
            case "term-format":
                asp_criteria.append(TERM_FORMAT.format(p=priority))
            case _:
                raise ValueError(f"Unknown criteria: {c}")
    return "\n".join(asp_criteria) + "\n"