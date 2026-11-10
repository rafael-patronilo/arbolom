# Tests from pymodrev

The tests, helper scripts and example files in this folder are adapted from the
test suite of [pymodrev](https://github.com/ptgm/pymodrev), at commit
`d2fb450c714ede82181942fdda5ccce5ad1b1bc8` (the code released as pymodrev 0.5.8).

- Copyright (c) the pymodrev authors: Filipe Gouveia, Antonio Romeu and Pedro T. Monteiro.
- pymodrev is distributed under the MIT License, as declared in its `pyproject.toml`.

They check that ARBoLoM's API and command line interface are compatible with pymodrev's.
Each Python file starts with a header that lists the changes made for ARBoLoM; the test
logic is unchanged.

`examples/` is a verbatim copy of pymodrev's `examples/` folder (models, observations
and pymodrev's expected outputs, `output.txt`), used by `test_model_files.py`.

Note: the tests of pymodrev's data model (`test_edge.py`, `test_model.py`,
`test_repair_set.py`, ...) import pymodrev directly: ARBoLoM uses that data model
for its pymodrev-compatible API, so they check the behaviour ARBoLoM relies on.
