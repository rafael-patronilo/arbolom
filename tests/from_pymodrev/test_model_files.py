# This file is adapted from pymodrev's test suite: https://github.com/ptgm/pymodrev
# (tests/test_model_files.py at commit d2fb450c714ede82181942fdda5ccce5ad1b1bc8, the code released as pymodrev 0.5.8).
# Copyright (c) the pymodrev authors: Filipe Gouveia, Antonio Romeu and Pedro T. Monteiro.
# pymodrev is distributed under the MIT License (as declared in its pyproject.toml).
# Changes for ARBoLoM (test logic unchanged):
#   - the examples and compare_outputs.py are in this folder (PROJECT_ROOT and the path of compare_outputs.py)
#   - run `python -m arbolom` instead of `python -m pymodrev`

"""
Integration test suite that replicates scripts/run_tests.sh using pytest.

Each test case:
1. Discovers an example directory with model.*, observation files, and output.txt
2. Runs `main.py` via subprocess (using the venv with all dependencies)
3. Compares the output against output.txt using scripts/compare_outputs.py
"""

import subprocess
import tempfile
import os
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
SUPPORTED_EXTENSIONS = {".lp", ".bnet", ".ginml", ".zginml"}

def discover_examples():
    """
    Finds all example directories (examples/*/*/) that contain:
    - model.* (where * is a supported extension)
    - at least one observation .lp file (not model.lp)
    - output.txt
    """
    examples_dir = PROJECT_ROOT / "examples"
    if not examples_dir.exists():
        return []

    valid_dirs = []
    for category_dir in sorted(examples_dir.iterdir()):
        if category_dir.is_dir():
            for example_dir in sorted(category_dir.iterdir()):
                if example_dir.is_dir():
                    output_txt = example_dir / "output.txt"
                    if not output_txt.exists():
                        continue

                    model_files = []
                    for ext in SUPPORTED_EXTENSIONS:
                        candidate = example_dir / f"model{ext}"
                        if candidate.exists():
                            model_files.append(candidate)

                    if model_files:
                        obs_files = [
                            f for f in example_dir.iterdir()
                            if f.suffix == ".lp" and f.name != "model.lp"
                        ]
                        if obs_files:
                            for mf in model_files:
                                valid_dirs.append((example_dir, mf))

    return valid_dirs

def pytest_generate_tests(metafunc):
    """Dynamically parametrize tests from example directories."""
    if "example_data" in metafunc.fixturenames:
        examples = discover_examples()
        ids = [f"{d[0].relative_to(PROJECT_ROOT)}/{d[1].name}" for d in examples]
        metafunc.parametrize("example_data", examples, ids=ids)

def test_example_output(example_data, venv_python: str):
    """
    Runs main.py on the example directory and compares output
    against the expected output.txt using compare_outputs.py.
    """
    example_dir, model_file_path = example_data
    model_file = str(model_file_path)
    output_txt = str(example_dir / "output.txt")

    # Build observation arguments (same logic as run_tests.sh)
    obs_args = []
    for obs_file in sorted(example_dir.iterdir()):
        if obs_file.suffix == ".lp" and "model" not in obs_file.name: # ignores model.ext and model_*.ext
            base = obs_file.stem           # e.g. "async_1" or "steady"
            typology = base.split("_")[0]   # e.g. "async" or "steady"
            obs_args.extend([str(obs_file), f"{typology}"])

    # Run pymodrev as a module and capture stdout to a temp file
    cmd = [venv_python, "-m", "arbolom", "-m", model_file, "-obs"] + obs_args + ["-f", "c"] + ["-t", "r"] + ["-s", "4"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )

    # Write stdout to a temp file for compare_outputs.py
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        tmp.write(result.stdout)
        tmp_path = tmp.name

    try:
        # Run compare_outputs.py
        cmp_result = subprocess.run(
            [venv_python, "compare_outputs.py", tmp_path, output_txt],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )

        # compare_outputs.py prints differences to stdout if outputs diverge
        assert cmp_result.stdout.strip() == "", (
            f"Output mismatch for {example_dir.relative_to(PROJECT_ROOT)}:\n"
            f"{cmp_result.stdout}\n"
            f"---\n"
            f"Command run: {' '.join(cmd)}\n"
            f"Process stderr: {result.stderr}\n"
        )
    finally:
        os.unlink(tmp_path)

def test_example_repair(example_data, venv_python: str):
    """
    Runs pymodrev with -t m to generate repaired models,
    then verifies each model is consistent using -t c -v 0.
    """
    example_dir, model_file_path = example_data
    
    # 1. Setup temporary directory and copy example files
    with tempfile.TemporaryDirectory() as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        
        # Copy model file
        shutil.copy(model_file_path, tmp_dir / model_file_path.name)
        
        # Copy all observation .lp files
        obs_files = []
        for f in example_dir.iterdir():
            if f.suffix == ".lp" and "model" not in f.name:
                shutil.copy(f, tmp_dir / f.name)
                obs_files.append(tmp_dir / f.name)
        
        if not obs_files:
            return # Should not happen given discover_examples logic
            
        # Build observation arguments
        obs_args = []
        for obs_file in sorted(obs_files):
            base = obs_file.stem
            typology = base.split("_")[0]
            obs_args.extend([str(obs_file), f"{typology}"])

        # 2. Run -t m to generate repaired models
        model_in_tmp = str(tmp_dir / model_file_path.name)
        cmd_m = [venv_python, "-m", "arbolom", "-m", model_in_tmp, "-obs"] + obs_args + ["-t", "m", "-s", "4", "-f", "c"]
        result_m = subprocess.run(cmd_m, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        
        assert result_m.returncode == 0, f"Failed to generate models:\n{result_m.stderr}"

        # 3. Find generated models (pattern model_*.ext)
        prefix = model_file_path.stem
        ext = model_file_path.suffix
        repaired_models = list(tmp_dir.glob(f"{prefix}_[0-9]*{ext}"))
        
        # We expect at least one model if there were repairs to be made
        # Some examples might already be consistent, but the test suite mainly has inconsistent ones.
        
        for rep_model in repaired_models:
            # 4. Check consistency of each repaired model
            cmd_c = [venv_python, "-m", "arbolom", "-m", str(rep_model), "-obs"] + obs_args + ["-t", "c", "-s", "4", "-f", "c"]
            result_c = subprocess.run(cmd_c, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
            
            assert result_c.returncode == 0, f"Consistency check failed for {rep_model.name}:\n{result_c.stderr}"
            assert "Consistent!" in result_c.stdout, (
                f"Repaired model {rep_model.name} is NOT consistent!\n"
                f"Output: {result_c.stdout}\n"
                f"Command: {' '.join(cmd_c)}"
            )
