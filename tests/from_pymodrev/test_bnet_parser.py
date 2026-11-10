# This file is adapted from pymodrev's test suite: https://github.com/ptgm/pymodrev
# (tests/test_bnet_parser.py at commit d2fb450c714ede82181942fdda5ccce5ad1b1bc8, the code released as pymodrev 0.5.8).
# Copyright (c) the pymodrev authors: Filipe Gouveia, Antonio Romeu and Pedro T. Monteiro.
# pymodrev is distributed under the MIT License (as declared in its pyproject.toml).
# Unchanged: it tests pymodrev's data model, which ARBoLoM uses for its pymodrev-compatible API.

"""
Unit tests for the BnetParser.

Tests cover: identity, negation→positive, AND, OR, XOR→monotone,
degenerate variable removal, parenthesised expressions, constants,
header/comment/blank handling, and complex nested expressions.
"""

import os
import tempfile
import pytest
from pymodrev.network.model import Model
from pymodrev.parsers.parser_bnet import BnetParser


@pytest.fixture
def reader():
    return BnetParser()


@pytest.fixture
def network():
    return Model()


def _write_bnet(content: str) -> str:
    """Write content to a temp .bnet file and return the path."""
    fd, path = tempfile.mkstemp(suffix='.bnet')
    with os.fdopen(fd, 'w') as f:
        f.write(content)
    return path


class TestBnetReaderBasic:
    """Basic parsing and monotone conversion tests."""

    def test_identity(self, reader, network):
        """A, A → single regulator A, sign=1, one term."""
        path = _write_bnet("A, A\n")
        try:
            result = reader.read(network, path)
            assert result == 1
            assert 'A' in network.nodes
            edge = network.get_edge('A', 'A')
            assert edge.sign == 1
            func = network.get_node('A').function
            assert func.regulators_by_term == {1: ['A']}
        finally:
            os.unlink(path)

    def test_negation_becomes_positive(self, reader, network):
        """B, !A → monotone conversion forces A to sign=1 (only negative
        appearance → keeps sign=0 actually, since no conflict)."""
        path = _write_bnet("B, !A\n")
        try:
            result = reader.read(network, path)
            assert result == 1
            assert 'A' in network.nodes
            assert 'B' in network.nodes
            edge = network.get_edge('A', 'B')
            # Only negative → sign stays 0
            assert edge.sign == 0
            func = network.get_node('B').function
            assert 'A' in func.regulators
        finally:
            os.unlink(path)

    def test_and_expression(self, reader, network):
        """D, A & B → one term with regulators A and B, both positive."""
        path = _write_bnet("D, A & B\n")
        try:
            result = reader.read(network, path)
            assert result == 1
            assert set(network.nodes.keys()) == {'A', 'B', 'D'}
            assert network.get_edge('A', 'D').sign == 1
            assert network.get_edge('B', 'D').sign == 1
            func = network.get_node('D').function
            assert func.regulators_by_term == {1: ['A', 'B']}
        finally:
            os.unlink(path)

    def test_or_expression(self, reader, network):
        """E, A | B → two terms."""
        path = _write_bnet("E, A | B\n")
        try:
            result = reader.read(network, path)
            assert result == 1
            func = network.get_node('E').function
            assert len(func.regulators_by_term) == 2
            assert set(func.regulators) == {'A', 'B'}
        finally:
            os.unlink(path)

    def test_xor_opposing_signs_forced_positive(self, reader, network):
        """F, !A & B | A & !B → both A and B appear with opposing signs,
        so both are forced to positive (sign=1)."""
        path = _write_bnet("F, !A & B | A & !B\n")
        try:
            result = reader.read(network, path)
            assert result == 1
            assert network.get_edge('A', 'F').sign == 1
            assert network.get_edge('B', 'F').sign == 1
            func = network.get_node('F').function
            assert set(func.regulators) == {'A', 'B'}
        finally:
            os.unlink(path)

    def test_degenerate_variable_removed(self, reader, network):
        """G, A & B | A & !B → B cancels out (degenerate), only A survives."""
        path = _write_bnet("G, A & B | A & !B\n")
        try:
            result = reader.read(network, path)
            assert result == 1
            func = network.get_node('G').function
            # B should be removed as degenerate; only A remains
            assert func.regulators == ['A']
            assert network.get_edge('A', 'G').sign == 1
        finally:
            os.unlink(path)

    def test_parenthesised_expression(self, reader, network):
        """H, A & (B | C) → distributes to A&B | A&C → two terms."""
        path = _write_bnet("H, A & (B | C)\n")
        try:
            result = reader.read(network, path)
            assert result == 1
            func = network.get_node('H').function
            assert set(func.regulators) == {'A', 'B', 'C'}
            # Should have 2 terms (A&B and A&C)
            assert len(func.regulators_by_term) == 2
            terms = {frozenset(v) for v in func.regulators_by_term.values()}
            assert terms == {frozenset({'B', 'A'}), frozenset({'C', 'A'})}
        finally:
            os.unlink(path)

    def test_nested_not_with_parentheses(self, reader, network):
        """K, !(A & B) | C → equiv. to !A|!B|C.
        After QMC, A and B may appear with opposing signs → forced positive."""
        path = _write_bnet("K, !(A & B) | C\n")
        try:
            result = reader.read(network, path)
            assert result == 1
            func = network.get_node('K').function
            assert set(func.regulators) == {'A', 'B', 'C'}
            terms = {frozenset(v) for v in func.regulators_by_term.values()}
            assert terms == {frozenset({'A'}), frozenset({'B'}), frozenset({'C'})}
            assert network.get_edge('A', 'K').sign == 0
            assert network.get_edge('B', 'K').sign == 0
            assert network.get_edge('C', 'K').sign == 1
        finally:
            os.unlink(path)


