# uPD7220_sv

Independent SystemVerilog reimplementation of the NEC μPD7220 and Intel
82720 Graphics Display Controller.

This project is under active incremental development. It does **not** yet claim
complete functional or cycle accuracy. The implemented scope currently covers
the physical/split-bus wrappers, asynchronous host transfers, the half-duplex
FIFO, base opcode parsing, dedicated RESET, and RESET/SYNC/VSYNC register
programming, START/BCTRL idle and blank control, falling-edge-aligned horizontal
raster timing, noninterlaced vertical/master-sync timing, and the base eight-bit
pitch register, plus CURS address/mask programming and five-byte CURD readback.
MASK directly loads the same shared 16-bit modification register with
interruptible low-byte/high-byte semantics.
The raw 16-byte Parameter RAM and its addressed sequential loading are also
implemented. Its display-partition consumer decodes the character, graphics,
and mixed-mode descriptor formats, sequences DAD across scanlines and area
boundaries, and implements image/wide access stepping. Display-memory bus
primitive cycles now reproduce the two-clock display access and four-clock RMW
address, ALE, DBIN, turnaround, sampling, and writeback phases. Raster fetch
scheduling is connected for unzoomed graphics mode, including pitch, partition,
image-repeat, blanking, idle, and 18-bit address behavior. Enabled dynamic-RAM
refresh now occupies every HSYNC word with a two-clock address-only cycle and
successive eight-bit row addresses, independently of START or screen blanking.
The first WDAT execution slice supports word-format REPLACE with FIGS DIR=0 and
DC=0: it performs a physical four-clock masked RMW at EAD, advances EAD by
pitch, and implements base graphics all-zero/all-one versus character full-word
data semantics.
Character/mixed physical fetch pins, full drawing/DMA arbitration, zoom, and
fetched pixel use remain later milestones. Accuracy claims are limited to
primary-source requirements with executable tests.

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
