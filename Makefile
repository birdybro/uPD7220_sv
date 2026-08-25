.PHONY: setup-dev lint test test-unit test-rtl test-random test-all references references-verify

PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_STAMP := $(VENV)/.upd7220-dev-ready
RTL_SOURCES := rtl/upd7220_pkg.sv rtl/upd7220_host_if.sv rtl/upd7220_fifo.sv rtl/upd7220_core.sv rtl/upd7220.sv

setup-dev: $(VENV_STAMP)

$(VENV_STAMP): requirements-dev.txt
	$(PYTHON) -m venv $(VENV)
	COCOTB_IGNORE_PYTHON_REQUIRES=1 $(VENV_PYTHON) -m pip install --disable-pip-version-check -r requirements-dev.txt
	touch $(VENV_STAMP)

lint:
	$(PYTHON) -m compileall -q model scripts tests
	$(PYTHON) scripts/check_spec_matrix.py
	verilator --lint-only --Wall --top-module upd7220 $(RTL_SOURCES)
	verilator --lint-only --Wall --top-module smoke_dut tests/rtl/smoke_dut.sv
	git diff --check

test: test-unit test-rtl

test-unit: $(VENV_STAMP)
	$(VENV_PYTHON) -m pytest -m "not rtl" tests

test-rtl: $(VENV_STAMP)
	$(VENV_PYTHON) -m pytest -m rtl tests

test-random: test

test-all: test

references:
	$(PYTHON) scripts/fetch_references.py

references-verify:
	$(PYTHON) scripts/fetch_references.py --verify-only
