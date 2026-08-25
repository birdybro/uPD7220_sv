.PHONY: lint test test-unit references references-verify

PYTHON ?= python3

lint:
	$(PYTHON) -m py_compile scripts/fetch_references.py scripts/check_spec_matrix.py tests/test_fetch_references.py tests/test_spec_matrix.py
	$(PYTHON) scripts/check_spec_matrix.py
	git diff --check

test: test-unit

test-unit:
	$(PYTHON) -m unittest discover -s tests -v

references:
	$(PYTHON) scripts/fetch_references.py

references-verify:
	$(PYTHON) scripts/fetch_references.py --verify-only
