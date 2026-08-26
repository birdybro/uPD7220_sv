from __future__ import annotations

from model.upd7220_model import CommandKind, GdcModel


SYNC_VECTOR = (0x1F, 0xFE, 0xBA, 0xAA, 0x3F, 0x00, 0xFF, 0x03)


def issue(model: GdcModel, opcode: int, parameters: tuple[int, ...] = ()) -> None:
    model.host_write(opcode, is_command=True)
    for value in parameters:
        model.host_write(value, is_command=False)
    event = model.parser_step()
    assert event.started is not None
    for _ in parameters:
        model.parser_step()


def test_sync_loads_every_field_and_base_pitch() -> None:
    model = GdcModel()
    model.reset_command()
    issue(model, 0x0F, SYNC_VECTOR)

    assert model.display_enabled
    assert model.sync_parameter_known_mask == 0xFF
    assert model.sync.display_mode == 1
    assert model.sync.framing_mode == 3
    assert model.sync.dynamic_refresh
    assert model.sync.retrace_only_drawing
    assert model.sync.active_words == 256
    assert model.pitch == 0
    assert model.sync.hsync_width == 27
    assert model.sync.vsync_width == 21
    assert model.sync.horizontal_front_porch == 43
    assert model.sync.horizontal_back_porch == 64
    assert model.sync.vertical_front_porch == 64
    assert model.sync.active_lines == 1023
    assert model.sync.vertical_back_porch == 64


def test_vertical_zero_fields_select_their_power_of_two_maxima() -> None:
    model = GdcModel()
    model.reset_command()
    issue(model, 0x0E, (0, 0, 0, 0, 0, 0, 0, 0))

    assert not model.display_enabled
    assert model.sync.vsync_width == 32
    assert model.sync.vertical_front_porch == 64
    assert model.sync.active_lines == 1024
    assert model.sync.vertical_back_porch == 64


def test_vsync_selects_master_and_reset_retains_mode_and_parameters() -> None:
    model = GdcModel()
    model.reset_command()
    issue(model, 0x0F, SYNC_VECTOR)
    issue(model, 0x6F)
    assert model.sync_master

    model.host_write(0x00, is_command=True)

    assert not model.display_enabled
    assert model.sync_master
    assert tuple(model.sync_parameter_bytes) == SYNC_VECTOR
    assert model.sync.active_words == 256
    assert model.active_command_kind is CommandKind.RESET


def test_partial_reset_prefix_updates_only_received_bytes() -> None:
    model = GdcModel()
    model.reset_command()
    issue(model, 0x0E, SYNC_VECTOR)
    retained = bytes(model.sync_parameter_bytes)

    model.host_write(0x00, is_command=True)
    model.host_write(0x02, is_command=False)
    model.host_write(0x10, is_command=False)
    model.host_write(0x6B, is_command=True)
    assert model.parser_step().parameter == (CommandKind.RESET, 0, 0x02)
    assert model.parser_step().parameter == (CommandKind.RESET, 1, 0x10)
    assert model.parser_step().interrupted_opcode == 0x00

    assert model.sync_parameter_bytes[:2] == bytes((0x02, 0x10))
    assert model.sync_parameter_bytes[2:] == retained[2:]
    assert model.sync.display_mode == 1
    assert model.sync.framing_mode == 0
    assert model.sync.active_words == 18
    assert model.sync.hsync_width == 27


def test_start_exits_idle_while_bctrl_only_changes_display_enable() -> None:
    model = GdcModel()
    model.reset_command()

    issue(model, 0x0D)
    assert model.idle
    assert model.display_enabled
    model.step_edge()
    model.step_falling_edge()
    assert model.blank

    issue(model, 0x6B)
    assert not model.idle
    assert model.display_enabled
    issue(model, 0x0C)
    assert not model.idle
    assert not model.display_enabled
    issue(model, 0x0D)
    assert not model.idle
    assert model.display_enabled

    model.reset_command()
    assert model.idle
    assert not model.display_enabled
