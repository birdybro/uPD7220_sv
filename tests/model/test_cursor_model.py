from __future__ import annotations

import pytest

from model.upd7220_model import (
    CommandKind,
    CommandState,
    FifoDirection,
    GdcModel,
    PowerOnStateError,
)


def program_cursor(model: GdcModel, *, ead: int, dot: int) -> None:
    model.host_write(0x49, is_command=True)
    model.host_write(ead & 0xFF, is_command=False)
    model.host_write((ead >> 8) & 0xFF, is_command=False)
    model.host_write(((dot & 0x0F) << 4) | ((ead >> 16) & 0x03), is_command=False)
    for _ in range(4):
        model.parser_step()


@pytest.mark.parametrize(
    ("ead", "dot"),
    ((0x00000, 0), (0x00001, 15), (0x2ABCD, 7), (0x3FFFF, 15)),
)
def test_curs_loads_18_bit_ead_and_expands_dot_address(ead: int, dot: int) -> None:
    model = GdcModel()
    model.reset_command()

    program_cursor(model, ead=ead, dot=dot)

    assert model.ead == ead
    assert model.dad_dot == dot
    assert model.mask == 1 << dot


def test_character_mode_prefix_updates_low_16_bits_without_overwriting_high_state() -> None:
    model = GdcModel()
    model.reset_command()
    program_cursor(model, ead=0x31234, dot=10)

    model.host_write(0x49, is_command=True)
    model.host_write(0x78, is_command=False)
    model.host_write(0x56, is_command=False)
    model.host_write(0x6B, is_command=True)
    model.parser_step()
    model.parser_step()
    model.parser_step()
    replacement = model.parser_step()

    assert replacement.interrupted_opcode == 0x49
    assert replacement.started is CommandKind.START
    assert model.ead == 0x35678
    assert model.dad_dot == 10
    assert model.mask == 0x0400


def test_curd_returns_five_defined_cursor_bytes_after_fifo_turnaround() -> None:
    model = GdcModel()
    model.reset_command()
    program_cursor(model, ead=0x31234, dot=10)
    model.host_write(0xE0, is_command=True)

    event = model.parser_step()

    assert event.started is CommandKind.CURD
    assert event.completed_opcode == 0xE0
    assert model.command_state is CommandState.READ_RESPONSE
    assert model.fifo_direction is FifoDirection.READ_FROM_GDC
    assert [entry.value for entry in model.fifo_entries] == [
        0x34,
        0x12,
        0x03,
        0x00,
        0x04,
    ]

    returned = []
    for _ in range(5):
        while not model.status() & 0x01:
            model.step_edge()
        returned.append(model.host_read_fifo())
    assert returned == [0x34, 0x12, 0x03, 0x00, 0x04]


def test_curd_requires_previously_programmed_cursor_state() -> None:
    model = GdcModel()
    model.reset_command()
    model.host_write(0xE0, is_command=True)

    with pytest.raises(PowerOnStateError):
        model.parser_step()
