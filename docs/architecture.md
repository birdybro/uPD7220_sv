# Architecture

## Public interface boundary

`rtl/upd7220.sv` is the pin-faithful functional wrapper. It exposes the
documented 2xWCLK, host bus, display-memory bus, synchronization, blanking, DMA,
and light-pen signals. VCC and GND are omitted. The host DB bus, display AD bus,
and V/EXT SYNC pin are the only top-level tri-states.

`rtl/upd7220_core.sv` is the synthesizable integration boundary. Each
bidirectional or mode-dependent physical signal is split into input, output, and
output-enable components. No internal FPGA tri-state is used.

The physical IC has no reset pin. Accordingly, the pin wrapper does not invent
one: software must issue the RESET command before relying on state. The core has
an `integration_reset_n` sideband for FPGA configuration and verification. It is
tied inactive by the pin wrapper and is not part of claimed original-device
behavior.

## Clock foundation

2xWCLK is the only clock. A registered `word_time_ce` pulse occurs after every
second rising edge, representing the manual's two-clock machine/word time. The
video pin registers consume that enable on the following falling edge because
the vendor TCO specification references HSYNC and BLANK changes to falling
2xWCLK. No derived clock is introduced; use of the opposite edge is explicit.

The integration reset establishes electrically safe idle directions: host and
display-memory buses are released, V/EXT SYNC is an input, DBIN is inactive,
ALE is high, DRQ and sync are low, and display blanking is asserted. These values
describe FPGA integration reset, not undocumented silicon power-up behavior.

## Asynchronous host interface

RD and WR are asynchronous chip pins, not 2xWCLK-derived clocks. RD's falling
edge captures status or FIFO data into a host data register; DB is driven only
while RD remains low. WR's rising edge captures DB and the A0 command/parameter
tag. FIFO-read completion is likewise detected at RD's rising edge only when A0
selects FIFO data.

Stable event toggles pass through two-flop synchronizers into 2xWCLK. Captured
data remains unchanged until well after the event is consumed. This relies on
the data sheet's four-TCY recovery requirement and avoids an arbitrary faster
internal clock. Setup/hold and minimum-pulse checks remain simulation-only.

RESET does not use the ordinary event toggle. Its host-domain request is held
until a separately synchronized acknowledgement returns. This dedicated path
can converge from unknown pre-RESET toggle state, bypasses FIFO storage, clears
both host-interface domains, and initializes the FIFO/parser/status path. It
also leaves the parser ready for RESET's optional eight SYNC-format bytes.

## Half-duplex FIFO

`upd7220_fifo` implements the documented 16-entry tagged ring shared by both
directions. In write mode, entries contain the A0 command/parameter tag and the
host has priority over a simultaneous command-processor pop. A protocol-violating
seventeenth host write reproduces the manual's oldest-byte overwrite behavior;
occupancy never exceeds 16.

Direction turnaround clears the entire ring. The read direction also has the
documented separate host data register: FIFO EMPTY describes the ring, while
DATA READY describes that register. A waiting byte takes four 2xWCLK edges to
move from the ring into the register. A command write aborts read mode and is
accepted even when the read ring reports full.

## Command decoder and parameter parser

`upd7220_command` consumes tagged write-direction FIFO entries through an
explicit enable. Opcode decoding is centralized in `upd7220_pkg` and covers the
complete base Figure 12 map, including all modifiers and invalid transfer-type
holes. Registered events separate command start, parameter delivery, normal
completion, interruption by a later command, and unexpected parameters.

Fixed-length commands complete at their documented boundary. RESET, CURS, and
FIGS may be terminated by a new command after an optional prefix; PRAM derives
its maximum length from SA; WDAT repeats one- or two-byte groups until another
command arrives. This parser does not implement command effects. Those effects
consume its events in later register, memory, drawing, and DMA modules.

## Base RESET state

Opcode `00h` blanks the display, enters idle, releases the display-memory bus,
deasserts DMA request, initializes the word-time phase, empties the FIFO and
host data register, and reinitializes command parsing. Status becomes meaningful
only after this path runs. Parameter/register storage is not globally cleared;
the base manuals explicitly require previously loaded parameters to survive
unless optional RESET parameters overwrite the sync-format fields.

## SYNC and VSYNC registers

