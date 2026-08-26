from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer


async def rising(dut: object) -> None:
    await RisingEdge(dut.clk_2x)
    await ReadOnly()


async def finish_edge() -> None:
    await Timer(1, unit="ps")


@cocotb.test()
async def counter_advances_only_on_accepted_enabled_hsync_requests(
    dut: object,
) -> None:
    dut.integration_reset_n.value = 0
    dut.reset_command.value = 0
    dut.refresh_enable.value = 0
    dut.hsync.value = 0
    dut.request_ready.value = 0
    cocotb.start_soon(Clock(dut.clk_2x, 200, unit="ns").start())
    await rising(dut)
    await finish_edge()
    dut.integration_reset_n.value = 1

    assert int(dut.request_valid.value) == 0
    assert int(dut.refresh_counter.value) == 0
    assert int(dut.request_address.value) == 0

    dut.refresh_enable.value = 1
    dut.hsync.value = 1
    await Timer(1, unit="ns")
    assert int(dut.request_valid.value) == 1
    for _ in range(3):
        await rising(dut)
        assert int(dut.request_accept.value) == 0
        assert int(dut.refresh_counter.value) == 0
        await finish_edge()

    dut.request_ready.value = 1
    for expected in range(1, 257):
        await rising(dut)
        assert int(dut.request_accept.value) == 1
        assert int(dut.refresh_counter.value) == (expected & 0xFF)
        assert int(dut.request_address.value) == (expected & 0xFF)
        await finish_edge()

    dut.hsync.value = 0
    await Timer(1, unit="ns")
    assert int(dut.request_valid.value) == 0
    await rising(dut)
    assert int(dut.refresh_counter.value) == 0
    await finish_edge()

    dut.hsync.value = 1
    dut.reset_command.value = 1
    await Timer(1, unit="ns")
    await rising(dut)
    assert int(dut.refresh_counter.value) == 0
    await finish_edge()
    dut.reset_command.value = 0
