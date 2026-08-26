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
drawing to retrace when set. Horizontal and noninterlaced vertical count/edge
behavior is normalized below.

SYNC opcode bit DE changes requested display enable. VSYNC opcode bit M changes
the V/EXT SYNC pin direction: M=0 releases it for slave input and M=1 drives it
for master output. The direction change is end-to-end tested through the host
interface. In master mode, the noninterlaced waveform described below reaches
the output side of that pin; slave acquisition and interlace remain pending.

## Horizontal raster edge table

Intel application manual section 6.1.1 defines every line, in order, as HFP,
HSYNC, HBP, and AW. The first three intervals are blanked; AW is unblanked only
when display output is enabled. With `p` as the zero-based word position:

| Position range | Interval | HSYNC | horizontal blank | BLANK when DE=1 |
|---|---|---:|---:|---:|
| `0 <= p < HFP` | front porch | 0 | 1 | 1 |
| `HFP <= p < HFP+HS` | sync | 1 | 1 | 1 |
| `HFP+HS <= p < HFP+HS+HBP` | back porch | 0 | 1 | 1 |
| remaining `AW` words | active | 0 | 0 | 0 |

When DE=0, BLANK remains 1 in all four ranges; the horizontal counter and
HSYNC continue to run. A line therefore consumes exactly
`2 * (HFP + HS + HBP + AW)` rising 2xWCLK periods.

The Intel preliminary data-sheet page-31 video-output waveform specifies TCO
from a falling 2xWCLK edge to HSYNC/BLANK. The synthesizable edge contract is:

| Clock edge after a word boundary | `word_time_ce` | Raster/pin action |
|---|---:|---|
| first rising edge | 0 | retain current word |
| first falling edge | 0 | retain video pins |
| second rising edge | 1 | mark completion of the two-clock word time |
| second falling edge | 1 | advance interval/word index; update HSYNC and BLANK |

No `#delay` models TCO. The RTL reproduces its controlling digital edge;
nanosecond propagation limits remain the responsibility of simulation timing
checks and implementation timing analysis. `tests/test_rtl_video_timing.py`
checks the complete boundary trace and `tests/test_rtl_foundation.py` verifies
the end-to-end two-clock cadence through the integrated core.

## Noninterlaced vertical raster edge table

The vertical intervals have the cyclic order VFP, VS, VBP, and AL. The
noninterlaced implementation uses VFP as the reset origin; the absence of an
explicit primary-source reset origin is recorded as OQ-001 in
`docs/open_questions.md`. With `q` as the zero-based line position:

| Position range | Interval | VSYNC | vertical blank |
|---|---|---:|---:|
| `0 <= q < VFP` | front porch | 0 | 1 |
| `VFP <= q < VFP+VS` | sync | 1 | 1 |
| `VFP+VS <= q < VFP+VS+VBP` | back porch | 0 | 1 |
| remaining `AL` lines | active | 0 | 0 |

One field consumes `(VFP + VS + VBP + AL)` complete horizontal lines. Every
vertical transition consumes the horizontal block's `line_advance_ce` on the
same falling edge that changes from the last AW word to the first HFP word.
Thus normal VSYNC transitions coincide with the leading BLANK edge, as required
by the interlace discussion's first-field rule and the page-31 TCO waveform.

The externally visible blank output is currently:

```text
BLANK = not display_enable or horizontal_blank or vertical_blank
```

Display-memory ownership will later suppress non-display fetches as an
additional term. `tests/test_rtl_vertical_timing.py` checks every line boundary;
`tests/test_rtl_foundation.py` checks that a 32-line VS pulse reaches the master
pin with exactly 320 falling-edge intervals for the default five-word line.

## Display-control timing

RESET sets `idle=1` and clears the display-enable request. SYNC and BCTRL replace
the request with opcode bit DE but do not change idle. START atomically sets
`idle=0` and the request to one at its registered command-start event. The
horizontal timing block samples the combined request on the following falling
2xWCLK edge, keeping BLANK changes aligned with the video-output TCO edge.

BCTRL DE=1 while idle therefore leaves BLANK asserted; START is the only base
command that exits idle. RESET re-enters idle from every display-control state.

## Display-partition and DAD edge table

