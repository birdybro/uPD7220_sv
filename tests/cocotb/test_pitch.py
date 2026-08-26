from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer


CMD_RESET = 1
CMD_SYNC = 2
CMD_PITCH = 10


async def edge(dut: object) -> None:
    await RisingEdge(dut.clk_2x)
    await ReadOnly()


async def finish_edge() -> None:
    await Timer(1, unit="ps")


async def start_and_reset(dut: object) -> None:
    dut.parameter_valid.value = 0
    dut.parameter_kind.value = 0
    dut.parameter_index.value = 0
    dut.parameter_data.value = 0
    dut.integration_reset_n.value = 0
    cocotb.start_soon(Clock(dut.clk_2x, 200, unit="ns").start())
    await edge(dut)
    await finish_edge()
    dut.integration_reset_n.value = 1


async def parameter(dut: object, kind: int, index: int, value: int) -> None:
    dut.parameter_kind.value = kind
    dut.parameter_index.value = index
    dut.parameter_data.value = value
    dut.parameter_valid.value = 1
    await edge(dut)
    await finish_edge()
    dut.parameter_valid.value = 0


@cocotb.test()
async def explicit_pitch_preserves_all_eight_parameter_bits(dut: object) -> None:
    await start_and_reset(dut)
    for value in (0x00, 0x01, 0x7F, 0xFE, 0xFF):
        await parameter(dut, CMD_PITCH, 0, value)
        assert int(dut.pitch.value) == value


@cocotb.test()
async def reset_and_sync_p2_load_active_words_into_base_pitch(dut: object) -> None:
    await start_and_reset(dut)
    for kind in (CMD_RESET, CMD_SYNC):
        for p2, expected in ((0x00, 0x02), (0x7E, 0x80), (0xFD, 0xFF), (0xFE, 0x00)):
            await parameter(dut, kind, 1, p2)
            assert int(dut.pitch.value) == expected


@cocotb.test()
async def unrelated_parameters_leave_pitch_unchanged(dut: object) -> None:
    await start_and_reset(dut)
    await parameter(dut, CMD_PITCH, 0, 0x55)
    await parameter(dut, CMD_SYNC, 0, 0xAA)
    await parameter(dut, 12, 0, 0x00)
    assert int(dut.pitch.value) == 0x55
