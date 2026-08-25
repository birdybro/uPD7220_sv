# uPD7220_sv

Independent SystemVerilog reimplementation of the NEC μPD7220 and Intel
82720 Graphics Display Controller.

This project is at the research/bootstrap stage. It does **not** yet claim
functional or cycle accuracy. Accuracy claims will be added only as the
corresponding primary-source requirements and executable tests are completed.

## Reference corpus

The repository records metadata and pinned SHA-256 hashes rather than
redistributing vendor manuals. Fetch and verify the research corpus with:

```sh
make references
make references-verify
```

See [`references/README.md`](references/README.md) for the corpus policy and
[`references/manifest.tsv`](references/manifest.tsv) for exact provenance.

## Current checks

```sh
make lint
make test
```

Additional RTL, simulation, formal, and synthesis targets will be introduced
with the implementation milestones they verify.
