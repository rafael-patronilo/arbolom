"""Shared fixtures and helpers for the ARBoLoM test suite.

All encodings are referenced by paths relative to the repository root, so
every test runs with the repository root as the working directory.
"""
import logging
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)


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
                    disable=(), timeout=(60, 0), parallel_mode=None, cost_bounds=None):
    """Runs the per-function repair exactly as revision.repair() does."""
    from aux_scripts import repair_functions as rf
    stable, sync, async_ = MODES[mode]
    prev = rf.generatePreviousObservations(func, inconsistencies, sync, async_)
    upo = rf.processPreviousObservations(prev)
    return rf.generateFunctions(
        func, model, inconsistencies, upo, list(criteria), list(disable), timeout,
        stable, sync, async_, parallel_mode=parallel_mode, cost_bounds=cost_bounds)


DEFAULT_CRITERIA = ["term-number", "regulators", "signs", "term-format"]
