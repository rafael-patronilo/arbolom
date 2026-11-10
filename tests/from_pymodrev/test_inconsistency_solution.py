# This file is adapted from pymodrev's test suite: https://github.com/ptgm/pymodrev
# (tests/test_inconsistency_solution.py at commit d2fb450c714ede82181942fdda5ccce5ad1b1bc8, the code released as pymodrev 0.5.8).
# Copyright (c) the pymodrev authors: Filipe Gouveia, Antonio Romeu and Pedro T. Monteiro.
# pymodrev is distributed under the MIT License (as declared in its pyproject.toml).
# Unchanged: it tests pymodrev's data model, which ARBoLoM uses for its pymodrev-compatible API.

import pytest
from pymodrev.network.inconsistency_solution import InconsistencySolution
from pymodrev.network.repair_set import RepairSet

@pytest.fixture
def solution():
    return InconsistencySolution()

def test_initial_values(solution):
    assert solution.inconsistent_nodes == {}
    assert solution.v_label == {}
    assert not solution.has_impossibility

def test_add_generalization(solution):
    solution.add_generalization("node1")
    assert "node1" in solution.inconsistent_nodes
    assert solution.get_i_node("node1").repair_type == 1

def test_add_v_label(solution):
    solution.add_v_label("profile1", "node1", "value1", "time1")
    assert solution.v_label["profile1"]["time1"]["node1"] == "value1"

def test_compare_repairs(solution):
    sol2 = InconsistencySolution()
    sol2.n_ar_operations = 5
    solution.n_ar_operations = 3
    assert solution.compare_repairs(sol2) == 1

def test_add_repair_set(solution):
    rs = RepairSet()
    rs.n_add_remove_operations = 2
    rs.n_repair_operations = 2
    solution.add_generalization("node1")
    solution.add_repair_set("node1", rs)
    assert solution.n_ar_operations == 2
    assert solution.n_repair_operations == 2