class TestBnetReaderEdgeCases:
    """Edge cases: headers, comments, blanks, constants."""

    def test_header_skipped(self, reader, network):
        """Header line 'targets, factors' should be skipped."""
        content = "targets, factors\nA, A\n"
        path = _write_bnet(content)
        try:
            result = reader.read(network, path)
            assert result == 1
            assert 'A' in network.nodes
            assert 'targets' not in network.nodes
        finally:
            os.unlink(path)

    def test_comment_skipped(self, reader, network):
        """Lines starting with # should be skipped."""
        content = "# this is a comment\nA, A\n"
        path = _write_bnet(content)
        try:
            result = reader.read(network, path)
            assert result == 1
            assert len(network.nodes) == 1
        finally:
            os.unlink(path)

    def test_blank_lines_skipped(self, reader, network):
        """Blank lines should be skipped."""
        content = "\n\nA, A\n\nB, !A\n\n"
        path = _write_bnet(content)
        try:
            result = reader.read(network, path)
            assert result == 1
            assert set(network.nodes.keys()) == {'A', 'B'}
        finally:
            os.unlink(path)

    def test_constant_zero(self, reader, network):
        """G, 0 → node G gets positive auto-regulation (self-loop)."""
        path = _write_bnet("G, 0\n")
        try:
            result = reader.read(network, path)
            assert result == 1
            assert 'G' in network.nodes
            func = network.get_node('G').function
            assert func.regulators == ['G']
            assert func.regulators_by_term == {1: ['G']}
            assert network.get_edge('G', 'G').sign == 1
        finally:
            os.unlink(path)

    def test_constant_one(self, reader, network):
        """H, 1 → node H gets positive auto-regulation (self-loop)."""
        path = _write_bnet("H, 1\n")
        try:
            result = reader.read(network, path)
            assert result == 1
            assert 'H' in network.nodes
            func = network.get_node('H').function
            assert func.regulators == ['H']
            assert func.regulators_by_term == {1: ['H']}
            assert network.get_edge('H', 'H').sign == 1
        finally:
            os.unlink(path)


class TestBnetReaderMultiLine:
    """Multi-line bnet files resembling real models."""

    def test_small_cell_cycle(self, reader, network):
        """Parse a small real-world-like model with multiple lines."""
        content = (
            "targets, factors\n"
            "CycB, !Cdc20 & !Cdh1\n"
            "Cdc20, CycB\n"
            "Cdh1, !CycB | Cdc20\n"
        )
        path = _write_bnet(content)
        try:
            result = reader.read(network, path)
            assert result == 1
            assert set(network.nodes.keys()) == {
                'CycB', 'Cdc20', 'Cdh1'
            }
            # CycB has two negative regulators
            func_cycb = network.get_node('CycB').function
            assert set(func_cycb.regulators) == {'Cdc20', 'Cdh1'}
            assert network.get_edge('Cdc20', 'CycB').sign == 0
            assert network.get_edge('Cdh1', 'CycB').sign == 0

            # Cdc20 has one positive regulator
            func_cdc20 = network.get_node('Cdc20').function
            assert func_cdc20.regulators == ['CycB']
            assert network.get_edge('CycB', 'Cdc20').sign == 1
        finally:
            os.unlink(path)

    def test_self_regulation(self, reader, network):
        """CycD, CycD → self-loop, single term."""
        path = _write_bnet("CycD, CycD\n")
        try:
            result = reader.read(network, path)
            assert result == 1
            func_cycd = network.get_node('CycD').function
            assert func_cycd.regulators == ['CycD']
            edge = network.get_edge('CycD', 'CycD')
            assert edge.sign == 1
        finally:
            os.unlink(path)


class TestBnetReaderMonotoneConversion:
    """Detailed tests of the monotone / non-degenerate conversion logic."""

    def test_pure_negation_stays_negative(self, reader, network):
        """X, !A & !B → both only negative → signs stay 0."""
        path = _write_bnet("X, !A & !B\n")
        try:
            reader.read(network, path)
            func_x = network.get_node('X').function
            assert set(func_x.regulators) == {'A', 'B'}
            assert network.get_edge('A', 'X').sign == 0
            assert network.get_edge('B', 'X').sign == 0
        finally:
            os.unlink(path)

    def test_mixed_sign_forced_positive(self, reader, network):
        """Y, A & !B | !A & B → both A and B have opposing signs → forced
        positive."""
        path = _write_bnet("Y, A & !B | !A & B\n")
        try:
            reader.read(network, path)
            func_y = network.get_node('Y').function
            assert set(func_y.regulators) == {'A', 'B'}
            assert network.get_edge('A', 'Y').sign == 1
            assert network.get_edge('B', 'Y').sign == 1
        finally:
            os.unlink(path)

    def test_tautology_gets_autoregulation(self, reader, network):
        """Z, A | !A → tautology → positive auto-regulation."""
        path = _write_bnet("Z, A | !A\n")
        try:
            result = reader.read(network, path)
            assert result == 1
            func = network.get_node('Z').function
            assert func.regulators == ['Z']
            assert func.regulators_by_term == {1: ['Z']}
            assert network.get_edge('Z', 'Z').sign == 1
        finally:
            os.unlink(path)

    def test_contradiction_gets_autoregulation(self, reader, network):
        """W, A & !A → contradiction → positive auto-regulation."""
        path = _write_bnet("W, A & !A\n")
        try:
            result = reader.read(network, path)
            assert result == 1
            func = network.get_node('W').function
            assert func.regulators == ['W']
            assert func.regulators_by_term == {1: ['W']}
            assert network.get_edge('W', 'W').sign == 1
        finally:
            os.unlink(path)
