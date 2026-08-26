from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge, Timer


DISPLAY = 0
RMW = 1
IDLE = 0
C1 = 1
C2 = 2
C3 = 3
C4 = 4


async def rising(dut: object) -> None:
    await RisingEdge(dut.clk_2x)
    await ReadOnly()


async def falling(dut: object) -> None:
    await FallingEdge(dut.clk_2x)
    await ReadOnly()


async def finish_edge() -> None:
    await Timer(1, unit="ps")


async def start_and_reset(dut: object) -> None:
    dut.integration_reset_n.value = 0
    dut.reset_command.value = 0
    dut.request_valid.value = 0
    dut.request_kind.value = DISPLAY
    dut.request_address.value = 0
    dut.rmw_write_data.value = 0
    dut.mem_ad_i.value = 0
    cocotb.start_soon(Clock(dut.clk_2x, 200, unit="ns").start())
    await rising(dut)
    await finish_edge()
    dut.integration_reset_n.value = 1


def pins(dut: object) -> tuple[int, ...]:
    return (
        int(dut.cycle_phase.value),
        int(dut.cycle_active.value),
        int(dut.request_ready.value),
        int(dut.mem_ale.value),
        int(dut.mem_dbin_n.value),
        int(dut.mem_ad_oe.value),
        int(dut.mem_ad_o.value),
        int(dut.mem_a16.value),
        int(dut.mem_a17.value),
    )


@cocotb.test()
async def display_cycle_has_exact_two_clock_address_and_turnaround_trace(
    dut: object,
) -> None:
    await start_and_reset(dut)
    assert pins(dut) == (IDLE, 0, 1, 1, 1, 0, 0, 0, 0)

    dut.request_kind.value = DISPLAY
    dut.request_address.value = 0x31234
    dut.request_valid.value = 1
    await rising(dut)
    assert pins(dut) == (C1, 1, 0, 1, 1, 1, 0x1234, 1, 1)
    await finish_edge()
    dut.request_valid.value = 0

    await falling(dut)
    assert pins(dut) == (C1, 1, 0, 0, 1, 1, 0x1234, 1, 1)
    await finish_edge()
    await rising(dut)
    assert pins(dut) == (C2, 1, 1, 0, 1, 0, 0x1234, 1, 1)
    await finish_edge()

    dut.mem_ad_i.value = 0xBEEF
    await falling(dut)
    assert pins(dut)[0:6] == (C2, 1, 1, 0, 1, 0)
    await finish_edge()
    await rising(dut)
    assert pins(dut)[0:6] == (IDLE, 0, 1, 1, 1, 0)
    assert int(dut.response_valid.value) == 1
    assert int(dut.response_kind.value) == DISPLAY
    assert int(dut.response_address.value) == 0x31234
    assert int(dut.response_read_data.value) == 0xBEEF

    await finish_edge()
    await rising(dut)
    assert int(dut.response_valid.value) == 0


@cocotb.test()
async def rmw_cycle_asserts_dbin_samples_then_drives_cycle_four(dut: object) -> None:
    await start_and_reset(dut)
    dut.request_kind.value = RMW
    dut.request_address.value = 0x255AA
    dut.rmw_write_data.value = 0
    dut.request_valid.value = 1
    await rising(dut)
    assert pins(dut) == (C1, 1, 0, 1, 1, 1, 0x55AA, 0, 1)
    await finish_edge()
    dut.request_valid.value = 0

    await falling(dut)
    assert pins(dut)[3:6] == (0, 1, 1)
    await finish_edge()
    await rising(dut)
    assert pins(dut)[0:6] == (C2, 1, 0, 0, 1, 0)
    await finish_edge()

    await falling(dut)
    assert pins(dut)[0:6] == (C2, 1, 0, 0, 0, 0)
    await finish_edge()
    dut.mem_ad_i.value = 0xA55A
    await rising(dut)
    assert pins(dut)[0:6] == (C3, 1, 0, 0, 0, 0)
    await finish_edge()

    await falling(dut)
    assert pins(dut)[0:6] == (C3, 1, 0, 0, 1, 0)
    await finish_edge()
    dut.rmw_write_data.value = 0x5AA5
    await rising(dut)
    assert pins(dut)[0:6] == (C4, 1, 1, 0, 1, 1)
    assert int(dut.mem_ad_o.value) == 0x5AA5
    assert int(dut.rmw_read_data_valid.value) == 1
    assert int(dut.rmw_read_data.value) == 0xA55A
    await finish_edge()

    dut.rmw_write_data.value = 0x1234
    await Timer(1, unit="ns")
    assert int(dut.mem_ad_o.value) == 0x5AA5

    await falling(dut)
    assert int(dut.mem_ad_oe.value) == 1
    assert int(dut.mem_ad_o.value) == 0x5AA5
    await finish_edge()
    await rising(dut)
    assert pins(dut)[0:6] == (IDLE, 0, 1, 1, 1, 0)
    assert int(dut.response_valid.value) == 1
    assert int(dut.response_kind.value) == RMW
    assert int(dut.response_address.value) == 0x255AA
    assert int(dut.response_read_data.value) == 0xA55A


@cocotb.test()
async def final_cycle_accepts_a_back_to_back_request_without_idle_gap(
    dut: object,
) -> None:
    await start_and_reset(dut)
    dut.request_kind.value = DISPLAY
    dut.request_address.value = 0x00011
    dut.request_valid.value = 1
    await rising(dut)
    await finish_edge()
    dut.request_valid.value = 0
    await falling(dut)
    await finish_edge()
    await rising(dut)
    assert int(dut.cycle_phase.value) == C2
    assert int(dut.request_ready.value) == 1
    await finish_edge()

    dut.request_address.value = 0x20022
    dut.request_valid.value = 1
    await falling(dut)
    await finish_edge()
    await rising(dut)
    assert int(dut.response_valid.value) == 1
    assert int(dut.response_address.value) == 0x00011
    assert pins(dut) == (C1, 1, 0, 1, 1, 1, 0x0022, 0, 1)
    await finish_edge()
    dut.request_valid.value = 0
    await falling(dut)
    assert int(dut.mem_ale.value) == 0


@cocotb.test()
async def functional_reset_immediately_releases_a_mid_rmw_bus(dut: object) -> None:
    await start_and_reset(dut)
    dut.request_kind.value = RMW
    dut.request_address.value = 0x12345
    dut.request_valid.value = 1
    await rising(dut)
    await finish_edge()
    dut.request_valid.value = 0
    await falling(dut)
    await finish_edge()
    await rising(dut)
    await finish_edge()
    await falling(dut)
    assert int(dut.mem_dbin_n.value) == 0
    await finish_edge()

    dut.reset_command.value = 1
    await Timer(1, unit="ns")
    assert int(dut.mem_dbin_n.value) == 1
    assert int(dut.mem_ad_oe.value) == 0
    assert int(dut.mem_ale.value) == 1
    await rising(dut)
    assert int(dut.cycle_phase.value) == IDLE
    assert int(dut.response_valid.value) == 0
