# Reference corpus

The μPD7220/82720 implementation is derived from contemporary primary sources.
Downloaded files live in `references/downloads/`, which is intentionally ignored
because redistribution rights for vendor scans are unclear. The committed
manifest records enough metadata, source mirrors, byte lengths, and SHA-256
digests to reproduce the local corpus.

## Fetching and verification

From the repository root:

```sh
make references
make references-verify
```

The fetcher tries mirrors in manifest order. A download is accepted only when
it has a PDF signature and trailer, is not labelled as HTML, satisfies a
minimum size, and matches the pinned byte length and SHA-256 digest. Files are
downloaded to a temporary path and atomically installed only after validation.

To fetch or verify selected documents:

```sh
python3 scripts/fetch_references.py --id nec-design-v3 --id intel-82720-app
python3 scripts/fetch_references.py --verify-only --id nec-7220-datasheet
```

## Initial primary set

The required corpus starts with:

- NEC *μPD7220 GDC Design Manual*, Version 3 (1982)
- NEC *μPD7220/7220A Graphic Display Controller User's Manual* (December 1985)
- Intel *82720 Graphics Display Controller Application Manual*, 230685-001
  (July 1983)
- Intel *82720 Graphics Display Controller Preliminary Data Sheet* (June 1983)
- NEC *μPD7220/GDC, μPD7220-1/-2 Graphics Display Controller* data sheet
  (April 7, 1983)
- Oguchi et al., *A Single-Chip Graphic Display Controller*, ISSCC 1981
- NEC's accompanying 37-page ISSCC presentation, *A Single-Chip Graphics
  Display Controller for Sophisticated Display Terminals* (February 19, 1981)

Additional system manuals, schematics, application material, and contemporary
software will be added with provenance as requirements are investigated.
