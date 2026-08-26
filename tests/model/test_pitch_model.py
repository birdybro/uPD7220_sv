from __future__ import annotations

from model.upd7220_model import GdcModel


def issue(model: GdcModel, opcode: int, parameters: tuple[int, ...] = ()) -> None:
    model.host_write(opcode, is_command=True)
    for value in parameters:
        model.host_write(value, is_command=False)
    model.parser_step()
    for _ in parameters:
        model.parser_step()


def test_explicit_pitch_keeps_literal_zero_and_full_range() -> None:
    model = GdcModel()
    model.reset_command()

    for value in (0x00, 0x01, 0x7F, 0xFE, 0xFF):
        issue(model, 0x47, (value,))
        assert model.pitch == value


def test_sync_active_words_load_wraps_the_eight_bit_base_register() -> None:
    model = GdcModel()
    model.reset_command()

    for p2, active_words, pitch in (
        (0x00, 2, 0x02),
        (0x7E, 128, 0x80),
        (0xFD, 255, 0xFF),
        (0xFE, 256, 0x00),
    ):
        issue(model, 0x0E, (0x02, p2))
        assert model.sync.active_words == active_words
        assert model.pitch == pitch


def test_reset_without_optional_p2_retains_explicit_pitch() -> None:
    model = GdcModel()
    model.reset_command()
    issue(model, 0x47, (0xA5,))

    model.host_write(0x00, is_command=True)

    assert model.pitch == 0xA5
