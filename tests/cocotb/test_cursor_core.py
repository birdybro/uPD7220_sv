from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

from tests.cocotb.host import HostBusDriver


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


async def wait_for_data_ready(host: HostBusDriver, limit: int = 32) -> None:
    for _ in range(limit):
        if await host.read_status() & 0x01:
            return
    raise AssertionError("CURD data did not become ready")


@cocotb.test()
async def host_reads_complete_curd_response_in_documented_byte_order(dut: object) -> None:
    host = await initialize(dut)
    await host.write_command(0x49)
    await host.write_parameter(0x34)
    await host.write_parameter(0x12)
    await host.write_parameter(0xA3)
    await host.write_command(0xE0)

    returned = []
    for _ in range(5):
        await wait_for_data_ready(host)
        returned.append(await host.read_fifo())

    assert returned == [0x34, 0x12, 0x03, 0x00, 0x04]
    assert await host.read_status() & 0x01 == 0


@cocotb.test()
async def new_command_aborts_unread_curd_bytes_and_restores_write_mode(dut: object) -> None:
    host = await initialize(dut)
    await host.write_command(0x49)
    await host.write_parameter(0xCD)
    await host.write_parameter(0xAB)
    await host.write_parameter(0x72)
    await host.write_command(0xE0)
    await wait_for_data_ready(host)
    assert await host.read_fifo() == 0xCD

    await host.write_command(0x47)
    await host.write_parameter(0x55)
    assert await host.read_status() & 0x01 == 0

    await host.write_command(0xE0)
    returned = []
    for _ in range(5):
        await wait_for_data_ready(host)
        returned.append(await host.read_fifo())
    assert returned == [0xCD, 0xAB, 0x02, 0x80, 0x00]
