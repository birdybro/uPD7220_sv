# uPD7220_sv

Independent SystemVerilog reimplementation of the NEC μPD7220 and Intel
82720 Graphics Display Controller.

This project is under active incremental development. It does **not** yet claim
complete functional or cycle accuracy. The implemented scope currently covers
the physical/split-bus wrappers, asynchronous host transfers, the half-duplex
FIFO, base opcode parsing, dedicated RESET, and RESET/SYNC/VSYNC register
programming, START/BCTRL idle and blank control, falling-edge-aligned horizontal
raster timing, and noninterlaced vertical/master-sync timing. Accuracy claims
are limited to primary-source requirements with executable tests.

## Reference corpus

The repository records metadata and pinned SHA-256 hashes rather than
redistributing vendor manuals. Fetch and verify the research corpus with:

```sh
make references
make references-verify
```

See [`references/README.md`](references/README.md) for the corpus policy and
[`references/manifest.tsv`](references/manifest.tsv) for exact provenance.

## Current checks

```sh
make setup-dev
make lint
make test
make test-timing
```

`make test` runs Python/model unit tests and all current Verilator+cocotb RTL
suites. Simulation output, seed-specific build files, and waveforms are written
below `build/`. Set a deterministic seed with `GDC_SEED`, for example:

```sh
make test-random GDC_SEED=29216
```

See [`docs/verification.md`](docs/verification.md) for the test architecture and
current scope. Additional formal and synthesis targets will be introduced with
the implementation milestones they verify.

The independent, edge-steppable architectural model begins in
[`model/upd7220_model.py`](model/upd7220_model.py). Its implemented scope is
intentionally narrower than the final command set and is expanded only with
primary-source-backed tests.

## RTL interfaces

[`rtl/upd7220.sv`](rtl/upd7220.sv) is the physical-bus wrapper. The split-bus
[`rtl/upd7220_core.sv`](rtl/upd7220_core.sv) is intended for FPGA integration and
verification. See [`docs/architecture.md`](docs/architecture.md),
[`docs/commands.md`](docs/commands.md), and [`docs/timing.md`](docs/timing.md)
for the exact implemented boundary and [`docs/open_questions.md`](docs/open_questions.md)
for unresolved source ambiguities.
