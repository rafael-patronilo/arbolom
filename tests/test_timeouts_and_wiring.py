"""Control-flow tests that stub out clingo: timeouts, argument wiring, CLI parsing."""
import inspect
import sys

import pytest

from arbolom.modes import UpdateMode
from arbolom.repair import deepening_search, search

MODEL = "compound(f).\nfunction(f, 2).\n"


@pytest.fixture
def fake_clingo_calls(monkeypatch):
    """Replace deepening_search.generate_functions_clingo with a scripted fake.

    Each scripted entry is (elapsed_seconds, completed, result) where `completed` means
    the search finished and result is None or (atoms, costs). The fake advances a fake
    monotonic clock by elapsed_seconds and records the (soft, hard) timeouts it got.
    """
    clock = {"now": 1000.0}
    calls = []
    script = []

    def fake(node_number, timeouts, *args, **kwargs):
        calls.append({"node_number": node_number, "timeouts": timeouts, **kwargs})
        elapsed, completed, result = script.pop(0)
        clock["now"] += elapsed
        return completed, result

    monkeypatch.setattr(deepening_search, "generate_functions_clingo", fake)
    monkeypatch.setattr(deepening_search.time, "monotonic", lambda: clock["now"])
    return script, calls


def _deepening(timeout, upo_count=5, **kwargs):
    # MODEL has 2 terms; upo_count is the node limit
    return deepening_search.generate_functions(
        timeout, "f", MODEL, "", ("", upo_count), UpdateMode.SYNC, ["regulators"], [], **kwargs)


def test_deepening_timeout_without_any_solution_does_not_crash(fake_clingo_calls):
    # Regression: when the first solver call timed out before finding any model,
    # make_return_tuple(None) raised "TypeError: 'NoneType' object is not subscriptable".
    script, _ = fake_clingo_calls
    script.append((10, False, None))
    assert _deepening(10) == ("timeout", [], None)


def test_deepening_never_passes_a_negative_timeout_to_clingo(fake_clingo_calls):
    # Regression: the remaining budget was passed straight to SolveHandle.wait(). Once
    # exhausted it was negative, which clingo treats as "no timeout at all".
    script, calls = fake_clingo_calls
    script += [
        (15, True, None),    # 2 nodes: proven unsat, but took longer than the budget
        (1, True, None),     # 3 nodes
        (1, True, None),     # 1 node
        (1, True, None),     # 4 nodes
        (1, True, None),     # 5 nodes
    ]
    assert _deepening(10) == ("no_solution", [], None)
    assert len(calls) == 5
    assert all(min(c["timeouts"]) >= 0 for c in calls), calls


def test_deepening_returns_best_of_both_directions(fake_clingo_calls):
    script, calls = fake_clingo_calls
    script += [
        (1, True, None),                       # 2 nodes
        (1, True, (["above"], [3])),           # 3 nodes
        (1, True, (["below"], [1])),           # 1 node: cheaper
    ]
    assert _deepening(100) == ("repaired", ["below"], [1, 1])


def test_deepening_uses_hard_timeout_only_until_a_candidate_exists(fake_clingo_calls):
    script, calls = fake_clingo_calls
    script += [
        (1, True, None),                       # 2 nodes
        (1, True, (["above"], [3])),           # 3 nodes
        (1, False, None),                      # 1 node: timed out
    ]
    assert _deepening((10, 50)) == ("timeout", ["above"], [1, 3])
    assert calls[0]["timeouts"] == (10, 50)
    assert calls[1]["timeouts"] == (9, 50)
    assert calls[2]["timeouts"] == (8, 0)    # a candidate exists: no hard extension


def test_deepening_forwards_parallel_mode(fake_clingo_calls):
    script, calls = fake_clingo_calls
    script.append((1, True, (["x"], [0])))
    _deepening(10, parallel_mode="4")
    assert calls[0]["parallel_mode"] == "4"


def test_deepening_cost_bounds(fake_clingo_calls):
    # bounds = previous repair: one node of variation, then clingo costs [2]
    script, calls = fake_clingo_calls
    script += [
        (1, True, None),     # 2 nodes (variation 0): no bound needed, anything is better
        (1, True, None),     # 3 nodes (variation 1): bounded
        (1, True, None),     # 1 node  (variation 1): bounded
    ]
    assert _deepening(10, cost_bounds=[1, 2]) == ("no_solution", [], None)
    assert [c["cost_bounds"] for c in calls] == [None, [2], [2]]  # variation 2 never tried


def test_recover_timeouts_calls_generate_functions_with_matching_arguments(monkeypatch):
    # Regression: recover_timeouts() was not updated when disable_change_criteria was added to
    # generateFunctions(). Its positional arguments are shifted by one
    # ((timeout, 0) lands in disable_change_criteria, toggle_stable_state in
    # repair_timeout, ...) and toggle_async is missing, so every recovery attempt raises
    # TypeError and a whole benchmark run is lost.
    from arbolom import revision
    signature = inspect.signature(search.generate_functions)
    bound_calls = []

    def spy(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)  # raises TypeError like the real call
        bound_calls.append(bound.arguments)
        return "repaired", ["node_regulator(1,a)", "regulator_activator(a)"], [0, 0, 0, 0]

    monkeypatch.setattr(revision, "generate_functions", spy)
    reviser = revision.ModelReviser(revision.RevisionSettings(
        mode=UpdateMode.SYNC,
        quiet=True,
        disable_change_criteria=["extra-regulators"],
        min_change_criteria=["term-number", "regulators", "signs", "term-format"],
    ))

    stats = {"f": {}}
    model_dict = {}
    to_recover = [("f", ("", 1), [1, 1, 1, 1], 3.0)]
    reviser.recover_timeouts("model", "incst", stats, to_recover,
                             revision.time.monotonic() + 100, model_dict)

    assert len(bound_calls) == 1
    args = bound_calls[0]
    assert args["disable_change_criteria"] == ["extra-regulators"]
    assert isinstance(args["repair_timeout"], tuple)
    assert args["mode"] is UpdateMode.SYNC


BENCH_REQUIRED = ["benchmark.py", "-f", "cfg", "-o", "obs", "-m", "model", "-s", "out"]


@pytest.mark.parametrize("mode_flag", [[], ["-sync"]], ids=["default-mode", "explicit-mode"])
def test_benchmark_skip_is_honoured(monkeypatch, mode_flag):
    # Regression: parseArgs() returned early when no mode flag was given (default stable
    # mode) before assigning skip_n_first, so `-skip N` was silently ignored.
    from arbolom.scripts import benchmark
    monkeypatch.setattr(sys, "argv", BENCH_REQUIRED + mode_flag + ["-skip", "3"])
    settings = benchmark.parse_args()
    assert settings.skip_n_first == 3
