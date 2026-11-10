"""ARBoLoM - ASP-based Revision of Boolean Logical Models.

The package exports the same API as pymodrev (so `import arbolom as mrev` can
replace `import pymodrev as mrev`), plus ARBoLoM's own revision classes.
"""
from pymodrev.network.edge import Edge
from pymodrev.network.function import Function
from pymodrev.network.model import Model
from pymodrev.network.node import Node
from pymodrev.network.observation import Observation
from pymodrev.network.observation_set import ObservationSet

from arbolom.api import (
  Configuration,
  Session,
  clear_obs,
  config,
  is_consistent,
  model_from_dict,
  model_from_file,
  model_to_file,
  obs_async_reach,
  obs_async_ts,
  obs_notsteady,
  obs_steady,
  obs_sync_reach,
  obs_sync_ts,
  repair,
)
from arbolom.bridge import UnsupportedObservationsError
from arbolom.engine import RevisionEngine
from arbolom.modes import UpdateMode
from arbolom.revision import ModelReviser, RevisionResult, RevisionSettings

__all__ = [
  # pymodrev-compatible API
  "clear_obs",
  "obs_steady",
  "obs_notsteady",
  "obs_sync_ts",
  "obs_async_ts",
  "obs_sync_reach",
  "obs_async_reach",
  "model_from_dict",
  "model_from_file",
  "is_consistent",
  "repair",
  "model_to_file",

  "Edge",
  "Function",
  "Model",
  "Node",
  "Observation",
  "ObservationSet",

  # ARBoLoM
  "Configuration",
  "Session",
  "config",
  "ModelReviser",
  "RevisionEngine",
  "RevisionResult",
  "RevisionSettings",
  "UnsupportedObservationsError",
  "UpdateMode",
]
