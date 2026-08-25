#!/usr/bin/env python3
"""Check structural completeness of docs/specification_matrix.md."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX = ROOT / "docs" / "specification_matrix.md"
REQUIREMENT_ID = re.compile(r"^[A-Z]+(?:-[A-Z0-9]+)*-[0-9]{3}$")
REQUIRED_FAMILIES = {
    "PIN",
    "HOST",
    "FIFO",
    "STATUS",
    "CMD",
    "REG",
    "MODE",
    "MEM",
    "RMW",
    "DRAW",
    "VIDEO",
    "TIMING",
    "DMA",
    "LPEN",
    "RESET",
    "VAR",
}
VALID_STATUS = {"Researched", "Open", "Implemented", "Unit verified", "Cycle verified"}


class MatrixError(RuntimeError):
    """Raised when the traceability matrix violates its schema."""


def parse_rows(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and REQUIREMENT_ID.fullmatch(cells[0]):
            if len(cells) != 8:
                raise MatrixError(
                    f"{path}:{line_number}: requirement {cells[0]} has {len(cells)} columns, expected 8"
                )
            rows.append(cells)
    if not rows:
        raise MatrixError(f"{path}: no requirement rows found")
    return rows


def check_matrix(path: Path) -> list[list[str]]:
    rows = parse_rows(path)
    seen: set[str] = set()
    families: set[str] = set()
    for cells in rows:
        requirement_id, feature, behavior, variants, source, owner, verification, status = cells
        if requirement_id in seen:
            raise MatrixError(f"{path}: duplicate requirement id {requirement_id}")
        seen.add(requirement_id)
        families.add(requirement_id.split("-", maxsplit=1)[0])
        for label, value in (
            ("feature", feature),
            ("behavior", behavior),
            ("variant", variants),
            ("source", source),
            ("owner", owner),
            ("verification", verification),
        ):
            if not value or value in {"-", "TBD", "TODO"}:
                raise MatrixError(f"{requirement_id}: missing {label}")
        if not re.search(r"\bpp?\.", source):
            raise MatrixError(f"{requirement_id}: source has no page citation")
        if status not in VALID_STATUS:
            raise MatrixError(f"{requirement_id}: invalid status {status!r}")

    missing_families = REQUIRED_FAMILIES.difference(families)
    if missing_families:
        raise MatrixError(f"matrix is missing families: {', '.join(sorted(missing_families))}")
    if len(rows) < 100:
        raise MatrixError(f"matrix has only {len(rows)} requirements; expected at least 100")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("matrix", nargs="?", type=Path, default=DEFAULT_MATRIX)
    arguments = parser.parse_args(argv)
    try:
        rows = check_matrix(arguments.matrix)
    except (FileNotFoundError, MatrixError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"checked {len(rows)} requirements in {arguments.matrix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
