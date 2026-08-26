from __future__ import annotations

import os
from pathlib import Path

import pytest
from cocotb_tools.runner import get_runner

from tests.support.seed import SeedContext


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.rtl
def test_pitch_register(gdc_seed: SeedContext) -> None:
    build_directory = ROOT / "build" / "sim" / f"pitch-seed-{gdc_seed.seed}"
    runner = get_runner(os.environ.get("SIM", "verilator"))
    runner.build(
        sources=[
            ROOT / "rtl" / "upd7220_pkg.sv",
            ROOT / "rtl" / "upd7220_pitch.sv",
        ],
        hdl_toplevel="upd7220_pitch",
        build_dir=build_directory,
        always=True,
        waves=True,
    )
    try:
        runner.test(
            hdl_toplevel="upd7220_pitch",
            test_module="tests.cocotb.test_pitch",
            build_dir=build_directory,
            waves=True,
            extra_env={"GDC_SEED": str(gdc_seed.seed)},
        )
    except BaseException:
        print(f"seed={gdc_seed.seed}")
        print(f"waveform/build artifacts: {build_directory}")
        raise
