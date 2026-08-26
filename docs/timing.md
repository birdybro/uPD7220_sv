# Timing model

This document separates three classes of timing:

1. digital state transitions tied to 2xWCLK edges, which synthesizable RTL can
   reproduce;
2. external setup, hold, pulse-width, and propagation limits, which belong in
   simulation timing checks and board-level constraints; and
3. portable-RTL-inexpressible transistor/trace delays, which are not emulated
   with `#delay` statements.

The primary sources for the normalized values below are Intel's *82720 Graphics
Display Controller Preliminary Data Sheet* (June 1983), printed pages 27–32,
and Intel's *82720 Graphics Display Controller Application Manual*, 230685-001
(July 1983), sections 2.5, 4.25.2, and 5.1. The NEC design manual Version 3
contains the corresponding descriptions on printed pages 107–112.

## Clock vocabulary

`TCY` is one complete 2xWCLK period. One display-memory word time is two 2xWCLK
cycles. The RTL therefore uses only `clk_2x` and creates a clock-enable pulse on
every second rising edge; it does not create a derived clock.

| Device/speed grade | TCY minimum | TCY maximum | high minimum | low minimum |
|---|---:|---:|---:|---:|
| 82720 base | 250 ns | 2000 ns | 105 ns | 105 ns |
| 82720-1 | 200 ns | 2000 ns | 80 ns | 80 ns |
| 82720-2 | 180 ns | 2000 ns | 70 ns | 70 ns |

Clock rise and fall times are each limited to 20 ns maximum. Speed-grade
limits are electrical constraints, not different logical command profiles.

## Host read and write requirements

The host strobes are asynchronous to 2xWCLK. The synthesizable core captures
the selected read source on falling RD and holds the host output register for
the entire low strobe. A0 is captured on falling WR and data on rising WR.

Base 82720 limits from printed page 27 are:

| Symbol | Requirement | Minimum | Maximum |
|---|---|---:|---:|
| TAR | A0 setup to falling RD | 0 ns | — |
| TRA | A0 hold after falling RD | 0 ns | — |
| TRR | RD pulse width | `TRD + 20 ns` | — |
| TRD | falling RD to data valid | — | 120 ns |
| TDF | rising RD to data float | 0 ns | 120 ns |
| TRV | RD recovery | 4 TCY | — |
| TAW | A0 setup to falling WR | 0 ns | — |
| TWA | A0 hold after falling WR | 0 ns | — |
| TWW | WR pulse width | 120 ns | — |
| TDW | data setup to rising WR | 100 ns | — |
| TWD | data hold after rising WR | 0 ns | — |
| TRV | WR recovery | 4 TCY | — |

The -1 grade reduces TRD to 80 ns, TDF to 100 ns, TWW to 100 ns, and TDW to
80 ns. The -2 grade reduces those values to 70 ns, 90 ns, 90 ns, and 70 ns and
requires 10 ns A0/data hold after rising WR. These are not implemented as
delays inside RTL. A later simulation-only timing-check module owns violations.

## FIFO edge rules

- A host byte may be transferred no more often than once per four 2xWCLK
  cycles, irrespective of FIFO FULL or DATA READY.
- The FIFO contains 16 ring locations shared half-duplex between directions.
- Host access has priority when host and command processor contend for the next
  ring access.
- A byte waiting in a read-direction ring takes four 2xWCLK rising edges to
  reach the separate host data register. DATA READY changes only when that
  transfer completes; FIFO EMPTY reports the ring, not the host data register.
- Direction turnaround empties the ring and host data register.

These boundaries are cycle-tested in `tests/cocotb/test_fifo.py`.

## RESET recognition and edge sequence

RESET opcode `00h` is documented as decoded by dedicated hardware ahead of the
FIFO. It must work without first trusting FIFO FULL and must initialize FIFO,
status, the command processor, and internal counters. The manuals do not state
an exact 2xWCLK edge from asynchronous rising WR to initialized status.

The portable RTL uses a level request/acknowledge crossing, chosen so the first
RESET converges from arbitrary pre-RESET event-toggle state:

