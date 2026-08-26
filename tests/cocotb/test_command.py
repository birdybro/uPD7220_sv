from __future__ import annotations

from dataclasses import dataclass

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer


CMD_INVALID = 0
CMD_RESET = 1
CMD_SYNC = 2
CMD_VSYNC = 3
CMD_CCHAR = 4
CMD_START = 5
CMD_BCTRL = 6
CMD_ZOOM = 7
CMD_CURS = 8
CMD_PRAM = 9
CMD_PITCH = 10
CMD_WDAT = 11
CMD_MASK = 12
CMD_FIGS = 13
CMD_FIGD = 14
CMD_GCHRD = 15
CMD_RDAT = 16
CMD_CURD = 17
CMD_LPRD = 18
CMD_DMAR = 19
CMD_DMAW = 20


@dataclass(frozen=True)
class ExpectedCommand:
    kind: int
    parameter_limit: int


def expected_command(opcode: int) -> ExpectedCommand:
    exact = {
        0x00: (CMD_RESET, 8),
        0x4B: (CMD_CCHAR, 3),
        0x6B: (CMD_START, 0),
        0x46: (CMD_ZOOM, 1),
        0x49: (CMD_CURS, 3),
        0x47: (CMD_PITCH, 1),
        0x4A: (CMD_MASK, 2),
        0x4C: (CMD_FIGS, 11),
        0x6C: (CMD_FIGD, 0),
        0x68: (CMD_GCHRD, 0),
        0xE0: (CMD_CURD, 0),
        0xC0: (CMD_LPRD, 0),
    }
    if opcode in exact:
        return ExpectedCommand(*exact[opcode])
    if opcode in (0x0E, 0x0F):
        return ExpectedCommand(CMD_SYNC, 8)
    if opcode in (0x6E, 0x6F):
        return ExpectedCommand(CMD_VSYNC, 0)
    if opcode in (0x0C, 0x0D):
        return ExpectedCommand(CMD_BCTRL, 0)
    if 0x70 <= opcode <= 0x7F:
        return ExpectedCommand(CMD_PRAM, 16 - (opcode & 0x0F))

    transfer_type = (opcode >> 3) & 0x03
    if transfer_type != 0x01:
        group_size = 2 if transfer_type == 0 else 1
        family = opcode & 0xE4
        if family == 0x20:
            return ExpectedCommand(CMD_WDAT, group_size)
        if family == 0x24:
            return ExpectedCommand(CMD_DMAW, 0)
        if family == 0xA0:
            return ExpectedCommand(CMD_RDAT, 0)
        if family == 0xA4:
            return ExpectedCommand(CMD_DMAR, 0)
    return ExpectedCommand(CMD_INVALID, 0)


async def edge(dut: object) -> None:
    await RisingEdge(dut.clk_2x)
    await ReadOnly()


async def finish_edge() -> None:
    await Timer(1, unit="ps")


async def start_and_reset(dut: object) -> None:
    cocotb.start_soon(Clock(dut.clk_2x, 200, unit="ns").start())
    dut.command_reset.value = 0
    dut.processor_enable.value = 1
    dut.fifo_valid.value = 0
    dut.fifo_is_command.value = 0
    dut.fifo_data.value = 0
    dut.integration_reset_n.value = 0
    await edge(dut)
    await finish_edge()
    dut.integration_reset_n.value = 1


async def parser_reset(dut: object) -> None:
    dut.command_reset.value = 1
    await edge(dut)
    await finish_edge()
    dut.command_reset.value = 0


async def entry(dut: object, value: int, *, command: bool) -> dict[str, int]:
    dut.fifo_data.value = value
    dut.fifo_is_command.value = int(command)
    dut.fifo_valid.value = 1
    await edge(dut)
    observed = {
        "pop": int(dut.fifo_pop.value),
        "start": int(dut.command_start.value),
        "known": int(dut.command_known.value),
        "kind": int(dut.started_kind.value),
        "opcode": int(dut.started_opcode.value),
        "limit": int(dut.started_parameter_limit.value),
        "parameter_valid": int(dut.parameter_valid.value),
        "parameter_data": int(dut.parameter_data.value),
        "parameter_index": int(dut.parameter_index.value),
        "parameter_kind": int(dut.parameter_kind.value),
        "complete": int(dut.command_complete.value),
        "completed_opcode": int(dut.completed_opcode.value),
        "interrupted": int(dut.command_interrupted.value),
        "interrupted_opcode": int(dut.interrupted_opcode.value),
        "unexpected": int(dut.unexpected_parameter.value),
        "active": int(dut.command_active.value),
        "next_index": int(dut.next_parameter_index.value),
    }
    await finish_edge()
    dut.fifo_valid.value = 0
    return observed


