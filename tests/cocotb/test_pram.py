from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer


CMD_START = 5
CMD_PRAM = 9


async def edge(dut: object) -> None:
    await RisingEdge(dut.clk_2x)
    await ReadOnly()


async def finish_edge() -> None:
    await Timer(1, unit="ps")


async def start_and_reset(dut: object) -> None:
    dut.reset_command.value = 0
    dut.parameter_valid.value = 0
    dut.parameter_kind.value = 0
    dut.start_address.value = 0
    dut.parameter_index.value = 0
    dut.parameter_data.value = 0
    dut.integration_reset_n.value = 0
    cocotb.start_soon(Clock(dut.clk_2x, 200, unit="ns").start())
    await edge(dut)
    await finish_edge()
    dut.integration_reset_n.value = 1


async def parameter(dut: object, start: int, index: int, value: int) -> None:
    dut.parameter_valid.value = 1
    dut.parameter_kind.value = CMD_PRAM
    dut.start_address.value = start
    dut.parameter_index.value = index
    dut.parameter_data.value = value
    await edge(dut)
    await finish_edge()
    dut.parameter_valid.value = 0


def byte_at(dut: object, address: int) -> int:
    return (int(dut.parameter_ram.value) >> (address * 8)) & 0xFF


@cocotb.test()
async def sequential_load_maps_every_sa_and_parameter_index(dut: object) -> None:
    await start_and_reset(dut)
    values = [(index * 0x11) & 0xFF for index in range(16)]
    for index, value in enumerate(values):
        await parameter(dut, 0, index, value)

    assert [byte_at(dut, index) for index in range(16)] == values
    assert int(dut.programmed_mask.value) == 0xFFFF

    for start in range(16):
        await parameter(dut, start, 0, 0x80 | start)
    assert [byte_at(dut, index) for index in range(16)] == [
        0x80 | index for index in range(16)
    ]


@cocotb.test()
async def partial_and_unrelated_parameters_do_not_touch_other_bytes(dut: object) -> None:
    await start_and_reset(dut)
    for index in range(16):
        await parameter(dut, 0, index, 0xA5)

    for index, value in enumerate((0x11, 0x22, 0x33)):
        await parameter(dut, 5, index, value)

    dut.parameter_valid.value = 1
    dut.parameter_kind.value = CMD_START
    dut.start_address.value = 0
    dut.parameter_index.value = 0
    dut.parameter_data.value = 0xFF
    await edge(dut)
    await finish_edge()
    dut.parameter_valid.value = 0

    assert [byte_at(dut, index) for index in range(16)] == (
        [0xA5] * 5 + [0x11, 0x22, 0x33] + [0xA5] * 8
    )


@cocotb.test()
async def functional_reset_retains_pram_and_blocks_a_coincident_write(dut: object) -> None:
    await start_and_reset(dut)
    for index, value in enumerate((0xDE, 0xAD, 0xBE, 0xEF)):
        await parameter(dut, 8, index, value)

    dut.reset_command.value = 1
    dut.parameter_valid.value = 1
    dut.parameter_kind.value = CMD_PRAM
    dut.start_address.value = 8
    dut.parameter_index.value = 0
    dut.parameter_data.value = 0x00
    await edge(dut)
    await finish_edge()
    dut.reset_command.value = 0
    dut.parameter_valid.value = 0

    assert [byte_at(dut, index) for index in range(8, 12)] == [
        0xDE,
        0xAD,
        0xBE,
        0xEF,
    ]
    assert int(dut.programmed_mask.value) == 0x0F00
