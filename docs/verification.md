# Verification architecture

The verification environment is designed to drive the Python architectural
model and SystemVerilog RTL with identical deterministic stimuli. At the current
bootstrap milestone, it proves the tool flow itself; it does not yet prove any
GDC behavior.

## Tool bootstrap

The normal setup creates an ignored virtual environment and installs pinned
versions of pytest and cocotb:

```sh
make setup-dev
```

Python 3.11 through 3.13 is preferred because cocotb 2.0.1 officially supports
those versions. The bootstrap also permits a source build on Python 3.14; that
path is exercised by the regression on development hosts where 3.14 is the only
interpreter. A specific supported interpreter can be selected without modifying
the repository:

```sh
make setup-dev PYTHON=python3.13
```

## Regression entry points

```sh
make lint       # Python syntax/schema checks and Verilator lint
make test-unit  # simulator-independent unit tests
make test-rtl   # Verilator+cocotb tests
make test       # normal unit and RTL regression
make test-all   # currently aliases the complete available regression
```

The smoke DUT under `tests/rtl/` exists only to test clock/reset, SystemVerilog
compilation, VPI loading, cocotb scheduling, and waveform generation before the
physical GDC wrapper is introduced.

## Deterministic failures

The default seed is hexadecimal 7220. Override it with either the environment or
pytest option:

```sh
make test-random GDC_SEED=29216
.venv/bin/python -m pytest --gdc-seed=29216 tests
```

`SeedContext` owns its own Python random generator so unrelated libraries cannot
perturb a sequence. Its failure report includes the integer seed, cycle,
commands, parameters, register state, memory hash, expected value, observed
value, and a reproduction command.

Each RTL build uses `build/sim/<test>-seed-<seed>/`. Waveform generation is
enabled for every RTL run so a failure never needs to be rerun merely to capture
the trace. The pytest wrapper prints the exact artifact directory and seed when
simulation fails.

## Reusable agents and models

- `tests/cocotb/host.py` drives asynchronous command, parameter, status, and FIFO
  cycles against the core's split host bus and permits phase offsets relative to
  2xWCLK.
- `tests/support/memory.py` supplies independent 256K-by-16 storage, masked
  writes, deterministic whole-memory hashes, and validated transaction records.
- `tests/cocotb/memory.py` is the edge monitor for the future physical
  display-memory bus. Each record contains 2xWCLK count, cycle type, owner, ALE,
  DBIN, address, data direction, read/write data, BLANK, A16, and A17.

The architectural model will not import RTL implementation logic. Cocotb agents
translate only between pin activity and independent model/test data structures.

The model represents undocumented pre-RESET status as explicitly unavailable,
advances one rising 2xWCLK edge per call, and hashes architectural state and the
full 256K-word display memory deterministically. Its RESET primitive preserves
programmed parameter state while clearing the FIFO and active operations, as the
base-device data sheet requires.

## Failure policy

A failing random vector must be retained as a fixed regression when practical.
Failures are classified by consulting primary documentation before changing
either model or RTL. No milestone commit is made until targeted tests, the full
available regression, and lint all pass.
