"""Translation between pymodrev's data model and ARBoLoM's LP programs.

pymodrev (https://github.com/ptgm/pymodrev) represents models as Model objects
(nodes, signed edges and functions as lists of terms) and observations as
Observation objects tied to an updater (steady, sync, async, ...). ARBoLoM works
on LP programs:

  model:        compound(C). regulates(R,C,S). function(C,N). term(C,I,R).
                (S is 0 for activators and 1 for inhibitors, whereas pymodrev
                edge signs are 1 for positive and 0 for negative)
  observations: experiment(E). observation(E,C,V). (stable state)
                experiment(E). observation(E,T,C,V). (time series)

Nodes without a function are inputs in pymodrev; ARBoLoM represents inputs as
compounds regulated only by themselves, so they are translated as such.
Fixed edges are translated into fixed(R,C,S) facts, which forbid the repairs
from removing them or changing their sign.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import clingo
from pymodrev.network.edge import Edge
from pymodrev.network.function import Function
from pymodrev.network.inconsistency_solution import InconsistencySolution
from pymodrev.network.model import Model
from pymodrev.network.observation_set import ObservationSet
from pymodrev.network.repair_set import RepairSet

from arbolom.common import parse_atom
from arbolom.modes import UpdateMode

#pymodrev updater types supported by ARBoLoM, and the corresponding update modes
SUPPORTED_UPDATERS = {
  "steady": UpdateMode.STABLE,
  "sync": UpdateMode.SYNC,
  "async": UpdateMode.ASYNC,
}


class UnsupportedObservationsError(ValueError):
  """The observations cannot be handled by ARBoLoM (unsupported or mixed updaters)."""


_PLAIN_CONSTANT = re.compile(r"[a-z][A-Za-z0-9_']*|[0-9]+")


def asp_term(name: str) -> str:
  """ASP term for a node or experiment name: the name itself if it is a valid
  constant (or integer), otherwise a quoted string."""
  name = str(name)
  if _PLAIN_CONSTANT.fullmatch(name):
    return name
  return str(clingo.String(name))


def _edge_sign_to_lp(sign: int) -> int:
  return 0 if sign == 1 else 1


def _lp_sign_to_edge(sign: int) -> int:
  return 1 if sign == 0 else 0


@dataclass
class ModelTranslation:
  """A pymodrev Model translated into ARBoLoM's LP format."""
  model: Model
  lp: str
  #program with the constraints on the repairs (fixed edges)
  constraints_lp: str
  #node identifier -> ASP term
  terms: dict[str, str]
  #ASP term -> node identifier
  nodes: dict[str, str]
  #nodes without a function, translated as self-regulated inputs
  synthetic_inputs: set[str] = field(default_factory=set)

  @property
  def program(self) -> str:
    """The model program including the repair constraints."""
    return self.lp + self.constraints_lp

  def term(self, node_id: str) -> str:
    return self.terms[node_id]

  def node(self, term) -> str:
    """Node identifier of an ASP term (a string or a clingo Symbol)."""
    return self.nodes[str(term)]

  def fixed_nodes(self) -> set[str]:
    return {node_id for node_id, node in self.model.nodes.items() if node.is_fixed}


def model_to_lp(model: Model) -> ModelTranslation:
  """Translates a pymodrev Model into ARBoLoM's LP format."""
  terms = {node_id: asp_term(node_id) for node_id in model.nodes}
  nodes = {term: node_id for node_id, term in terms.items()}
  if len(nodes) != len(terms):
    raise ValueError("Distinct node identifiers map to the same ASP term")

  compounds = ["%Compounds"]
  functions = []
  constraints = []
  synthetic_inputs = set()
  for node_id, node in model.nodes.items():
    c = terms[node_id]
    compounds.append(f"compound({c}).")
    function = node.function
    term_ids = sorted(function.regulators_by_term) if function is not None else []
    if not term_ids or not function.regulators:
      # an input: ARBoLoM represents it as regulated only by itself
      synthetic_inputs.add(node_id)
      functions += [f"%Regulators of {c}", f"regulates({c}, {c}, 0).", "",
                    f"%Regulatory function of {c}", f"function({c}, 1).", f"term({c}, 1, {c}).", ""]
      continue
    functions.append(f"%Regulators of {c}")
    for regulator in function.regulators:
      edge = model.get_edge(regulator, node_id)
      functions.append(f"regulates({terms[regulator]}, {c}, {_edge_sign_to_lp(edge.sign)}).")
    functions += ["", f"%Regulatory function of {c}", f"function({c}, {len(term_ids)})."]
    for i, term_id in enumerate(term_ids, start=1):
      for regulator in function.regulators_by_term[term_id]:
        functions.append(f"term({c}, {i}, {terms[regulator]}).")
    functions.append("")

  for regulator_id, edges in model.graph.items():
    for edge in edges:
      if edge.is_fixed:
        constraints.append(f"fixed({terms[regulator_id]}, {terms[edge.end_node.identifier]}, "
                           f"{_edge_sign_to_lp(edge.sign)}).")
  constraints_lp = ("%Fixed edges\n" + "\n".join(constraints) + "\n") if constraints else ""

  lp = "\n".join(compounds) + "\n\n" + "\n".join(functions) + "\n"
  return ModelTranslation(model, lp, constraints_lp, terms, nodes, synthetic_inputs)


@dataclass
class ObservationsTranslation:
  """A pymodrev ObservationSet translated into ARBoLoM's LP format."""
  lp: str
  mode: UpdateMode
  #ASP term -> experiment (profile) identifier
  experiments: dict[str, str]

  def experiment(self, term) -> str:
    return self.experiments[str(term)]


