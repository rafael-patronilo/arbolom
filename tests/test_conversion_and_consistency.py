import itertools

import pytest

from aux_scripts.common import getAllCompounds, parse_atom
from conftest import bnet_to_lp, find_inconsistencies, stable_obs, timeseries_obs


# --- Conversion -------------------------------------------------------------

def test_bnet_to_lp_facts():
    lp = bnet_to_lp("a, a\nb, b\nf, (a & !b) | b\n")
    facts = {line for line in lp.splitlines() if line and not line.startswith("%")}
    assert {"compound(a).", "compound(b).", "compound(f)."} <= facts
    assert {"regulates(a, f, 0).", "regulates(b, f, 1).", "regulates(b, f, 0)."} <= facts
    assert {"function(f, 2).", "term(f, 1, a).", "term(f, 1, b).", "term(f, 2, b)."} <= facts
    # input compounds are encoded as self-activating single-term functions
    assert {"function(a, 1).", "term(a, 1, a).", "regulates(a, a, 0)."} <= facts


def test_regulator_only_compounds_become_inputs():
    lp = bnet_to_lp("f, x & y\n")
    assert "function(x, 1)." in lp and "term(x, 1, x)." in lp


def test_get_all_compounds_strips_negation():
    assert getAllCompounds({"f": ["a&!b"], "g": ["!f"]}) == ["a", "b", "f", "g"]


@pytest.mark.parametrize("text, expected", [
    ("term(f, 1, a).", ("term", ["f", "1", "a"])),
    ("% comment", (None, None)),
    ("", (None, None)),
])
def test_parse_atom(text, expected):
    assert parse_atom(text) == expected


# --- Consistency ------------------------------------------------------------

def _inconsistent_atoms(incst):
    return sorted(a for a in incst.split() if a.startswith("inconsistent"))


def test_stable_consistent_model(write_obs):
    model = bnet_to_lp("a, a\nb, b\nf, a & b\n")
    obs = stable_obs([{"a": x, "b": y, "f": x & y} for x, y in itertools.product((0, 1), repeat=2)])
    assert find_inconsistencies(model, write_obs(obs), "stable") is None


def test_stable_detects_inconsistency(write_obs):
    model = bnet_to_lp("a, a\nb, b\nf, a & b\n")
    obs = stable_obs([{"a": 1, "b": 0, "f": 1}, {"a": 1, "b": 1, "f": 1}])
    incst = find_inconsistencies(model, write_obs(obs), "stable")
    assert _inconsistent_atoms(incst) == ["inconsistent(1,f,0)."]


def test_sync_detects_inconsistency(write_obs):
    model = bnet_to_lp("a, a\nb, b\nf, a | b\n")
    obs = timeseries_obs([
        [{"a": 0, "b": 1, "f": 0}, {"a": 0, "b": 1, "f": 0}],   # a|b predicts f=1 at t=1
        [{"a": 1, "b": 0, "f": 0}, {"a": 1, "b": 0, "f": 1}],
    ])
    incst = find_inconsistencies(model, write_obs(obs), "sync")
    assert _inconsistent_atoms(incst) == ["inconsistent(1,1,f,1)."]


def test_unsatisfiable_check_is_not_reported_as_consistent(write_obs, monkeypatch):
    # BUG: when the consistency program has no answer set (here: async observations in
    # which two compounds change in the same step, which the async encoding forbids),
    # consistencyCheck() returns [] and isConsistent() returns None -- the same value it
    # returns for a consistent model. revision.checkConsistency() then reports the model
    # as consistent and skips repair entirely.
    import revision
    monkeypatch.setattr(revision, "toggle_stable_state", False)
    monkeypatch.setattr(revision, "toggle_sync", False)
    monkeypatch.setattr(revision, "toggle_async", True)
    monkeypatch.setattr(revision, "benchmark_enabled", True)

    model = bnet_to_lp("a, !a\nb, !b\n")
    obs = timeseries_obs([[{"a": 0, "b": 0}, {"a": 1, "b": 1}]])
    try:
        result = revision.checkConsistency(model, write_obs(obs))
    except Exception:
        return  # raising is an acceptable way to surface the problem
    assert result is not None, "unsatisfiable consistency check was reported as 'consistent'"
