from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge, Timer

from tests.cocotb.host import HostBusDriver
from tests.cocotb.test_partitions import graphics_descriptor


C1 = 1


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


async def configure_graphics_raster(dut: object, host: HostBusDriver) -> None:
    # Graphics, AW=2, HS=1, VS=1, HFP/HBP/VFP/VBP=1, AL=3.
    await host.write_command(0x0F)
    for parameter in (0x02, 0x00, 0x20, 0x00, 0x00, 0x01, 0x03, 0x04):
        await host.write_parameter(parameter)
    await host.write_command(0x47)
    await host.write_parameter(4)

    area0 = graphics_descriptor(0x30100, 2)
    area1 = graphics_descriptor(0x20200, 1, image=True)
    await host.write_command(0x70)
    for parameter in (*area0, *area1):
        await host.write_parameter(parameter)

    # RESET restarts raster and bus phases without erasing the configuration.
    await host.write_command(0x00)


async def collect_fetch_addresses(
    dut: object, count: int, *, require_blank: int | None = None
) -> list[int]:
    addresses: list[int] = []
    for _ in range(2000):
        await FallingEdge(dut.clk_2x)
        await ReadOnly()
        if (
            int(dut.unused_mem_cycle_phase.value) == C1
            and int(dut.mem_ad_oe.value) == 1
            and int(dut.mem_ale.value) == 0
        ):
            address = (
                (int(dut.mem_a17.value) << 17)
                | (int(dut.mem_a16.value) << 16)
                | int(dut.mem_ad_o.value)
            )
            addresses.append(address)
            if require_blank is not None:
                assert int(dut.blank.value) == require_blank
            await Timer(1, unit="ps")
            dut.mem_ad_i.value = (address ^ 0xA5A5) & 0xFFFF
            if len(addresses) == count:
                return addresses
        await Timer(1, unit="ps")
    raise AssertionError(f"only observed {len(addresses)} of {count} display fetches")


async def collect_responses(dut: object, count: int) -> list[tuple[int, int]]:
    responses: list[tuple[int, int]] = []
    for _ in range(4000):
        await RisingEdge(dut.clk_2x)
        await ReadOnly()
        if int(dut.mem_response_valid.value):
            responses.append(
                (
                    int(dut.mem_response_address.value),
                    int(dut.mem_response_read_data.value),
                )
            )
            if len(responses) == count:
                return responses
        await Timer(1, unit="ps")
    raise AssertionError(f"only observed {len(responses)} of {count} responses")


@cocotb.test()
async def raster_fetches_follow_dad_pitch_partitions_and_image_repeat(
    dut: object,
) -> None:
    host = await initialize(dut)
    await configure_graphics_raster(dut, host)
    await host.write_command(0x6B)

    response_task = cocotb.start_soon(collect_responses(dut, 6))
    addresses = await collect_fetch_addresses(dut, 6, require_blank=0)
    responses = await response_task

    assert addresses == [0x30100, 0x30101, 0x30104, 0x30105, 0x20200, 0x20200]
    assert responses == [
        (address, (address ^ 0xA5A5) & 0xFFFF) for address in addresses
    ]
    assert int(dut.unused_partition_index.value) == 1


@cocotb.test()
async def idle_suppresses_fetch_but_bctrl_only_blanks_running_fetches(
    dut: object,
) -> None:
    host = await initialize(dut)
    await configure_graphics_raster(dut, host)

    for _ in range(120):
        await RisingEdge(dut.clk_2x)
        await ReadOnly()
        assert int(dut.mem_cycle_active.value) == 0
        assert int(dut.mem_ale.value) == 1
        await Timer(1, unit="ps")

    await host.write_command(0x6B)
    assert await collect_fetch_addresses(dut, 1, require_blank=0)

    await host.write_command(0x0C)
    for _ in range(16):
        await RisingEdge(dut.clk_2x)
        await Timer(1, unit="ps")
    assert int(dut.sync_display_enable.value) == 0
    assert await collect_fetch_addresses(dut, 1, require_blank=1)

    await host.write_command(0x0D)
    for _ in range(16):
        await RisingEdge(dut.clk_2x)
        await Timer(1, unit="ps")
    assert int(dut.sync_display_enable.value) == 1
    assert await collect_fetch_addresses(dut, 1, require_blank=0)
