# This file is adapted from pymodrev's test suite: https://github.com/ptgm/pymodrev
# (tests/test_node.py at commit d2fb450c714ede82181942fdda5ccce5ad1b1bc8, the code released as pymodrev 0.5.8).
# Copyright (c) the pymodrev authors: Filipe Gouveia, Antonio Romeu and Pedro T. Monteiro.
# pymodrev is distributed under the MIT License (as declared in its pyproject.toml).
# Unchanged: it tests pymodrev's data model, which ARBoLoM uses for its pymodrev-compatible API.

import pytest
from pymodrev.network.node import Node
from pymodrev.network.function import Function

def test_node_initialization():
    node = Node('test_node')
    assert node.identifier == 'test_node'
    assert isinstance(node.function, Function)
    assert node.function.node_id == 'test_node'

def test_node_add_function():
    node = Node('test_node')
    func = Function('test_function')
    node.function = func
    assert node.function == func
    assert node.function.node_id == 'test_function'

def test_node_get_function():
    node = Node('test_node')
    assert node.function.node_id == 'test_node'
    func = Function('test_function')
    node.function = func
    assert node.function == func

def test_node_get_id():
    node = Node('test_node')
    assert node.identifier == 'test_node'
