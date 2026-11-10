# This file is adapted from pymodrev's test suite: https://github.com/ptgm/pymodrev
# (tests/test_observation_parsers.py at commit d2fb450c714ede82181942fdda5ccce5ad1b1bc8, the code released as pymodrev 0.5.8).
# Copyright (c) the pymodrev authors: Filipe Gouveia, Antonio Romeu and Pedro T. Monteiro.
# pymodrev is distributed under the MIT License (as declared in its pyproject.toml).
# Unchanged: it tests pymodrev's data model, which ARBoLoM uses for its pymodrev-compatible API.

import os
from pymodrev.updaters.async_updater import AsyncUpdater
from pymodrev.updaters.steady_updater import SteadyUpdater
import pytest
from pymodrev.network.observation import Observation
from pymodrev.parsers.parser_observation import get_observation_parser, LPObservationParser, CSVObservationParser

def test_lp_parser_steady_state(tmp_path):
    lp_content = """
    exp(p1).
    obs_vlabel(p1, node1, 0).
    obs_vlabel(p1, node2, 1).
    """
    lp_file = tmp_path / "obs.lp"
    lp_file.write_text(lp_content)
    
    parser = get_observation_parser(str(lp_file))
    assert isinstance(parser, LPObservationParser)
    
    obs = parser.read(str(lp_file), SteadyUpdater())
    assert obs.experiments == {"p1"}
    assert len(obs.data) == 2
    assert ("p1", None, "node1", 0) in obs.data
    assert ("p1", None, "node2", 1) in obs.data

def test_lp_parser_time_series(tmp_path):
    lp_content = """
    exp(p1).
    obs_vlabel(p1, 0, node1, 0).
    obs_vlabel(p1, 1, node1, 1).
    """
    lp_file = tmp_path / "obs.lp"
    lp_file.write_text(lp_content)
    
    parser = LPObservationParser()
    obs = parser.read(str(lp_file), AsyncUpdater())
    assert obs.experiments == {"p1"}
    assert len(obs.data) == 2
    assert ("p1", '0', "node1", 0) in obs.data
    assert ("p1", '1', "node1", 1) in obs.data

def test_csv_parser_steady_state(tmp_path):
    csv_content = ",node1,node2\np1,0,1\np2,1,0\n"
    csv_file = tmp_path / "obs.csv"
    csv_file.write_text(csv_content)
    
    parser = get_observation_parser(str(csv_file))
    assert isinstance(parser, CSVObservationParser)
    
    obs = parser.read(str(csv_file), SteadyUpdater())
    assert obs.experiments == {"p1", "p2"}
    assert len(obs.data) == 4
    assert ("p1", None, "node1", 0) in obs.data
    assert ("p1", None, "node2", 1) in obs.data
    assert ("p2", None, "node1", 1) in obs.data
    assert ("p2", None, "node2", 0) in obs.data

def test_csv_parser_time_series(tmp_path):
    csv_content = ",,node1,node2\np1,0,0,1\np1,1,1,0\n"
    csv_file = tmp_path / "obs.csv"
    csv_file.write_text(csv_content)
    
    parser = CSVObservationParser()
    obs = parser.read(str(csv_file), AsyncUpdater())
    assert obs.experiments == {"p1"}
    assert len(obs.data) == 4
    assert ("p1", '0', "node1", 0) in obs.data
    assert ("p1", '0', "node2", 1) in obs.data
    assert ("p1", '1', "node1", 1) in obs.data
    assert ("p1", '1', "node2", 0) in obs.data

def test_csv_parser_with_missing_values(tmp_path):
    # node1 at time 1 is empty, node2 at time 1 is " N/A ", node1 at time 2 is " - "
    csv_content = ",,node1,node2\np1,0,0,1\np1,1, , N/A \np1,2, - ,0\n"
    csv_file = tmp_path / "obs_robust.csv"
    csv_file.write_text(csv_content)
    
    parser = CSVObservationParser()
    obs = parser.read(str(csv_file), AsyncUpdater())
    assert len(obs.data) == 3
    assert ("p1", '0', "node1", 0) in obs.data
    assert ("p1", '0', "node2", 1) in obs.data
    assert ("p1", '2', "node2", 0) in obs.data
    
    facts = obs.to_asp_facts(2)
    assert "obs_vlabel(p1,0,node1,0)." in facts
    assert "obs_vlabel(p1,0,node2,1)." in facts
    assert "obs_vlabel(p1,2,node2,0)." in facts
    # Ensure no facts are generated for missing values
    assert "obs_vlabel(p1,1,node1," not in facts
    assert "obs_vlabel(p1,1,node2," not in facts
    assert "obs_vlabel(p1,2,node1," not in facts

def test_excel_parser_xlsx(tmp_path):
    import openpyxl
    xlsx_file = tmp_path / "obs.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["", "", "node1", "node2"])
    ws.append(["p1", 0, 0, 1])
    ws.append(["p1", 1, 1, 0])
    wb.save(str(xlsx_file))
    
    from pymodrev.parsers.parser_observation import get_observation_parser, ExcelObservationParser
    parser = get_observation_parser(str(xlsx_file))
    assert isinstance(parser, ExcelObservationParser)
    
    obs = parser.read(str(xlsx_file), AsyncUpdater())
    assert obs.experiments == {"p1"}
    assert len(obs.data) == 4
    assert ("p1", '0', "node1", 0) in obs.data
    assert ("p1", '1', "node2", 0) in obs.data

def test_excel_parser_xls(tmp_path):
    # Testing .xls is harder as it needs a specialized writer, 
    # but the logic is very similar to .xlsx and .csv.
    # For now, we rely on the internal rows processing which is shared.
    pass

def test_observation_to_asp_facts():
    from pymodrev.network.observation import Observation
    updater = SteadyUpdater()
    obs = Observation(updater)
    obs.add_data("p1", None, "node1", 0)
    obs.add_data("p1", '0', "node1", 1) # Mixed just for test
    
    facts = obs.to_asp_facts(1)
    assert "exp(p1)." in facts
    assert "obs_vlabel(p1,node1,0)." in facts
    assert "obs_vlabel(p1,0,node1,1)." in facts
