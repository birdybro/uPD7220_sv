#!/usr/bin/env python3
"""Fetch and cryptographically verify the uPD7220 primary-source corpus."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
from pathlib import Path
import sys
import tempfile
from typing import BinaryIO, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "references" / "manifest.tsv"
DEFAULT_DESTINATION = ROOT / "references" / "downloads"
USER_AGENT = "uPD7220_sv-reference-fetcher/1.0 (+https://github.com/birdybro/uPD7220_sv)"
MINIMUM_PDF_SIZE = 4096
COPY_BLOCK_SIZE = 1024 * 1024


class ReferenceError(RuntimeError):
    """Raised when reference metadata or content is invalid."""


def sha256_stream(stream: BinaryIO) -> tuple[str, int]:
    digest = hashlib.sha256()
    length = 0
    while chunk := stream.read(COPY_BLOCK_SIZE):
        digest.update(chunk)
        length += len(chunk)
    return digest.hexdigest(), length


def inspect_pdf(path: Path) -> tuple[str, int]:
    """Return (sha256, length) after conservative PDF sanity checks."""
    size = path.stat().st_size
    if size < MINIMUM_PDF_SIZE:
        raise ReferenceError(f"{path}: only {size} bytes; not a plausible manual")

    with path.open("rb") as stream:
        signature = stream.read(8)
        if not signature.startswith(b"%PDF-"):
            raise ReferenceError(f"{path}: missing PDF signature (possible HTML error page)")
        stream.seek(max(0, size - 4096))
        if b"%%EOF" not in stream.read():
            raise ReferenceError(f"{path}: missing PDF EOF marker (truncated download)")
        stream.seek(0)
        return sha256_stream(stream)


def load_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))

    required = {"id", "filename", "sha256", "size_bytes", "media_type", "sources"}
    if not rows:
        raise ReferenceError(f"{path}: manifest is empty")
    missing = required.difference(rows[0])
    if missing:
        raise ReferenceError(f"{path}: missing columns: {', '.join(sorted(missing))}")

    seen_ids: set[str] = set()
    seen_filenames: set[str] = set()
    for line_number, row in enumerate(rows, start=2):
        reference_id = row["id"]
        filename = row["filename"]
        if not reference_id or reference_id in seen_ids:
            raise ReferenceError(f"{path}:{line_number}: missing or duplicate id {reference_id!r}")
        if not filename or filename in seen_filenames or Path(filename).name != filename:
            raise ReferenceError(f"{path}:{line_number}: unsafe or duplicate filename {filename!r}")
        if row["media_type"] != "application/pdf":
            raise ReferenceError(f"{path}:{line_number}: unsupported media type")
        if not row["sources"]:
            raise ReferenceError(f"{path}:{line_number}: no source URLs")
        seen_ids.add(reference_id)
        seen_filenames.add(filename)
    return rows


def verify_expected(row: dict[str, str], digest: str, size: int, *, allow_unpinned: bool) -> None:
    expected_digest = row["sha256"].lower()
    expected_size_text = row["size_bytes"]
    if not expected_digest or expected_size_text in {"", "0"}:
        if allow_unpinned:
            return
        raise ReferenceError(f"{row['id']}: manifest digest/size is not pinned")
    if len(expected_digest) != 64 or any(c not in "0123456789abcdef" for c in expected_digest):
        raise ReferenceError(f"{row['id']}: malformed SHA-256 in manifest")
    if digest != expected_digest:
        raise ReferenceError(
            f"{row['id']}: SHA-256 mismatch: expected {expected_digest}, observed {digest}"
        )
    try:
        expected_size = int(expected_size_text)
    except ValueError as error:
        raise ReferenceError(f"{row['id']}: malformed byte length") from error
    if size != expected_size:
        raise ReferenceError(
            f"{row['id']}: byte-length mismatch: expected {expected_size}, observed {size}"
        )


def verify_file(row: dict[str, str], path: Path, *, allow_unpinned: bool = False) -> tuple[str, int]:
    digest, size = inspect_pdf(path)
    verify_expected(row, digest, size, allow_unpinned=allow_unpinned)
    return digest, size


def download_source(url: str, output: BinaryIO, timeout: float) -> None:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/pdf"})
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get_content_type()
        if content_type in {"text/html", "application/xhtml+xml"}:
            raise ReferenceError(f"server returned {content_type}")
        while chunk := response.read(COPY_BLOCK_SIZE):
            output.write(chunk)


def fetch_reference(
    row: dict[str, str], destination: Path, timeout: float, *, allow_unpinned: bool
) -> tuple[Path, str, int, str | None]:
    output_path = destination / row["filename"]
    if output_path.exists():
        digest, size = verify_file(row, output_path, allow_unpinned=allow_unpinned)
        return output_path, digest, size, None

    failures: list[str] = []
    destination.mkdir(parents=True, exist_ok=True)
    for source in row["sources"].split("|"):
        source = source.strip()
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w+b", prefix=f".{row['id']}.", suffix=".part", dir=destination, delete=False
            ) as temporary:
                temporary_name = temporary.name
                download_source(source, temporary, timeout)
                temporary.flush()
                os.fsync(temporary.fileno())
            temporary_path = Path(temporary_name)
            digest, size = verify_file(row, temporary_path, allow_unpinned=allow_unpinned)
            temporary_path.replace(output_path)
            return output_path, digest, size, source
        except (HTTPError, URLError, TimeoutError, OSError, ReferenceError) as error:
            failures.append(f"{source}: {error}")
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)

    details = "\n  ".join(failures)
    raise ReferenceError(f"{row['id']}: all source mirrors failed:\n  {details}")


def selected_rows(rows: Iterable[dict[str, str]], requested_ids: list[str]) -> list[dict[str, str]]:
    rows_by_id = {row["id"]: row for row in rows}
    unknown = sorted(set(requested_ids).difference(rows_by_id))
    if unknown:
        raise ReferenceError(f"unknown reference id(s): {', '.join(unknown)}")
    if not requested_ids:
        return list(rows)
    requested = set(requested_ids)
    return [row for row in rows if row["id"] in requested]


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument("--id", action="append", default=[], dest="reference_ids")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--list", action="store_true", help="list selected manifest records and exit")
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument(
        "--allow-unpinned",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    try:
        rows = selected_rows(load_manifest(arguments.manifest), arguments.reference_ids)
        if arguments.list:
            for row in rows:
                print(f"{row['id']}\t{row['title']}\t{row['publication_date']}")
            return 0

        for row in rows:
            output_path = arguments.destination / row["filename"]
            if arguments.verify_only:
                digest, size = verify_file(
                    row, output_path, allow_unpinned=arguments.allow_unpinned
                )
                print(f"verified  {row['id']}: {size} bytes sha256={digest}")
            else:
                path, digest, size, source = fetch_reference(
                    row,
                    arguments.destination,
                    arguments.timeout,
                    allow_unpinned=arguments.allow_unpinned,
                )
                action = "fetched" if source is not None else "verified"
                source_note = f" from {source}" if source is not None else ""
                print(
                    f"{action:<8} {row['id']}: {size} bytes sha256={digest}{source_note} -> {path}"
                )
        return 0
    except (FileNotFoundError, ReferenceError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
