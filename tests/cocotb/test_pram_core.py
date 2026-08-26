from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

from tests.cocotb.host import HostBusDriver


def bytes_from_packed(value: int) -> list[int]:
    return [(value >> (address * 8)) & 0xFF for address in range(16)]


async def initialize(dut: object) -> HostBusDriver:
    dut.host_rd_n.value = 1
    dut.host_wr_n.value = 1
    dut.host_a0.value = 0
    dut.host_db_i.value = 0
    dut.v_ext_sync_i.value = 0
    dut.dack_n.value = 1
    dut.mem_ad_i.value = 0
    dut.lpen.value = 0
    dut.integration_reset_n.value = 0
    cocotb.start_soon(Clock(dut.clk_2x, 200, unit="ns").start())
    await RisingEdge(dut.clk_2x)
    await Timer(1, unit="ps")
    dut.integration_reset_n.value = 1
    host = HostBusDriver(dut)
    await host.write_command(0x00)
    return host


async def settle_pipeline(dut: object, edges: int = 8) -> None:
    for _ in range(edges):
        await RisingEdge(dut.clk_2x)
        await Timer(1, unit="ps")


@cocotb.test()
async def host_pram_stream_reaches_selected_internal_bytes(dut: object) -> None:
    host = await initialize(dut)
    await host.write_command(0x70)
    for value in range(16):
        await host.write_parameter(0x40 + value)
    await settle_pipeline(dut)

    assert bytes_from_packed(int(dut.unused_parameter_ram.value)) == [
        0x40 + value for value in range(16)
    ]
    assert int(dut.unused_pram_programmed_mask.value) == 0xFFFF


@cocotb.test()
async def host_interruption_and_reset_retain_unaffected_pram_bytes(dut: object) -> None:
    host = await initialize(dut)
    await host.write_command(0x70)
    for _ in range(16):
        await host.write_parameter(0xA5)

    await host.write_command(0x75)
    for value in (0x11, 0x22, 0x33):
        await host.write_parameter(value)
    await host.write_command(0x6B)
    await settle_pipeline(dut)

    expected = [0xA5] * 5 + [0x11, 0x22, 0x33] + [0xA5] * 8
    assert bytes_from_packed(int(dut.unused_parameter_ram.value)) == expected

    await host.write_command(0x00)
    await settle_pipeline(dut)
    assert bytes_from_packed(int(dut.unused_parameter_ram.value)) == expected
