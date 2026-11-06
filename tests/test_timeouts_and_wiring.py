"""Control-flow tests that stub out clingo: timeouts, argument wiring, CLI parsing."""
import inspect
import sys

import pytest

from aux_scripts import deepening_search, repair_functions

MODEL = "compound(f).\nfunction(f, 2).\n"


@pytest.fixture
def fake_clingo_calls(monkeypatch):
    """Replace deepening_search.generateFunctionsClingo with a scripted fake.

    Each scripted entry is (elapsed_seconds, timed_out, result) where result is None or
    (atoms, costs). The fake advances a fake monotonic clock by elapsed_seconds.
    """
    clock = {"now": 1000.0}
    calls = []
    script = []

    def fake(node_number, repair_timeout, *args, **kwargs):
        calls.append({"node_number": node_number, "timeout": repair_timeout})
        elapsed, timed_out, result = script.pop(0)
        clock["now"] += elapsed
        return timed_out, result

    monkeypatch.setattr(deepening_search, "generateFunctionsClingo", fake)
    monkeypatch.setattr(deepening_search.time, "monotonic", lambda: clock["now"])
    return script, calls


def test_deepening_timeout_without_any_solution_does_not_crash(fake_clingo_calls):
    # BUG: when the first solver call times out before finding any model,
    # generateFunctionsClingo returns (True, None) and make_return_tuple(None) raises
    # "TypeError: 'NoneType' object is not subscriptable" instead of reporting a timeout.
    script, _ = fake_clingo_calls
    script.append((10, True, None))
    result, atoms, costs = deepening_search.generateFunctions(
        10, "f", MODEL, "", ("", 5), False, True, False, ["regulators"], [])
    assert result == "timeout"
    assert not atoms and costs is None


def test_deepening_never_passes_a_negative_timeout_to_clingo(fake_clingo_calls):
    # BUG: the remaining budget is computed as repair_timeout - elapsed and passed straight
    # to SolveHandle.wait(). Once the budget is exhausted that value is negative, and
    # clingo documents that a negative timeout means "block until a result is ready",
    # i.e. no timeout at all.
    script, calls = fake_clingo_calls
    script += [
        (15, False, None),   # 2 nodes: proven unsat, but took longer than the budget
        (1, False, None),    # 3 nodes
        (1, False, None),    # 1 node
    ]
    try:
        deepening_search.generateFunctions(
            10, "f", MODEL, "", ("", 5), False, True, False, ["regulators"], [])
    except IndexError:
        pass  # ran out of scripted calls: irrelevant to this check
    assert all(c["timeout"] >= 0 for c in calls), calls


def test_recover_timeouts_calls_generate_functions_with_matching_arguments(monkeypatch):
    # BUG: recover_timeouts() was not updated when disable_change_criteria was added to
    # generateFunctions(). Its positional arguments are shifted by one
    # ((timeout, 0) lands in disable_change_criteria, toggle_stable_state in
    # repair_timeout, ...) and toggle_async is missing, so every recovery attempt raises
    # TypeError and a whole benchmark run is lost.
    import revision
    signature = inspect.signature(repair_functions.generateFunctions)
    bound_calls = []

    def spy(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)  # raises TypeError like the real call
        bound_calls.append(bound.arguments)
        return "repaired", ["node_regulator(1,a)", "regulator_activator(a)"], [0, 0, 0, 0]

    monkeypatch.setattr(revision, "generateFunctions", spy)
    monkeypatch.setattr(revision, "benchmark_enabled", True)
    monkeypatch.setattr(revision, "toggle_stable_state", False)
    monkeypatch.setattr(revision, "toggle_sync", True)
    monkeypatch.setattr(revision, "toggle_async", False)
    monkeypatch.setattr(revision, "disable_change_criteria", ["extra-regulators"])
    monkeypatch.setattr(revision, "min_change_criteria", ["term-number", "regulators", "signs", "term-format"])

    stats = {"f": {}}
    model_dict = {}
    to_recover = [("f", ("", 1), [1, 1, 1, 1], 3.0)]
    revision.recover_timeouts("model", "incst", stats, to_recover,
                              revision.time.monotonic() + 100, model_dict)

    assert len(bound_calls) == 1
    args = bound_calls[0]
    assert args["disable_change_criteria"] == ["extra-regulators"]
    assert isinstance(args["repair_timeout"], tuple)
    assert (args["toggle_stable_state"], args["toggle_sync"], args["toggle_async"]) == (False, True, False)


BENCH_REQUIRED = ["benchmark.py", "-f", "cfg", "-o", "obs", "-m", "model", "-s", "out"]


@pytest.mark.parametrize("mode_flag", [[], ["-sync"]], ids=["default-mode", "explicit-mode"])
def test_benchmark_skip_is_honoured(monkeypatch, mode_flag):
    # BUG: parseArgs() returns early when no mode flag is given (default stable mode)
    # before assigning skip_n_first, so `-skip N` is silently ignored and a resumed
    # benchmark re-runs (and then refuses to overwrite) completed tests.
    import benchmark
    monkeypatch.setattr(sys, "argv", BENCH_REQUIRED + mode_flag + ["-skip", "3"])
    monkeypatch.setattr(benchmark, "skip_n_first", 0)
    benchmark.parseArgs()
    assert benchmark.skip_n_first == 3
