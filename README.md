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
make setup-dev
make lint
make test
```

`make test` currently runs Python unit tests and a Verilator+cocotb RTL smoke
simulation. Simulation output, seed-specific build files, and waveforms are
written below `build/`. Set a deterministic seed with `GDC_SEED`, for example:

```sh
make test-random GDC_SEED=29216
```

See [`docs/verification.md`](docs/verification.md) for the test architecture and
current scope. Additional formal and synthesis targets will be introduced with
the implementation milestones they verify.

The independent, edge-steppable architectural model begins in
[`model/upd7220_model.py`](model/upd7220_model.py). Its implemented scope is
intentionally narrower than the final command set and is expanded only with
primary-source-backed tests.
