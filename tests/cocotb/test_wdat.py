from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge, Timer

from tests.cocotb.host import HostBusDriver


MEM_CYCLE_RMW = 1
C1 = 1
C2 = 2
C3 = 3
C4 = 4


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


async def configure(
    host: HostBusDriver,
    *,
    graphics: bool,
    pitch: int,
    ead: int,
    dot: int,
    mask: int,
) -> None:
    # Valid one-word raster fields; display remains idle and refresh is off.
    p1 = 0x02 if graphics else 0x20
    await host.write_command(0x0E)
    for parameter in (p1, 0x00, 0x20, 0x00, 0x00, 0x01, 0x01, 0x04):
        await host.write_parameter(parameter)
    await host.write_command(0x47)
    await host.write_parameter(pitch)
    await host.write_command(0x49)
    await host.write_parameter(ead & 0xFF)
    await host.write_parameter((ead >> 8) & 0xFF)
    await host.write_parameter(((dot & 0xF) << 4) | ((ead >> 16) & 0x3))
    await host.write_command(0x4A)
    await host.write_parameter(mask & 0xFF)
    await host.write_parameter((mask >> 8) & 0xFF)
    # The Milestone-22 subset is FIGS DIR=0 and DC=0.
    await host.write_command(0x4C)
    await host.write_parameter(0x00)
    await host.write_parameter(0x00)
    await host.write_parameter(0x00)


async def monitor_rmw(
    dut: object, *, address: int, old_word: int, expected_write: int
) -> None:
    dut.mem_ad_i.value = old_word
    for _ in range(200):
        await RisingEdge(dut.clk_2x)
        await ReadOnly()
        if (
            int(dut.unused_mem_cycle_kind.value) == MEM_CYCLE_RMW
            and int(dut.unused_mem_cycle_phase.value) == C1
        ):
            break
        await Timer(1, unit="ps")
    else:
        raise AssertionError("WDAT RMW cycle did not begin")

    observed_address = (
        (int(dut.mem_a17.value) << 17)
        | (int(dut.mem_a16.value) << 16)
        | int(dut.mem_ad_o.value)
    )
    assert observed_address == address
    assert int(dut.mem_ale.value) == 1
    assert int(dut.mem_dbin_n.value) == 1
    assert int(dut.mem_ad_oe.value) == 1

    await FallingEdge(dut.clk_2x)
    await ReadOnly()
    assert int(dut.unused_mem_cycle_phase.value) == C1
    assert int(dut.mem_ale.value) == 0
    assert int(dut.mem_ad_oe.value) == 1
    await Timer(1, unit="ps")

    await RisingEdge(dut.clk_2x)
    await ReadOnly()
    assert int(dut.unused_mem_cycle_phase.value) == C2
    assert int(dut.mem_ad_oe.value) == 0
    await Timer(1, unit="ps")
    await FallingEdge(dut.clk_2x)
    await ReadOnly()
    assert int(dut.mem_dbin_n.value) == 0
    assert int(dut.mem_ad_oe.value) == 0
    await Timer(1, unit="ps")

    await RisingEdge(dut.clk_2x)
    await ReadOnly()
    assert int(dut.unused_mem_cycle_phase.value) == C3
    assert int(dut.mem_dbin_n.value) == 0
    await Timer(1, unit="ps")
    await FallingEdge(dut.clk_2x)
    await ReadOnly()
    assert int(dut.mem_dbin_n.value) == 1
    await Timer(1, unit="ps")

    await RisingEdge(dut.clk_2x)
    await ReadOnly()
    assert int(dut.unused_mem_cycle_phase.value) == C4
    assert int(dut.mem_ad_oe.value) == 1
    assert int(dut.mem_ad_o.value) == expected_write
    assert int(dut.mem_a16.value) == ((address >> 16) & 1)
    assert int(dut.mem_a17.value) == ((address >> 17) & 1)
    await Timer(1, unit="ps")
    await FallingEdge(dut.clk_2x)
    await ReadOnly()
    assert int(dut.mem_ad_oe.value) == 1
    assert int(dut.mem_ad_o.value) == expected_write
    await Timer(1, unit="ps")

    await RisingEdge(dut.clk_2x)
    await ReadOnly()
    assert int(dut.mem_cycle_active.value) == 0
    assert int(dut.mem_ad_oe.value) == 0
    await Timer(1, unit="ps")


async def read_cursor(host: HostBusDriver) -> list[int]:
    await host.write_command(0xE0)
    result: list[int] = []
    for _ in range(5):
        for _ in range(32):
            if await host.read_status() & 1:
                break
        else:
            raise AssertionError("CURD response did not become ready")
        result.append(await host.read_fifo())
    return result


@cocotb.test()
async def character_word_replace_runs_exact_masked_rmw_and_advances_ead(
    dut: object,
) -> None:
    host = await initialize(dut)
    await configure(
        host,
        graphics=False,
        pitch=4,
        ead=0x12345,
        dot=6,
        mask=0x0FF0,
    )
    await host.write_command(0x20)
    await host.write_parameter(0x5A)
    trace = cocotb.start_soon(
        monitor_rmw(
            dut, address=0x12345, old_word=0xF00F, expected_write=0xF55F
        )
    )
    await host.write_parameter(0xA5)
    await trace

    assert await read_cursor(host) == [0x49, 0x23, 0x01, 0xF0, 0x0F]


@cocotb.test()
async def graphics_groups_expand_p1_lsb_and_each_execute_once(dut: object) -> None:
    host = await initialize(dut)
    await configure(
        host,
        graphics=True,
        pitch=1,
        ead=0x20010,
        dot=0,
        mask=0x00FF,
    )
    await host.write_command(0x20)

    await host.write_parameter(0x00)
    first = cocotb.start_soon(
        monitor_rmw(
            dut, address=0x20010, old_word=0xA55A, expected_write=0xA500
        )
    )
    await host.write_parameter(0xFF)
    await first

    await host.write_parameter(0x01)
    second = cocotb.start_soon(
        monitor_rmw(
            dut, address=0x20011, old_word=0x1234, expected_write=0x12FF
        )
    )
    await host.write_parameter(0x00)
    await second

    assert await read_cursor(host) == [0x12, 0x00, 0x02, 0xFF, 0x00]