Intel application-manual section 4.24.16 establishes that the first area's
four-byte descriptor has already been fetched during VBP, while a later area is
not needed until its boundary. The portable RTL represents this at the first
rising 2xWCLK edge that observes entry into the active vertical interval and at
the rising edge following each active-line boundary:

| Observed event | Latched/updated state |
|---|---|
| active-line rising transition | fetch area 0 SAD/LEN/IM/WD; load DAD and saved line base from SAD |
| next active line within the same area | increment line count; reset DAD to saved line base plus pitch for a graphics row |
| character scanline below LR | increment line counter; reset DAD to the unchanged character-row base |
| character scanline reaching LR | clear line counter; advance saved base and DAD by pitch |
| line count reaches the latched LEN | fetch the next area's four live PRAM bytes and load its SAD into DAD |
| active display slot, IM=0 | increment DAD by one, or two when WD=1 |
| two active display slots, IM=1 | hold DAD on the first and apply the one/two-word increment on the second |

The line count is latched with its descriptor, so rewriting the current LEN
cannot shorten or extend the area in progress. The independent core test checks
these events against the falling-edge raster generator and its following rising
partition edge. Physical ALE/DBIN transactions remain pending and are not
implied by this architectural DAD schedule; the implemented primitive below is
not connected to the partition request stream until the display-fetch milestone.

## Base display-memory primitive edge table

Every numbered clock begins on a rising 2xWCLK edge. Address and write drive
continue across the following falling edge and end at the next rising edge.
The pin state immediately after each controlling digital edge is:

| Edge | Display cycle | RMW cycle |
|---|---|---|
| rising C1 | ALE=1; drive address on AD and A16/A17 | same |
| falling C1 | ALE=0; continue driving address | same |
| rising C2 | release AD; ALE remains 0 | same |
| falling C2 | external video register may sample data; DBIN remains 1 | DBIN=0; memory drives read data |
| rising C3 | cycle complete; ALE=1, or next C1 begins | DBIN remains 0; memory continues driving |
| falling C3 | — | sample AD read data; DBIN=1 |
| rising C4 | — | drive the latched modified word; ALE remains 0 |
| falling C4 | — | continue driving the stable modified word |
| rising C5 | — | cycle complete; release AD and raise ALE, or begin next C1 |

The display sample in the RTL is an integration convenience and does not imply
that original silicon consumed raster data internally. In an original system,
external video hardware loads that word at the end of C2. RMW does consume the
read word and always performs C4 writeback, including read operations whose
writeback is unchanged.

## Unzoomed graphics fetch cadence

For a running graphics raster, the active-word and primitive edges compose as:

| Edge | Raster state | Memory action | DAD action |
|---|---|---|---|
| falling edge entering active word | active word becomes true | none | retain current line/area start |
| following rising edge | active word stable | accept display C1 and drive current DAD | advance/repeat DAD from the accepted-cycle handshake |
| following falling edge | same active word | ALE falls | no architectural address change |
| next rising edge | same active word | enter C2 and release AD | none |
| next falling edge | advance horizontal word/line | sample external display data | none |
| next rising edge | next word or retrace already selected | complete response; accept next C1 only if another active word exists | next accepted cycle advances DAD |

At active-line entry and every partition boundary, descriptor/line-base loading
occurs during horizontal retrace before the first active request. Thus the first
C1 of every line observes the newly selected SAD or pitched line base. BCTRL
changes BLANK but does not alter this cadence after START; RESET/idle prevents
requests entirely. The current integrated cadence is constrained to unzoomed
graphics mode until mode-pin multiplexing and zoom-lengthening milestones.

## Display-memory electrical timing (base 82720)

The following page-27 propagation/setup values are recorded separately from the
implemented digital-edge schedule; they are not portable RTL delay claims:

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

RTL now reproduces which clock edge begins each base unzoomed phase and the
logical relationships among AD, ALE, DBIN, and direction. The nanosecond
propagation columns will become assertions/checks, not synthesizable delays.

## Pending timing normalization

The following source diagrams still require machine-readable edge tables as
their implementation milestones arrive: zoom-extended memory cycles,
display-fetch and refresh ownership, DRQ/DACK sequencing, drawing execution
latency, interlaced vertical raster edges, slave synchronization, light-pen
sampling/deglitching, interlace half-lines, and active-display memory
arbitration. Until those tables and tests exist, the project does not claim
cycle accuracy for those subsystems.
