from __future__ import annotations

import os
from pathlib import Path

import pytest
from cocotb_tools.runner import get_runner

from tests.support.seed import SeedContext


ROOT = Path(__file__).resolve().parents[1]
CORE_SOURCES = [
    ROOT / "rtl" / "upd7220_pkg.sv",
    ROOT / "rtl" / "upd7220_host_if.sv",
    ROOT / "rtl" / "upd7220_fifo.sv",
    ROOT / "rtl" / "upd7220_command.sv",
    ROOT / "rtl" / "upd7220_sync_control.sv",
    ROOT / "rtl" / "upd7220_pitch.sv",
    ROOT / "rtl" / "upd7220_cursor.sv",
    ROOT / "rtl" / "upd7220_pram.sv",
    ROOT / "rtl" / "upd7220_partitions.sv",
    ROOT / "rtl" / "upd7220_refresh.sv",
    ROOT / "rtl" / "upd7220_wdat.sv",
    ROOT / "rtl" / "upd7220_memif.sv",
    ROOT / "rtl" / "upd7220_video_timing.sv",
    ROOT / "rtl" / "upd7220_vertical_timing.sv",
    ROOT / "rtl" / "upd7220_core.sv",
]


@pytest.mark.rtl
def test_graphics_display_fetch_integration(gdc_seed: SeedContext) -> None:
    build_directory = (
        ROOT / "build" / "sim" / f"display-fetch-seed-{gdc_seed.seed}"
    )
    runner = get_runner(os.environ.get("SIM", "verilator"))
    runner.build(
        sources=CORE_SOURCES,
        hdl_toplevel="upd7220_core",
        build_dir=build_directory,
        always=True,
        waves=True,
    )
    try:
        runner.test(
            hdl_toplevel="upd7220_core",
            test_module="tests.cocotb.test_display_fetch",
            build_dir=build_directory,
            waves=True,
            extra_env={"GDC_SEED": str(gdc_seed.seed)},
        )
    except BaseException:
        print(f"seed={gdc_seed.seed}")
        print(f"waveform/build artifacts: {build_directory}")
        raise
