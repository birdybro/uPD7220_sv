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
    ROOT / "rtl" / "upd7220_memif.sv",
    ROOT / "rtl" / "upd7220_video_timing.sv",
    ROOT / "rtl" / "upd7220_vertical_timing.sv",
    ROOT / "rtl" / "upd7220_core.sv",
]


def run_cocotb(
    *, top: str, sources: list[Path], module: str, build_directory: Path, seed: int
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
def test_parameter_ram_register(gdc_seed: SeedContext) -> None:
    run_cocotb(
        top="upd7220_pram",
        sources=[
            ROOT / "rtl" / "upd7220_pkg.sv",
            ROOT / "rtl" / "upd7220_pram.sv",
        ],
        module="tests.cocotb.test_pram",
        build_directory=ROOT / "build" / "sim" / f"pram-seed-{gdc_seed.seed}",
        seed=gdc_seed.seed,
    )


@pytest.mark.rtl
def test_parameter_ram_through_host_fifo(gdc_seed: SeedContext) -> None:
    run_cocotb(
        top="upd7220_core",
        sources=CORE_SOURCES,
        module="tests.cocotb.test_pram_core",
        build_directory=ROOT / "build" / "sim" / f"pram-core-seed-{gdc_seed.seed}",
        seed=gdc_seed.seed,
    )
