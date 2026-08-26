from __future__ import annotations

import pytest

from model.upd7220_model import DisplayMode, GdcModel, PowerOnStateError


def graphics_descriptor(
    start: int, lines: int, *, image: bool = False, wide: bool = False
) -> tuple[int, int, int, int]:
    raw_lines = lines & 0x3FF
    return (
        start & 0xFF,
        (start >> 8) & 0xFF,
        ((raw_lines & 0x0F) << 4) | ((start >> 16) & 0x03),
        (int(wide) << 7) | (int(image) << 6) | ((raw_lines >> 4) & 0x3F),
    )


def character_descriptor(
    start: int, lines: int, *, image: bool = False, wide: bool = False
) -> tuple[int, int, int, int]:
    raw_lines = lines & 0x3FF
    return (
        start & 0xFF,
        (start >> 8) & 0x1F,
        (raw_lines & 0x0F) << 4,
        (int(wide) << 7) | (int(image) << 6) | ((raw_lines >> 4) & 0x3F),
    )


def load_descriptors(model: GdcModel, *descriptors: tuple[int, ...]) -> None:
    data = bytes(value for descriptor in descriptors for value in descriptor)
    model.parameter_ram[: len(data)] = data
    model.parameter_ram_known_mask |= (1 << len(data)) - 1


def test_graphics_partition_fetch_and_image_wide_stepping() -> None:
    model = GdcModel()
    model.reset_command()
    model.sync.display_mode = DisplayMode.GRAPHICS
    model.pitch = 0x20
    load_descriptors(
        model,
        graphics_descriptor(0x31234, 2),
        graphics_descriptor(0x00080, 3, image=True, wide=True),
    )

    model.start_active_display()
    assert model.display_partition_index == 0
    assert model.display_partition_line_count == 2
    assert model.dad == 0x31234
    model.advance_display_slot()
    assert model.dad == 0x31235

    # The current descriptor remains latched while the next is read live.
    load_descriptors(
        model,
        graphics_descriptor(0x22222, 1, image=True, wide=True),
        graphics_descriptor(0x00100, 4, image=True, wide=True),
    )
    assert model.display_partition_start_address == 0x31234
    assert model.display_partition_line_count == 2
    model.start_display_line()
    assert model.dad == 0x31254
    model.start_display_line()
    assert model.display_partition_index == 1
    assert model.display_partition_line_count == 4
    assert model.dad == 0x00100

    model.advance_display_slot()
    assert model.dad == 0x00100
    model.advance_display_slot()
    assert model.dad == 0x00102


def test_character_row_repeat_four_areas_and_thirteen_bit_wrap() -> None:
    model = GdcModel()
    model.reset_command()
    model.sync.display_mode = DisplayMode.CHARACTER
    model.pitch = 5
    model.cursor_characteristics.lines_per_row = 2
    load_descriptors(
        model,
        character_descriptor(0x1FFE, 3, wide=True),
        character_descriptor(0x0123, 1),
        character_descriptor(0x0234, 1),
        character_descriptor(0x0345, 1),
    )

    model.start_active_display()
    model.advance_display_slot()
    assert model.dad == 0
    model.start_display_line()
    assert model.display_character_scanline == 1
    assert model.dad == 0x1FFE
    model.start_display_line()
    assert model.display_character_scanline == 0
    assert model.dad == 3
    model.start_display_line()
    assert model.display_partition_index == 1
    for expected in (2, 3, 0):
        model.start_display_line()
        assert model.display_partition_index == expected


def test_mixed_mode_uses_image_as_area_type_and_wraps_sixteen_bits() -> None:
    model = GdcModel()
    model.reset_command()
    model.sync.display_mode = DisplayMode.MIXED
    model.pitch = 1
    load_descriptors(
        model,
        graphics_descriptor(0x2FFFE, 1, wide=True),
        graphics_descriptor(0x1FFFF, 2, image=True, wide=True),
    )

    model.start_active_display()
    assert not model.display_partition_graphics
    assert model.dad == 0xFFFE
    model.advance_display_slot()
    assert model.dad == 0
    model.start_display_line()
    assert model.display_partition_graphics
    assert model.dad == 0xFFFF
    model.advance_display_slot()
    assert model.dad == 0xFFFF
    model.advance_display_slot()
    assert model.dad == 1


def test_zero_length_unknown_bytes_invalid_mode_and_reset() -> None:
    model = GdcModel()
    model.reset_command()
    model.sync.display_mode = DisplayMode.GRAPHICS
    with pytest.raises(PowerOnStateError):
        model.start_active_display()

    load_descriptors(
        model,
        graphics_descriptor(0x3FFFF, 0),
        graphics_descriptor(0, 1),
    )
    model.start_active_display()
    assert model.display_partition_line_count == 1024
    model.advance_display_slot()
    assert model.dad == 0

    model.reset_command()
    assert not model.display_partition_active
    assert model.dad == 0

    model.sync.display_mode = DisplayMode.INVALID
    model.start_active_display()
    assert not model.display_partition_active
