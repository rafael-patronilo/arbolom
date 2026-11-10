"""ARBoLoM's consistency checking and repair applied to pymodrev models and
observations, with results expressed in pymodrev's data model."""
from __future__ import annotations

import copy
import dataclasses
import json
import logging
from collections import OrderedDict, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass

from pymodrev.configuration import config as pymodrev_config
from pymodrev.network.inconsistency_solution import InconsistencySolution
from pymodrev.network.model import Model
from pymodrev.network.observation_set import ObservationSet
from pymodrev.repair.consistency import consistency_to_str
from pymodrev.repair.repair import apply_repair

from arbolom.bridge import (ModelTranslation, ObservationsTranslation, inconsistency_solution,
                            model_to_lp, observations_to_lp, repair_set)
from arbolom.lp_model import format_model_dict, model_to_dict
from arbolom.revision import (SUBOPTIMALLY_REPAIRED, FunctionRepair, ModelReviser,
                              RevisionSettings)

logger = logging.getLogger(__name__)


@contextmanager
def pymodrev_output_format(output_format: str):
  """Temporarily sets the output format of pymodrev's formatters (which read it
  from pymodrev's global configuration): 'c' compact, 'j' json or 'h' human-readable."""
  previous = pymodrev_config.format
  pymodrev_config.format = output_format
  try:
    yield
  finally:
    pymodrev_config.format = previous


@dataclass
class ConsistencyOutcome:
  """Result of checking the consistency of a pymodrev model."""
  model_translation: ModelTranslation
  observations_translation: ObservationsTranslation
  #inconsistencies and curated observations in LP format (None if consistent)
  inconsistencies: str | None
  #the inconsistent nodes and profiles (None if consistent)
  solution: InconsistencySolution | None

  @property
  def consistent(self) -> bool:
    return self.inconsistencies is None

  @property
  def optimization(self) -> int:
    """pymodrev's optimization value: 0 if consistent, otherwise the number of inconsistent nodes."""
    return 0 if self.consistent else max(1, len(self.solution.inconsistent_nodes))

  def to_str(self, output_format: str = 'h') -> str:
    with pymodrev_output_format(output_format):
      return consistency_to_str([] if self.consistent else [self.solution], self.optimization)


@dataclass
class RepairOutcome:
  """Result of repairing a pymodrev model."""
  model: Model
  consistency: ConsistencyOutcome
  #the inconsistent nodes with their repair sets
  solution: InconsistencySolution
  final_state: str
  #FunctionRepair of each inconsistent node (by node identifier)
  function_repairs: dict[str, FunctionRepair]

  @property
  def possible(self) -> bool:
    """Whether every inconsistent node was repaired."""
    return not self.solution.has_impossibility

  @property
  def suboptimal(self) -> bool:
    """Whether some repair is not proven optimal (its search timed out)."""
    return any(fr.state == SUBOPTIMALLY_REPAIRED for fr in self.function_repairs.values())

  def to_str(self, output_format: str = 'h', subopt: bool | None = None) -> str:
    """The repairs in pymodrev's output format ('' if the model could not be repaired)."""
    if not self.possible:
      return ""
    if subopt is None:
      subopt = self.suboptimal
    with pymodrev_output_format(output_format):
      return self.solution.solution_to_str(self.model, subopt)

  def details(self) -> dict:
    """The repairs in pymodrev's JSON structure ({} if the model could not be repaired)."""
    if not self.possible:
      return {}
    return json.loads(self.solution.solution_to_json_str(self.model, self.suboptimal))

  def repaired_models(self) -> list[Model]:
    """Copies of the model with the repairs applied ([] if the model could not be repaired)."""
    if not self.possible or not self.solution.inconsistent_nodes:
      return []
    repaired = copy.deepcopy(self.model)
    apply_repair(repaired, self.solution)
    return [repaired]


class RevisionEngine:
  """Checks the consistency of pymodrev models and repairs them with ARBoLoM.

  The update mode of the settings is ignored: it is determined by the
  updaters of the observations (steady, sync or async).
  """

  def __init__(self, settings: RevisionSettings | None = None):
    self.settings = settings if settings is not None else RevisionSettings(quiet=True)

  def _reviser(self, obs_tr: ObservationsTranslation) -> ModelReviser:
    return ModelReviser(dataclasses.replace(self.settings, mode=obs_tr.mode))

  def check_consistency(self, model: Model, observation_set: ObservationSet) -> ConsistencyOutcome:
    model_tr = model_to_lp(model)
    obs_tr = observations_to_lp(observation_set, model_tr)
    inconsistencies = self._reviser(obs_tr).check_consistency(model_tr.program, obs_tr.lp, observations_are_path=False)
    solution = None if inconsistencies is None else inconsistency_solution(inconsistencies, model_tr, obs_tr)
    return ConsistencyOutcome(model_tr, obs_tr, inconsistencies, solution)

  def repair(self, model: Model, observation_set: ObservationSet,
             consistency: ConsistencyOutcome | None = None) -> RepairOutcome:
    """Repairs the inconsistent nodes of the model.

    consistency - a previous consistency check of this model and observations, to reuse
    """
    if consistency is None:
      consistency = self.check_consistency(model, observation_set)
    else:
      # the translations depend only on the node identifiers, so the
      # inconsistencies of a previous check remain valid for this model
      consistency = dataclasses.replace(consistency, model_translation=model_to_lp(model),
                                        solution=copy.deepcopy(consistency.solution))
    model_tr = consistency.model_translation
    if consistency.consistent:
      return RepairOutcome(model, consistency, InconsistencySolution(), "consistent", {})

    reviser = self._reviser(consistency.observations_translation)
    solution = consistency.solution
    model_dict = model_to_dict(model_tr.program)
    stats = defaultdict(OrderedDict)
    function_repairs: dict[str, FunctionRepair] = {}
    fixed = {model_tr.term(node_id) for node_id in model_tr.fixed_nodes()}
    final_state = reviser.repair(model_tr.program, consistency.inconsistencies, stats, model_dict,
                                 function_repairs, skip_functions=fixed)

    repairs_by_node = {model_tr.node(term): fr for term, fr in function_repairs.items()}
    for node_id in solution.inconsistent_nodes:
      function_repair = repairs_by_node.get(node_id)
      if function_repair is None or not function_repair.repaired:
        logger.warning(f"Node {node_id} could not be repaired"
                       + (f" ({function_repair.state})" if function_repair else ""))
        solution.has_impossibility = True
        continue
      solution.add_repair_set(node_id, repair_set(node_id, function_repair.atoms, model_tr))

    outcome = RepairOutcome(model, consistency, solution, final_state, repairs_by_node)
    if reviser.settings.sanity_checks and outcome.possible:
      repaired_lp = format_model_dict(model_dict) + model_tr.constraints_lp
      remaining = reviser.check_consistency(repaired_lp, consistency.observations_translation.lp,
                                            observations_are_path=False)
      if remaining:
        raise Exception(f"State {final_state} is wrong: inconsistencies found in the repaired model.")
    return outcome
