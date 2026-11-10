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
    assert pairs == [ # expanded literal result, here for readability
        ({'a': 0, 'b': 0, 'f': 0}, {'a': 0, 'b': 0, 'f': 0}),
        ({'a': 0, 'b': 0, 'f': 1}, {'a': 0, 'b': 0, 'f': 0}),
        ({'a': 0, 'b': 1, 'f': 0}, {'a': 0, 'b': 1, 'f': 0}),
        ({'a': 0, 'b': 1, 'f': 1}, {'a': 0, 'b': 1, 'f': 0}),
        ({'a': 1, 'b': 0, 'f': 0}, {'a': 1, 'b': 0, 'f': 1}),
        ({'a': 1, 'b': 0, 'f': 1}, {'a': 1, 'b': 0, 'f': 1}),
        ({'a': 1, 'b': 1, 'f': 0}, {'a': 1, 'b': 1, 'f': 0}),
        ({'a': 1, 'b': 1, 'f': 1}, {'a': 1, 'b': 1, 'f': 0})
        ]
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
    assert pairs == [ # expanded literal result, here for readability
        ({'a': 0, 'b': 0, 'f': 0}, {'a': 0, 'b': 0, 'f': 0}),
        ({'a': 0, 'b': 0, 'f': 1}, {'a': 0, 'b': 0, 'f': 0}),
        ({'a': 0, 'b': 1, 'f': 0}, {'a': 0, 'b': 1, 'f': 1}),
        ({'a': 0, 'b': 1, 'f': 1}, {'a': 0, 'b': 1, 'f': 1}),
        ({'a': 1, 'b': 0, 'f': 0}, {'a': 1, 'b': 0, 'f': 1}),
        ({'a': 1, 'b': 0, 'f': 1}, {'a': 1, 'b': 0, 'f': 1}),
        ({'a': 1, 'b': 1, 'f': 0}, {'a': 1, 'b': 1, 'f': 1}),
        ({'a': 1, 'b': 1, 'f': 1}, {'a': 1, 'b': 1, 'f': 1})
    ]
    obs_path = write_obs(_sync_two_step(pairs))
    incst = find_inconsistencies(model, obs_path, "sync")

    result, atoms, costs = repair_function(model, incst, "f", "sync", DEFAULT_CRITERIA)
    assert result == "repaired"
    _assert_repaired_model_is_consistent(model, "f", atoms, obs_path, "sync")
    assert costs[0] == 1
    repair_count_sanity_check("f", model, atoms, list(zip(DEFAULT_CRITERIA, costs)), None)


# --- Bugs --------------------------------------------------------------------

def test_deepening_search_term_number_cost_when_removing_a_term(write_obs):
    # Regression: deepening_search.make_return_tuple() used to prepend the *signed* node variation as the
    # "term-number" cost. When the best repair has fewer terms the cost is -1, so the
    # benchmark CSV reports a negative change count and revision.py's SANITY_CHECKS
    # (repair_count_sanity_check) raise AssertionError, aborting the whole revision.
    #
    # true f(t+1) = a ; corrupted model has f = a | b. With every (a, b, f) combination
    # observed, no 2-term function fits, so the only repair is the 1-term f = a.
    model = bnet_to_lp("a, a\nb, b\nf, a | b\n")
    pairs = [({"a": a, "b": b, "f": f0}, {"a": a, "b": b, "f": a})
             for a, b, f0 in itertools.product((0, 1), repeat=3)]
    assert pairs == [ # expanded literal result, here for readability
        ({'a': 0, 'b': 0, 'f': 0}, {'a': 0, 'b': 0, 'f': 0}),
        ({'a': 0, 'b': 0, 'f': 1}, {'a': 0, 'b': 0, 'f': 0}),
        ({'a': 0, 'b': 1, 'f': 0}, {'a': 0, 'b': 1, 'f': 0}),
        ({'a': 0, 'b': 1, 'f': 1}, {'a': 0, 'b': 1, 'f': 0}),
        ({'a': 1, 'b': 0, 'f': 0}, {'a': 1, 'b': 0, 'f': 1}),
        ({'a': 1, 'b': 0, 'f': 1}, {'a': 1, 'b': 0, 'f': 1}),
        ({'a': 1, 'b': 1, 'f': 0}, {'a': 1, 'b': 1, 'f': 1}),
        ({'a': 1, 'b': 1, 'f': 1}, {'a': 1, 'b': 1, 'f': 1})
    ]
    obs_path = write_obs(_sync_two_step(pairs))
    incst = find_inconsistencies(model, obs_path, "sync")

    result, atoms, costs = repair_function(model, incst, "f", "sync", DEFAULT_CRITERIA)
    assert result == "repaired"
    _assert_repaired_model_is_consistent(model, "f", atoms, obs_path, "sync")
    assert costs[0] == 1, f"term-number cost should count one removed term, got {costs[0]}"
    repair_count_sanity_check("f", model, atoms, list(zip(DEFAULT_CRITERIA, costs)), None)


