# This file is adapted from pymodrev's test suite: https://github.com/ptgm/pymodrev
# (tests/test_function.py at commit d2fb450c714ede82181942fdda5ccce5ad1b1bc8, the code released as pymodrev 0.5.8).
# Copyright (c) the pymodrev authors: Filipe Gouveia, Antonio Romeu and Pedro T. Monteiro.
# pymodrev is distributed under the MIT License (as declared in its pyproject.toml).
# Unchanged: it tests pymodrev's data model, which ARBoLoM uses for its pymodrev-compatible API.

import pytest
from pyfunctionhood.function import Function as PFHFunction
from pyfunctionhood.clause import Clause
from pymodrev.network.function import Function

def test_function_initialization():
    func = Function('node_1')
    assert func.node_id == 'node_1'
    assert func.distance_from_original == 0
    assert not func.son_consistent
    assert func.regulators == []
    assert func.regulators_by_term == {}

def test_add_regulator_to_term():
    func = Function('node_1')
    func.add_regulator_to_term(1, 'reg_1')
    assert 'reg_1' in func.regulators
    assert 'reg_1' in func.regulators_by_term[1]
    
    func.add_regulator_to_term(2, 'reg_2')
    assert 'reg_2' in func.regulators
    assert 'reg_2' in func.regulators_by_term[2]

    # Duplicate check
    func.add_regulator_to_term(1, 'reg_1')
    assert len(func.regulators_by_term[1]) == 1
    assert len(func.regulators) == 2

def test_function_equality_and_hash():
    f1 = Function("node1")
    f1.add_regulator_to_term(1, "A")
    f1.add_regulator_to_term(1, "B")
    
    f2 = Function("node1")
    f2.add_regulator_to_term(1, "A")
    f2.add_regulator_to_term(1, "B")

    f3 = Function("node1")
    f3.add_regulator_to_term(1, "A")

    assert f1 == f2
    assert f1 != f3
    assert hash(f1) == hash(f2)
    assert f1 != "not a function"

def test_empty_function_equality():
    f1 = Function("node1")
    f2 = Function("node2") # Different node, same empty logic
    f3 = Function("node1")
    
    # Empty functions of same node should be equal if logic is same
    assert f1 == f3
    # Actually the current implementation says if both empty -> True
    # Let's check if node_id matters for hash
    assert hash(f1) == hash(f3)
    # If node_id matters for hash but not for eq, it might violate invariant if we aren't careful
    # But currently __eq__ for empty returns True.
    assert f1 == f2

def test_function_string_rep():
    f = Function("node1")
    f.add_regulator_to_term(1, "A")
    f.add_regulator_to_term(1, "B")
    f.add_regulator_to_term(2, "C")
    
    # 1. Without network (no signs)
    assert f.print_function() == "(A && B) || (C)"

    # 2. With network (sign-aware)
    from pymodrev.network.model import Model
    net = Model()
    A = net.add_node("A")
    B = net.add_node("B")
    C = net.add_node("C")
    node1 = net.add_node("node1")
    
    net.add_edge(A, node1, 0) # Negative
    net.add_edge(B, node1, 1) # Positive
    net.add_edge(C, node1, 1) # Positive
    
    assert f.print_function(network=net) == "(!A && B) || (C)"

    # 3. With repair_set (account for flips)
    from pymodrev.network.repair_set import RepairSet
    from pymodrev.network.edge import Edge
    rs = RepairSet()
    # Flip A back to positive, flip B to negative
    rs.add_flipped_edge(Edge(A, node1, 0))
    rs.add_flipped_edge(Edge(B, node1, 1))
    
    assert f.print_function(network=net, repair_set=rs) == "(A && !B) || (C)"

def test_pfh_integration():
    f = Function("node1")
    f.add_regulator_to_term(1, "A")
    f.create_pfh_function()
    assert isinstance(f.pfh_function, PFHFunction)
    assert f.get_n_clauses() == 1
