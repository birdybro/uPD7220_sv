from __future__ import annotations

import pytest

from model.upd7220_model import GdcModel, ModelError


def configure_short_line(model: GdcModel, *, refresh: bool) -> None:
    # Graphics, optional D; AW=2, HS=2, HFP/HBP=1, all vertical counts valid.
    p1 = 0x02 | (0x04 if refresh else 0)
    for index, value in enumerate((p1, 0x00, 0x21, 0x00, 0x00, 0x01, 0x01, 0x04)):
        model.load_sync_parameter(index, value)


def enter_hsync(model: GdcModel) -> None:
    # RESET begins HFP. The second rising edge produces a word-time enable;
    # the following falling edge enters the first HSYNC word.
    model.step_edge()
    model.step_falling_edge()
    model.step_edge()
    model.step_falling_edge()
    assert model.horizontal_sync


def test_enabled_hsync_slots_advance_successive_eight_bit_addresses() -> None:
    model = GdcModel()
    model.reset_command()
    configure_short_line(model, refresh=True)
    enter_hsync(model)

    assert model.refresh_request
    assert model.accept_refresh_cycle() == 0x00
    assert model.accept_refresh_cycle() == 0x01
    model.refresh_counter = 0xFF
    assert model.accept_refresh_cycle() == 0xFF
    assert model.refresh_counter == 0x00


def test_disabled_or_non_hsync_slots_cannot_accept_refresh() -> None:
    model = GdcModel()
    model.reset_command()
    configure_short_line(model, refresh=False)
    enter_hsync(model)
    assert not model.refresh_request
    with pytest.raises(ModelError):
        model.accept_refresh_cycle()

    model.sync.dynamic_refresh = True
    model.horizontal_sync = False
    with pytest.raises(ModelError):
        model.accept_refresh_cycle()


def test_reset_initializes_refresh_counter_but_retains_sync_parameters() -> None:
    model = GdcModel()
    model.reset_command()
    configure_short_line(model, refresh=True)
    enter_hsync(model)
    assert model.accept_refresh_cycle() == 0x00
    assert model.refresh_counter == 1

    model.reset_command()
    assert model.sync.dynamic_refresh is True
    assert model.refresh_counter == 0
