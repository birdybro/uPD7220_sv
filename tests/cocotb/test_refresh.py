from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer

from tests.cocotb.host import HostBusDriver


REFRESH = 2
C1 = 1


async def initialize(dut: object) -> HostBusDriver:
    dut.host_rd_n.value = 1
    dut.host_wr_n.value = 1
    dut.host_a0.value = 0
    dut.host_db_i.value = 0
    dut.v_ext_sync_i.value = 0
    dut.dack_n.value = 1
    dut.mem_ad_i.value = 0xBEEF
    dut.lpen.value = 0
    dut.integration_reset_n.value = 0
    cocotb.start_soon(Clock(dut.clk_2x, 200, unit="ns").start())
    await RisingEdge(dut.clk_2x)
    await Timer(1, unit="ps")
    dut.integration_reset_n.value = 1
    host = HostBusDriver(dut)
    await host.write_command(0x00)
    return host


async def configure_raster(host: HostBusDriver, *, refresh: bool) -> None:
    # Graphics; AW=2, HS=3, VS/HFP/HBP/VFP/VBP=1, AL=1.
    p1 = 0x02 | (0x04 if refresh else 0)
    await host.write_command(0x0F)
    for parameter in (p1, 0x00, 0x22, 0x00, 0x00, 0x01, 0x01, 0x04):
        await host.write_parameter(parameter)


async def reset_and_observe_pulse(dut: object, host: HostBusDriver) -> None:
    async def wait_for_reset() -> None:
        for _ in range(40):
            await RisingEdge(dut.clk_2x)
            await ReadOnly()
            if int(dut.reset_command.value):
                return
            await Timer(1, unit="ps")
        raise AssertionError("RESET command did not reach the core")

    waiter = cocotb.start_soon(wait_for_reset())
    await host.write_command(0x00)
    await waiter


async def collect_refresh_starts(
    dut: object, count: int
) -> tuple[list[int], list[int]]:
    addresses: list[int] = []
    rising_indices: list[int] = []
    for rising_index in range(1000):
        await RisingEdge(dut.clk_2x)
        await ReadOnly()
        if (
            int(dut.unused_mem_cycle_kind.value) == REFRESH
            and int(dut.unused_mem_cycle_phase.value) == C1
        ):
            assert int(dut.hsync.value) == 1
            assert int(dut.blank.value) == 1
            assert int(dut.mem_dbin_n.value) == 1
            assert int(dut.mem_ad_oe.value) == 1
            assert int(dut.mem_a16.value) == 0
            assert int(dut.mem_a17.value) == 0
            address = int(dut.mem_ad_o.value)
            assert address < 0x100
            addresses.append(address)
            rising_indices.append(rising_index)
            if len(addresses) == count:
                return addresses, rising_indices
        await Timer(1, unit="ps")
    raise AssertionError(f"only observed {len(addresses)} of {count} refresh cycles")


@cocotb.test()
async def idle_hsync_issues_every_refresh_slot_with_successive_addresses(
    dut: object,
) -> None:
    host = await initialize(dut)
    await configure_raster(host, refresh=True)
    await reset_and_observe_pulse(dut, host)

    addresses, indices = await collect_refresh_starts(dut, 6)
    assert addresses == [0, 1, 2, 3, 4, 5]
    # Three adjacent two-clock cycles fill HS. The next line starts after the
    # two-clock HBP, two active words, and two-clock HFP intervals.
    assert [right - left for left, right in zip(indices, indices[1:])] == [
        2, 2, 10, 2, 2
    ]


@cocotb.test()
async def disabled_refresh_leaves_idle_hsync_memory_slots_unclaimed(
    dut: object,
) -> None:
    host = await initialize(dut)
    await configure_raster(host, refresh=False)
    await reset_and_observe_pulse(dut, host)

    observed_hsync_edges = 0
    for _ in range(200):
        await RisingEdge(dut.clk_2x)
        await ReadOnly()
        if int(dut.hsync.value):
            observed_hsync_edges += 1
            assert int(dut.mem_cycle_active.value) == 0
            assert int(dut.mem_ad_oe.value) == 0
            assert int(dut.mem_ale.value) == 1
        await Timer(1, unit="ps")
    assert observed_hsync_edges >= 12
