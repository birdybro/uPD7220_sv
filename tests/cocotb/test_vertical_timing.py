from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge, Timer


VFP = 0
VSYNC = 1
VBP = 2
ACTIVE = 3


async def falling(dut: object) -> None:
    await FallingEdge(dut.clk_2x)
    await ReadOnly()


async def finish_edge() -> None:
    await Timer(1, unit="ps")


async def start_and_reset(dut: object) -> None:
    dut.integration_reset_n.value = 0
    dut.reset_command.value = 0
    dut.line_advance_ce.value = 0
    dut.vsync_width.value = 2
    dut.vertical_front_porch.value = 2
    dut.active_lines.value = 2
    dut.vertical_back_porch.value = 3
    cocotb.start_soon(Clock(dut.clk_2x, 200, unit="ns").start())
    await falling(dut)
    await finish_edge()
    dut.integration_reset_n.value = 1


async def advance_line(dut: object) -> None:
    dut.line_advance_ce.value = 1
    await falling(dut)
    await finish_edge()
    dut.line_advance_ce.value = 0


def sample(dut: object) -> tuple[int, int, int, int, int, int]:
    return (
        int(dut.vertical_phase.value),
        int(dut.vertical_line_index.value),
        int(dut.vsync.value),
        int(dut.vertical_blank.value),
        int(dut.active_line.value),
        int(dut.field_start.value),
    )


@cocotb.test()
async def exact_noninterlaced_vertical_phase_trace(dut: object) -> None:
    await start_and_reset(dut)
    assert sample(dut) == (VFP, 0, 0, 1, 0, 0)

    expected = (
        (VFP, 1, 0, 1, 0, 0),
        (VSYNC, 0, 1, 1, 0, 0),
        (VSYNC, 1, 1, 1, 0, 0),
        (VBP, 0, 0, 1, 0, 0),
        (VBP, 1, 0, 1, 0, 0),
        (VBP, 2, 0, 1, 0, 0),
        (ACTIVE, 0, 0, 0, 1, 0),
        (ACTIVE, 1, 0, 0, 1, 0),
        (VFP, 0, 0, 1, 0, 1),
    )
    observed = []
    for _ in expected:
        await advance_line(dut)
        observed.append(sample(dut))
    assert tuple(observed) == expected

    await falling(dut)
    assert sample(dut) == (VFP, 0, 0, 1, 0, 0)


@cocotb.test()
async def vsync_changes_only_on_the_falling_line_boundary(dut: object) -> None:
    await start_and_reset(dut)
    await advance_line(dut)
    assert sample(dut)[:2] == (VFP, 1)

    dut.line_advance_ce.value = 1
    await RisingEdge(dut.clk_2x)
    await ReadOnly()
    assert sample(dut) == (VFP, 1, 0, 1, 0, 0)
    await finish_edge()
    await falling(dut)
    assert sample(dut) == (VSYNC, 0, 1, 1, 0, 0)


@cocotb.test()
async def reset_restarts_vertical_front_porch(dut: object) -> None:
    await start_and_reset(dut)
    await advance_line(dut)
    await advance_line(dut)
    assert int(dut.vsync.value) == 1

    dut.reset_command.value = 1
    await RisingEdge(dut.clk_2x)
    await ReadOnly()
    assert int(dut.vsync.value) == 1
    await finish_edge()
    await falling(dut)
    assert sample(dut) == (VFP, 0, 0, 1, 0, 0)
