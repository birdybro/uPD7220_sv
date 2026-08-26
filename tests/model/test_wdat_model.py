from __future__ import annotations

import pytest

from model.upd7220_model import (
    DisplayMode,
    GdcModel,
    ModelError,
    PowerOnStateError,
)


def configured_model(mode: DisplayMode) -> GdcModel:
    model = GdcModel()
    model.reset_command()
    model.sync.display_mode = int(mode)
    model.ead = 0x12345
    model.mask = 0x0FF0
    model.pitch = 4
    model.write_memory(0x12345, 0xF00F)
    return model


def test_character_word_replace_uses_all_parameter_and_mask_bits() -> None:
    model = configured_model(DisplayMode.CHARACTER)
    assert model.execute_basic_wdat_word_replace(0xA55A) == (
        0x12345,
        0xF00F,
        0xF55F,
    )
    assert model.read_memory(0x12345) == 0xF55F
    assert model.pattern == 0xA55A
    assert model.ead == 0x12349


@pytest.mark.parametrize(
    ("data", "expected"),
    ((0xFF00, 0x0000), (0x0001, 0xFFFF), (0xA5A1, 0xFFFF)),
)
def test_graphics_word_replace_expands_only_p1_bit_zero(
    data: int, expected: int
) -> None:
    model = configured_model(DisplayMode.GRAPHICS)
    model.mask = 0xFFFF
    model.execute_basic_wdat_word_replace(data)
    assert model.read_memory(0x12345) == expected


def test_basic_wdat_wraps_ead_after_direction_zero_pitch_step() -> None:
    model = configured_model(DisplayMode.CHARACTER)
    model.ead = 0x3FFFE
    model.pitch = 4
    model.mask = 0
    model.execute_basic_wdat_word_replace(0xFFFF)
    assert model.ead == 0x00002


def test_character_replace_is_exhaustive_per_bit() -> None:
    for bit in range(16):
        bit_mask = 1 << bit
        for old_bit in (0, 1):
            for data_bit in (0, 1):
                model = configured_model(DisplayMode.CHARACTER)
                model.mask = bit_mask
                old_word = 0xA55A
                old_word = (old_word & ~bit_mask) | (old_bit << bit)
                data = 0x5AA5
                data = (data & ~bit_mask) | (data_bit << bit)
                model.write_memory(model.ead, old_word)
                _, _, new_word = model.execute_basic_wdat_word_replace(data)
                assert ((new_word >> bit) & 1) == data_bit
                assert (new_word & ~bit_mask) == (old_word & ~bit_mask)


def test_basic_wdat_rejects_unprogrammed_or_unsupported_state() -> None:
    model = GdcModel()
    model.reset_command()
    with pytest.raises(PowerOnStateError):
        model.execute_basic_wdat_word_replace(0)

    model = configured_model(DisplayMode.CHARACTER)
    with pytest.raises(ModelError):
        model.execute_basic_wdat_word_replace(0, direction=1)

    model.sync.display_mode = int(DisplayMode.MIXED)
    with pytest.raises(ModelError):
        model.execute_basic_wdat_word_replace(0)
