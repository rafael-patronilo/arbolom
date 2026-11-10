# This file is adapted from pymodrev's test suite: https://github.com/ptgm/pymodrev
# (tests/test_updater_factory.py at commit d2fb450c714ede82181942fdda5ccce5ad1b1bc8, the code released as pymodrev 0.5.8).
# Copyright (c) the pymodrev authors: Filipe Gouveia, Antonio Romeu and Pedro T. Monteiro.
# pymodrev is distributed under the MIT License (as declared in its pyproject.toml).
# Unchanged: it tests pymodrev's data model, which ARBoLoM uses for its pymodrev-compatible API.

from pymodrev.updaters.factory import get_available_updaters, get_updater, is_valid_updater_type
from pymodrev.updaters.async_updater import AsyncUpdater
from pymodrev.updaters.complete_updater import CompleteUpdater
from pymodrev.updaters.notsteady_updater import NotsteadyUpdater
from pymodrev.updaters.reachasync_updater import ReachasyncUpdater
from pymodrev.updaters.reachsync_updater import ReachsyncUpdater
from pymodrev.updaters.steady_updater import SteadyUpdater
from pymodrev.updaters.sync_updater import SyncUpdater

_EXPECTED_UPDATERS = [
    "steady", "sync", "async", "complete", "notsteady", "reachasync", "reachsync"
]

def test_discovered_updater_types_match_declared_types():
    discovered_types = set(get_available_updaters().keys())
    assert discovered_types == set(_EXPECTED_UPDATERS)


def test_is_valid_updater_type():
    for updater_type in _EXPECTED_UPDATERS:
        assert is_valid_updater_type(updater_type)
    assert not is_valid_updater_type("invalid")


def test_get_updater_returns_expected_type_instance():
    assert get_updater("steady").__class__.__name__ == SteadyUpdater.__name__
    assert get_updater("sync").__class__.__name__ == SyncUpdater.__name__
    assert get_updater("async").__class__.__name__ == AsyncUpdater.__name__
    assert get_updater("complete").__class__.__name__ == CompleteUpdater.__name__
    assert get_updater("notsteady").__class__.__name__ == NotsteadyUpdater.__name__
    assert get_updater("reachasync").__class__.__name__ == ReachasyncUpdater.__name__
    assert get_updater("reachsync").__class__.__name__ == ReachsyncUpdater.__name__


def test_get_updater_raises_for_unknown_type():
    try:
        get_updater("invalid")
        assert False, "Expected ValueError for invalid updater type"
    except ValueError as exc:
        assert "Updater 'invalid' not found" in str(exc)