@pytest.mark.parametrize("criteria", [DEFAULT_CRITERIA, NON_DEEPENING_CRITERIA])
def test_stable_state_repair_can_add_terms(write_obs, criteria):
    # Regression: in stable-state mode generatePreviousObservations() returned [], so the
    # node limit (upo count) was 0 and stable-state repairs could never add a term. The
    # limit is now the number of distinct states of experiments where f is active.
    #
    # true f = a | b ; corrupted model has f = a & b. "extra-regulators" is disabled so
    # the degenerate self-loop repair f = f (see test below) is not available.
    model = bnet_to_lp("a, a\nb, b\nf, a & b\n")
    raw_obs = [{"a": a, "b": b, "f": a | b} for a, b in itertools.product((0, 1), repeat=2)]
    assert raw_obs == [ # expanded literal result, here for readability
        {'a': 0, 'b': 0, 'f': 0},
        {'a': 0, 'b': 1, 'f': 1},
        {'a': 1, 'b': 0, 'f': 1},
        {'a': 1, 'b': 1, 'f': 1}
    ]
    obs_path = write_obs(stable_obs(raw_obs))
    incst = find_inconsistencies(model, obs_path, "stable")
    assert inconsistent_functions(model, incst) == ["f"]

    result, atoms, costs = repair_function(model, incst, "f", "stable", criteria,
                                           disable=["extra-regulators"])
    assert result == "repaired"
    _assert_repaired_model_is_consistent(model, "f", atoms, obs_path, "stable")


def test_parallel_mode_reaches_clingo_with_default_criteria(write_obs, monkeypatch):
    # Regression: with the default criteria ("term-number" first) generateFunctions()
    # delegates to deepening_search, which used to never receive parallel_mode.
    model = bnet_to_lp("a, a\nb, b\nf, a & b\n")
    pairs = [({"a": a, "b": b, "f": f0}, {"a": a, "b": b, "f": a | b})
             for a, b, f0 in itertools.product((0, 1), repeat=3)]
    assert pairs == [ # expanded literal result, here for readability
        ({'a': 0, 'b': 0, 'f': 0}, {'a': 0, 'b': 0, 'f': 0}),
        ({'a': 0, 'b': 0, 'f': 1}, {'a': 0, 'b': 0, 'f': 0}),
        ({'a': 0, 'b': 1, 'f': 0}, {'a': 0, 'b': 1, 'f': 1}),
        ({'a': 0, 'b': 1, 'f': 1}, {'a': 0, 'b': 1, 'f': 1}),
        ({'a': 1, 'b': 0, 'f': 0}, {'a': 1, 'b': 0, 'f': 1}),
        ({'a': 1, 'b': 0, 'f': 1}, {'a': 1, 'b': 0, 'f': 1}),
        ({'a': 1, 'b': 1, 'f': 0}, {'a': 1, 'b': 1, 'f': 1}),
        ({'a': 1, 'b': 1, 'f': 1}, {'a': 1, 'b': 1, 'f': 1})
    ]
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
    assert pairs == [ # expanded literal result, here for readability
        ({'a': 0, 'b': 0, 'f': 0}, {'a': 0, 'b': 0, 'f': 0}),
        ({'a': 0, 'b': 0, 'f': 1}, {'a': 0, 'b': 0, 'f': 0}),
        ({'a': 0, 'b': 1, 'f': 0}, {'a': 0, 'b': 1, 'f': 1}),
        ({'a': 0, 'b': 1, 'f': 1}, {'a': 0, 'b': 1, 'f': 1}),
        ({'a': 1, 'b': 0, 'f': 0}, {'a': 1, 'b': 0, 'f': 1}),
        ({'a': 1, 'b': 0, 'f': 1}, {'a': 1, 'b': 0, 'f': 1}),
        ({'a': 1, 'b': 1, 'f': 0}, {'a': 1, 'b': 1, 'f': 1}),
        ({'a': 1, 'b': 1, 'f': 1}, {'a': 1, 'b': 1, 'f': 1})
    ]
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


