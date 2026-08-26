# Verification architecture

The verification environment drives the Python architectural model and
SystemVerilog RTL with identical deterministic stimuli. Its current scope
covers reset, FIFO/parser/register behavior including CURS/CURD, horizontal
raster timing, and noninterlaced vertical/master-sync pin timing. Later command,
memory, drawing, DMA, interlace, and slave-sync layers remain pending.

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
make test-timing # independent model and exact video-edge traces
make test       # normal unit and RTL regression
make test-all   # currently aliases the complete available regression
```

The timing target checks every horizontal HFP/HSYNC/HBP/AW and noninterlaced
vertical VFP/VS/VBP/AL transition, the two-rising-edge word cadence,
falling-edge video output changes, composed BLANK behavior, and reset from
active horizontal and vertical sync intervals.

Display-control tests separately verify the enable request and idle latch:
BCTRL/SYNC cannot leave idle, START both enables and leaves idle, pin blanking
samples the combined state on a falling edge, and RESET restores idle.

Pitch tests exhaust representative literal boundaries (`00h`, `01h`, `7Fh`,
`FEh`, and `FFh`), RESET/SYNC-derived loads including AW=256 wrap, retention
across RESET without optional P2, unrelated-parameter isolation, and the full
host/FIFO/parser/register path.

Cursor tests cover EAD zero and 18-bit boundaries, every significant P3 field,
dAD values 0, 7, 10, and 15, one-hot mask expansion, character-mode two-byte
prefix interruption, RESET retention, CURD snapshot isolation, producer
backpressure, all five returned bytes, four-edge host-data-register refill, and
new-command abortion of unread response bytes. The integrated test drives only
the asynchronous host pins and checks the documented byte order via status
polling and FIFO reads.

MASK tests load `0000h`, `FFFFh`, `A55Ah`, `8001h`, and an asymmetric shared
CURS/MASK sequence. They verify low-before-high assembly, immediate P1 effect,
new-command interruption after P1, prior-high-byte retention, RESET retention,
EAD isolation, CURS replacement of an arbitrary mask, and CURD readback through
the complete host/FIFO path.

Parameter RAM tests load all 16 locations both sequentially from SA=0 and as P1
from every SA value, verify the packed byte ordering, interrupt a partial stream,
check unrelated-parameter isolation, retain data across functional RESET, and
exercise the complete asynchronous host/FIFO/parser/register route. Per-byte RTL
assertions prove that a write loads its selected byte and leaves every other byte
stable.

Display-partition tests independently pack and decode the primary Figures 10
and 11 layouts. The RTL suite covers two graphics and mixed areas, all four
character areas, current-versus-future descriptor rewrites, exact line-count
transitions, character-row repetition, image every-other-slot behavior, wide
two-word increments, and 13-, 16-, and 18-bit DAD wrapping. A full integration
test sends SYNC, PRAM, RESET, and START through the asynchronous host/FIFO/parser
path and observes area and DAD transitions on the live raster. The Python model
uses boundary-triggered descriptor decoding rather than the RTL decoder's
structure and checks the same architectural vectors.

Memory-interface primitive tests sample every rising and falling 2xWCLK edge.
They verify address drive throughout C1, ALE's midpoint fall and completion
rise, AD release, display-data sampling at the end of C2, the DBIN-low window
from mid-C2 to mid-C3, RMW read sampling, C4 write stability, A16/A17, a
back-to-back cycle with no idle bubble, and reset during an asserted DBIN. A
separate Python timing table produces five display/refresh half-edge samples
and nine RMW samples without reusing the RTL state-machine structure. The
refresh trace proves that C2 neither samples AD nor asserts DBIN. Assertions
prove that DBIN and GDC AD drive never overlap and that an RMW write cannot
precede the read phase.

The integrated graphics-fetch test programs SYNC, PITCH, two PRAM areas, RESET,
and START solely through asynchronous host pins. Its recorded physical address
sequence crosses line pitch, partition, image-repeat, and upper-address-bank
boundaries: `30100,30101,30104,30105,20200,20200`. An independent model emits
the same accepted-fetch sequence. The memory-side driver supplies a distinct
word for every address and the test checks the primitive's end-C2 samples.
A second trace proves that idle emits no memory cycle, BCTRL DE=0 leaves the
running scan cadence intact while BLANK is high, and BCTRL DE=1 restores
unblanked fetches.

Refresh tests independently exercise the eight-bit scheduler with backpressure,
enable/HSYNC gating, RESET, all 256 counter values, and wrap. The integrated
host-programmed raster uses HS=3 and proves the physical sequence `00,01,02`
on one HSYNC followed by `03,04,05` on the next. It checks exact two-clock
spacing, the full-line gap, BLANK, inactive DBIN, zero-extended FPGA output,
operation while still idle, and an entirely unclaimed HSYNC bus when D=0.

The smoke DUT under `tests/rtl/` remains a minimal check of SystemVerilog
compilation, VPI loading, cocotb scheduling, and waveform generation independent
of the physical GDC wrapper.

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
advances rising and falling 2xWCLK edges explicitly, and hashes architectural
state and the full 256K-word display memory deterministically. Its RESET primitive preserves
programmed parameter state while clearing the FIFO and active operations, as the
base-device data sheet requires.

## Failure policy

A failing random vector must be retained as a fixed regression when practical.
Failures are classified by consulting primary documentation before changing
either model or RTL. No milestone commit is made until targeted tests, the full
available regression, and lint all pass.
