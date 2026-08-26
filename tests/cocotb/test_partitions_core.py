from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer

from tests.cocotb.host import HostBusDriver
from tests.cocotb.test_partitions import graphics_descriptor


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


async def wait_for(dut: object, predicate: object, limit: int = 500) -> None:
    for _ in range(limit):
        await RisingEdge(dut.clk_2x)
        await ReadOnly()
        if predicate():
            await Timer(1, unit="ps")
            return
        await Timer(1, unit="ps")
    raise AssertionError(f"condition was not reached in {limit} 2xWCLK edges")


@cocotb.test()
async def host_programmed_partitions_follow_the_live_raster(dut: object) -> None:
    host = await initialize(dut)

    # Graphics, AW=2, HS=1, VS=1, HFP/HBP/VFP/VBP=1, AL=3.
    await host.write_command(0x0F)
    for parameter in (0x02, 0x00, 0x20, 0x00, 0x00, 0x01, 0x03, 0x04):
        await host.write_parameter(parameter)

    area0 = graphics_descriptor(0x00100, 2)
    area1 = graphics_descriptor(0x00200, 1, image=True, wide=True)
    await host.write_command(0x70)
    for parameter in (*area0, *area1):
        await host.write_parameter(parameter)

    # Establish a known raster origin without erasing SYNC or PRAM, then run.
    await host.write_command(0x00)
    await host.write_command(0x6B)

    await wait_for(dut, lambda: int(dut.raster_partition_active.value) == 1)
    assert int(dut.unused_partition_index.value) == 0
    assert int(dut.unused_partition_line_count.value) == 2
    assert int(dut.unused_partition_start_address.value) == 0x00100
    assert int(dut.raster_dad.value) == 0x00100

    await wait_for(dut, lambda: int(dut.unused_partition_line_index.value) == 1)
    assert int(dut.raster_dad.value) == 0x00102

    await wait_for(dut, lambda: int(dut.unused_partition_index.value) == 1)
    assert int(dut.unused_partition_start_address.value) == 0x00200
    assert int(dut.raster_dad.value) == 0x00200
    assert int(dut.unused_image_area.value) == 1
    assert int(dut.unused_graphics_area.value) == 1
    assert int(dut.unused_wide_access.value) == 1
