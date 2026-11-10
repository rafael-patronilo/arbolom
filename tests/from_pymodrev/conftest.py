# This file is adapted from pymodrev's test suite: https://github.com/ptgm/pymodrev
# (tests/conftest.py at commit d2fb450c714ede82181942fdda5ccce5ad1b1bc8, the code released as pymodrev 0.5.8).
# Copyright (c) the pymodrev authors: Filipe Gouveia, Antonio Romeu and Pedro T. Monteiro.
# pymodrev is distributed under the MIT License (as declared in its pyproject.toml).
# Changes for ARBoLoM (test logic unchanged):
#   - import arbolom instead of pymodrev for the observation registry cleared between tests
#   - requirements.txt is read from this folder instead of the rootdir

"""
Pytest configuration for integration tests.

Provides a session-scoped fixture that detects the active Python environment.
Works with both virtual environments and system Python without requiring
the project to be installed — the src/ directory is added to PYTHONPATH.
"""

import importlib.util
import os
import re
from pathlib import Path
import pytest
import arbolom as mrev

venv_dir = os.environ.get("VIRTUAL_ENV")

def get_required_packages(requirements_path: Path):
    packages = ["pymodrev"]
    pattern = re.compile(r'^([a-zA-Z0-9\-_]+)')
    with open(requirements_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            match = pattern.match(line)
            if match: packages.append(match.group(1))
    return packages

def check_package_resolvable(package_name: str):
    return importlib.util.find_spec(package_name.replace('-', '_')) is not None


@pytest.fixture(scope="session")
def venv_python():
    return str(Path(venv_dir) / "bin" / "python3")


@pytest.fixture(autouse=True)
def clean_observations():
    mrev.clear_obs()
    yield
    mrev.clear_obs()

def pytest_sessionstart(session):
    if not venv_dir:
        error_msg = (
            f"\nFATAL: Variable VIRTUAL_ENV not found.\n"
            f"Create and activate a virtual environment before running tests:\n"
            f"  python3 -m venv .venv\n"
            f"  source .venv/bin/activate"
        )
        pytest.exit(reason=error_msg, returncode=1)

    req_file = Path(__file__).parent / "requirements.txt"
    required_packages = get_required_packages(req_file)
    missing = [pkg for pkg in required_packages if not check_package_resolvable(pkg)]

    if missing:
        error_log = (
            f"\n[FATAL] Dependencies missing in environment.\n"
            f"Missing Packages: {', '.join(missing)}\n"
            f"Resolution: Execute 'pip install -r requirements.txt' within the target environment."
        )
        pytest.exit(reason=error_log, returncode=1)