def update_mode_of(observation_set: ObservationSet) -> UpdateMode:
  """The ARBoLoM update mode of a set of observations."""
  updater_types = sorted({updater.get_type() for updater in observation_set.updaters})
  if not updater_types:
    raise UnsupportedObservationsError("No observations were given")
  unsupported = [t for t in updater_types if t not in SUPPORTED_UPDATERS]
  if unsupported:
    raise UnsupportedObservationsError(
      f"ARBoLoM does not support observations with the updater(s) {', '.join(unsupported)}. "
      f"Supported updaters: {', '.join(SUPPORTED_UPDATERS)}")
  if len(updater_types) > 1:
    raise UnsupportedObservationsError(
      f"ARBoLoM revises models with observations of a single updater, got: {', '.join(updater_types)}")
  return SUPPORTED_UPDATERS[updater_types[0]]


def observations_to_lp(observation_set: ObservationSet, translation: ModelTranslation) -> ObservationsTranslation:
  """Translates a pymodrev ObservationSet into ARBoLoM's LP format."""
  mode = update_mode_of(observation_set)
  lines = []
  experiments = {}
  for observation in observation_set.observations:
    for exp_id in sorted(observation.experiments):
      e = asp_term(exp_id)
      if experiments.setdefault(e, exp_id) != exp_id:
        raise ValueError(f"Distinct experiment identifiers map to the same ASP term {e}")
      lines.append(f"experiment({e}).")
    for exp_id, time, node_id, value in observation.data:
      if node_id not in translation.terms:
        raise ValueError(f"Observation {exp_id} contains node {node_id} which is not in the model.")
      e, c = asp_term(exp_id), translation.term(node_id)
      if mode is UpdateMode.STABLE:
        lines.append(f"observation({e},{c},{int(value)}).")
      else:
        if time is None:
          raise UnsupportedObservationsError(f"Observation {exp_id} of {node_id} has no time step")
        lines.append(f"observation({e},{int(time)},{c},{int(value)}).")
  return ObservationsTranslation("\n".join(lines) + "\n", mode, experiments)


def _arguments(atom: str) -> list[clingo.Symbol]:
  return clingo.parse_term(atom.strip().rstrip('.')).arguments


def inconsistency_solution(inconsistencies: str, model_tr: ModelTranslation,
                           obs_tr: ObservationsTranslation) -> InconsistencySolution:
  """InconsistencySolution with the nodes and profiles of ARBoLoM's inconsistencies
  (the output of arbolom.consistency.is_consistent)."""
  solution = InconsistencySolution()
  for atom in inconsistencies.split("\n"):
    if not atom.startswith("inconsistent("):
      continue
    args = _arguments(atom)
    experiment = obs_tr.experiment(args[0])
    node_id = model_tr.node(args[-2])
    if args[-1].number == 0: # observed active, but the function evaluates to inactive
      solution.add_generalization(node_id)
    else:
      solution.add_particularization(node_id)
    if node_id not in solution.inconsistent_profiles.get(experiment, []):
      solution.add_inconsistent_profile(experiment, node_id)
  return solution


def repaired_function_terms(atoms: list[str], model_tr: ModelTranslation):
  """The terms (lists of node identifiers) and edge signs of a repaired function,
  from the atoms of ARBoLoM's repair encoding."""
  nodes: dict[int, list[str]] = {}
  signs: dict[str, int] = {}
  for atom in atoms:
    predicate, _ = parse_atom(atom)
    if predicate not in ("node_regulator", "regulator_activator", "regulator_inhibitor"):
      continue
    args = _arguments(atom)
    if predicate == "node_regulator":
      nodes.setdefault(args[0].number, []).append(model_tr.node(args[1]))
    else:
      signs[model_tr.node(args[0])] = 1 if predicate == "regulator_activator" else 0
  terms = [regulators for _, regulators in sorted(nodes.items())]
  return terms, signs


def repair_set(node_id: str, atoms: list[str], model_tr: ModelTranslation) -> RepairSet:
  """RepairSet that turns the function of node_id in the pymodrev model into
  the function repaired by ARBoLoM: added/removed edges for added/removed
  regulators, flipped edges for regulators whose sign changed and a repaired
  function if the terms changed."""
  model = model_tr.model
  node = model.get_node(node_id)
  terms, signs = repaired_function_terms(atoms, model_tr)

  original = node.function
  if node_id in model_tr.synthetic_inputs:
    original_regulators, original_terms = set(), set()
  else:
    original_regulators = set(original.regulators)
    original_terms = {frozenset(regs) for regs in original.regulators_by_term.values()}
  new_regulators = {r for term in terms for r in term}

  rs = RepairSet()
  for regulator in sorted(new_regulators - original_regulators):
    rs.add_edge(Edge(model.get_node(regulator), node, signs[regulator]))
  for regulator in sorted(original_regulators - new_regulators):
    rs.remove_edge(Edge(model.get_node(regulator), node, model.get_edge(regulator, node_id).sign))
  for regulator in sorted(original_regulators & new_regulators):
    sign = model.get_edge(regulator, node_id).sign
    if sign != signs[regulator]:
      # pymodrev records flipped edges with their original sign
      rs.add_flipped_edge(Edge(model.get_node(regulator), node, sign))
  if {frozenset(term) for term in terms} != original_terms:
    function = Function(node_id)
    for i, term in enumerate(terms, start=1):
      for regulator in term:
        function.add_regulator_to_term(i, regulator)
    rs.add_repaired_function(function)
  return rs
