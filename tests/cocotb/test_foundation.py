from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge, Timer


async def sample_after_rising_edge(dut: object) -> None:
    await RisingEdge(dut.clk_2x)
    await ReadOnly()


async def sample_after_falling_edge(dut: object) -> None:
    await FallingEdge(dut.clk_2x)
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
async def hsync_uses_two_clocks_per_word_and_changes_on_falling_edges(
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

    while True:
        await sample_after_rising_edge(dut)
        if int(dut.word_time_ce.value):
            break
        await Timer(1, unit="ps")
    assert int(dut.hsync.value) == 0
    await sample_after_falling_edge(dut)
    assert int(dut.hsync.value) == 1

    await Timer(1, unit="ps")
    await sample_after_rising_edge(dut)
    assert int(dut.word_time_ce.value) == 0
    await sample_after_falling_edge(dut)
    assert int(dut.hsync.value) == 1

    await Timer(1, unit="ps")
    await sample_after_rising_edge(dut)
    assert int(dut.word_time_ce.value) == 1
    assert int(dut.hsync.value) == 1
    await sample_after_falling_edge(dut)
    assert int(dut.hsync.value) == 0


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


async def host_command_and_settle(dut: object, opcode: int) -> None:
    dut.host_a0.value = 1
    dut.host_db_i.value = opcode
    dut.host_wr_n.value = 0
    await Timer(120, unit="ns")
    dut.host_wr_n.value = 1
    for _ in range(8):
        await sample_after_rising_edge(dut)
        await Timer(1, unit="ps")


async def host_parameter_and_settle(dut: object, value: int) -> None:
    dut.host_a0.value = 0
    dut.host_db_i.value = value
    dut.host_wr_n.value = 0
    await Timer(120, unit="ns")
    dut.host_wr_n.value = 1
    for _ in range(8):
        await sample_after_rising_edge(dut)
        await Timer(1, unit="ps")


@cocotb.test()
async def vsync_commands_control_the_external_sync_pin_direction(dut: object) -> None:
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

    await host_command_and_settle(dut, 0x00)
    assert int(dut.v_ext_sync_oe.value) == 0
    await host_command_and_settle(dut, 0x6F)
    assert int(dut.v_ext_sync_oe.value) == 1
    await host_command_and_settle(dut, 0x6E)
    assert int(dut.v_ext_sync_oe.value) == 0


@cocotb.test()
async def master_vsync_pin_has_the_programmed_default_line_width(dut: object) -> None:
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

    await host_command_and_settle(dut, 0x00)
    await host_command_and_settle(dut, 0x6F)
    assert int(dut.v_ext_sync_oe.value) == 1

    falling_index = 0
    while not int(dut.v_ext_sync_o.value):
        await sample_after_falling_edge(dut)
        falling_index += 1
        assert falling_index < 800
        await Timer(1, unit="ps")
    high_start = falling_index

    while int(dut.v_ext_sync_o.value):
        await sample_after_falling_edge(dut)
        falling_index += 1
        assert falling_index - high_start <= 320
        await Timer(1, unit="ps")

    # Zero-valued retained integration parameters decode as VS=32 lines and
    # HFP+HS+HBP+AW=5 words, each two clocks: 32 * 5 * 2 falling edges.
    assert falling_index - high_start == 320


@cocotb.test()
async def start_exits_idle_while_bctrl_only_changes_enable(dut: object) -> None:
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

    await host_command_and_settle(dut, 0x00)
    assert int(dut.idle_q.value) == 1
    assert int(dut.sync_display_enable.value) == 0

    await host_command_and_settle(dut, 0x0D)
    assert int(dut.idle_q.value) == 1
    assert int(dut.sync_display_enable.value) == 1
    assert int(dut.blank.value) == 1

    await host_command_and_settle(dut, 0x6B)
    assert int(dut.idle_q.value) == 0
    assert int(dut.sync_display_enable.value) == 1

    await host_command_and_settle(dut, 0x0C)
    assert int(dut.idle_q.value) == 0
    assert int(dut.sync_display_enable.value) == 0
    assert int(dut.blank.value) == 1

    await host_command_and_settle(dut, 0x0D)
    assert int(dut.idle_q.value) == 0
    assert int(dut.sync_display_enable.value) == 1


@cocotb.test()
async def pitch_parameters_reach_the_retained_register(dut: object) -> None:
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

    await host_command_and_settle(dut, 0x00)
    await host_command_and_settle(dut, 0x47)
    await host_parameter_and_settle(dut, 0xA5)
    assert int(dut.unused_pitch.value) == 0xA5

    await host_command_and_settle(dut, 0x00)
    assert int(dut.unused_pitch.value) == 0xA5

    await host_command_and_settle(dut, 0x0E)
    await host_parameter_and_settle(dut, 0x02)
    await host_parameter_and_settle(dut, 0xFE)
    assert int(dut.unused_pitch.value) == 0x00
