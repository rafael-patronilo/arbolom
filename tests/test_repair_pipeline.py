"""End-to-end repair of a single function, driven in-process the way revision.repair() does."""
import itertools

import clingo
import pytest

from aux_scripts.repair_functions import processPreviousObservations, repair_count_sanity_check
from conftest import (DEFAULT_CRITERIA, bnet_to_lp, find_inconsistencies, inconsistent_functions,
                      repair_function, stable_obs, timeseries_obs)

NON_DEEPENING_CRITERIA = ["regulators", "term-number", "signs", "term-format"]


def _assert_repaired_model_is_consistent(model, func, atoms, obs_path, mode):
    import revision
    model_dict = revision.model_to_dict(model)
    revision.repair_model_dict(model_dict, func, atoms, "repaired")
    repaired = revision.format_model_dict(model_dict)
    assert find_inconsistencies(repaired, obs_path, mode) is None, repaired


def _sync_two_step(pairs):
    """One experiment per (state at t=0, state at t=1) pair."""
    return timeseries_obs([[s0, s1] for s0, s1 in pairs])


# --- Happy paths -------------------------------------------------------------

@pytest.mark.parametrize("criteria", [DEFAULT_CRITERIA, NON_DEEPENING_CRITERIA])
def test_sync_repair_same_number_of_terms(write_obs, criteria):
    # true f(t+1) = a & !b ; corrupted model has f = a & b
    model = bnet_to_lp("a, a\nb, b\nf, a & b\n")
    pairs = [({"a": a, "b": b, "f": f0}, {"a": a, "b": b, "f": a & (1 - b)})
             for a, b, f0 in itertools.product((0, 1), repeat=3)]
    obs_path = write_obs(_sync_two_step(pairs))
    incst = find_inconsistencies(model, obs_path, "sync")
    assert inconsistent_functions(model, incst) == ["f"]

    result, atoms, costs = repair_function(model, incst, "f", "sync", criteria)
    assert result == "repaired"
    _assert_repaired_model_is_consistent(model, "f", atoms, obs_path, "sync")
    repair_count_sanity_check("f", model, atoms, list(zip(criteria, costs)), None)
    assert dict(zip(criteria, costs)) == {"term-number": 0, "regulators": 0, "signs": 1, "term-format": 0}


def test_sync_repair_adding_a_term(write_obs):
    # true f(t+1) = a | b ; corrupted model has f = a & b
    model = bnet_to_lp("a, a\nb, b\nf, a & b\n")
    pairs = [({"a": a, "b": b, "f": f0}, {"a": a, "b": b, "f": a | b})
             for a, b, f0 in itertools.product((0, 1), repeat=3)]
    obs_path = write_obs(_sync_two_step(pairs))
    incst = find_inconsistencies(model, obs_path, "sync")

    result, atoms, costs = repair_function(model, incst, "f", "sync", DEFAULT_CRITERIA)
    assert result == "repaired"
    _assert_repaired_model_is_consistent(model, "f", atoms, obs_path, "sync")
    assert costs[0] == 1
    repair_count_sanity_check("f", model, atoms, list(zip(DEFAULT_CRITERIA, costs)), None)


# --- Bugs --------------------------------------------------------------------

def test_deepening_search_term_number_cost_when_removing_a_term(write_obs):
    # BUG: deepening_search.make_return_tuple() prepends the *signed* node variation as the
    # "term-number" cost. When the best repair has fewer terms the cost is -1, so the
    # benchmark CSV reports a negative change count and revision.py's SANITY_CHECKS
    # (repair_count_sanity_check) raise AssertionError, aborting the whole revision.
    #
    # true f(t+1) = a ; corrupted model has f = a | b. With every (a, b, f) combination
    # observed, no 2-term function fits, so the only repair is the 1-term f = a.
    model = bnet_to_lp("a, a\nb, b\nf, a | b\n")
    pairs = [({"a": a, "b": b, "f": f0}, {"a": a, "b": b, "f": a})
             for a, b, f0 in itertools.product((0, 1), repeat=3)]
    obs_path = write_obs(_sync_two_step(pairs))
    incst = find_inconsistencies(model, obs_path, "sync")

    result, atoms, costs = repair_function(model, incst, "f", "sync", DEFAULT_CRITERIA)
    assert result == "repaired"
    _assert_repaired_model_is_consistent(model, "f", atoms, obs_path, "sync")
    assert costs[0] == 1, f"term-number cost should count one removed term, got {costs[0]}"
    repair_count_sanity_check("f", model, atoms, list(zip(DEFAULT_CRITERIA, costs)), None)


