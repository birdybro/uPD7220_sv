from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer


CMD_RESET = 1
CMD_SYNC = 2
CMD_VSYNC = 3
SYNC_VECTOR = (0x1F, 0xFE, 0xBA, 0xAA, 0x3F, 0x00, 0xFF, 0x03)


async def edge(dut: object) -> None:
    await RisingEdge(dut.clk_2x)
    await ReadOnly()


async def finish_edge() -> None:
    await Timer(1, unit="ps")


async def start_and_reset(dut: object) -> None:
    cocotb.start_soon(Clock(dut.clk_2x, 200, unit="ns").start())
    dut.reset_command.value = 0
    dut.command_start.value = 0
    dut.started_kind.value = 0
    dut.started_opcode.value = 0
    dut.parameter_valid.value = 0
    dut.parameter_kind.value = 0
    dut.parameter_index.value = 0
    dut.parameter_data.value = 0
    dut.integration_reset_n.value = 0
    await edge(dut)
    await finish_edge()
    dut.integration_reset_n.value = 1


async def command(dut: object, kind: int, opcode: int) -> None:
    dut.started_kind.value = kind
    dut.started_opcode.value = opcode
    dut.command_start.value = 1
    await edge(dut)
    await finish_edge()
    dut.command_start.value = 0


async def parameter(dut: object, kind: int, index: int, value: int) -> None:
    dut.parameter_kind.value = kind
    dut.parameter_index.value = index
    dut.parameter_data.value = value
    dut.parameter_valid.value = 1
    await edge(dut)
    await finish_edge()
    dut.parameter_valid.value = 0


async def program_sync(dut: object, opcode: int, values: tuple[int, ...]) -> None:
    await command(dut, CMD_SYNC, opcode)
    for index, value in enumerate(values):
        await parameter(dut, CMD_SYNC, index, value)


def raw_parameters(dut: object) -> tuple[int, ...]:
    return tuple(int(getattr(dut, f"sync_p{index}").value) for index in range(1, 9))


@cocotb.test()
async def sync_decodes_all_fields_and_base_pitch(dut: object) -> None:
    await start_and_reset(dut)
    await program_sync(dut, 0x0F, SYNC_VECTOR)

    assert int(dut.display_enable.value) == 1
    assert int(dut.programmed_mask.value) == 0xFF
    assert raw_parameters(dut) == SYNC_VECTOR
    assert int(dut.display_mode.value) == 1
    assert int(dut.framing_mode.value) == 3
    assert int(dut.refresh_enable.value) == 1
    assert int(dut.drawing_during_retrace_only.value) == 1
    assert int(dut.active_words.value) == 256
    assert int(dut.base_pitch.value) == 256
    assert int(dut.hsync_width.value) == 27
    assert int(dut.vsync_width.value) == 21
    assert int(dut.horizontal_front_porch.value) == 43
    assert int(dut.horizontal_back_porch.value) == 64
    assert int(dut.vertical_front_porch.value) == 64
    assert int(dut.active_lines.value) == 1023
    assert int(dut.vertical_back_porch.value) == 64


@cocotb.test()
async def zero_vertical_encodings_select_power_of_two_maxima(dut: object) -> None:
    await start_and_reset(dut)
    await program_sync(dut, 0x0E, (0,) * 8)

    assert int(dut.display_enable.value) == 0
    assert int(dut.active_words.value) == 2
    assert int(dut.hsync_width.value) == 1
    assert int(dut.vsync_width.value) == 32
    assert int(dut.horizontal_front_porch.value) == 1
    assert int(dut.horizontal_back_porch.value) == 1
    assert int(dut.vertical_front_porch.value) == 64
    assert int(dut.active_lines.value) == 1024
    assert int(dut.vertical_back_porch.value) == 64


@cocotb.test()
async def vsync_mode_and_parameters_survive_base_reset(dut: object) -> None:
    await start_and_reset(dut)
    await program_sync(dut, 0x0F, SYNC_VECTOR)
    await command(dut, CMD_VSYNC, 0x6F)
    assert int(dut.sync_master.value) == 1

    dut.reset_command.value = 1
    await edge(dut)
    await finish_edge()
    dut.reset_command.value = 0

    assert int(dut.display_enable.value) == 0
    assert int(dut.sync_master.value) == 1
    assert int(dut.programmed_mask.value) == 0xFF
    assert raw_parameters(dut) == SYNC_VECTOR
    await command(dut, CMD_VSYNC, 0x6E)
    assert int(dut.sync_master.value) == 0


@cocotb.test()
async def partial_reset_prefix_updates_only_received_fields(dut: object) -> None:
    await start_and_reset(dut)
    await program_sync(dut, 0x0E, SYNC_VECTOR)

    dut.reset_command.value = 1
    await edge(dut)
    await finish_edge()
    dut.reset_command.value = 0
    await parameter(dut, CMD_RESET, 0, 0x02)
    await parameter(dut, CMD_RESET, 1, 0x10)

    assert raw_parameters(dut) == (0x02, 0x10, *SYNC_VECTOR[2:])
    assert int(dut.display_mode.value) == 1
    assert int(dut.framing_mode.value) == 0
    assert int(dut.active_words.value) == 18
    assert int(dut.hsync_width.value) == 27


@cocotb.test()
async def non_sync_parameters_do_not_modify_timing_registers(dut: object) -> None:
    await start_and_reset(dut)
    await program_sync(dut, 0x0E, SYNC_VECTOR)
    await parameter(dut, 12, 0, 0x00)
    assert raw_parameters(dut) == SYNC_VECTOR
    assert int(dut.programmed_mask.value) == 0xFF
