from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer


CMD_START = 5
CMD_CURS = 8
CMD_CURD = 17


async def edge(dut: object) -> None:
    await RisingEdge(dut.clk_2x)
    await ReadOnly()


async def finish_edge() -> None:
    await Timer(1, unit="ps")


async def start_and_reset(dut: object) -> None:
    dut.reset_command.value = 0
    dut.command_start.value = 0
    dut.started_kind.value = 0
    dut.parameter_valid.value = 0
    dut.parameter_kind.value = 0
    dut.parameter_index.value = 0
    dut.parameter_data.value = 0
    dut.response_ready.value = 0
    dut.integration_reset_n.value = 0
    cocotb.start_soon(Clock(dut.clk_2x, 200, unit="ns").start())
    await edge(dut)
    await finish_edge()
    dut.integration_reset_n.value = 1


async def parameter(dut: object, index: int, value: int) -> None:
    dut.parameter_valid.value = 1
    dut.parameter_kind.value = CMD_CURS
    dut.parameter_index.value = index
    dut.parameter_data.value = value
    await edge(dut)
    await finish_edge()
    dut.parameter_valid.value = 0


async def program_cursor(dut: object, ead: int, dot: int) -> None:
    await parameter(dut, 0, ead & 0xFF)
    await parameter(dut, 1, (ead >> 8) & 0xFF)
    await parameter(dut, 2, ((dot & 0x0F) << 4) | ((ead >> 16) & 0x03))


async def command_event(dut: object, kind: int) -> None:
    dut.started_kind.value = kind
    dut.command_start.value = 1
    await edge(dut)
    await finish_edge()
    dut.command_start.value = 0


@cocotb.test()
async def curs_loads_all_address_bits_and_one_hot_dot_masks(dut: object) -> None:
    await start_and_reset(dut)
    for ead, dot in ((0x00000, 0), (0x00001, 15), (0x2ABCD, 7), (0x3FFFF, 15)):
        await program_cursor(dut, ead, dot)
        assert int(dut.ead.value) == ead
        assert int(dut.dot_address.value) == dot
        assert int(dut.mask.value) == 1 << dot


@cocotb.test()
async def cursor_state_survives_functional_reset_and_partial_curs(dut: object) -> None:
    await start_and_reset(dut)
    await program_cursor(dut, 0x31234, 10)

    dut.reset_command.value = 1
    await edge(dut)
    await finish_edge()
    dut.reset_command.value = 0
    assert int(dut.ead.value) == 0x31234
    assert int(dut.mask.value) == 0x0400

    await parameter(dut, 0, 0x78)
    await parameter(dut, 1, 0x56)
    await command_event(dut, CMD_START)
    assert int(dut.ead.value) == 0x35678
    assert int(dut.dot_address.value) == 10
    assert int(dut.mask.value) == 0x0400


@cocotb.test()
async def curd_turns_fifo_once_and_streams_a_five_byte_snapshot(dut: object) -> None:
    await start_and_reset(dut)
    await program_cursor(dut, 0x31234, 10)

    dut.started_kind.value = CMD_CURD
    dut.command_start.value = 1
    await Timer(1, unit="ps")
    assert int(dut.turn_to_read.value) == 1
    assert int(dut.response_valid.value) == 0
    await edge(dut)
    await finish_edge()
    dut.command_start.value = 0
    await Timer(1, unit="ps")
    assert int(dut.turn_to_read.value) == 0

    dut.response_ready.value = 1
    observed = []
    for _ in range(5):
        await Timer(1, unit="ps")
        assert int(dut.response_valid.value) == 1
        observed.append(int(dut.response_data.value))
        await edge(dut)
        await finish_edge()
    assert observed == [0x34, 0x12, 0x03, 0x00, 0x04]
    assert int(dut.response_valid.value) == 0


@cocotb.test()
async def curd_holds_its_snapshot_while_fifo_backpressures(dut: object) -> None:
    await start_and_reset(dut)
    await program_cursor(dut, 0x2ABCD, 7)
    await command_event(dut, CMD_CURD)

    for _ in range(3):
        await edge(dut)
        await finish_edge()
        assert int(dut.response_valid.value) == 1
        assert int(dut.response_data.value) == 0xCD

    await program_cursor(dut, 0x00000, 0)
    dut.response_ready.value = 1
    observed = []
    for _ in range(5):
        await Timer(1, unit="ps")
        observed.append(int(dut.response_data.value))
        await edge(dut)
        await finish_edge()
    assert observed == [0xCD, 0xAB, 0x02, 0x80, 0x00]
