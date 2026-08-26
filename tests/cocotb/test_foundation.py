from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer


async def sample_after_rising_edge(dut: object) -> None:
    await RisingEdge(dut.clk_2x)
    await ReadOnly()


@cocotb.test()
async def integration_reset_establishes_safe_idle_outputs(dut: object) -> None:
    cocotb.start_soon(Clock(dut.clk_2x, 200, unit="ns").start())
    dut.host_rd_n.value = 1
    dut.host_wr_n.value = 1
    dut.host_a0.value = 0
    dut.host_db_i.value = 0
    dut.v_ext_sync_i.value = 0
    dut.dack_n.value = 1
    dut.mem_ad_i.value = 0
    dut.lpen.value = 0
    dut.integration_reset_n.value = 0

    await sample_after_rising_edge(dut)
    assert int(dut.host_db_oe.value) == 0
    assert int(dut.mem_ad_oe.value) == 0
    assert int(dut.v_ext_sync_oe.value) == 0
    assert int(dut.mem_dbin_n.value) == 1
    assert int(dut.mem_ale.value) == 1
    assert int(dut.blank.value) == 1
    assert int(dut.hsync.value) == 0
    assert int(dut.drq.value) == 0
    assert int(dut.word_time_ce.value) == 0


@cocotb.test()
async def word_time_enable_pulses_every_second_clock_edge(dut: object) -> None:
    cocotb.start_soon(Clock(dut.clk_2x, 200, unit="ns").start())
    dut.host_rd_n.value = 1
    dut.host_wr_n.value = 1
    dut.host_a0.value = 0
    dut.host_db_i.value = 0
    dut.v_ext_sync_i.value = 0
    dut.dack_n.value = 1
    dut.mem_ad_i.value = 0
    dut.lpen.value = 0
    dut.integration_reset_n.value = 0
    await sample_after_rising_edge(dut)
    await Timer(1, unit="ps")
    dut.integration_reset_n.value = 1

    observed = []
    for _ in range(6):
        await sample_after_rising_edge(dut)
        observed.append(int(dut.word_time_ce.value))
        await Timer(1, unit="ps")

    assert observed == [0, 1, 0, 1, 0, 1]

    dut.integration_reset_n.value = 0
    await Timer(1, unit="ns")
    assert int(dut.word_time_ce.value) == 0


@cocotb.test()
async def reset_write_initializes_status_and_idle_pins_on_the_documented_path(
    dut: object,
) -> None:
    cocotb.start_soon(Clock(dut.clk_2x, 200, unit="ns").start())
    dut.host_rd_n.value = 1
    dut.host_wr_n.value = 1
    dut.host_a0.value = 0
    dut.host_db_i.value = 0
    dut.v_ext_sync_i.value = 0
    dut.dack_n.value = 1
    dut.mem_ad_i.value = 0
    dut.lpen.value = 0
    dut.integration_reset_n.value = 0
    await sample_after_rising_edge(dut)
    await Timer(1, unit="ps")
    dut.integration_reset_n.value = 1

    await Timer(25, unit="ns")
    dut.host_a0.value = 1
    dut.host_db_i.value = 0x00
    dut.host_wr_n.value = 0
    await Timer(120, unit="ns")
    dut.host_wr_n.value = 1

    await sample_after_rising_edge(dut)
    assert int(dut.reset_command.value) == 0
    await Timer(1, unit="ps")
    await sample_after_rising_edge(dut)
    assert int(dut.reset_command.value) == 1
    assert int(dut.fifo_write_valid.value) == 0
    await Timer(1, unit="ps")
    await sample_after_rising_edge(dut)
    assert int(dut.reset_command.value) == 1
    assert int(dut.device_initialized_q.value) == 1
    assert int(dut.idle_q.value) == 1
    assert int(dut.word_time_ce.value) == 0
    assert int(dut.blank.value) == 1
    assert int(dut.mem_dbin_n.value) == 1
    assert int(dut.mem_ale.value) == 1
    assert int(dut.mem_ad_oe.value) == 0
    assert int(dut.v_ext_sync_oe.value) == 0
    assert int(dut.drq.value) == 0
    await Timer(1, unit="ps")
    await sample_after_rising_edge(dut)
    assert int(dut.reset_command.value) == 0
    assert int(dut.word_time_ce.value) == 0
    await Timer(1, unit="ps")

    dut.host_a0.value = 0
    dut.host_rd_n.value = 0
    await Timer(1, unit="ns")
    assert int(dut.host_db_oe.value) == 1
    assert int(dut.host_db_o.value) == 0x04
    dut.host_rd_n.value = 1
