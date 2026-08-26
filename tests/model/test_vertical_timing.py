from __future__ import annotations

from model.upd7220_model import GdcModel, VerticalPhase


SYNC_PARAMETERS = (0x02, 0x00, 0x40, 0x00, 0x00, 0x02, 0x02, 0x0C)


def issue(model: GdcModel, opcode: int, parameters: tuple[int, ...] = ()) -> None:
    model.host_write(opcode, is_command=True)
    for value in parameters:
        model.host_write(value, is_command=False)
    model.parser_step()
    for _ in parameters:
        model.parser_step()


def latch_initial_outputs(model: GdcModel) -> None:
    model.step_edge()
    model.step_falling_edge()


def advance_line(model: GdcModel) -> None:
    while True:
        previous_word = model.horizontal_word_position
        model.step_edge()
        model.step_falling_edge()
        if (
            model.word_time_ce
            and model.horizontal_word_position == 0
            and previous_word != 0
        ):
            return


def pins(model: GdcModel) -> tuple[VerticalPhase | None, int, bool, bool]:
    return (
        model.vertical_phase,
        model.vertical_line_position,
        model.vertical_sync,
        model.vertical_blank,
    )


def test_absolute_line_model_matches_documented_four_intervals() -> None:
    model = GdcModel()
    model.reset_command()
    issue(model, 0x0F, SYNC_PARAMETERS)
    issue(model, 0x6B)
    latch_initial_outputs(model)

    assert pins(model) == (VerticalPhase.FRONT_PORCH, 0, False, True)
    expected = (
        (VerticalPhase.FRONT_PORCH, 1, False, True),
        (VerticalPhase.SYNC, 2, True, True),
        (VerticalPhase.SYNC, 3, True, True),
        (VerticalPhase.BACK_PORCH, 4, False, True),
        (VerticalPhase.BACK_PORCH, 5, False, True),
        (VerticalPhase.BACK_PORCH, 6, False, True),
        (VerticalPhase.ACTIVE, 7, False, False),
        (VerticalPhase.ACTIVE, 8, False, False),
        (VerticalPhase.FRONT_PORCH, 0, False, True),
    )
    observed = []
    for _ in expected:
        advance_line(model)
        observed.append(pins(model))
    assert tuple(observed) == expected


def test_vertical_transition_waits_for_falling_line_boundary() -> None:
    model = GdcModel()
    model.reset_command()
    issue(model, 0x0F, SYNC_PARAMETERS)
    latch_initial_outputs(model)
    advance_line(model)
    assert pins(model)[:2] == (VerticalPhase.FRONT_PORCH, 1)

    while True:
        previous_word = model.horizontal_word_position
        model.step_edge()
        if (
            model.word_time_ce
            and previous_word == 4
        ):
            break
        model.step_falling_edge()
    assert pins(model)[:2] == (VerticalPhase.FRONT_PORCH, 1)
    model.step_falling_edge()
    assert pins(model)[:2] == (VerticalPhase.SYNC, 2)


def test_blank_requires_both_horizontal_and_vertical_active_intervals() -> None:
    model = GdcModel()
    model.reset_command()
    issue(model, 0x0F, SYNC_PARAMETERS)
    issue(model, 0x6B)
    latch_initial_outputs(model)
    assert model.blank

    while model.vertical_phase is not VerticalPhase.ACTIVE:
        advance_line(model)
    while model.horizontal_phase.value != "active":
        model.step_edge()
        model.step_falling_edge()
    assert not model.horizontal_blank
    assert not model.vertical_blank
    assert not model.blank
