import importlib.util
import sys

import clingo
import pytest

from conftest import ROOT, bnet_to_lp


def load_real_repair_criteria(allow_partial=False):
    """Load src/arbolom/repair/criteria.py from disk as a fresh, isolated module.

    With allow_partial=True, an exception during module execution is swallowed and
    whatever was defined before it (e.g. the RepairCriterion class) is returned, so a
    test can target one bug without being masked by another.
    """
    name = "repair_criteria_under_test"
    spec = importlib.util.spec_from_file_location(name, ROOT / "src" / "arbolom" / "repair" / "criteria.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses need the module registered while executing
    try:
        spec.loader.exec_module(module)
    except Exception:
        if not allow_partial:
            raise
    finally:
        sys.modules.pop(name, None)
    return module


# --- Bugs ------------------------------------------------------------------

def test_module_imports():
    # Regression: RepairCriterion.combine() used to call RepairCriterion(optimize, disable, description),
    # dropping `name` and shifting every field by one. The combined criterion is then
    # registered under its optimize string, so CRITERIA["term-number"] raises KeyError
    # at import time and revision.py / benchmark.py cannot start.
    load_real_repair_criteria()


@pytest.mark.parametrize("name", ["term-number", "regulators", "signs", "term-format", "terms"])
def test_combined_criteria_are_registered_under_their_name(name):
    criteria = load_real_repair_criteria().CRITERIA
    assert name in criteria
    assert criteria[name].name == name


def test_basic_criterion_builds_minimize_statement():
    # Regression: from_expression() used to emit "#minimize{1@{p}, ...}." -- the outer braces are not
    # escaped, so build_optimize_statement() raises
    # "ValueError: unexpected '{' in field name" for every criterion.
    mod = load_real_repair_criteria(allow_partial=True)
    crit = mod.RepairCriterion.from_expression("x", ["C"], "activator(C)", "")
    assert crit.build_optimize_statement(3) == "#minimize{1@3, C : activator(C)}."
    assert crit.build_disable_statement() == ":- activator(C)."


def test_combine_preserves_fields():
    mod = load_real_repair_criteria(allow_partial=True)
    RC = mod.RepairCriterion
    a = RC("a", "#minimize{{1@{p}, C : activator(C)}}.", ":- activator(C).")
    b = RC("b", "#minimize{{1@{p}, C : inhibitor(C)}}.", ":- inhibitor(C).")
    combined = a.combine(b, "both", "desc")
    assert combined.name == "both"
    assert combined.description == "desc"
    assert combined.build_optimize_statement(7).count("#minimize") == 2
    assert combined.build_disable_statement().count(":-") == 2


# --- Characterisation --------------------------------------------------------

def test_priorities_follow_list_order():
    from arbolom.repair.criteria import build_asp_change_criteria
    asp = build_asp_change_criteria(["extra-regulators", "sign-to-inhibitor"])
    first, second = asp.strip().splitlines()
    assert "1@2" in first and "not regulates" in first
    assert "1@1" in second and "inhibitor(C)" in second


def test_unknown_criterion_rejected():
    from arbolom.repair.criteria import build_asp_change_criteria
    with pytest.raises(ValueError):
        build_asp_change_criteria(["nope"])


@pytest.fixture(scope="module")
def small_model():
    return bnet_to_lp("a, a\nb, b\nf, a & b\n")


def _all_criteria():
    from arbolom.repair.criteria import CRITERIA
    return sorted(CRITERIA)


@pytest.mark.parametrize("name", _all_criteria())
@pytest.mark.parametrize("encoding", ["repairs_sync.lp", "repairs_stable.lp", "deepening_search/repairs_sync.lp"])
def test_every_criterion_grounds_with_repair_encodings(name, encoding, small_model):
    """Each criterion's #minimize and disabling constraint must be valid, safe ASP."""
    from arbolom.repair.criteria import CRITERIA
    from arbolom.resources import ENCODINGS_DIR
    crit = CRITERIA[name]
    ctl = clingo.Control(["-c", "compound=f", "-c", "max_node_number=2", "-c", "node_number=2"],
                         logger=lambda *_: None)
    ctl.add("base", [], small_model)
    ctl.load(str(ENCODINGS_DIR / "repairs" / encoding))
    ctl.add("base", [], crit.build_optimize_statement(1))
    if crit.disable_constraints:
        ctl.add("base", [], crit.build_disable_statement())
    ctl.ground([("base", [])])