`upd7220_sync_control` retains the eight raw RESET/SYNC parameter bytes and
provides decoded count views without losing their original encodings. Received
prefix bytes update individually; fields not reached before a new command keep
their prior values. The block decodes display/framing modes, refresh and drawing
window selection, AW, HS, VS, HFP, HBP, VFP, AL, and VBP. Vertical
all-zero fields expand to their documented power-of-two maximum.

SYNC's opcode DE bit updates the requested display-enable state without
entering idle or clearing other state. VSYNC's M bit directly controls whether
the physical V/EXT SYNC pin is driven (master) or released as an input (slave).
The noninterlaced master waveform comes from the vertical timing block;
interlaced and slave resynchronization behavior remain later timing work.

## START, BCTRL, and idle

Idle and display enable are distinct state. RESET enters idle and clears the
enable request. SYNC and BCTRL update the enable request without changing idle;
START sets the request and exits idle. The BLANK path uses
`display_enable && !idle`, sampled on the documented falling video-output edge,
so BCTRL cannot accidentally start display scanning from idle.

## Horizontal raster timing

`upd7220_video_timing` implements the documented four-interval line sequence:
horizontal front porch, horizontal sync, horizontal back porch, then active
words. Every programmed count is measured in display-word times of two 2xWCLK
periods. Its explicit interval state and word index drive HSYNC, horizontal
blank, active-word qualification, and a line-start pulse.

HSYNC is high only in the sync interval. BLANK is high throughout all three
horizontal retrace intervals and remains high in the active interval when SYNC
has disabled display output. Horizontal timing continues while display output
is disabled. Vertical blanking is also combined into BLANK; memory-cycle
ownership will add the remaining qualification in its milestone.

## Noninterlaced vertical raster timing

`upd7220_vertical_timing` consumes the horizontal block's combinational
line-advance enable on the same falling edge that begins HFP. It counts VFP,
VSYNC, VBP, and active-line intervals, asserts vertical blank outside active
lines, and supplies the master V/EXT SYNC pin waveform. The independent model
uses one absolute line position rather than the RTL's interval counter.

The module currently generates the documented noninterlaced sequence for all
framing codes. This is correct while the device is in idle mode, where the
manual requires noninterlaced synchronization even when interlace is
programmed. START/idle blanking is implemented; switching the timing generator
to the programmed two-field half-line sequence after START remains pending. The
inferred RESET phase origin is recorded in `docs/open_questions.md`.

## Base pitch register

`upd7220_pitch` owns the base device's eight-bit display-memory row width.
PITCH P1 loads all eight bits literally. RESET/SYNC P2 loads `(P2 + 2)` into
the same eight-bit register, independently of the nine-bit decoded AW count;
therefore valid AW=256 produces base pitch `00h`. A RESET opcode without P2
retains the earlier pitch.

The explicit 7220A PH ninth bit is not mixed into the base behavior. Its
evidence-backed location is SYNC/RESET P5 bit 6 and will be enabled with
variant-specific tests in the A-profile milestone.

## Cursor address and CURD response

`upd7220_cursor` owns the 18-bit Execute Address and the shared 16-bit mask.
CURS P1/P2 update the low and middle EAD bytes independently. Graphics-mode P3
loads EAD bits 17:16 and expands its four-bit dAD field to a one-of-16 mask.
This incremental loading preserves the documented optional character-mode
two-byte prefix behavior. Functional RESET aborts a response without erasing
the programmer-loaded address or mask.

CURD snapshots EAD and mask on its registered command-start event and requests
FIFO read turnaround at that same command boundary. Its held-valid producer
emits the five Figure 28 bytes and keeps a byte stable whenever the FIFO's ring
RAM read port temporarily backpressures it. The FIFO then applies its existing
four-edge transfer into the separate host data register. A command written
during this response immediately returns the FIFO to write mode and discards
all unread bytes.

CURD P3 bits 7:2 are undefined on the device. The synthesizable implementation
uses zero for deterministic FPGA behavior, but no compatibility claim depends
on those bits.

## Compatibility profiles

`upd7220_pkg::gdc_variant_t` defines three explicit profiles:

- `GDC_7220` (default)
- `GDC_82720`
- `GDC_7220A`

Variant gates are elaboration-time parameters. Base behavior must never depend
on a 7220A-only enhancement.