@cocotb.test()
async def exhaustive_base_opcode_decode_and_parameter_limits(dut: object) -> None:
    await start_and_reset(dut)
    for opcode in range(256):
        await parser_reset(dut)
        observed = await entry(dut, opcode, command=True)
        expected = expected_command(opcode)
        assert observed["pop"] == 1, f"opcode=0x{opcode:02x}"
        assert observed["start"] == 1, f"opcode=0x{opcode:02x}"
        assert observed["opcode"] == opcode
        assert observed["kind"] == expected.kind, f"opcode=0x{opcode:02x}"
        assert observed["known"] == int(expected.kind != CMD_INVALID)
        assert observed["limit"] == expected.parameter_limit
        expected_immediate = expected.kind != CMD_INVALID and expected.parameter_limit == 0
        assert observed["complete"] == int(expected_immediate)
        assert observed["active"] == int(expected.parameter_limit != 0)


@cocotb.test()
async def fixed_parameter_commands_complete_on_their_last_byte(dut: object) -> None:
    await start_and_reset(dut)
    for opcode, count in ((0x0E, 8), (0x4B, 3), (0x46, 1), (0x47, 1), (0x4A, 2)):
        await parser_reset(dut)
        started = await entry(dut, opcode, command=True)
        expected_kind = expected_command(opcode).kind
        assert started["active"] == 1
        for index in range(count):
            observed = await entry(dut, 0x80 + index, command=False)
            assert observed["parameter_valid"] == 1
            assert observed["parameter_data"] == 0x80 + index
            assert observed["parameter_index"] == index
            assert observed["parameter_kind"] == expected_kind
            assert observed["complete"] == int(index == count - 1)
            assert observed["active"] == int(index != count - 1)


@cocotb.test()
async def pram_uses_start_address_to_limit_sequential_bytes(dut: object) -> None:
    await start_and_reset(dut)
    for start_address in range(16):
        await parser_reset(dut)
        opcode = 0x70 | start_address
        count = 16 - start_address
        started = await entry(dut, opcode, command=True)
        assert started["limit"] == count
        for index in range(count):
            observed = await entry(dut, index, command=False)
            assert observed["parameter_index"] == index
            assert observed["complete"] == int(index == count - 1)


@cocotb.test()
async def optional_prefix_commands_are_terminated_by_a_new_command(dut: object) -> None:
    await start_and_reset(dut)
    for opcode, prefix_length in ((0x00, 0), (0x00, 4), (0x49, 2), (0x4C, 7)):
        await parser_reset(dut)
        await entry(dut, opcode, command=True)
        for index in range(prefix_length):
            await entry(dut, index, command=False)
        observed = await entry(dut, 0x6B, command=True)
        assert observed["interrupted"] == 1
        assert observed["interrupted_opcode"] == opcode
        assert observed["start"] == 1
        assert observed["opcode"] == 0x6B
        assert observed["complete"] == 1
        assert observed["active"] == 0


@cocotb.test()
async def wdat_repeats_word_or_byte_parameter_groups(dut: object) -> None:
    await start_and_reset(dut)
    for opcode, expected_indices in (
        (0x20, (0, 1, 0, 1, 0)),
        (0x30, (0, 0, 0, 0, 0)),
        (0x38, (0, 0, 0, 0, 0)),
    ):
        await parser_reset(dut)
        await entry(dut, opcode, command=True)
        for value, expected_index in enumerate(expected_indices):
            observed = await entry(dut, value, command=False)
            assert observed["parameter_index"] == expected_index
            assert observed["complete"] == 0
            assert observed["active"] == 1
        observed = await entry(dut, 0x68, command=True)
        assert observed["interrupted"] == 1
        assert observed["interrupted_opcode"] == opcode


@cocotb.test()
async def unexpected_parameters_are_consumed_and_processor_can_stall(dut: object) -> None:
    await start_and_reset(dut)
    observed = await entry(dut, 0x55, command=False)
    assert observed["pop"] == 1
    assert observed["unexpected"] == 1

    dut.processor_enable.value = 0
    dut.fifo_valid.value = 1
    dut.fifo_is_command.value = 1
    dut.fifo_data.value = 0x6B
    await edge(dut)
    assert int(dut.fifo_pop.value) == 0
    assert int(dut.command_start.value) == 0
    await finish_edge()

    dut.processor_enable.value = 1
    await edge(dut)
    assert int(dut.fifo_pop.value) == 1
    assert int(dut.command_start.value) == 1
    assert int(dut.started_opcode.value) == 0x6B
    await finish_edge()
    dut.fifo_valid.value = 0
