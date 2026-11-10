# This file is adapted from pymodrev's test suite: https://github.com/ptgm/pymodrev
# (tests/test_apply_repair.py at commit d2fb450c714ede82181942fdda5ccce5ad1b1bc8, the code released as pymodrev 0.5.8).
# Copyright (c) the pymodrev authors: Filipe Gouveia, Antonio Romeu and Pedro T. Monteiro.
# pymodrev is distributed under the MIT License (as declared in its pyproject.toml).
# Unchanged: it tests pymodrev's data model, which ARBoLoM uses for its pymodrev-compatible API.

"""
Unit tests for the apply_repair function.

Tests cover each type of repair operation individually:
- Adding edges
- Removing edges
- Flipping edge signs
- Changing node functions
- Combined repairs (all four at once)
"""

import pytest
from pymodrev.network.model import Model
from pymodrev.network.node import Node
from pymodrev.network.edge import Edge
from pymodrev.network.function import Function
from pymodrev.network.inconsistency_solution import InconsistencySolution
from pymodrev.network.inconsistent_node import InconsistentNode
from pymodrev.network.repair_set import RepairSet
from pymodrev.network.exceptions import EdgeNotFoundError
from pymodrev.repair.repair import apply_repair


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def base_network():
    """Create a simple network: A -> B -> C (all positive edges).
    B has function (A), C has function (B)."""
    net = Model()
    A = net.add_node("A")
    B = net.add_node("B")
    C = net.add_node("C")

    net.add_edge(A, B, 1)  # A -> B (positive)
    net.add_edge(B, C, 1)  # B -> C (positive)

    func_B = Function("B")
    func_B.add_regulator_to_term(1, "A")
    B.function = func_B

    func_C = Function("C")
    func_C.add_regulator_to_term(1, "B")
    C.function = func_C

    return net


def _make_solution_with_single_repair(node_id, generalization, setup_fn):
    """Helper to create an InconsistencySolution with a single repair set
    for the given node_id. `setup_fn` is called with (network_unused, repair_set)
    to configure the repair."""
    solution = InconsistencySolution()
    i_node = InconsistentNode(node_id, generalization)
    repair_set = RepairSet()
    setup_fn(repair_set)
    i_node.add_repair_set(repair_set)
    solution.inconsistent_nodes[node_id] = i_node
    return solution


# ── Individual Repair Type Tests ────────────────────────────────────────


class TestAddEdgeRepair:
    """Test that adding edges via repair works correctly."""

    def test_add_single_edge(self, base_network):
        """Adding an edge C -> B with sign 0 should create that edge."""
        net = base_network
        C = net.get_node("C")
        B = net.get_node("B")

        solution = _make_solution_with_single_repair(
            "B", False,
            lambda rs: rs.add_edge(Edge(C, B, 0))
        )

        apply_repair(net, solution)

        edge_CB = net.get_edge("C", "B")
        assert edge_CB is not None
        assert edge_CB.sign == 0

    def test_add_edge_preserves_existing(self, base_network):
        """Adding an edge should not affect existing edges."""
        net = base_network
        C = net.get_node("C")
        B = net.get_node("B")

        solution = _make_solution_with_single_repair(
            "B", False,
            lambda rs: rs.add_edge(Edge(C, B, 0))
        )

        apply_repair(net, solution)

        # Existing edges should still be present
        assert net.get_edge("A", "B").sign == 1
        assert net.get_edge("B", "C").sign == 1

    def test_add_edge_with_positive_sign(self, base_network):
        """Adding an edge with positive sign (1)."""
        net = base_network
        A = net.get_node("A")
        C = net.get_node("C")

        solution = _make_solution_with_single_repair(
            "C", False,
            lambda rs: rs.add_edge(Edge(A, C, 1))
        )

        apply_repair(net, solution)

        edge_AC = net.get_edge("A", "C")
        assert edge_AC is not None
        assert edge_AC.sign == 1


class TestRemoveEdgeRepair:
    """Test that removing edges via repair works correctly."""

    def test_remove_single_edge(self, base_network):
        """Removing edge A -> B should make it no longer exist."""
        net = base_network
        A = net.get_node("A")
        B = net.get_node("B")

        solution = _make_solution_with_single_repair(
            "B", False,
            lambda rs: rs.remove_edge(Edge(A, B, 1))
        )

        apply_repair(net, solution)

        with pytest.raises(EdgeNotFoundError):
            net.get_edge("A", "B")

    def test_remove_edge_preserves_other_edges(self, base_network):
        """Removing one edge should not affect other edges."""
        net = base_network
        A = net.get_node("A")
        B = net.get_node("B")

        solution = _make_solution_with_single_repair(
            "B", False,
            lambda rs: rs.remove_edge(Edge(A, B, 1))
        )

        apply_repair(net, solution)

        # B -> C should still exist
        assert net.get_edge("B", "C").sign == 1


