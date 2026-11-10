"""Update modes (interaction types) supported by ARBoLoM."""
from enum import Enum


class UpdateMode(Enum):
  """How observations relate to the model's dynamics.

  Replaces the former ``toggle_stable_state``/``toggle_sync``/``toggle_async``
  flag triple: exactly one mode is always selected.
  """
  STABLE = "stable"
  SYNC = "sync"
  ASYNC = "async"

  @classmethod
  def from_flags(cls, stable=False, sync=False, async_=False) -> "UpdateMode":
    """Mode selected by the -stable/-sync/-async command line flags.

    The first flag set wins, in that order; stable state is the default.
    """
    if stable:
      return cls.STABLE
    if sync:
      return cls.SYNC
    if async_:
      return cls.ASYNC
    return cls.STABLE

  @property
  def is_time_series(self) -> bool:
    return self is not UpdateMode.STABLE

  @property
  def description(self) -> str:
    return {
      UpdateMode.STABLE: "Stable State \U0001f6d1",
      UpdateMode.SYNC: "Synchronous \U0001f550",
      UpdateMode.ASYNC: "Asynchronous \U0001f331",
    }[self]
