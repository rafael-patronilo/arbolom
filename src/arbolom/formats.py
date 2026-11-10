"""Reading and writing models and observations as pymodrev objects.

Besides the formats supported by pymodrev (models: .bnet, .lp in ModRev's
format, .ginml/.zginml; observations: .lp in ModRev's format, .csv, .xls,
.xlsx), ARBoLoM's own LP formats are supported:

  model:        compound(C). regulates(R,C,S). function(C,N). term(C,I,R).
  observations: experiment(E). observation(E,C,V). / observation(E,T,C,V).

.lp files are recognized as ARBoLoM's format by their content.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import clingo
from pymodrev.network.model import Model
from pymodrev.network.observation import Observation
from pymodrev.parsers.parser_factory import get_parser
from pymodrev.parsers.parser_observation import get_observation_parser
from pymodrev.updaters.updater import Updater

from arbolom.bridge import model_to_lp

ARBOLOM_LP = "arbolom"
MODREV_LP = "modrev"


def _symbol_name(symbol: clingo.Symbol) -> str:
  if symbol.type == clingo.SymbolType.String:
    return symbol.string
  return str(symbol)


def _facts(text: str) -> list[clingo.Symbol]:
  ctl = clingo.Control(["--warn=none"])
  ctl.add("base", [], text)
  ctl.ground([("base", [])])
  return [atom.symbol for atom in ctl.symbolic_atoms if atom.is_fact]


def is_arbolom_model_lp(text: str) -> bool:
  return re.search(r"^\s*compound\s*\(", text, re.M) is not None \
    and re.search(r"^\s*(vertex|edge)\s*\(", text, re.M) is None


def is_arbolom_observations_lp(text: str) -> bool:
  return re.search(r"\bobservation\s*\(", text) is not None and "obs_vlabel" not in text


def model_from_arbolom_lp(text: str) -> Model:
  """Builds a pymodrev Model from a model in ARBoLoM's LP format."""
  model = Model()
  facts = _facts(text)
  for symbol in facts:
    if symbol.name == "compound" and len(symbol.arguments) == 1:
      model.add_node(_symbol_name(symbol.arguments[0]))
  for symbol in facts:
    if symbol.name == "regulates" and len(symbol.arguments) == 3:
      regulator, target, sign = symbol.arguments
      start = model.add_node(_symbol_name(regulator))
      end = model.add_node(_symbol_name(target))
      model.add_edge(start, end, 1 if sign.number == 0 else 0)
  for symbol in sorted((s for s in facts if s.name == "term" and len(s.arguments) == 3),
                       key=lambda s: (str(s.arguments[0]), s.arguments[1].number, str(s.arguments[2]))):
    target, term_id, regulator = symbol.arguments
    node = model.add_node(_symbol_name(target))
    node.function.add_regulator_to_term(term_id.number, _symbol_name(regulator))
  return model


def observation_from_arbolom_lp(text: str, updater: Updater) -> Observation:
  """Builds a pymodrev Observation from observations in ARBoLoM's LP format."""
  observation = Observation(updater)
  for symbol in _facts(text):
    if symbol.name == "experiment" and len(symbol.arguments) == 1:
      observation.experiments.add(_symbol_name(symbol.arguments[0]))
    elif symbol.name == "observation" and len(symbol.arguments) == 3:
      e, c, v = symbol.arguments
      observation.add_data(_symbol_name(e), None, _symbol_name(c), v.number)
    elif symbol.name == "observation" and len(symbol.arguments) == 4:
      e, t, c, v = symbol.arguments
      observation.add_data(_symbol_name(e), str(t.number), _symbol_name(c), v.number)
  return observation


def model_format(filepath: os.PathLike[str] | str) -> str | None:
  """ARBOLOM_LP or MODREV_LP for .lp models, None for other formats."""
  filename = os.fspath(filepath)
  if os.path.splitext(filename)[1].lower() != ".lp":
    return None
  return ARBOLOM_LP if is_arbolom_model_lp(Path(filename).read_text()) else MODREV_LP


def read_model_file(filepath: os.PathLike[str] | str, strict: bool = False) -> Model:
  """Loads a model from a supported file format (.bnet, .zginml, .ginml, .lp).

  strict - raise ValueError if the parser reports problems (like pymodrev's CLI;
    pymodrev's API ignores them)
  """
  filename = os.fspath(filepath)
  if model_format(filename) == ARBOLOM_LP:
    return model_from_arbolom_lp(Path(filename).read_text())
  network = Model()
  parser = get_parser(filename)
  if parser.read(network, filename) < 1 and strict:
    raise ValueError(f"Model definition with errors in {filename}. Check documentation for input definition details.")
  return network


def write_model_file(model: Model, filepath: os.PathLike[str] | str, lp_format: str = MODREV_LP) -> None:
  """Writes a model to disk. lp_format selects the format of .lp files."""
  path = Path(filepath)
  path.parent.mkdir(parents=True, exist_ok=True)
  path.unlink(missing_ok=True)
  if path.suffix.lower() == ".lp" and lp_format == ARBOLOM_LP:
    path.write_text(model_to_lp(model).lp)
    return
  get_parser(str(path)).write(model, str(path))


def read_observation_file(filepath: os.PathLike[str] | str, updater: Updater) -> Observation:
  """Loads observations from a supported file format (.lp, .csv, .xls, .xlsx)."""
  filename = os.fspath(filepath)
  if os.path.splitext(filename)[1].lower() == ".lp":
    text = Path(filename).read_text()
    if is_arbolom_observations_lp(text):
      return observation_from_arbolom_lp(text, updater)
  return get_observation_parser(filename).read(filename, updater)