class TestFlipEdgeRepair:
    """Test that flipping edge signs via repair works correctly."""

    def test_flip_positive_to_negative(self, base_network):
        """Flipping edge B -> C (sign 1 -> 0)."""
        net = base_network
        B = net.get_node("B")
        C = net.get_node("C")

        solution = _make_solution_with_single_repair(
            "C", False,
            lambda rs: rs.add_flipped_edge(Edge(B, C, 1))
        )

        apply_repair(net, solution)

        edge_BC = net.get_edge("B", "C")
        assert edge_BC.sign == 0

    def test_flip_preserves_other_edges(self, base_network):
        """Flipping one edge should not affect other edges."""
        net = base_network
        B = net.get_node("B")
        C = net.get_node("C")

        solution = _make_solution_with_single_repair(
            "C", False,
            lambda rs: rs.add_flipped_edge(Edge(B, C, 1))
        )

        apply_repair(net, solution)

        # A -> B should be unchanged
        assert net.get_edge("A", "B").sign == 1


class TestChangeFunctionRepair:
    """Test that changing node functions via repair works correctly."""

    def test_change_function(self, base_network):
        """Changing function of B from (A) to (C)."""
        net = base_network

        new_func = Function("B")
        new_func.add_regulator_to_term(1, "C")

        solution = _make_solution_with_single_repair(
            "B", False,
            lambda rs: rs.add_repaired_function(new_func)
        )

        apply_repair(net, solution)

        assert net.get_node("B").function.print_function() == "(C)"
        assert "C" in net.get_node("B").function.regulators

    def test_change_function_preserves_original_regulators(self, base_network):
        """Original function's regulators should be replaced entirely."""
        net = base_network

        new_func = Function("B")
        new_func.add_regulator_to_term(1, "C")

        solution = _make_solution_with_single_repair(
            "B", False,
            lambda rs: rs.add_repaired_function(new_func)
        )

        apply_repair(net, solution)

        # 'A' should no longer be in the new function's regulators
        assert "A" not in net.get_node("B").function.regulators

    def test_change_function_multi_term(self, base_network):
        """Changing function of B to a multi-term function (A) || (C)."""
        net = base_network

        new_func = Function("B")
        new_func.add_regulator_to_term(1, "A")
        new_func.add_regulator_to_term(2, "C")

        solution = _make_solution_with_single_repair(
            "B", False,
            lambda rs: rs.add_repaired_function(new_func)
        )

        apply_repair(net, solution)

        func = net.get_node("B").function
        assert set(func.regulators) == {"A", "C"}
        assert len(func.regulators_by_term) == 2


class TestCombinedRepairs:
    """Test applying multiple repair types simultaneously."""

    def test_all_repair_types_combined(self, base_network):
        """Apply add, remove, flip, and function change all at once."""
        net = base_network
        A = net.get_node("A")
        B = net.get_node("B")
        C = net.get_node("C")

        solution = InconsistencySolution()
        i_node_B = InconsistentNode("B", False)
        repair_set = RepairSet()

        # 1. Add edge C -> B (sign 0)
        repair_set.add_edge(Edge(C, B, 0))

        # 2. Remove edge A -> B
        repair_set.remove_edge(Edge(A, B, 1))

        # 3. Flip edge B -> C (sign 1 -> 0)
        repair_set.add_flipped_edge(Edge(B, C, 1))

        # 4. Change function of B to (C)
        new_func_B = Function("B")
        new_func_B.add_regulator_to_term(1, "C")
        repair_set.add_repaired_function(new_func_B)

        i_node_B.add_repair_set(repair_set)
        solution.inconsistent_nodes["B"] = i_node_B

        apply_repair(net, solution)

        # Verify added edge C -> B
        edge_CB = net.get_edge("C", "B")
        assert edge_CB.sign == 0

        # Verify removed edge A -> B
        with pytest.raises(EdgeNotFoundError):
            net.get_edge("A", "B")

        # Verify flipped edge B -> C
        edge_BC = net.get_edge("B", "C")
        assert edge_BC.sign == 0

        # Verify updated function of B
        assert net.get_node("B").function.print_function() == "(C)"
        assert "C" in net.get_node("B").function.regulators

    def test_no_repair_sets_is_noop(self):
        """An empty InconsistencySolution should not change the network."""
        net = Model()
        A = net.add_node("A")
        B = net.add_node("B")
        net.add_edge(A, B, 1)

        solution = InconsistencySolution()

        apply_repair(net, solution)

        # Network should be unchanged
        assert net.get_edge("A", "B").sign == 1

    def test_empty_repair_set_is_noop(self):
        """An inconsistent node with no repair sets should not modify anything."""
        net = Model()
        A = net.add_node("A")
        B = net.add_node("B")
        net.add_edge(A, B, 1)

        solution = InconsistencySolution()
        i_node = InconsistentNode("B", False)
        # No repair set added
        solution.inconsistent_nodes["B"] = i_node

        apply_repair(net, solution)

        assert net.get_edge("A", "B").sign == 1
