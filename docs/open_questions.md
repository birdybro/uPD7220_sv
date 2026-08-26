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
