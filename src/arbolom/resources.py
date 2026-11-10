"""Locations of the ASP encodings shipped with the package.

The encodings used to be loaded through paths relative to the repository root,
which only worked when running from it. They are now resolved relative to the
installed package.
"""
from pathlib import Path

from arbolom.modes import UpdateMode

ENCODINGS_DIR = Path(__file__).resolve().parent / "encodings"


def encoding_path(*parts: str) -> str:
  """Absolute path (as a string, which is what clingo expects) of an encoding."""
  return str(ENCODINGS_DIR.joinpath(*parts))


CONSISTENCY_ENCODINGS = {
  UpdateMode.STABLE: encoding_path("consistency", "ss_consistency.lp"),
  UpdateMode.SYNC: encoding_path("consistency", "sync_consistency.lp"),
  UpdateMode.ASYNC: encoding_path("consistency", "async_consistency.lp"),
}

OBSERVATION_GENERATION_ENCODINGS = {
  UpdateMode.SYNC: encoding_path("observations", "sync_observations.lp"),
  UpdateMode.ASYNC: encoding_path("observations", "async_observations.lp"),
}

INCONSISTENT_FUNCTIONS_ENCODING = encoding_path("repairs", "auxiliary", "inconsistent_functions.lp")

PREVIOUS_OBSERVATIONS_ENCODINGS = {
  UpdateMode.STABLE: encoding_path("repairs", "auxiliary", "previous_observations_stable.lp"),
  UpdateMode.SYNC: encoding_path("repairs", "auxiliary", "previous_observations_sync.lp"),
  UpdateMode.ASYNC: encoding_path("repairs", "auxiliary", "previous_observations_async.lp"),
}

REPAIR_ENCODINGS = {
  UpdateMode.STABLE: encoding_path("repairs", "repairs_stable.lp"),
  UpdateMode.SYNC: encoding_path("repairs", "repairs_sync.lp"),
  UpdateMode.ASYNC: encoding_path("repairs", "repairs_async.lp"),
}

DEEPENING_SEARCH_REPAIR_ENCODINGS = {
  UpdateMode.STABLE: encoding_path("repairs", "deepening_search", "repairs_stable.lp"),
  UpdateMode.SYNC: encoding_path("repairs", "deepening_search", "repairs_sync.lp"),
  UpdateMode.ASYNC: encoding_path("repairs", "deepening_search", "repairs_async.lp"),
}
