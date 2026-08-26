from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge, Timer


HFP = 0
HSYNC = 1
HBP = 2
ACTIVE = 3


async def falling(dut: object) -> None:
    await FallingEdge(dut.clk_2x)
    await ReadOnly()


async def finish_edge() -> None:
    await Timer(1, unit="ps")


async def start_and_reset(dut: object) -> None:
    dut.integration_reset_n.value = 0
    dut.reset_command.value = 0
    dut.word_time_ce.value = 0
    dut.display_enable.value = 0
    dut.active_words.value = 2
    dut.hsync_width.value = 2
    dut.horizontal_front_porch.value = 2
    dut.horizontal_back_porch.value = 3
    dut.vertical_blank.value = 0
    cocotb.start_soon(Clock(dut.clk_2x, 200, unit="ns").start())
    await falling(dut)
    await finish_edge()
    dut.integration_reset_n.value = 1


async def advance_word(dut: object) -> None:
    dut.word_time_ce.value = 1
    await falling(dut)
    await finish_edge()
    dut.word_time_ce.value = 0


def sample(dut: object) -> tuple[int, int, int, int, int, int, int]:
    return (
        int(dut.horizontal_phase.value),
        int(dut.horizontal_word_index.value),
        int(dut.hsync.value),
        int(dut.horizontal_blank.value),
        int(dut.blank.value),
        int(dut.active_word.value),
        int(dut.line_start.value),
    )


@cocotb.test()
async def exact_horizontal_phase_trace(dut: object) -> None:
    await start_and_reset(dut)
    dut.display_enable.value = 1

    assert sample(dut) == (HFP, 0, 0, 1, 1, 0, 0)
    expected = (
        (HFP, 1, 0, 1, 1, 0, 0),
        (HSYNC, 0, 1, 1, 1, 0, 0),
        (HSYNC, 1, 1, 1, 1, 0, 0),
        (HBP, 0, 0, 1, 1, 0, 0),
        (HBP, 1, 0, 1, 1, 0, 0),
        (HBP, 2, 0, 1, 1, 0, 0),
        (ACTIVE, 0, 0, 0, 0, 1, 0),
        (ACTIVE, 1, 0, 0, 0, 1, 0),
        (HFP, 0, 0, 1, 1, 0, 1),
    )
    observed = []
    for _ in expected:
        await advance_word(dut)
        observed.append(sample(dut))
    assert tuple(observed) == expected

    await falling(dut)
    assert sample(dut) == (HFP, 0, 0, 1, 1, 0, 0)


@cocotb.test()
async def video_outputs_change_only_after_falling_clock_edges(dut: object) -> None:
    await start_and_reset(dut)
    dut.display_enable.value = 1
    await advance_word(dut)
    assert sample(dut)[:2] == (HFP, 1)

    dut.word_time_ce.value = 1
    await RisingEdge(dut.clk_2x)
    await ReadOnly()
    assert sample(dut) == (HFP, 1, 0, 1, 1, 0, 0)
    await finish_edge()
    await falling(dut)
    assert sample(dut) == (HSYNC, 0, 1, 1, 1, 0, 0)
    await finish_edge()
    dut.word_time_ce.value = 0

    await advance_word(dut)
    await advance_word(dut)
    await advance_word(dut)
    await advance_word(dut)
    await advance_word(dut)
    assert sample(dut)[:6] == (ACTIVE, 0, 0, 0, 0, 1)

    dut.display_enable.value = 0
    await RisingEdge(dut.clk_2x)
    await ReadOnly()
    assert int(dut.blank.value) == 0
    await finish_edge()
    await falling(dut)
    assert int(dut.blank.value) == 1


@cocotb.test()
async def reset_restarts_front_porch_on_falling_edge(dut: object) -> None:
    await start_and_reset(dut)
    dut.display_enable.value = 1
    await advance_word(dut)
    await advance_word(dut)
    assert int(dut.hsync.value) == 1

    dut.reset_command.value = 1
    await RisingEdge(dut.clk_2x)
    await ReadOnly()
    assert int(dut.hsync.value) == 1
    await finish_edge()
    await falling(dut)
    assert sample(dut) == (HFP, 0, 0, 1, 1, 0, 0)
