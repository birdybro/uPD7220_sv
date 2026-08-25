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
second rising edge, representing the manual's two-clock machine/word time. All
future memory, command, DMA, and raster state machines use clock enables; no
derived clock is introduced.

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

## Compatibility profiles

`upd7220_pkg::gdc_variant_t` defines three explicit profiles:

- `GDC_7220` (default)
- `GDC_82720`
- `GDC_7220A`

Variant gates are elaboration-time parameters. Base behavior must never depend
on a 7220A-only enhancement.
