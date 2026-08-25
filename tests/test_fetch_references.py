from __future__ import annotations

import contextlib
import csv
import hashlib
import io
from pathlib import Path
import tempfile
import unittest

from scripts import fetch_references


def minimal_pdf(body: bytes = b"reference fixture") -> bytes:
    padding = b"% fixture padding\n" * 300
    return b"%PDF-1.4\n" + body + b"\n" + padding + b"%%EOF\n"


class FetchReferencesTest(unittest.TestCase):
    def write_manifest(self, path: Path, source: str, payload: bytes) -> None:
        fields = ["id", "filename", "sha256", "size_bytes", "media_type", "sources"]
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t")
            writer.writeheader()
            writer.writerow(
                {
                    "id": "fixture",
                    "filename": "fixture.pdf",
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size_bytes": len(payload),
                    "media_type": "application/pdf",
                    "sources": source,
                }
            )

    def test_fetches_and_verifies_pinned_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            payload = minimal_pdf()
            source = root / "source.pdf"
            source.write_bytes(payload)
            manifest = root / "manifest.tsv"
            destination = root / "downloads"
            self.write_manifest(manifest, source.as_uri(), payload)

            with contextlib.redirect_stdout(io.StringIO()):
                result = fetch_references.main(
                    ["--manifest", str(manifest), "--destination", str(destination)]
                )
                verify_result = fetch_references.main(
                    [
                        "--manifest",
                        str(manifest),
                        "--destination",
                        str(destination),
                        "--verify-only",
                    ]
                )

            self.assertEqual(result, 0)
            self.assertEqual(verify_result, 0)
            self.assertEqual((destination / "fixture.pdf").read_bytes(), payload)

    def test_rejects_html_error_page_with_pdf_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            fake_pdf = root / "error.pdf"
            fake_pdf.write_bytes(b"<html>not a PDF</html>" * 300)

            with self.assertRaisesRegex(fetch_references.ReferenceError, "PDF signature"):
                fetch_references.inspect_pdf(fake_pdf)

    def test_rejects_digest_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            pdf = Path(temporary_directory) / "changed.pdf"
            pdf.write_bytes(minimal_pdf(b"changed"))
            row = {
                "id": "fixture",
                "sha256": "0" * 64,
                "size_bytes": str(pdf.stat().st_size),
            }

            with self.assertRaisesRegex(fetch_references.ReferenceError, "SHA-256 mismatch"):
                fetch_references.verify_file(row, pdf)

    def test_committed_manifest_is_complete_and_pinned(self) -> None:
        rows = fetch_references.load_manifest(fetch_references.DEFAULT_MANIFEST)

        self.assertGreaterEqual(len(rows), 6)
        for row in rows:
            with self.subTest(reference_id=row["id"]):
                self.assertRegex(row["sha256"], r"^[0-9a-f]{64}$")
                self.assertGreater(int(row["size_bytes"]), fetch_references.MINIMUM_PDF_SIZE)
                self.assertTrue(
                    all(source.startswith("https://") for source in row["sources"].split("|"))
                )


if __name__ == "__main__":
    unittest.main()
