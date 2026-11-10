# This file is adapted from pymodrev's test suite: https://github.com/ptgm/pymodrev
# (tests/test_observation_set.py at commit d2fb450c714ede82181942fdda5ccce5ad1b1bc8, the code released as pymodrev 0.5.8).
# Copyright (c) the pymodrev authors: Filipe Gouveia, Antonio Romeu and Pedro T. Monteiro.
# pymodrev is distributed under the MIT License (as declared in its pyproject.toml).
# Unchanged: it tests pymodrev's data model, which ARBoLoM uses for its pymodrev-compatible API.

import pytest
from pymodrev.network.observation_set import ObservationSet
from pymodrev.network.observation import Observation
from pymodrev.updaters.steady_updater import SteadyUpdater
from pymodrev.network.exceptions import ParseError


@pytest.fixture
def observation_set():
    return ObservationSet()


def test_add_observation(observation_set):
    updater = SteadyUpdater()
    obs = Observation(updater)
    obs.experiments.add('exp1')
    observation_set.add_observation(obs)
    assert obs in observation_set.observations


def test_get_observation_updater(observation_set):
    updater = SteadyUpdater()
    obs = Observation(updater)
    obs.experiments.add('exp1')
    observation_set.add_observation(obs)
    assert updater == observation_set.get_observation_updater('exp1')


def test_duplicated_observation(observation_set):
    updater = SteadyUpdater()
    obs = Observation(updater)
    obs.experiments.add('exp1')
    observation_set.add_observation(obs)
    with pytest.raises(ParseError):
        observation_set.add_observation(obs)
