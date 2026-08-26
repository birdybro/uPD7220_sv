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

## Parameter RAM

`upd7220_pram` owns the 16 raw bytes RA0 through RA15 and a verification-only
programmed-byte mask. PRAM's opcode start address and registered parser index
form a five-bit checked address; each parameter changes only the selected byte.
The command parser prevents an address beyond RA15 and permits a new command to
stop any partial load.

Integration reset establishes deterministic zeros for FPGA use. The functional
RESET command blocks a coincident write but retains all Parameter RAM bytes, as
required for programmer-loaded parameters. Dedicated consumers interpret the
partition fields now and will later interpret graphics drawing patterns and
graphics-character scan order; the raw store itself imposes none of them.

## Display partitions and DAD

`upd7220_partitions` interprets the raw Parameter RAM only when a display area
begins. Character mode uses four RA0/4/8/12 descriptors with 13-bit SADs;
graphics and mixed modes use two RA0/4 descriptors with 18-bit SADs, leaving
RA8 through RA15 available for drawing patterns. Each descriptor latches its
SAD, ten-bit line count, image bit, and wide bit. The later-area fetch boundary
is important: software may update a future partition during the current one,
while changing any byte of the current four-byte descriptor cannot perturb the
already running area.

DAD is normalized to the address range externally supported in each mode:
13 bits in character mode, 16 bits in mixed mode, and 18 bits in graphics mode.
At a graphics scanline boundary the saved line base advances by pitch. A
character area repeats the line base for the programmed character-row height,
then advances by pitch for the next character row. The standalone partition
block already accepts the actual row height; the integrated core supplies one
until the later CCHAR milestone connects its decoded LR register.

A normal display slot advances DAD by one word, and WD advances it by two.
When IM is set, one address is held for two successive display slots before
that increment. In mixed mode the same IM bit classifies the area as graphics;
in character mode it selects the documented every-other-read DAD operation.
The application manual also documents this repeated-address operation in
graphics mode, while requiring IM=0 for normal graphics display.

The partition block currently produces the address stream consumed by the
future display-memory-cycle scheduler. It does not yet drive AD/A16/A17, issue
ALE/DBIN, fetch display data, or generate mode-dependent character pins; those
are separate bus and character-timing milestones.

## Display-memory cycle primitive

`upd7220_memif` owns the split physical AD, A16/A17, ALE, and DBIN signals. Its
request boundary accepts either a two-clock display/read cycle or a four-clock
RMW cycle. The address is latched when a request starts and driven on AD for all
of C1, while A16/A17 retain its upper bits through the complete primitive.

ALE uses a rising-edge cycle epoch and a falling-edge acknowledgement. This
produces the documented high first half of C1 and low remainder without a
dual-edge procedural block, an internal generated clock, or a synthesizable
delay. AD releases at the C1-to-C2 rising edge. A display access samples the
external value at the falling edge ending C2 for verification/convenience use;
original external video hardware independently loads its shift register there.

For RMW, DBIN falls at the midpoint of C2, stays low through the first half of
C3, and rises at C3's midpoint when AD input is sampled. Upstream logic sees
that sample during the following half-cycle and supplies modified data. The
primitive latches it at the C4 rising edge, drives it for all of C4, then
releases AD. This boundary will allow MASK/WDAT/drawing logic to remain
separate from physical bus timing.

The final clock of either primitive may accept the next request, so consecutive
cycles have no idle bubble. Integration and functional reset immediately force
ALE/DBIN inactive-high and release AD, including a reset during DBIN or C4.
Assertions prevent AD drive during DBIN and require read-before-write ordering.

The primitive is connected to the public core pins and accepts unzoomed graphics
raster requests as described below. Refresh ownership, RMW arbitration, zoom
extension, and character/mixed A16/A17 multiplexing are not claimed yet.

## Graphics raster fetch scheduling

After START leaves idle, each active graphics word requests one two-clock
display primitive. The first request begins on the rising edge after horizontal
timing enters an active word. Its C2 completes in time for the horizontal block
to advance at the following falling word boundary; when another active word
follows, the next request is accepted at the immediately following rising edge.
This gives one address phase per programmed word with no idle memory clock.

The request address is the partition block's current DAD. The same handshake
that accepts C1 advances DAD, so a stalled or unavailable bus cannot make the
display address run ahead of observable memory cycles. At a line boundary the
partition sequencer reloads DAD from the saved line base plus pitch before the
next active interval. Area boundaries likewise load the newly fetched SAD.
Image mode therefore repeats an address on two accepted cycles and wide mode
steps by two only after an actual cycle begins.

Idle suppresses raster requests. Once START begins the display process, BCTRL
and SYNC DE only control BLANK and do not stop the address scan; this preserves
the documented distinction between display-process state and video blanking.
Reset aborts an in-progress primitive and returns the scheduler to idle.

Only graphics mode currently reaches this raw 18-bit path. Character mode must
multiplex line-count/cursor information onto AD13-15 and A16/A17, while mixed
mode uses A16/A17 for image/cursor/attribute control. Fetches for those modes
remain gated until those responsibilities are implemented and cycle-tested.

## Compatibility profiles

`upd7220_pkg::gdc_variant_t` defines three explicit profiles:

- `GDC_7220` (default)
- `GDC_82720`
- `GDC_7220A`

Variant gates are elaboration-time parameters. Base behavior must never depend
on a 7220A-only enhancement.
