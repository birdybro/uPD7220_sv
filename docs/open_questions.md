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
