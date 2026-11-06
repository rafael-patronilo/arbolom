"""Shared fixtures and helpers for the ARBoLoM test suite.

Notes
-----
* All encodings are referenced by paths relative to the repository root, so
  every test runs with the repository root as the working directory.
* ``aux_scripts/repair_criteria.py`` currently has two bugs (see
  ``test_repair_criteria.py``): it raises ``KeyError`` at import time, and
  every criterion's ``#minimize`` template fails ``str.format``. Because every
  repair goes through that module, those bugs would turn the whole suite into
  the same two errors and hide everything else. While the buggy snippets are
  present, we load a copy with exactly those snippets fixed, so the remaining
  tests exercise their own code paths. ``test_repair_criteria.py`` always tests
  the real file. Once both bugs are fixed this shim does nothing.
"""
import importlib
import logging
import os
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

_CRITERIA_SHIM_ACTIVE = False

_KNOWN_CRITERIA_BUGS = {
    # combine() drops `name` and shifts every positional field
    "return RepairCriterion(combined_optimize_format, combined_disable_constraints, description)":
    "return RepairCriterion(name, combined_optimize_format, combined_disable_constraints, description)",
    # braces of #minimize{...} are not escaped for the later str.format(p=...)
    """f"#minimize{{1@{{p}}, {', '.join(variables)} : {expression}}}." """.strip():
    """f"#minimize{{{{1@{{p}}, {', '.join(variables)} : {expression}}}}}." """.strip(),
}


def _install_repair_criteria_shim():
    global _CRITERIA_SHIM_ACTIVE
    path = ROOT / "aux_scripts" / "repair_criteria.py"
    src = path.read_text()
    patched = src
    for buggy, fixed in _KNOWN_CRITERIA_BUGS.items():
        patched = patched.replace(buggy, fixed)
    if patched == src:
        return
    module = types.ModuleType("aux_scripts.repair_criteria")
    module.__file__ = str(path)
    sys.modules["aux_scripts.repair_criteria"] = module
    exec(compile(patched, str(path), "exec"), module.__dict__)
    importlib.import_module("aux_scripts").repair_criteria = module
    _CRITERIA_SHIM_ACTIVE = True


_install_repair_criteria_shim()


def pytest_report_header(config):
    if _CRITERIA_SHIM_ACTIVE:
        return ("NOTE: aux_scripts/repair_criteria.py has known bugs; tests outside "
                "test_repair_criteria.py use a patched copy (see tests/conftest.py).")


@pytest.fixture(autouse=True)
def _repo_root_cwd(monkeypatch):
    monkeypatch.chdir(ROOT)


# ---------------------------------------------------------------------------
# Helpers to build models / observations and drive the pipeline in-process,
# mirroring what revision.repair() does for a single model.
# ---------------------------------------------------------------------------

def bnet_to_lp(bnet: str) -> str:
    from aux_scripts.conversion_functions import convertModelToLP
    return convertModelToLP(bnet.strip().splitlines(), logging.getLogger("test"))


def stable_obs(experiments: list[dict[str, int]]) -> str:
    lines = []
    for e, state in enumerate(experiments, start=1):
        lines.append(f"experiment({e}).")
        lines += [f"observation({e},{c},{v})." for c, v in state.items()]
    return "\n".join(lines) + "\n"


def timeseries_obs(experiments: list[list[dict[str, int]]]) -> str:
    lines = []
    for e, trajectory in enumerate(experiments, start=1):
        lines.append(f"experiment({e}).")
        for t, state in enumerate(trajectory):
            lines += [f"observation({e},{t},{c},{v})." for c, v in state.items()]
    return "\n".join(lines) + "\n"


MODES = {
    "stable": (True, False, False),
    "sync": (False, True, False),
    "async": (False, False, True),
}


@pytest.fixture
def write_obs(tmp_path):
    def _write(text: str, name="obs.lp") -> str:
        p = tmp_path / name
        p.write_text(text)
        return str(p)
    return _write


def find_inconsistencies(model: str, obs_path: str, mode: str):
    from aux_scripts.consistency_functions import consistencyCheck, isConsistent
    flags = MODES[mode]
    atoms = consistencyCheck(model, obs_path, *flags)
    return isConsistent(atoms, *flags, print_consistent=False)


def inconsistent_functions(model: str, inconsistencies: str) -> list[str]:
    from aux_scripts import repair_functions as rf
    return rf.processInconsistentFunctions(rf.generateInconsistentFunctions(model, inconsistencies)) or []


def repair_function(model, inconsistencies, func, mode, criteria,
                    disable=(), timeout=(60, 0), parallel_mode=None):
    """Runs the per-function repair exactly as revision.repair() does."""
    from aux_scripts import repair_functions as rf
    stable, sync, async_ = MODES[mode]
    prev = rf.generatePreviousObservations(func, inconsistencies, sync, async_)
    upo = rf.processPreviousObservations(prev)
    return rf.generateFunctions(
        func, model, inconsistencies, upo, list(criteria), list(disable), timeout,
        stable, sync, async_, parallel_mode=parallel_mode)


DEFAULT_CRITERIA = ["term-number", "regulators", "signs", "term-format"]
