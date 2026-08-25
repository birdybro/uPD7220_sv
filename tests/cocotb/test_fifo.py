from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer


async def start_and_reset(dut: object) -> None:
    cocotb.start_soon(Clock(dut.clk_2x, 200, unit="ns").start())
    dut.fifo_reset.value = 0
    dut.host_write_valid.value = 0
    dut.host_write_is_command.value = 0
    dut.host_write_data.value = 0
    dut.host_read_pop.value = 0
    dut.command_pop.value = 0
    dut.turn_to_read.value = 0
    dut.response_valid.value = 0
    dut.response_data.value = 0
    dut.integration_reset_n.value = 0
    await RisingEdge(dut.clk_2x)
    await Timer(1, unit="ps")
    dut.integration_reset_n.value = 1


async def edge(dut: object) -> None:
    await RisingEdge(dut.clk_2x)
    await ReadOnly()


async def finish_edge() -> None:
    await Timer(1, unit="ps")


async def write(dut: object, value: int, *, command: bool = False) -> None:
    dut.host_write_data.value = value
    dut.host_write_is_command.value = int(command)
    dut.host_write_valid.value = 1
    await edge(dut)
    await finish_edge()
    dut.host_write_valid.value = 0


async def command_pop(dut: object) -> tuple[int, int]:
    value = int(dut.command_data.value)
    tag = int(dut.command_is_command.value)
    dut.command_pop.value = 1
    await edge(dut)
    await finish_edge()
    dut.command_pop.value = 0
    return value, tag


async def response_push(dut: object, value: int) -> None:
    await Timer(1, unit="ps")
    while int(dut.response_ready.value) == 0:
        await edge(dut)
        await finish_edge()
    dut.response_data.value = value
    dut.response_valid.value = 1
    await edge(dut)
    await finish_edge()
    dut.response_valid.value = 0


@cocotb.test()
async def every_write_mode_occupancy_boundary_and_order(dut: object) -> None:
    await start_and_reset(dut)
    assert int(dut.fifo_empty.value) == 1
    assert int(dut.fifo_full.value) == 0
    for value in range(16):
        await write(dut, value, command=(value % 3 == 0))
        assert int(dut.occupancy.value) == value + 1
        assert int(dut.fifo_empty.value) == 0
        assert int(dut.fifo_full.value) == int(value == 15)

    for value in range(16):
        observed, tag = await command_pop(dut)
        assert observed == value
        assert tag == int(value % 3 == 0)
        assert int(dut.occupancy.value) == 15 - value
    assert int(dut.fifo_empty.value) == 1


@cocotb.test()
async def seventeenth_host_write_overwrites_oldest_byte(dut: object) -> None:
    await start_and_reset(dut)
    for value in range(16):
        await write(dut, value)
    await write(dut, 16, command=True)

    assert int(dut.occupancy.value) == 16
    assert int(dut.fifo_full.value) == 1
    for expected in range(1, 17):
        observed, tag = await command_pop(dut)
        assert observed == expected
        assert tag == int(expected == 16)


@cocotb.test()
async def host_write_has_priority_over_simultaneous_processor_pop(dut: object) -> None:
    await start_and_reset(dut)
    await write(dut, 0x11, command=True)
    dut.host_write_data.value = 0x22
    dut.host_write_is_command.value = 0
    dut.host_write_valid.value = 1
    dut.command_pop.value = 1
    await edge(dut)
    await finish_edge()
    dut.host_write_valid.value = 0
    dut.command_pop.value = 0

    assert int(dut.occupancy.value) == 2
    assert await command_pop(dut) == (0x11, 1)
    assert await command_pop(dut) == (0x22, 0)


@cocotb.test()
async def read_turnaround_and_four_clock_data_register_refill(dut: object) -> None:
    await start_and_reset(dut)
    await write(dut, 0xAA, command=True)
    dut.turn_to_read.value = 1
    await edge(dut)
    await finish_edge()
    dut.turn_to_read.value = 0
    assert int(dut.read_direction.value) == 1
    assert int(dut.occupancy.value) == 0
    assert int(dut.data_ready.value) == 0

    await response_push(dut, 0x35)
    assert int(dut.occupancy.value) == 1
    for remaining in (3, 2, 1):
        await edge(dut)
        assert int(dut.data_ready.value) == 0
        assert int(dut.occupancy.value) == 1
        await finish_edge()
        assert remaining >= 1
    await edge(dut)
    assert int(dut.data_ready.value) == 1
    assert int(dut.host_read_data.value) == 0x35
    assert int(dut.occupancy.value) == 0
    assert int(dut.fifo_empty.value) == 1


@cocotb.test()
async def read_data_register_serializes_multiple_response_bytes(dut: object) -> None:
    await start_and_reset(dut)
    dut.turn_to_read.value = 1
    await edge(dut)
    await finish_edge()
    dut.turn_to_read.value = 0
    await response_push(dut, 0x12)
    await response_push(dut, 0x34)

    for _ in range(3):
        await edge(dut)
        await finish_edge()
    await edge(dut)
    assert int(dut.data_ready.value) == 1
    assert int(dut.host_read_data.value) == 0x12
    assert int(dut.occupancy.value) == 1
    await finish_edge()

    dut.host_read_pop.value = 1
    await edge(dut)
    await finish_edge()
    dut.host_read_pop.value = 0
    assert int(dut.data_ready.value) == 0
    for _ in range(3):
        await edge(dut)
        await finish_edge()
    await edge(dut)
    assert int(dut.data_ready.value) == 1
    assert int(dut.host_read_data.value) == 0x34
    assert int(dut.occupancy.value) == 0


@cocotb.test()
async def command_aborts_even_a_full_read_fifo(dut: object) -> None:
    await start_and_reset(dut)
    dut.turn_to_read.value = 1
    await edge(dut)
    await finish_edge()
    dut.turn_to_read.value = 0
    # The host data register is separate from the 16-location ring. Load one
    # byte into that register and fill all 16 ring locations behind it.
    for value in range(17):
        await response_push(dut, value)
    assert int(dut.fifo_full.value) == 1

    await write(dut, 0x6B, command=True)
    assert int(dut.read_direction.value) == 0
    assert int(dut.occupancy.value) == 1
    assert int(dut.data_ready.value) == 0
    assert await command_pop(dut) == (0x6B, 1)