@pytest.mark.parametrize("criteria", [DEFAULT_CRITERIA, NON_DEEPENING_CRITERIA])
def test_stable_state_repair_can_add_terms(write_obs, criteria):
    # BUG: in stable-state mode generatePreviousObservations() returns [], so the node
    # limit (upo count) is 0. The non-deepening encoding then only offers the original
    # term IDs, and the deepening search never tries more terms than the original.
    # Stable-state repairs can therefore never add a term.
    #
    # true f = a | b ; corrupted model has f = a & b. "extra-regulators" is disabled so
    # the degenerate self-loop repair f = f (see test below) is not available.
    model = bnet_to_lp("a, a\nb, b\nf, a & b\n")
    obs_path = write_obs(stable_obs([{"a": a, "b": b, "f": a | b}
                                     for a, b in itertools.product((0, 1), repeat=2)]))
    incst = find_inconsistencies(model, obs_path, "stable")
    assert inconsistent_functions(model, incst) == ["f"]

    result, atoms, costs = repair_function(model, incst, "f", "stable", criteria,
                                           disable=["extra-regulators"])
    assert result == "repaired"
    _assert_repaired_model_is_consistent(model, "f", atoms, obs_path, "stable")


def test_parallel_mode_reaches_clingo_with_default_criteria(write_obs, monkeypatch):
    # BUG (relevant to the parallel-mode branch): with the default criteria
    # ("term-number" first) generateFunctions() delegates to deepening_search, which
    # never receives parallel_mode (nor cost_bounds or the hard timeout). `-p` is
    # silently ignored for the default configuration.
    model = bnet_to_lp("a, a\nb, b\nf, a & b\n")
    pairs = [({"a": a, "b": b, "f": f0}, {"a": a, "b": b, "f": a | b})
             for a, b, f0 in itertools.product((0, 1), repeat=3)]
    incst = find_inconsistencies(model, write_obs(_sync_two_step(pairs)), "sync")

    real_control = clingo.Control
    seen_args = []

    def spy_control(*args, **kwargs):
        seen_args.append(list(kwargs.get("arguments", args[0] if args else [])))
        return real_control(*args, **kwargs)

    monkeypatch.setattr(clingo, "Control", spy_control)
    result, _, _ = repair_function(model, incst, "f", "sync", DEFAULT_CRITERIA, parallel_mode="2")
    assert result == "repaired"
    solver_calls = [a for a in seen_args if any("compound=" in x for x in a)]
    repair_calls = [a for a in solver_calls if any("node_number" in x for x in a)]
    assert repair_calls, "no repair solver call observed"
    assert all("--parallel-mode" in a for a in repair_calls), repair_calls


def test_parallel_mode_reaches_clingo_with_non_deepening_criteria(write_obs, monkeypatch):
    model = bnet_to_lp("a, a\nb, b\nf, a & b\n")
    pairs = [({"a": a, "b": b, "f": f0}, {"a": a, "b": b, "f": a | b})
             for a, b, f0 in itertools.product((0, 1), repeat=3)]
    incst = find_inconsistencies(model, write_obs(_sync_two_step(pairs)), "sync")

    real_control = clingo.Control
    seen_args = []

    def spy_control(*args, **kwargs):
        seen_args.append(list(kwargs.get("arguments", [])))
        return real_control(*args, **kwargs)

    monkeypatch.setattr(clingo, "Control", spy_control)
    result, _, _ = repair_function(model, incst, "f", "sync", NON_DEEPENING_CRITERIA, parallel_mode="2")
    assert result == "repaired"
    repair_calls = [a for a in seen_args if any("max_node_number" in x for x in a)]
    assert repair_calls and all("--parallel-mode" in a for a in repair_calls)


# --- Unique positive observations (node limit) -------------------------------

def _prev_obs(states):
    """states: list of dicts (state at t-1 preceding a positive observation)."""
    atoms = []
    for i, state in enumerate(states):
        atoms += [f"previous_observation({i},0,{c},{v})" for c, v in state.items()]
    return atoms


def test_upo_deduplicates_identical_states():
    upos, count = processPreviousObservations(_prev_obs([{"a": 1, "b": 0}, {"a": 1, "b": 0}]))
    assert count == 1
    assert upos.count("unique_positive_observation") == 1


def test_upo_fuses_states_differing_in_one_compound():
    # {a=1,b=0} and {a=1,b=1} are covered by the single term "a"
    upos, count = processPreviousObservations(_prev_obs([{"a": 1, "b": 0}, {"a": 1, "b": 1}]))
    assert count == 1
    assert upos.count("unique_positive_observation") == 2  # the program keeps both


def test_upo_keeps_unrelated_states_apart():
    _, count = processPreviousObservations(_prev_obs([{"a": 1, "b": 0}, {"a": 0, "b": 1}]))
    assert count == 2


def test_upo_empty():
    assert processPreviousObservations([]) == ("", 0)
