# ARBoLoM (**A**SP-based **R**evision of **B**oolean **L**ogical **M**odels)
The ARBoLoM tool aims to automate the revision of Boolean logical models, with fully Answer Set Programming-based consistency checking and repair algorithms. 

## Encoding Directories
The ASP encodings are shipped with the Python package, in [`src/arbolom/encodings`](src/arbolom/encodings).

The encodings responsible for verifying the consistency of a model given [stable state](src/arbolom/encodings/consistency/ss_consistency.lp), [synchronous](src/arbolom/encodings/consistency/sync_consistency.lp), or [asynchronous observations](src/arbolom/encodings/consistency/async_consistency.lp), can be found [here](src/arbolom/encodings/consistency).

The encodings responsible for repairing a function using [stable state](src/arbolom/encodings/repairs/repairs_stable.lp), [synchronous](src/arbolom/encodings/repairs/repairs_sync.lp), or [asynchronous observations](src/arbolom/encodings/repairs/repairs_async.lp), can be found [here](src/arbolom/encodings/repairs).

## Installation
Python 3.13 or above is required. ARBoLoM is a Python package (`src/arbolom`) depending on [clingo](https://pypi.org/project/clingo/) and on [pymodrev](https://github.com/ptgm/pymodrev), whose data model it shares.

- With [uv](https://docs.astral.sh/uv/): `uv sync` installs the package and its dependencies in `.venv`; prefix commands with `uv run` (e.g. `uv run arbolom-revision ...`) or activate the environment.
- With pip: `pip install .`
- With Google Colab: see the [notebook](ARBoLoM.ipynb), which installs the package with pip.

`uv run pytest` runs the test suite. The tests in [`tests/from_pymodrev`](tests/from_pymodrev) come from pymodrev and check the compatibility of ARBoLoM's API and command line interface with pymodrev's.

## Package Layout
| Module | Contents |
|---|---|
| `arbolom.api`, `arbolom.cli` | pymodrev-compatible API and command line interface |
| `arbolom.engine`, `arbolom.bridge`, `arbolom.formats` | ARBoLoM's revision applied to pymodrev's data model; translation to and from ARBoLoM's LP format |
| `arbolom.revision` | `RevisionSettings` and `ModelReviser`: consistency checking followed by the repair of each inconsistent function |
| `arbolom.consistency` | consistency checking |
| `arbolom.repair` | repair of a single function (`search`, `deepening_search`), its preprocessing, change minimization criteria and sanity checks |
| `arbolom.conversion`, `arbolom.lp_model` | .bnet to LP conversion; manipulation of LP models |
| `arbolom.corruption`, `arbolom.observation_generation` | model corruption and observation generation, used to build benchmarks |
| `arbolom.modes` | `UpdateMode` (stable, sync, async) |
| `arbolom.scripts` | ARBoLoM's original command line tools |

## Running the Tools
The command line tools are installed as commands (each also runs with `python -m arbolom.scripts.<module>`):

| Command | Former script | Purpose |
|---|---|---|
| `arbolom-revision` | `revision.py` | Check the consistency of a model and repair it |
| `arbolom-consistency` | `consistency_checking.py` | Check the consistency of a model, saving the inconsistencies |
| `arbolom-repair` | `repair.py` | Repair a model given the inconsistencies saved by `arbolom-consistency` |
| `arbolom-conversion` | `conversion.py` | Convert .bnet models to .lp |
| `arbolom-corruption` | `corruption.py` | Corrupt .bnet models (`-seed` makes it reproducible) |
| `arbolom-gen-observations` | `gen_observations.py` | Generate time-series observations from a .lp model |
| `arbolom-benchmark` | `benchmark.py` | Run benchmarks (see below) |
| `arbolom-summarize-benchmark` | `aux_scripts/summarize_benchmark.py` | Summarize benchmark results |
| `arbolom-merge-csv` | `aux_scripts/merge_csv.py` | Merge benchmark results |

Each command describes its arguments with `--help`. Further instructions and examples can be found in the [notebook](ARBoLoM.ipynb) file.

## pymodrev-Compatible API and Command Line Interface
ARBoLoM can be used as a drop-in replacement for [pymodrev](https://github.com/ptgm/pymodrev): the `arbolom` command accepts pymodrev's arguments and prints the same output formats,

```bash
arbolom -m model.bnet -obs obs.lp sync -t r -f c
```

and the `arbolom` package exports pymodrev's API, working on pymodrev's `Model` objects:

```python
import arbolom as mrev

model = mrev.model_from_file("model.bnet")
mrev.obs_sync_ts("p1", {0: {"a": 1, "b": 0}, 1: {"a": 1, "b": 1}})
print(mrev.is_consistent(model, ["p1"]))
repaired_models, details = mrev.repair(model)
```

Models can be given in the formats supported by pymodrev (.bnet, .lp in ModRev's format, .ginml, .zginml) and in ARBoLoM's .lp format; observations in pymodrev's formats (.lp, .csv, .xls, .xlsx) and in ARBoLoM's .lp format. ARBoLoM-specific options (change minimization criteria, timeout, parallel mode) are available as extra arguments of the `arbolom` command, and as `RevisionSettings` of an `arbolom.Session` in the API.

Differences with pymodrev:
- Only steady (stable state), sync and async observations are supported, with a single updater per run.
- In async mode ARBoLoM allows at most one node to change per time step, whereas pymodrev requires exactly one.
- ARBoLoM computes one repair per inconsistent node, optimal with respect to its change minimization criteria, so the repairs often differ from pymodrev's (which prefers changing functions, then flipping edge signs, then adding or removing edges).
- Fixed edges forbid removing the edge or changing its sign; an inconsistent fixed node makes the model unrepairable.

## Quick Testing
For quick testing, the models in the [simple_models](simple_models) folder may be used. These are small, hand-made examples of hypothethical biological networks. Due to their compact nature, one can use them to perform quick tests with the scripts, or to manually verify the correctness of the results produced by said scripts.

Generally, the models will be used in the following fashion:
1. One of the models is chosen to perform tests on; 
2. `arbolom-corruption` can then be used to create a "wrong" version of this model;
3. `arbolom-conversion` is ran on both models, to convert them to .lp format;
4. `arbolom-gen-observations` is ran on the original .lp model, to generate observations that can be used to check the correctness of the wrong model;
5. `arbolom-revision` is ran on the corrupted model alongisde the generated observations, to revise it. 

Note: Alternatively, instead of using `arbolom-revision`, `arbolom-consistency` can also be used on the inconsistent .lp model, alongside the observations generated from the original model. This tool will tell you if the model is consistent with the given observations or not. In case it is not, the inconsistencies generated can then be given to `arbolom-repair`, which will repair the inconsistent model (`arbolom-revision` simply streamlines this process, doing it all at once).

## Benchmarking
The files used for benchmarking can be found [here](https://drive.google.com/drive/folders/1larx4vTX602bdXbAS1NtjSpwm8muxYHM?usp=sharing). The folder is organised as follows:
- There is one folder containing the original models;
- There is another folder containing all the applied corruption configurations to the original models;
- There is a folder with the observations obtained from the original models (the time-series observations were generated using `arbolom-gen-observations`);
- There is one last folder containing results obtained from the benchmarks.

## Task Progress

[![Task 1 - Create simple models](https://img.shields.io/badge/Task_1-Create_simple_models-green?style=for-the-badge&logo=Adobe+Acrobat+Reader)](https://github.com/fpaleixo/arbolom/tree/main/simple_models) 
[![Task 2 - Script for model corruption](https://img.shields.io/badge/Task_2-Script_for_model_corruption-green?style=for-the-badge&logo=python)](https://github.com/fpaleixo/arbolom/blob/main/corruption.py)
[![Task 3 - Script for model conversion](https://img.shields.io/badge/Task_3-Script_for_model_conversion-green?style=for-the-badge&logo=python)](https://github.com/fpaleixo/arbolom/blob/main/conversion.py)
[![Task 4 - Encodings to create observations](https://img.shields.io/badge/Task_4-Encodings_to_create_observations-green?style=for-the-badge&logo=dev.to)](https://github.com/fpaleixo/arbolom/tree/main/encodings)
[![Task 5 - Encodings for model consistency](https://img.shields.io/badge/Task_5-Encodings_for_model_consistency-green?style=for-the-badge&logo=dev.to)](https://github.com/fpaleixo/arbolom/tree/main/encodings)
![Task 6 - Define repair strategy](https://img.shields.io/badge/Task_6-Define_repair_strategy-green?style=for-the-badge&logo=Adobe+Acrobat+Reader)
[![Task 7 - Encodings to repair models](https://img.shields.io/badge/Task_7-Encodings_to_repair_models_(and_respective_optimizations)-green?style=for-the-badge&logo=dev.to)](https://github.com/fpaleixo/arbolom/tree/main/encodings)
![Task 8 - Benchmarking and writing the document](https://img.shields.io/badge/Task_8-Benchmarking_and_writing_the_document-green?style=for-the-badge&logo=dev.to)

### Timestamps (relative*)

Task 1: Week 1 (07/03 to 09/03)

Task 2: Week 1-2 (09/03 to 17/03)

Task 3: Week 2-3 (17/03 to 21/03)

Task 4: Week 3-4 (21/03 to 28/03)

Task 5: Week 4-5 (28/03 to 05/04)

Task 6: Week 5-6 (05/04 to 11/04)

Task 7: Week 6-21 (11/04 to 01/08)

Task 8: Week 20-29 (29/07 to 30/09)

\* *for reference only - dates are not absolutely exact and deliverables usually suffer tweaks/changes after these  periods*



##

This work is licensed under a
[Creative Commons Attribution 4.0 International License][cc-by].

[![CC BY 4.0][cc-by-image]][cc-by]

[cc-by]: http://creativecommons.org/licenses/by/4.0/
[cc-by-image]: https://i.creativecommons.org/l/by/4.0/88x31.png
[cc-by-shield]: https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg
