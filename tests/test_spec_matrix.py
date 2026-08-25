from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scripts import check_spec_matrix


class SpecificationMatrixTest(unittest.TestCase):
    def test_committed_matrix_passes_schema(self) -> None:
        rows = check_spec_matrix.check_matrix(check_spec_matrix.DEFAULT_MATRIX)
        self.assertGreaterEqual(len(rows), 100)

    def test_duplicate_requirement_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "matrix.md"
            row = "| PIN-001 | x | y | All | Manual, p. 1 | rtl | test | Researched |\n"
            path.write_text(row + row, encoding="utf-8")
            with self.assertRaisesRegex(check_spec_matrix.MatrixError, "duplicate"):
                check_spec_matrix.check_matrix(path)

    def test_missing_page_citation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "matrix.md"
            path.write_text(
                "| PIN-001 | x | y | All | Manual section 1 | rtl | test | Researched |\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(check_spec_matrix.MatrixError, "page citation"):
                check_spec_matrix.check_matrix(path)


if __name__ == "__main__":
    unittest.main()
