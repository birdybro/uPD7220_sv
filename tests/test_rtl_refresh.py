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


def run_cocotb(
    *,
    sources: list[Path],
    top: str,
    module: str,
    build_directory: Path,
    seed: int,
) -> None:
    runner = get_runner(os.environ.get("SIM", "verilator"))
    runner.build(
        sources=sources,
        hdl_toplevel=top,
        build_dir=build_directory,
        always=True,
        waves=True,
    )
    try:
        runner.test(
            hdl_toplevel=top,
            test_module=module,
            build_dir=build_directory,
            waves=True,
            extra_env={"GDC_SEED": str(seed)},
        )
    except BaseException:
        print(f"seed={seed}")
        print(f"waveform/build artifacts: {build_directory}")
        raise


@pytest.mark.rtl
def test_refresh_counter_unit(gdc_seed: SeedContext) -> None:
    run_cocotb(
        sources=[ROOT / "rtl" / "upd7220_refresh.sv"],
        top="upd7220_refresh",
        module="tests.cocotb.test_refresh_unit",
        build_directory=(
            ROOT / "build" / "sim" / f"refresh-unit-seed-{gdc_seed.seed}"
        ),
        seed=gdc_seed.seed,
    )


@pytest.mark.rtl
def test_refresh_raster_integration(gdc_seed: SeedContext) -> None:
    run_cocotb(
        sources=CORE_SOURCES,
        top="upd7220_core",
        module="tests.cocotb.test_refresh",
        build_directory=(
            ROOT / "build" / "sim" / f"refresh-core-seed-{gdc_seed.seed}"
        ),
        seed=gdc_seed.seed,
    )
