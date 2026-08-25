from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.support.seed import SeedContext


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--gdc-seed",
        action="store",
        default=os.environ.get("GDC_SEED", "0x7220"),
        help="deterministic integer seed (decimal or 0x-prefixed)",
    )


@pytest.fixture
def gdc_seed(request: pytest.FixtureRequest) -> SeedContext:
    return SeedContext.parse(str(request.config.getoption("--gdc-seed")))


@pytest.fixture
def artifact_root(gdc_seed: SeedContext) -> Path:
    path = Path("build") / "artifacts" / f"seed-{gdc_seed.seed}"
    path.mkdir(parents=True, exist_ok=True)
    return path
