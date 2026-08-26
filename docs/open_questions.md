# Open specification questions

This file records unresolved digital behavior rather than silently assigning
certainty to an engineering choice. Each question remains tied to executable
tests for the currently selected interpretation.

## OQ-001 — vertical counter phase immediately after RESET

The Intel application manual section 6.1.1 enumerates a field as VFP, VS, VBP,
then AL. The Intel preliminary data-sheet Figure 36 depicts the same cyclic
order but chooses the beginning of VBP as its one-field measurement origin.
Neither source explicitly identifies which phase the RESET command loads into
the vertical counter.

The current implementation starts at VFP because that is the prose's first
interval and RESET is documented to initialize internal counters. All periodic
phase widths and transitions are verified independently of this origin. This
choice is **inferred**, not primary-source proven, and must be revisited if a
manufacturer source or physical trace identifies the reset load state.

## OQ-002 — allocation of the extra interlaced line

The Intel application manual states that a two-field interlaced frame has one
more line than twice the programmed per-field count and precisely locates the
two fields' VSYNC transitions relative to the horizontal waveform. It does not
state in equally direct language which internal vertical interval owns the
extra line. Interlace implementation must preserve the documented frame total
and pin edges while treating interval ownership as unresolved until further
evidence is found.

## OQ-003 — semantic use of base pitch `00h`

The base command figure exposes an eight-bit literal PITCH parameter without a
special-zero note. The 7220A appendix explicitly says PH increases the register
from eight to nine bits and raises supported pitch to 511, which establishes a
base maximum of 255 rather than a zero-as-256 encoding. RESET/SYNC can still
request AW=256; loading its low eight-bit `(P2+2)` result produces pitch `00h`.

The implemented register behavior follows that width evidence and never aliases
`00h` to 256. What drawing/address hardware does with a deliberately programmed
zero pitch is not described; it remains undefined until primary evidence or a
physical trace establishes whether it acts as zero or has another internal
interpretation.

## OQ-004 — undefined high bits in CURD P3

Intel preliminary data-sheet Figure 28 defines only bits 1:0 of CURD response
byte P3 as EAD bits 17:16 and marks bits 7:2 `X`/undefined. No primary source in
the current corpus assigns stable silicon values to those upper bits.

The RTL returns zero in bits 7:2 so an FPGA implementation is deterministic.
The independent model makes the same portable choice, but conformance tests
mask those bits and the project does not claim that original 7220/82720 silicon
necessarily returns zero.

## OQ-005 — all-zero partition length encoding

Figures 10 and 11 define each partition LEN as a ten-bit active-line count, and
the manuals allow as many as 1024 active lines per field. The current corpus
does not state in direct prose whether a raw LEN value of zero denotes zero
lines or the unrepresentable maximum of 1024, as the AL synchronization field
explicitly does.

The implemented sequencer interprets zero as 1024. This is the only encoding
that represents the documented maximum and avoids a zero-length area that could
never become active, but it remains an **engineering inference**. Fixed RTL and
model tests preserve this interpretation so a future manufacturer clarification
or physical-device trace can change it deliberately rather than silently.

## OQ-006 — refresh upper outputs and RESET origin

The NEC design manual section 2.5.1 and Intel application manual section 2.5.1
specify that the internal eight-bit refresh counter appears on the lower eight
AD lines during HSYNC. Neither assigns refresh meaning to AD15-AD8 or A16/A17.
RESET is documented to initialize internal counters, but the currently
available text does not state the refresh counter's numerical post-RESET value.

For deterministic FPGA behavior, the RTL drives all unspecified upper address
outputs low during refresh and initializes the refresh counter to `00h`. The
model and fixed tests preserve that convention, while conformance claims cover
only the successive modulo-256 AD0-AD7 sequence after the selected origin. A
manufacturer clarification or physical trace may refine these values without
changing the evidence-backed cycle cadence.

## OQ-007 — base graphics WDAT parameter-bit wording

The Intel preliminary data sheet and application manual state that graphics
WDAT can supply only an all-zero or all-one pattern. Worked multi-pixel-write
sequences explicitly require bit zero of the low parameter byte to be one, and
the prose elsewhere refers to “the least significant bit” replacing every bit
of a written word. One sentence instead says the least significant bit of the
parameter “bytes” is used, despite a two-byte word group.

The base implementation selects P1 bit zero and ignores P2 for graphics modify
data, while retaining the complete `{P2,P1}` Pattern register and using it in
character mode. Fixed tests distinguish this interpretation by setting P1 bit
zero low while P2 bit zero is high. The later 7220A WG profile will allow the
documented full graphics WDAT pattern only behind its variant gate. Physical
base-device evidence should resolve whether the plural wording has any further
observable meaning.
