# Reference and provenance policy

The implementation is specification-derived. Evidence is evaluated in this
order: manufacturer data sheets and manuals; manufacturer timing diagrams and
application notes; contemporary system manuals, schematics, and software;
measurements from physical devices; modern emulator implementations; modern
secondary descriptions.

The initial primary corpus and its reproducible download metadata are maintained
in [`../references/manifest.tsv`](../references/manifest.tsv). Vendor PDFs are
not committed. Page-level citations will be attached to requirements in the
specification matrix and to command/timing documentation as those materials are
transcribed.

Inspection of a modern emulator or third-party HDL must be recorded here with
project name, exact revision, license, reason for consultation, and any known
limitations. No such implementation has been inspected at this stage.
