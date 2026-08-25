from __future__ import annotations

import hashlib

import pytest

from model.upd7220_model import (
    FIFO_CAPACITY,
    EdgeInputs,
    FifoDirection,
    FifoOverflowError,
    FifoUnderflowError,
    GdcModel,
    GdcVariant,
    PowerOnStateError,
)


def test_status_is_explicitly_unknown_before_first_reset() -> None:
    model = GdcModel()
    assert model.architectural_state()["status"] is None
    with pytest.raises(PowerOnStateError):
        model.status()


def test_reset_initializes_control_but_retains_parameters() -> None:
    model = GdcModel()
    model.ead = 0x23456
    model.mask = 0xA55A
    model.pitch = 80
    model.parameter_ram[:] = bytes(range(16))
    model.parameter_ram_known = True
    model.drawing_active = True
    model.dma_active = True
    model.light_pen_detected = True
    model.host_write(0x46, is_command=True)

    model.reset_command()

    assert model.has_reset
    assert model.idle
    assert not model.display_enabled
    assert not model.drawing_active
    assert not model.dma_active
    assert not model.light_pen_detected
    assert model.fifo_occupancy == 0
    assert model.fifo_direction is FifoDirection.WRITE_TO_GDC
    assert model.status() == 0x04
    assert model.ead == 0x23456
    assert model.mask == 0xA55A
    assert model.pitch == 80
    assert model.parameter_ram == bytes(range(16))


def test_two_clock_edges_make_one_word_time() -> None:
    model = GdcModel()
    model.reset_command()

    first = model.step_edge(EdgeInputs(light_pen=True))
    second = model.step_edge()

    assert first["edge_count"] == 1
    assert first["word_half"] == 1
    assert first["word_time_count"] == 0
    assert second["edge_count"] == 2
    assert second["word_half"] == 0
    assert second["word_time_count"] == 1
    assert model.last_inputs == EdgeInputs()


def test_fifo_stores_command_metadata_and_reaches_exact_capacity() -> None:
    model = GdcModel()
    model.reset_command()
    for value in range(FIFO_CAPACITY):
        model.host_write(value, is_command=(value == 0))

    assert model.fifo_occupancy == FIFO_CAPACITY
    assert model.status() & 0x02
    assert not (model.status() & 0x04)
    assert model.fifo_entries[0].is_command
    assert not model.fifo_entries[1].is_command
    with pytest.raises(FifoOverflowError):
        model.host_write(0xFF, is_command=False)


def test_fifo_read_turnaround_discards_queued_writes() -> None:
    model = GdcModel()
    model.reset_command()
    model.host_write(0x46, is_command=True)
    model.host_write(0x12, is_command=False)

    model.begin_read_response()
    model.response_write(0x34)
    model.response_write(0x12)

    assert model.fifo_direction is FifoDirection.READ_FROM_GDC
    assert model.fifo_occupancy == 2
    assert model.status() & 0x01
    assert model.host_read_fifo() == 0x34
    assert model.host_read_fifo() == 0x12
    assert not (model.status() & 0x01)
    assert model.status() & 0x04


def test_command_write_aborts_unread_response() -> None:
    model = GdcModel()
    model.reset_command()
    model.begin_read_response()
    model.response_write(0xAA)

    model.host_write(0x6B, is_command=True)

    assert model.fifo_direction is FifoDirection.WRITE_TO_GDC
    assert model.fifo_occupancy == 1
    assert model.command_processor_read().value == 0x6B
    with pytest.raises(FifoUnderflowError):
        model.command_processor_read()


def test_7220a_can_select_vertical_blank_for_sr6() -> None:
    model = GdcModel(GdcVariant.UPD7220A)
    model.reset_command()
    model.horizontal_blank = False
    model.vertical_blank = True

    assert not (model.status() & 0x40)
    model.vertical_blank_status_select = True
    assert model.status() & 0x40


def test_memory_and_state_hashes_are_reproducible() -> None:
    left = GdcModel(display_memory=[0x1234, 0xABCD])
    right = GdcModel(display_memory=[0x1234, 0xABCD])
    left.reset_command()
    right.reset_command()

    expected_prefix = b"\x34\x12\xcd\xab"
    expected_memory = expected_prefix + b"\x00\x00" * ((1 << 18) - 2)
    assert left.memory_sha256() == hashlib.sha256(expected_memory).hexdigest()
    assert left.memory_sha256() == right.memory_sha256()
    assert left.state_sha256() == right.state_sha256()

    right.write_memory(0x3FFFF, 1)
    assert left.state_sha256() != right.state_sha256()
