"""High-level API, compatible with pymodrev's (pymodrev.api).

The functions mirror pymodrev's API, using pymodrev's data model (Model,
Observation, ...), so that ARBoLoM can be used as a drop-in replacement:

    import arbolom as mrev
    model = mrev.model_from_file("model.bnet")
    mrev.obs_sync_ts("p1", {0: {"a": 1, "b": 0}, 1: {"a": 1, "b": 1}})
    print(mrev.is_consistent(model, ["p1"]))
    repaired_models, details = mrev.repair(model)

Like pymodrev, the module-level functions keep the registered observations
and the last consistency result between calls. That state lives in a Session
object (the default session) instead of in module globals; independent
Session instances can be created for isolated use, and ARBoLoM's revision
settings (criteria, timeout, ...) are set through Session.settings.

Differences with pymodrev:
  - only steady, sync and async observations are supported (and a single
    updater per check); notsteady, reachability and complete observations can
    be registered but checking them raises UnsupportedObservationsError
  - ARBoLoM computes one optimal repair per inconsistent node (according to the
    change minimization criteria), so repair() returns at most one model
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import List, Mapping, Tuple

from pymodrev.network.model import Model
from pymodrev.network.observation import Observation
from pymodrev.network.observation_set import ObservationSet
from pymodrev.parsers.boolean_expression import add_positive_autoregulation, parse_and_minimise_expression
from pymodrev.updaters.factory import get_updater

from arbolom.engine import ConsistencyOutcome, RevisionEngine
from arbolom.formats import MODREV_LP, read_model_file, write_model_file
from arbolom.revision import RevisionSettings


@dataclass
class Configuration:
  """Settings of the pymodrev-compatible API and CLI (mirrors pymodrev.configuration.Configuration)."""
  task: str = 'r'          # c - check consistency, r - get repairs, m - get repaired models
  format: str = 'h'        # c - compact, j - json, h - human-readable
  solutions: int = 1
  debug: bool = False
  force_optimum: bool = False
  fixed_nodes: List[str] = field(default_factory=list)
  fixed_edges: List[str] = field(default_factory=list)
  input_filename: str = ""

  def __getitem__(self, key):
    return getattr(self, key)

  def __setitem__(self, key, value):
    setattr(self, key, value)


#-----Models-----
def _coerce_expression(expression) -> str:
  if isinstance(expression, (bool, int)):
    return "1" if expression else "0"
  return expression if isinstance(expression, str) else str(expression)


def model_from_dict(model_definition: Mapping[str, object]) -> Model:
  """Build a model from a node-to-expression mapping.

  The Boolean expressions are parsed and simplified to extract the
  edges and corresponding signs, before being stored in the model.
  """
  network = Model()

  for node_id in model_definition.keys():
    network.add_node(str(node_id))

  for node_id, expression in model_definition.items():
    target = str(node_id)
    target_node = network.get_node(target)

    expression_text = _coerce_expression(expression).strip()
    if expression_text in ("0", "1"):
      if expression_text == "1":
        add_positive_autoregulation(network, target_node, target)
      continue

    parse_and_minimise_expression(network, target_node, target, expression_text)

  return network


def model_from_file(filepath: os.PathLike[str] | str) -> Model:
  """Load a model from a supported file format (.bnet, .zginml, .ginml, .lp).

  .lp files may use either ModRev's format or ARBoLoM's format.
  """
  return read_model_file(filepath)


def model_to_file(model: Model, filepath: os.PathLike[str] | str, lp_format: str = MODREV_LP) -> None:
  """Write a model to disk (lp_format selects ModRev's or ARBoLoM's format for .lp files)."""
  write_model_file(model, filepath, lp_format)


#-----Observations-----
def _add_observation_value(observation: Observation, obs_id: str,
    time, node_id: str, value: str | int) -> None:
  if value is None:
    return
  if isinstance(value, str):
    normalized = value.strip().lower()
    if normalized in ("", "na", "n/a", "nan", "*", "-"):
      return # ignore: no restriction on this (obs_id,node_id)
    elif normalized in ("1", "true", "t", "yes", "y"):
      value = 1
    elif normalized in ("0", "false", "f", "no", "n"):
      value = 0
    else:
      raise ValueError(f"Invalid observation '{obs_id}' value: '{node_id}' = '{value}'")
  observation.add_data(obs_id, time, node_id, value)

def _single_state_obs(obs_id: str, data: Mapping[str, str | int], updater_type: str) -> Observation:
  observation = Observation(get_updater(updater_type))
  for node_id, value in data.items():
    _add_observation_value(observation, obs_id, None, node_id, value)
  return observation

def _multiple_state_obs(obs_id: str, data: Mapping, updater_type: str) -> Observation:
  observation = Observation(get_updater(updater_type))

  if data and all(isinstance(value, Mapping) for value in data.values()):
    for time, values in data.items():
      if not isinstance(time, int) and (not isinstance(time, str) or time not in {"init", "final"}):
        raise ValueError(f"Invalid observation time '{time}' for '{obs_id}'")
      for node_id, value in values.items():
        _add_observation_value(observation, obs_id, time, node_id, value)
  else:
    for node_id, value in data.items():
      _add_observation_value(observation, obs_id, None, node_id, value)

  return observation


class Session:
  """Registered observations, settings and the last consistency result.

  settings - ARBoLoM's revision settings (criteria, timeout, parallel mode,
    sanity checks); the update mode is taken from the observations.
  """

  def __init__(self, settings: RevisionSettings | None = None, config: Configuration | None = None):
    self.settings = settings if settings is not None else RevisionSettings(quiet=True)
    self.config = config if config is not None else Configuration()
    self.observation_set = ObservationSet()
    self._last_observation_names: List[str] | None = None
    self._last_consistency: ConsistencyOutcome | None = None

  @property
  def engine(self) -> RevisionEngine:
    return RevisionEngine(self.settings)

  def clear_obs(self) -> None:
    """Remove all registered observations (and the last consistency result)."""
    self.observation_set = ObservationSet()
    self._last_observation_names = None
    self._last_consistency = None

  def add_observation(self, observation: Observation) -> None:
    self.observation_set.add_observation(observation)

  def obs_steady(self, obs_id: str, state: Mapping[str, str | int]) -> None:
    """Register a named steady-state observation from a dictionary of nodes and their values."""
    self.add_observation(_single_state_obs(obs_id, state, "steady"))

  def obs_notsteady(self, obs_id: str, state: Mapping[str, int]) -> None:
    """Register a named notsteady-state observation (not supported by ARBoLoM's revision)."""
    self.add_observation(_single_state_obs(obs_id, state, "notsteady"))

  def obs_sync_ts(self, obs_id: str, data: Mapping[str|int, Mapping[str, int]]) -> None:
    """Register a named synchronous time-series observation from a dictionary of time points to node-value mappings."""
    self.add_observation(_multiple_state_obs(obs_id, data, "sync"))

  def obs_async_ts(self, obs_id: str, data: Mapping[str|int, Mapping[str, int]]) -> None:
    """Register a named asynchronous time-series observation from a dictionary of time points to node-value mappings."""
    self.add_observation(_multiple_state_obs(obs_id, data, "async"))

  def obs_sync_reach(self, obs_id: str, data_init: Mapping[str, int], data_final: Mapping[str, int]) -> None:
    """Register a named synchronous reachability observation (not supported by ARBoLoM's revision)."""
    self.add_observation(_multiple_state_obs(obs_id, {"init": data_init, "final": data_final}, "reachsync"))

  def obs_async_reach(self, obs_id: str, data_init: Mapping[str, int], data_final: Mapping[str, int]) -> None:
    """Register a named asynchronous reachability observation (not supported by ARBoLoM's revision)."""
    self.add_observation(_multiple_state_obs(obs_id, {"init": data_init, "final": data_final}, "reachasync"))

  def _subset_observations(self, observation_names: List[str] | None) -> ObservationSet:
    if observation_names is None:
      return self.observation_set

    subset = ObservationSet()
    for observation_name in observation_names:
      observation = self.observation_set.observations_dictionary.get(observation_name)
      if observation is None:
        raise KeyError(f"Observation '{observation_name}' is not registered")
      if observation not in subset.observations:
        subset.add_observation(observation)
    return subset

  def is_consistent(self, model: Model, observation_names: List[str] | str, sol: int = 1) -> dict:
    """Check whether a model is consistent with the selected observations.

    Returns pymodrev's JSON result: {"consistent": true} or
    {"consistent": false, "inconsistencies": [{"nodes": [...], "profiles": [...]}]}
    """
    if sol not in (1, 2, 3, 4):
      raise ValueError("sol must be one of: 1, 2, 3, 4")
    self.config.solutions = sol
    self.config.format = 'j'

    if not observation_names:
      raise ValueError("At least one observation name must be provided")
    if isinstance(observation_names, str):
      observation_names = [observation_names]
    observation_set = self._subset_observations(observation_names)

    outcome = self.engine.check_consistency(model, observation_set)
    self._last_observation_names = observation_names
    self._last_consistency = outcome
    return json.loads(outcome.to_str('j'))

  def repair(self, model: Model, obs_names: List[str] | str | None = None,
             use_consistency: bool = False) -> Tuple[List[Model], dict]:
    """Compute and apply repair solutions for a model.

    By default this method recomputes consistency for the provided model
    before searching for repairs. If ``use_consistency`` is True, it reuses the
    cached inconsistency result from the previous ``is_consistent`` call.

    Returns the repaired models and the repairs in pymodrev's JSON structure
    (([], {}) if the model is consistent or could not be repaired).
    """
    if obs_names is not None:
      if isinstance(obs_names, str):
        obs_names = [obs_names]
      self._last_observation_names = obs_names
    elif not self._last_observation_names:
      raise ValueError("is_consistent() method must be run before")

    observation_set = self._subset_observations(self._last_observation_names)

    if use_consistency:
      if self._last_consistency is None:
        raise ValueError("No previous consistency result available; run is_consistent() first")
      consistency = self._last_consistency
    else:
      consistency = self._last_consistency = self.engine.check_consistency(model, observation_set)

    if consistency.consistent:
      return [], {}

    self.config.task = 'r'
    self.config.format = 'j'
    outcome = self.engine.repair(model, observation_set, consistency)
    return outcome.repaired_models(), outcome.details()


#-----Module-level API (pymodrev compatible), backed by a default session-----
_default_session = Session()

#Configuration of the default session (like pymodrev.configuration.config)
config = _default_session.config


def default_session() -> Session:
  """The session used by the module-level functions."""
  return _default_session

def clear_obs() -> None:
  """Remove all observations stored in the default session."""
  _default_session.clear_obs()

def obs_steady(obs_id: str, state: Mapping[str, str | int]) -> None:
  """Register a named steady-state observation from a dictionary of nodes and their values."""
  _default_session.obs_steady(obs_id, state)

def obs_notsteady(obs_id: str, state: Mapping[str, int]) -> None:
  """Register a named notsteady-state observation (not supported by ARBoLoM's revision)."""
  _default_session.obs_notsteady(obs_id, state)

def obs_sync_ts(obs_id: str, data: Mapping[str|int, Mapping[str, int]]) -> None:
  """Register a named synchronous time-series observation from a dictionary of time points to node-value mappings."""
  _default_session.obs_sync_ts(obs_id, data)

def obs_async_ts(obs_id: str, data: Mapping[str|int, Mapping[str, int]]) -> None:
  """Register a named asynchronous time-series observation from a dictionary of time points to node-value mappings."""
  _default_session.obs_async_ts(obs_id, data)

def obs_sync_reach(obs_id: str, data_init: Mapping[str, int], data_final: Mapping[str, int]) -> None:
  """Register a named synchronous reachability observation (not supported by ARBoLoM's revision)."""
  _default_session.obs_sync_reach(obs_id, data_init, data_final)

def obs_async_reach(obs_id: str, data_init: Mapping[str, int], data_final: Mapping[str, int]) -> None:
  """Register a named asynchronous reachability observation (not supported by ARBoLoM's revision)."""
  _default_session.obs_async_reach(obs_id, data_init, data_final)

def is_consistent(model: Model, observation_names: List[str] | str, sol: int = 1) -> dict:
  """Check whether a model is consistent with the selected observations."""
  return _default_session.is_consistent(model, observation_names, sol)

def repair(model: Model, obs_names: List[str] | str | None = None,
           use_consistency: bool = False) -> Tuple[List[Model], dict]:
  """Compute and apply repair solutions for a model."""
  return _default_session.repair(model, obs_names, use_consistency)
