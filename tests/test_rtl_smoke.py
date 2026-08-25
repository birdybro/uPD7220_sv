from __future__ import annotations

import os
from pathlib import Path

import pytest
from cocotb_tools.runner import get_runner

from tests.support.seed import SeedContext


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.rtl
def test_verilator_cocotb_smoke(gdc_seed: SeedContext) -> None:
    build_directory = ROOT / "build" / "sim" / f"smoke-seed-{gdc_seed.seed}"
    runner = get_runner(os.environ.get("SIM", "verilator"))
    runner.build(
        sources=[ROOT / "tests" / "rtl" / "smoke_dut.sv"],
        hdl_toplevel="smoke_dut",
        build_dir=build_directory,
        always=True,
        waves=True,
    )
    try:
        runner.test(
            hdl_toplevel="smoke_dut",
            test_module="tests.cocotb.test_smoke",
            build_dir=build_directory,
            waves=True,
            extra_env={"GDC_SEED": str(gdc_seed.seed)},
        )
    except BaseException:
        print(f"seed={gdc_seed.seed}")
        print(f"waveform/build artifacts: {build_directory}")
        print(f"reproduce: {gdc_seed.reproduce}")
        raise
