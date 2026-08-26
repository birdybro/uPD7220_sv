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
    ROOT / "rtl" / "upd7220_video_timing.sv",
    ROOT / "rtl" / "upd7220_vertical_timing.sv",
    ROOT / "rtl" / "upd7220_core.sv",
]


@pytest.mark.rtl
def test_display_partition_sequencer(gdc_seed: SeedContext) -> None:
    build_directory = (
        ROOT / "build" / "sim" / f"partitions-seed-{gdc_seed.seed}"
    )
    runner = get_runner(os.environ.get("SIM", "verilator"))
    runner.build(
        sources=[
            ROOT / "rtl" / "upd7220_pkg.sv",
            ROOT / "rtl" / "upd7220_partitions.sv",
        ],
        hdl_toplevel="upd7220_partitions",
        build_dir=build_directory,
        always=True,
        waves=True,
    )
    try:
        runner.test(
            hdl_toplevel="upd7220_partitions",
            test_module="tests.cocotb.test_partitions",
            build_dir=build_directory,
            waves=True,
            extra_env={"GDC_SEED": str(gdc_seed.seed)},
        )
    except BaseException:
        print(f"seed={gdc_seed.seed}")
        print(f"waveform/build artifacts: {build_directory}")
        raise


@pytest.mark.rtl
def test_display_partitions_through_host_and_raster(gdc_seed: SeedContext) -> None:
    build_directory = (
        ROOT / "build" / "sim" / f"partitions-core-seed-{gdc_seed.seed}"
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
            test_module="tests.cocotb.test_partitions_core",
            build_dir=build_directory,
            waves=True,
            extra_env={"GDC_SEED": str(gdc_seed.seed)},
        )
    except BaseException:
        print(f"seed={gdc_seed.seed}")
        print(f"waveform/build artifacts: {build_directory}")
        raise