# --- Timeouts and recovery against the real solver ----------------------------

def _sync_case(true_f, model_f="a & b"):
    model = bnet_to_lp(f"a, a\nb, b\nf, {model_f}\n")
    pairs = [({"a": a, "b": b, "f": f0}, {"a": a, "b": b, "f": true_f(a, b)})
             for a, b, f0 in itertools.product((0, 1), repeat=3)]
    return model, _sync_two_step(pairs)


@pytest.mark.parametrize("criteria", [DEFAULT_CRITERIA, NON_DEEPENING_CRITERIA])
def test_unsat_found_during_hard_wait_is_no_solution(write_obs, criteria):
    # Regression (non-deepening path): if the search was exhausted during the hard wait,
    # the function was reported as "timeout" instead of "no_solution".
    # true f = b, model f = a; adding regulators is disabled, so there is no repair.
    model, obs = _sync_case(lambda a, b: b, model_f="a")
    incst = find_inconsistencies(model, write_obs(obs), "sync")
    result, atoms, costs = repair_function(model, incst, "f", "sync", criteria,
                                           disable=["extra-regulators"], timeout=(0, 60))
    assert (result, atoms, costs) == ("no_solution", [], None)


@pytest.mark.parametrize("criteria", [DEFAULT_CRITERIA, NON_DEEPENING_CRITERIA])
def test_hard_timeout_is_used_when_soft_timeout_is_zero(write_obs, criteria):
    model, obs = _sync_case(lambda a, b: a | b)
    obs_path = write_obs(obs)
    incst = find_inconsistencies(model, obs_path, "sync")
    result, atoms, costs = repair_function(model, incst, "f", "sync", criteria, timeout=(0, 60))
    assert result in ("repaired", "timeout")
    assert atoms and costs is not None
    _assert_repaired_model_is_consistent(model, "f", atoms, obs_path, "sync")


@pytest.mark.parametrize("criteria", [DEFAULT_CRITERIA, NON_DEEPENING_CRITERIA])
def test_recovery_with_cost_bounds_finds_a_repair_at_least_as_good(write_obs, criteria):
    # What revision.recover_timeouts() does: re-run bounded by the costs found earlier
    model, obs = _sync_case(lambda a, b: a | b)
    incst = find_inconsistencies(model, write_obs(obs), "sync")
    _, _, costs = repair_function(model, incst, "f", "sync", criteria)
    result, atoms, new_costs = repair_function(model, incst, "f", "sync", criteria, cost_bounds=costs)
    assert result == "repaired"
    assert new_costs == costs


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


def _curated(experiments):
    """experiments: list of trajectories (list of states) -> curated_observation facts."""
    return "\n".join(f"curated_observation({e},{t},{c},{v})."
                     for e, trajectory in enumerate(experiments, start=1)
                     for t, state in enumerate(trajectory)
                     for c, v in state.items())


def _upo_states(upo_program, prev_obs):
    """Maps each unique_positive_observation(E,T) back to the state at T-1."""
    ids = [tuple(a[len("unique_positive_observation("):-2].split(","))
           for a in upo_program.splitlines()]
    states = {}
    for atom in prev_obs:
        e, t, c, v = atom[len("previous_observation("):-1].split(",")
        states.setdefault((e, str(int(t) + 1)), {})[c] = int(v)
    return sorted(tuple(sorted(states[i].items())) for i in ids)


