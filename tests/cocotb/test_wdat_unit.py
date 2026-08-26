from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer


CMD_WDAT = 11
DISPLAY_GRAPHICS = 1
DISPLAY_CHARACTER = 2
MEM_CYCLE_RMW = 1


async def edge(dut: object) -> None:
    await RisingEdge(dut.clk_2x)
    await ReadOnly()


async def finish_edge() -> None:
    await Timer(1, unit="ps")


async def initialize(dut: object) -> None:
    dut.integration_reset_n.value = 0
    dut.reset_command.value = 0
    dut.parameter_valid.value = 0
    dut.parameter_kind.value = 0
    dut.parameter_opcode.value = 0
    dut.parameter_index.value = 0
    dut.parameter_data.value = 0
    dut.display_mode.value = DISPLAY_CHARACTER
    dut.cursor_ead.value = 0x12345
    dut.cursor_mask.value = 0x0FF0
    dut.pitch.value = 4
    dut.request_ready.value = 0
    dut.response_valid.value = 0
    dut.response_kind.value = 0
    dut.response_address.value = 0
    dut.rmw_read_data_valid.value = 0
    dut.rmw_read_data.value = 0
    cocotb.start_soon(Clock(dut.clk_2x, 200, unit="ns").start())
    await edge(dut)
    await finish_edge()
    dut.integration_reset_n.value = 1


async def parameter(dut: object, index: int, value: int, opcode: int = 0x20) -> None:
    dut.parameter_valid.value = 1
    dut.parameter_kind.value = CMD_WDAT
    dut.parameter_opcode.value = opcode
    dut.parameter_index.value = index
    dut.parameter_data.value = value
    await edge(dut)
    await finish_edge()
    dut.parameter_valid.value = 0


@cocotb.test()
async def character_word_replace_latches_group_and_waits_for_rmw_response(
    dut: object,
) -> None:
    await initialize(dut)
    await parameter(dut, 0, 0x5A)
    assert int(dut.pattern.value) == 0x005A
    await parameter(dut, 1, 0xA5)
    assert int(dut.pattern.value) == 0xA55A
    assert int(dut.busy.value) == 1
    assert int(dut.request_valid.value) == 1
    assert int(dut.request_address.value) == 0x12345

    for _ in range(2):
        await edge(dut)
        assert int(dut.request_valid.value) == 1
        await finish_edge()

    dut.request_ready.value = 1
    await edge(dut)
    assert int(dut.request_valid.value) == 0
    assert int(dut.busy.value) == 1
    await finish_edge()
    dut.request_ready.value = 0

    dut.rmw_read_data.value = 0xF00F
    await Timer(1, unit="ns")
    assert int(dut.rmw_write_data.value) == 0xF55F
    dut.rmw_read_data_valid.value = 1
    await edge(dut)
    await finish_edge()
    dut.rmw_read_data_valid.value = 0

    dut.response_valid.value = 1
    dut.response_kind.value = MEM_CYCLE_RMW
    dut.response_address.value = 0x12345
    await Timer(1, unit="ns")
    assert int(dut.cursor_update_valid.value) == 1
    assert int(dut.cursor_update_ead.value) == 0x12349
    await edge(dut)
    assert int(dut.busy.value) == 0
    await finish_edge()
    dut.response_valid.value = 0


@cocotb.test()
async def graphics_mode_expands_only_the_low_parameter_lsb(dut: object) -> None:
    await initialize(dut)
    dut.display_mode.value = DISPLAY_GRAPHICS
    dut.cursor_mask.value = 0xFFFF
    await parameter(dut, 0, 0x01)
    await parameter(dut, 1, 0x00)
    dut.rmw_read_data.value = 0x0000
    assert int(dut.rmw_write_data.value) == 0xFFFF


@cocotb.test()
async def reset_aborts_pending_cycle_but_retains_pattern(dut: object) -> None:
    await initialize(dut)
    await parameter(dut, 0, 0x96)
    await parameter(dut, 1, 0x69)
    assert int(dut.request_valid.value) == 1

    dut.reset_command.value = 1
    await edge(dut)
    assert int(dut.busy.value) == 0
    assert int(dut.request_valid.value) == 0
    assert int(dut.pattern.value) == 0x6996
    await finish_edge()
