from __future__ import annotations

import pytest

from model.upd7220_model import (
    CommandKind,
    CommandState,
    FifoDirection,
    GdcModel,
    ModelError,
    decode_command,
)


def expected_kind_and_limit(opcode: int) -> tuple[CommandKind | None, int]:
    fixed = {
        0x00: (CommandKind.RESET, 8),
        0x4B: (CommandKind.CCHAR, 3),
        0x6B: (CommandKind.START, 0),
        0x46: (CommandKind.ZOOM, 1),
        0x49: (CommandKind.CURS, 3),
        0x47: (CommandKind.PITCH, 1),
        0x4A: (CommandKind.MASK, 2),
        0x4C: (CommandKind.FIGS, 11),
        0x6C: (CommandKind.FIGD, 0),
        0x68: (CommandKind.GCHRD, 0),
        0xE0: (CommandKind.CURD, 0),
        0xC0: (CommandKind.LPRD, 0),
    }
    if opcode in fixed:
        return fixed[opcode]
    if opcode in (0x0E, 0x0F):
        return CommandKind.SYNC, 8
    if opcode in (0x6E, 0x6F):
        return CommandKind.VSYNC, 0
    if opcode in (0x0C, 0x0D):
        return CommandKind.BCTRL, 0
    if opcode >> 4 == 7:
        return CommandKind.PRAM, 16 - (opcode & 15)
    transfer_type = (opcode >> 3) & 3
    if transfer_type == 1:
        return None, 0
    groups = {
        0x20: CommandKind.WDAT,
        0x24: CommandKind.DMAW,
        0xA0: CommandKind.RDAT,
        0xA4: CommandKind.DMAR,
    }
    kind = groups.get(opcode & 0xE4)
    if kind is None:
        return None, 0
    return kind, (2 if transfer_type == 0 else 1) if kind is CommandKind.WDAT else 0


def test_all_base_opcode_decodes_and_limits() -> None:
    for opcode in range(256):
        decoded = decode_command(opcode)
        expected_kind, expected_limit = expected_kind_and_limit(opcode)
        assert decoded.kind is expected_kind, f"opcode=0x{opcode:02x}"
        assert decoded.parameter_limit == expected_limit, f"opcode=0x{opcode:02x}"


def test_parser_tracks_parameters_completion_and_interruption() -> None:
    model = GdcModel()
    model.reset_command()
    model.host_write(0x4B, is_command=True)
    model.host_write(0x12, is_command=False)
    model.host_write(0x34, is_command=False)
    model.host_write(0x6B, is_command=True)

    start = model.parser_step()
    assert start.started is CommandKind.CCHAR
    assert model.command_state is CommandState.PARAMETERS
    assert model.parser_step().parameter == (CommandKind.CCHAR, 0, 0x12)
    assert model.parser_step().parameter == (CommandKind.CCHAR, 1, 0x34)
    replacement = model.parser_step()
    assert replacement.interrupted_opcode == 0x4B
    assert replacement.started is CommandKind.START
    assert replacement.completed_opcode == 0x6B
    assert model.command_state is CommandState.IDLE


def test_wdat_parameter_groups_repeat_until_a_command() -> None:
    model = GdcModel()
    model.reset_command()
    model.host_write(0x20, is_command=True)
    for value in range(5):
        model.host_write(value, is_command=False)
    model.host_write(0x68, is_command=True)

    assert model.parser_step().started is CommandKind.WDAT
    for value, expected_index in zip(range(5), (0, 1, 0, 1, 0), strict=True):
        event = model.parser_step()
        assert event.parameter == (CommandKind.WDAT, expected_index, value)
        assert event.completed_opcode is None
    final = model.parser_step()
    assert final.interrupted_opcode == 0x20
    assert final.started is CommandKind.GCHRD


def test_read_direction_requires_a_command_abort_and_discards_data_register() -> None:
    model = GdcModel()
    model.reset_command()
    model.begin_read_response()
    model.response_write(0xAA)
    for _ in range(4):
        model.step_edge()
    assert model.data_register == 0xAA

    with pytest.raises(ModelError):
        model.host_write(0x55, is_command=False)
    assert model.fifo_direction is FifoDirection.READ_FROM_GDC
    assert model.data_register == 0xAA

    model.host_write(0x6B, is_command=True)
    assert model.fifo_direction is FifoDirection.WRITE_TO_GDC
    assert model.data_register is None
    assert model.read_refill_count == 0
