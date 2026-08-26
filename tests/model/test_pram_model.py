from __future__ import annotations

from model.upd7220_model import CommandKind, GdcModel


def issue_pram(model: GdcModel, start: int, values: tuple[int, ...]) -> None:
    model.host_write(0x70 | start, is_command=True)
    event = model.parser_step()
    assert event.started is CommandKind.PRAM
    for value in values:
        model.host_write(value, is_command=False)
        model.parser_step()


def test_pram_can_load_all_sixteen_bytes_sequentially() -> None:
    model = GdcModel()
    model.reset_command()
    values = tuple((index * 0x11) & 0xFF for index in range(16))

    issue_pram(model, 0, values)

    assert bytes(model.parameter_ram) == bytes(values)
    assert model.parameter_ram_known_mask == 0xFFFF
    assert model.command_state.value == "idle"


def test_every_pram_start_address_maps_p1_to_its_selected_location() -> None:
    model = GdcModel()
    model.reset_command()

    for start in range(16):
        issue_pram(model, start, (0x80 | start,))
        model.host_write(0x6B, is_command=True)
        replacement = model.parser_step()
        if start != 15:
            assert replacement.interrupted_opcode == 0x70 | start
        else:
            assert replacement.interrupted_opcode is None

    assert bytes(model.parameter_ram) == bytes(0x80 | index for index in range(16))
    assert model.parameter_ram_known_mask == 0xFFFF


def test_interrupted_partial_pram_load_changes_only_received_suffix_bytes() -> None:
    model = GdcModel()
    model.reset_command()
    issue_pram(model, 0, tuple([0xA5] * 16))

    issue_pram(model, 5, (0x11, 0x22, 0x33))
    model.host_write(0x6B, is_command=True)
    event = model.parser_step()

    assert event.interrupted_opcode == 0x75
    assert bytes(model.parameter_ram) == bytes(
        [0xA5] * 5 + [0x11, 0x22, 0x33] + [0xA5] * 8
    )


def test_functional_reset_retains_parameter_ram_and_known_mask() -> None:
    model = GdcModel()
    model.reset_command()
    issue_pram(model, 8, (0xDE, 0xAD, 0xBE, 0xEF))

    model.host_write(0x00, is_command=True)

    assert bytes(model.parameter_ram[8:12]) == bytes((0xDE, 0xAD, 0xBE, 0xEF))
    assert model.parameter_ram_known_mask == 0x0F00
