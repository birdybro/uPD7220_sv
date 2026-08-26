from __future__ import annotations

from model.upd7220_model import GdcModel, HorizontalPhase


SYNC_PARAMETERS = (0x02, 0x00, 0x21, 0x04, 0x02, 0x01, 0x01, 0x04)


def issue(model: GdcModel, opcode: int, parameters: tuple[int, ...] = ()) -> None:
    model.host_write(opcode, is_command=True)
    for value in parameters:
        model.host_write(value, is_command=False)
    model.parser_step()
    for _ in parameters:
        model.parser_step()


def falling_after_rising(model: GdcModel) -> None:
    model.step_edge()
    model.step_falling_edge()


def advance_word(model: GdcModel) -> None:
    while True:
        model.step_edge()
        model.step_falling_edge()
        if model.word_time_ce:
            return


def pins(model: GdcModel) -> tuple[HorizontalPhase | None, int, bool, bool]:
    return (
        model.horizontal_phase,
        model.horizontal_word_position,
        model.horizontal_sync,
        model.horizontal_blank,
    )


def test_absolute_position_model_matches_documented_four_intervals() -> None:
    model = GdcModel()
    model.reset_command()
    issue(model, 0x0F, SYNC_PARAMETERS)

    falling_after_rising(model)
    assert pins(model) == (HorizontalPhase.FRONT_PORCH, 0, False, True)

    expected = (
        (HorizontalPhase.FRONT_PORCH, 1, False, True),
        (HorizontalPhase.SYNC, 2, True, True),
        (HorizontalPhase.SYNC, 3, True, True),
        (HorizontalPhase.BACK_PORCH, 4, False, True),
        (HorizontalPhase.BACK_PORCH, 5, False, True),
        (HorizontalPhase.BACK_PORCH, 6, False, True),
        (HorizontalPhase.ACTIVE, 7, False, False),
        (HorizontalPhase.ACTIVE, 8, False, False),
        (HorizontalPhase.FRONT_PORCH, 0, False, True),
    )
    observed = []
    for _ in expected:
        advance_word(model)
        observed.append(pins(model))
    assert tuple(observed) == expected


def test_outputs_wait_for_falling_edge_and_blank_tracks_display_enable() -> None:
    model = GdcModel()
    model.reset_command()
    issue(model, 0x0F, SYNC_PARAMETERS)
    issue(model, 0x6B)
    falling_after_rising(model)
    advance_word(model)

    model.step_edge()
    if not model.word_time_ce:
        model.step_falling_edge()
        model.step_edge()
    assert model.word_time_ce
    assert pins(model)[:2] == (HorizontalPhase.FRONT_PORCH, 1)
    model.step_falling_edge()
    assert pins(model)[:2] == (HorizontalPhase.SYNC, 2)

    while model.vertical_phase is None or model.vertical_phase.value != "active":
        advance_word(model)
    while model.horizontal_phase is not HorizontalPhase.ACTIVE:
        advance_word(model)
    assert not model.blank

    issue(model, 0x0E)
    assert not model.display_enabled
    assert not model.blank
    model.step_edge()
    model.step_falling_edge()
    assert model.blank


def test_reset_restarts_retained_horizontal_timing() -> None:
    model = GdcModel()
    model.reset_command()
    issue(model, 0x0F, SYNC_PARAMETERS)
    falling_after_rising(model)
    advance_word(model)
    advance_word(model)
    assert model.horizontal_sync

    model.reset_command()
    assert model.horizontal_word_position == 0
    assert model.blank
    falling_after_rising(model)
    assert pins(model) == (HorizontalPhase.FRONT_PORCH, 0, False, True)
