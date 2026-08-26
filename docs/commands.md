# Command reference

This catalog is the implementation-facing transcription of Intel's *82720
Graphics Display Controller Preliminary Data Sheet* (June 1983), Figure 12 and
the command figures on printed pages 17–25. Parameter-prefix behavior is
cross-checked against Intel's *82720 Graphics Display Controller Application
Manual*, 230685-001 (July 1983), especially sections 4.11, 4.12, 5.1.4, and
5.1.5.

The table records base μPD7220/Intel 82720 decoding. μPD7220A-only opcodes are
reserved in the base profiles until their separate compatibility milestone.
“Decode verified” means opcode recognition and parser byte boundaries are
exhaustively tested; it does not claim that the command's architectural or
memory-cycle effects are implemented yet.

## Base command map

Bit patterns are written from D7 through D0. `TT` is transfer type, `MM` is the
read-modify-write modifier, `DE` is display enable, `M` selects sync master, and
`SA` is the four-bit Parameter RAM start address.

| Command | Encoding | Parameter bytes accepted by parser | Architectural destination/effect | FIFO and completion rule | Current status |
|---|---:|---:|---|---|---|
| RESET | `00` | 0–8 | Reset control state; optional bytes use SYNC format | Dedicated pre-FIFO path; a new command terminates the optional prefix | Reset and sync-format parameter effects unit verified |
| SYNC | `0E`, `0F` (`0000111DE`) | 8 | Mode and raster-format registers; DE controls display | Completes after P8 or is interrupted by a new command | Register effects unit verified |
| VSYNC | `6E`, `6F` (`0110111M`) | 0 | Master/slave vertical-sync selection | Completes with opcode | Register and pin-direction effects unit verified |
| CCHAR | `4B` | 3 | Character row, cursor, and blink registers | Completes after P3 | Decode verified |
| START | `6B` | 0 | Exit idle and force display enable | Completes with opcode | Control effect unit verified |
| BCTRL | `0C`, `0D` (`0000110DE`) | 0 | Change display enable without leaving idle | Completes with opcode | Control effect unit verified |
| ZOOM | `46` | 1 | Display and graphics-character zoom | Completes after P1 | Decode verified |
| CURS | `49` | 2 in character mode; 3 in graphics mode | EAD and, for graphics, dAD/mask | Parser accepts a three-byte maximum; a new command legally terminates after P2 | Decode verified |
| PRAM | `70`–`7F` (`0111SA`) | 1 through `16-SA` | Sequential Parameter RAM locations SA through 15 | Ends at location 15 or when a new command arrives | Decode verified |
| PITCH | `47` | 1 | Load literal base 8-bit display-memory horizontal pitch | Completes after P1 | Register effect unit verified |
| WDAT | `001TT0MM` | Repeated groups of 2 for word or 1 for byte | Pattern/data input for display-memory RMW writes | Remains active for further groups until a new command | Decode verified |
| MASK | `4A` | 2 | 16-bit mask, low byte then high byte | Completes after P2 | Decode verified |
| FIGS | `4C` | 0–11 | Figure type/DIR, then DC, D, D2, D1, and DM | Registers initialize on opcode; the optional ordered prefix ends at P11 or on a new command | Decode verified |
| FIGD | `6C` | 0 | Start figure drawing | Completes with opcode | Decode verified |
| GCHRD | `68` | 0 | Start graphics-character drawing/area fill | Completes with opcode | Decode verified |
| RDAT | `101TT0MM` | 0 | Start display-memory read | Reverses FIFO direction; queued following bytes are discarded | Decode verified |
| CURD | `E0` | 0 | Return three bytes of EAD/dAD | Reverses FIFO direction | Decode verified |
| LPRD | `C0` | 0 | Return three bytes of captured LAD | Reverses FIFO direction and clears light-pen status at the documented transfer point | Decode verified |
| DMAR | `101TT1MM` | 0 | Start DMA display-memory read | DMA bypasses host FIFO | Decode verified |
| DMAW | `001TT1MM` | 0 | Start DMA display-memory write/RMW | DMA bypasses host FIFO | Decode verified |

For all four transfer families, `TT=00` means word with low byte first,
`TT=10` means low byte only, `TT=11` means high byte only, and `TT=01` is
explicitly invalid. `MM=00`, `01`, `10`, and `11` select replace, complement,
reset-to-zero, and set-to-one for write/RMW operations. The RDAT data sheet says
to use `MM=00`; effects of other RDAT modifier values are not yet claimed.

## Parser rules

- Each host-to-GDC FIFO location retains the A0-derived command/parameter tag.
- A command tag is decoded regardless of the current parameter position and
  terminates any active optional or incomplete parameter sequence.
- Fixed sequences complete only after their final parameter byte.
- FIGS parameters are accepted only in the documented fixed order. A field
  cannot be skipped to load a later field.
- WDAT parameter indices wrap at the selected word/byte group boundary rather
  than completing the command.
- A parameter with no active parameter-taking command is consumed and reported
  as unexpected; its architectural effect is undefined.
- The parser exposes a processing enable so command execution and memory
  arbitration can stall FIFO consumption in later milestones.

`tests/cocotb/test_command.py` checks all 256 byte values, every valid transfer
family/member, every invalid transfer-type hole, fixed completion boundaries,
all PRAM starting addresses, optional-prefix interruption, repeated WDAT groups,
unexpected parameters, and processor stalls. `tests/model/test_command_model.py`
independently checks the same architectural map and stream transitions.

## Execution timing status

Opcode consumption is currently represented as one registered parser event on
an enabled 2xWCLK edge. This is an internal interface, not yet a claim about the
final command's externally visible completion latency. Command-specific FIFO
stalling, register-update points, memory scheduling, drawing/DMA busy timing,
and read-direction turnaround are verified in their respective milestones.

START and BCTRL have separate state effects. START sets display enable and
permanently leaves idle until the next RESET. BCTRL DE=0/1 changes the display
enable request but never changes idle. Consequently, BCTRL DE=1 during idle does
not unblank the pin; a later START is still required. SYNC DE controls the same
enable request and likewise does not leave idle. The request is sampled into
the BLANK path on a falling 2xWCLK edge.

PITCH loads its parameter literally, including `00h` and `FFh`. RESET/SYNC P2
also loads pitch through the eight-bit `(P2 + 2)` result. Thus AW=256 is retained
as a nine-bit active display count while the base pitch register contains
`00h`; `00h` is not silently decoded as 256. The evidence/inference boundary
for that zero case is recorded in `docs/open_questions.md`.

## Variant notes

The December 1985 NEC μPD7220/μPD7220A user's manual Appendix E identifies
additional A-revision command encodings including RESET2 (`01`), RESET3 (`09`),
and BLANK2 (`05`). These remain unknown/reserved under the base 7220 and 82720
decoder. They will be enabled only under `GDC_7220A` with separate tests.
