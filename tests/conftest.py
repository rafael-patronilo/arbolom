"""Shared fixtures and helpers for the ARBoLoM test suite.

The encodings are located relative to the installed arbolom package, so the
tests no longer depend on the working directory.
"""
import logging
from pathlib import Path

import pytest

from arbolom.modes import UpdateMode

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers to build models / observations and drive the pipeline in-process,
# mirroring what ModelReviser.repair() does for a single model.
# ---------------------------------------------------------------------------

def bnet_to_lp(bnet: str) -> str:
    from arbolom.conversion import convert_model_to_lp
    return convert_model_to_lp(bnet.strip().splitlines(), logging.getLogger("test"))


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
    "stable": UpdateMode.STABLE,
    "sync": UpdateMode.SYNC,
    "async": UpdateMode.ASYNC,
}


@pytest.fixture
def write_obs(tmp_path):
    def _write(text: str, name="obs.lp") -> str:
        p = tmp_path / name
        p.write_text(text)
        return str(p)
    return _write


def find_inconsistencies(model: str, obs_path: str, mode: str):
    from arbolom.consistency import consistency_check, is_consistent
    update_mode = MODES[mode]
    atoms = consistency_check(model, obs_path, update_mode)
    return is_consistent(atoms, update_mode, print_consistent=False)


def inconsistent_functions(model: str, inconsistencies: str) -> list[str]:
    from arbolom.repair import preprocessing as rf
    return rf.process_inconsistent_functions(rf.generate_inconsistent_functions(model, inconsistencies)) or []


def repair_function(model, inconsistencies, func, mode, criteria,
                    disable=(), timeout=(60, 0), parallel_mode=None, cost_bounds=None):
    """Runs the per-function repair exactly as ModelReviser.repair() does."""
    from arbolom.repair import preprocessing, search
    update_mode = MODES[mode]
    prev = preprocessing.generate_previous_observations(func, inconsistencies, update_mode)
    upo = preprocessing.process_previous_observations(prev)
    return search.generate_functions(
        func, model, inconsistencies, upo, list(criteria), list(disable), timeout,
        update_mode, parallel_mode=parallel_mode, cost_bounds=cost_bounds)


DEFAULT_CRITERIA = ["term-number", "regulators", "signs", "term-format"]
