from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer


async def start_and_reset(dut: object) -> None:
    cocotb.start_soon(Clock(dut.clk_2x, 200, unit="ns").start())
    dut.host_rd_n.value = 1
    dut.host_wr_n.value = 1
    dut.host_a0.value = 0
    dut.host_db_i.value = 0
    dut.status_i.value = 0
    dut.fifo_read_data_i.value = 0
    dut.integration_reset_n.value = 0
    await RisingEdge(dut.clk_2x)
    await Timer(1, unit="ps")
    dut.integration_reset_n.value = 1


async def clock_sample(dut: object) -> tuple[int, int]:
    await RisingEdge(dut.clk_2x)
    await ReadOnly()
    result = (int(dut.fifo_write_valid.value), int(dut.fifo_read_pop.value))
    await Timer(1, unit="ps")
    return result


async def host_write(
    dut: object, *, command: bool, value: int, change_a0_during_strobe: bool = False
) -> None:
    dut.host_a0.value = int(command)
    dut.host_db_i.value = value
    dut.host_wr_n.value = 0
    await Timer(60, unit="ns")
    if change_a0_during_strobe:
        dut.host_a0.value = int(not command)
    await Timer(60, unit="ns")
    dut.host_wr_n.value = 1


async def host_read_start(dut: object, *, fifo: bool) -> None:
    dut.host_a0.value = int(fifo)
    dut.host_rd_n.value = 0
    await Timer(1, unit="ns")


@cocotb.test()
async def a0_selects_status_or_fifo_and_read_data_is_held(dut: object) -> None:
    await start_and_reset(dut)
    dut.status_i.value = 0xA6
    dut.fifo_read_data_i.value = 0x5B

    await host_read_start(dut, fifo=False)
    assert int(dut.host_db_oe.value) == 1
    assert int(dut.host_db_o.value) == 0xA6
    dut.status_i.value = 0x11
    dut.host_a0.value = 1
    await Timer(10, unit="ns")
    assert int(dut.host_db_o.value) == 0xA6
    dut.host_rd_n.value = 1
    await Timer(10, unit="ns")
    assert int(dut.host_db_oe.value) == 0

    # The A0 change after RD's leading edge must not turn a status read into a
    # FIFO pop at the trailing edge.
    assert await clock_sample(dut) == (0, 0)
    assert await clock_sample(dut) == (0, 0)
    assert await clock_sample(dut) == (0, 0)

    await host_read_start(dut, fifo=True)
    assert int(dut.host_db_o.value) == 0x5B
    dut.fifo_read_data_i.value = 0xC3
    dut.host_a0.value = 0
    await Timer(10, unit="ns")
    assert int(dut.host_db_o.value) == 0x5B
    dut.host_rd_n.value = 1


@cocotb.test()
async def command_and_parameter_writes_cross_after_two_clock_edges(dut: object) -> None:
    await start_and_reset(dut)
    await Timer(25, unit="ns")
    await host_write(dut, command=True, value=0x6B, change_a0_during_strobe=True)

    assert await clock_sample(dut) == (0, 0)
    assert await clock_sample(dut) == (1, 0)
    assert int(dut.fifo_write_is_command.value) == 1
    assert int(dut.fifo_write_data.value) == 0x6B
    assert await clock_sample(dut) == (0, 0)

    # Respect the specified recovery interval before the next host access.
    for _ in range(4):
        await clock_sample(dut)
    await host_write(dut, command=False, value=0x34, change_a0_during_strobe=True)
    assert await clock_sample(dut) == (0, 0)
    assert await clock_sample(dut) == (1, 0)
    assert int(dut.fifo_write_is_command.value) == 0
    assert int(dut.fifo_write_data.value) == 0x34


@cocotb.test()
async def only_fifo_reads_generate_pop_events(dut: object) -> None:
    await start_and_reset(dut)
    dut.status_i.value = 0x04
    dut.fifo_read_data_i.value = 0x77

    await host_read_start(dut, fifo=False)
    dut.host_rd_n.value = 1
    assert await clock_sample(dut) == (0, 0)
    assert await clock_sample(dut) == (0, 0)
    assert await clock_sample(dut) == (0, 0)

    for _ in range(4):
        await clock_sample(dut)
    await host_read_start(dut, fifo=True)
    dut.host_rd_n.value = 1
    assert await clock_sample(dut) == (0, 0)
    assert await clock_sample(dut) == (0, 1)
    assert await clock_sample(dut) == (0, 0)


@cocotb.test()
async def reset_opcode_uses_the_dedicated_pre_fifo_path(dut: object) -> None:
    await start_and_reset(dut)
    await Timer(25, unit="ns")
    await host_write(dut, command=True, value=0x00)

    assert await clock_sample(dut) == (0, 0)
    await RisingEdge(dut.clk_2x)
    await ReadOnly()
    assert int(dut.reset_command.value) == 1
    assert int(dut.fifo_write_valid.value) == 0
    await Timer(1, unit="ps")
    assert await clock_sample(dut) == (0, 0)