| Relative event | Digital action |
|---|---|
| rising WR | A0/data identify RESET and force the host-domain request high |
| first following rising 2xWCLK | request enters synchronizer stage 1 |
| second following rising 2xWCLK | synchronized RESET level asserts; normal host event CDC is cleared |
| third following rising 2xWCLK | FIFO, parser, idle/status, word-time phase, and safe output state observe RESET |
| acknowledgement drain | RESET remains asserted long enough to clear both domains, then deasserts |

This edge sequence is an engineering implementation contract, not a claimed
vendor propagation value. It is tested in `tests/cocotb/test_foundation.py`.
The four-TCY host recovery requirement prevents a conforming subsequent access
from observing the intermediate synchronizer stages.

After recognition, status is `04h` in the currently implemented status subset:
FIFO EMPTY=1, FIFO FULL=0, DATA READY=0, and all implemented activity flags are
zero. The display is blanked, idle mode is set, memory buses are released, DBIN
is inactive, ALE is high, DRQ is low, and optional RESET parameters may follow.

## RESET/SYNC timing-register encodings

The eight parameter bytes update their destinations as the command processor
consumes them; a later command terminates the sequence and unreceived registers
retain their earlier values. Decoded counts are:

| Field | Encoding | Decoded count |
|---|---|---|
| AW | P2[7:0] | raw + 2 display words; valid programmed range is even 2–256 |
| HS | P3[4:0] | raw + 1 word times |
| VS | `{P4[1:0],P3[7:5]}` | raw lines, with zero meaning 32 |
| HFP | P4[7:2] | raw + 1 word times |
| HBP | P5[5:0] | raw + 1 word times |
| VFP | P6[5:0] | raw lines, with zero meaning 64 |
| AL | `{P8[1:0],P7[7:0]}` | raw lines, with zero meaning 1024 |
| VBP | P8[7:2] | raw lines, with zero meaning 64 |

P1 uses C=P1[5] and G=P1[1] for mixed/graphics/character mode; I=P1[3]
and S=P1[0] select framing; D=P1[2] enables refresh; F=P1[4] restricts
drawing to retrace when set. Exact raster counter load/edge behavior follows in
the horizontal and vertical timing milestones.

SYNC opcode bit DE changes requested display enable. VSYNC opcode bit M changes
the V/EXT SYNC pin direction: M=0 releases it for slave input and M=1 drives it
for master output. The direction change is end-to-end tested through the host
interface; the vertical waveform itself is pending.

## Display-memory electrical timing (base 82720)

The following page-27 values are recorded now for the memory-cycle milestones;
they are not yet implementation claims:

| Symbol | Relationship | Minimum | Maximum |
|---|---|---:|---:|
| TCA | rising 2xWCLK to address/data | 30 ns | 160 ns |
| TAC | address/data float time | 30 ns | 160 ns |
| TDC | data setup to falling 2xWCLK | 0 ns | — |
| TCD | data hold | `TIE - 20 ns` | — |
| TIE | falling 2xWCLK to DBIN | 30 ns | 120 ns |
| TCAH | rising 2xWCLK to rising ALE | 30 ns | 125 ns |
| TCAL | falling 2xWCLK to falling ALE | 30 ns | 100 ns |
| TAL | ALE low time | `TCY + 30 ns` | — |
| TAH | ALE high time | `TCH - 20 ns` | — |
| TCO | falling 2xWCLK to video signal | — | 150 ns |

RTL will reproduce which clock edge begins each phase and the logical
relationships among AD, ALE, DBIN, and direction. The nanosecond propagation
columns will become assertions/checks, not synthesizable delay statements.

## Pending timing normalization

The following source diagrams still require machine-readable edge tables as
their implementation milestones arrive: display read/write/RMW cycles,
display-fetch and refresh ownership, DRQ/DACK sequencing, drawing execution
latency, horizontal and vertical raster edges, master/slave synchronization,
light-pen sampling/deglitching, interlace half-lines, and active-display memory
arbitration. Until those tables and tests exist, the project does not claim
cycle accuracy for those subsystems.