def test_previous_observations_across_experiments_and_time_steps_sync():
    from aux_scripts.repair_functions import generatePreviousObservations
    s = lambda a, b, f: {"a": a, "b": b, "f": f}
    experiments = [
        [s(1, 0, 0), s(1, 0, 1), s(1, 0, 1)],   # f=1 at t=1 and t=2
        [s(1, 0, 0), s(0, 1, 1), s(0, 1, 0)],   # f=1 at t=1, preceded by the same state as exp 1
        [s(0, 1, 0), s(0, 1, 1), s(0, 0, 0)],   # f=1 at t=1
        [s(0, 0, 0), s(0, 0, 0)],               # never positive
    ]
    prev = generatePreviousObservations("f", _curated(experiments), True, False)
    # one previous state (3 compounds) per positive observation: e1t1, e1t2, e2t1, e3t1
    assert len(prev) == 4 * 3
    upos, count = processPreviousObservations(prev)
    # the identical state preceding e1t1 and e2t1 is kept once
    assert _upo_states(upos, prev) == [
        (("a", 0), ("b", 1), ("f", 0)),
        (("a", 1), ("b", 0), ("f", 0)),
        (("a", 1), ("b", 0), ("f", 1)),
    ]
    # {a1,b0,f0} and {a1,b0,f1} fuse into the single term "a & !b"
    assert count == 2


def test_previous_observations_across_experiments_async_only_counts_activations():
    from aux_scripts.repair_functions import generatePreviousObservations
    s = lambda a, b, f: {"a": a, "b": b, "f": f}
    experiments = [
        [s(1, 0, 0), s(1, 0, 1), s(1, 0, 1)],   # f activates at t=1, then stays 1 (not counted)
        [s(0, 1, 0), s(0, 1, 1)],               # f activates at t=1
        [s(0, 0, 1), s(0, 0, 1)],               # f stays 1: not an activation
    ]
    prev = generatePreviousObservations("f", _curated(experiments), False, True)
    upos, count = processPreviousObservations(prev)
    assert _upo_states(upos, prev) == [
        (("a", 0), ("b", 1), ("f", 0)),
        (("a", 1), ("b", 0), ("f", 0)),
    ]
    assert count == 2


def test_previous_observations_across_experiments_stable():
    from aux_scripts.repair_functions import generatePreviousObservations
    s = lambda a, b, f: {"a": a, "b": b, "f": f}
    experiments = [s(1, 0, 1), s(1, 1, 1), s(1, 0, 1), s(0, 1, 1), s(0, 0, 0)]
    curated = "\n".join(f"curated_observation({e},{c},{v})."
                         for e, state in enumerate(experiments, start=1) for c, v in state.items())
    prev = generatePreviousObservations("f", curated, False, False)
    # the full state of every experiment where f=1: experiments 1-4
    assert sorted(prev) == sorted(f"previous_observation({e},{c},{v})"
                                  for e, state in enumerate(experiments, start=1)
                                  if state["f"] == 1 for c, v in state.items())
    upos, count = processPreviousObservations(prev)
    # experiment 3 repeats the state of experiment 1, so 3 distinct states remain
    upo_experiments = [a[len("unique_positive_observation("):-2] for a in upos.splitlines()]
    assert len(upo_experiments) == 3
    assert {"1", "3"} & set(upo_experiments) and "2" in upo_experiments and "4" in upo_experiments
    # {a1,b0} and {a1,b1} fuse into the single term "a"
    assert count == 2


def test_previous_observations_stable_without_positive_experiments():
    from aux_scripts.repair_functions import generatePreviousObservations
    curated = "curated_observation(1,a,1). curated_observation(1,f,0)."
    assert generatePreviousObservations("f", curated, False, False) == []


def test_upo_empty():
    assert processPreviousObservations([]) == ("", 0)
