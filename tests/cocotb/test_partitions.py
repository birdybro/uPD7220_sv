from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer


DISPLAY_MIXED = 0
DISPLAY_GRAPHICS = 1
DISPLAY_CHARACTER = 2
DISPLAY_INVALID = 3


def graphics_descriptor(
    start: int, lines: int, *, image: bool = False, wide: bool = False
) -> tuple[int, int, int, int]:
    raw_lines = lines & 0x3FF
    return (
        start & 0xFF,
        (start >> 8) & 0xFF,
        ((raw_lines & 0x0F) << 4) | ((start >> 16) & 0x03),
        (int(wide) << 7) | (int(image) << 6) | ((raw_lines >> 4) & 0x3F),
    )


def character_descriptor(
    start: int, lines: int, *, image: bool = False, wide: bool = False
) -> tuple[int, int, int, int]:
    raw_lines = lines & 0x3FF
    return (
        start & 0xFF,
        (start >> 8) & 0x1F,
        (raw_lines & 0x0F) << 4,
        (int(wide) << 7) | (int(image) << 6) | ((raw_lines >> 4) & 0x3F),
    )


def packed_parameter_ram(*descriptors: tuple[int, int, int, int]) -> int:
    data = tuple(value for descriptor in descriptors for value in descriptor)
    data += (0,) * (16 - len(data))
    return sum(value << (8 * index) for index, value in enumerate(data))


async def edge(dut: object) -> None:
    await RisingEdge(dut.clk_2x)
    await ReadOnly()


async def finish_edge() -> None:
    await Timer(1, unit="ps")


async def start_and_reset(dut: object) -> None:
    dut.integration_reset_n.value = 0
    dut.reset_command.value = 0
    dut.display_mode.value = DISPLAY_INVALID
    dut.pitch.value = 0
    dut.lines_per_character_row.value = 1
    dut.parameter_ram.value = 0
    dut.active_line.value = 0
    dut.line_start.value = 0
    dut.display_advance.value = 0
    cocotb.start_soon(Clock(dut.clk_2x, 200, unit="ns").start())
    await edge(dut)
    await finish_edge()
    dut.integration_reset_n.value = 1


async def pulse(dut: object, signal_name: str) -> None:
    getattr(dut, signal_name).value = 1
    await edge(dut)
    await finish_edge()
    getattr(dut, signal_name).value = 0


def state(dut: object) -> tuple[int, ...]:
    return (
        int(dut.partition_active.value),
        int(dut.partition_index.value),
        int(dut.partition_line_index.value),
        int(dut.partition_line_count.value),
        int(dut.character_scanline.value),
        int(dut.partition_start_address.value),
        int(dut.dad.value),
        int(dut.image_area.value),
        int(dut.graphics_area.value),
        int(dut.wide_access.value),
    )


@cocotb.test()
async def graphics_descriptors_latch_at_area_boundaries(dut: object) -> None:
    await start_and_reset(dut)
    area0 = graphics_descriptor(0x31234, 2)
    area1 = graphics_descriptor(0x00080, 3, image=True, wide=True)
    dut.display_mode.value = DISPLAY_GRAPHICS
    dut.pitch.value = 0x20
    dut.parameter_ram.value = packed_parameter_ram(area0, area1)
    dut.active_line.value = 1
    await edge(dut)
    await finish_edge()

    assert state(dut) == (1, 0, 0, 2, 0, 0x31234, 0x31234, 0, 1, 0)
    await pulse(dut, "display_advance")
    assert int(dut.dad.value) == 0x31235

    # A live rewrite cannot perturb the already fetched current descriptor,
    # but the second area observes its rewritten bytes when that area begins.
    updated_area0 = graphics_descriptor(0x22222, 1, image=True, wide=True)
    updated_area1 = graphics_descriptor(0x00100, 4, image=True, wide=True)
    dut.parameter_ram.value = packed_parameter_ram(updated_area0, updated_area1)
    assert int(dut.partition_start_address.value) == 0x31234
    assert int(dut.partition_line_count.value) == 2

    await pulse(dut, "line_start")
    assert state(dut)[:7] == (1, 0, 1, 2, 0, 0x31234, 0x31254)
    await pulse(dut, "line_start")
    assert state(dut) == (1, 1, 0, 4, 0, 0x00100, 0x00100, 1, 1, 1)

    # IM repeats an address for two display slots; WD then advances by two.
    await pulse(dut, "display_advance")
    assert int(dut.dad.value) == 0x00100
    await pulse(dut, "display_advance")
    assert int(dut.dad.value) == 0x00102


@cocotb.test()
async def character_mode_repeats_rows_and_wraps_thirteen_bits(dut: object) -> None:
    await start_and_reset(dut)
    areas = (
        character_descriptor(0x1FFE, 3, wide=True),
        character_descriptor(0x0123, 1),
        character_descriptor(0x0234, 1),
        character_descriptor(0x0345, 1),
    )
    dut.display_mode.value = DISPLAY_CHARACTER
    dut.pitch.value = 5
    dut.lines_per_character_row.value = 2
    dut.parameter_ram.value = packed_parameter_ram(*areas)
    dut.active_line.value = 1
    await edge(dut)
    await finish_edge()

    assert state(dut) == (1, 0, 0, 3, 0, 0x1FFE, 0x1FFE, 0, 0, 1)
    await pulse(dut, "display_advance")
    assert int(dut.dad.value) == 0x0000

    await pulse(dut, "line_start")
    assert int(dut.partition_line_index.value) == 1
    assert int(dut.character_scanline.value) == 1
    assert int(dut.dad.value) == 0x1FFE

    await pulse(dut, "line_start")
    assert int(dut.partition_line_index.value) == 2
    assert int(dut.character_scanline.value) == 0
    assert int(dut.dad.value) == 0x0003

    await pulse(dut, "line_start")
    assert state(dut)[1:7] == (1, 0, 1, 0, 0x0123, 0x0123)
    await pulse(dut, "line_start")
    assert int(dut.partition_index.value) == 2
    await pulse(dut, "line_start")
    assert int(dut.partition_index.value) == 3
    await pulse(dut, "line_start")
    assert int(dut.partition_index.value) == 0


@cocotb.test()
async def mixed_mode_image_bit_selects_area_type_and_sixteen_bit_wrap(dut: object) -> None:
    await start_and_reset(dut)
    area0 = graphics_descriptor(0x2FFFE, 1, wide=True)
    area1 = graphics_descriptor(0x1FFFF, 2, image=True, wide=True)
    dut.display_mode.value = DISPLAY_MIXED
    dut.pitch.value = 1
    dut.parameter_ram.value = packed_parameter_ram(area0, area1)
    dut.active_line.value = 1
    await edge(dut)
    await finish_edge()

    assert state(dut)[5:] == (0xFFFE, 0xFFFE, 0, 0, 1)
    await pulse(dut, "display_advance")
    assert int(dut.dad.value) == 0x0000

    await pulse(dut, "line_start")
    assert state(dut)[1:10] == (1, 0, 2, 0, 0xFFFF, 0xFFFF, 1, 1, 1)
    await pulse(dut, "display_advance")
    assert int(dut.dad.value) == 0xFFFF
    await pulse(dut, "display_advance")
    assert int(dut.dad.value) == 0x0001


@cocotb.test()
async def zero_length_expands_to_1024_and_reset_stops_scanning(dut: object) -> None:
    await start_and_reset(dut)
    area0 = graphics_descriptor(0x3FFFF, 0)
    area1 = graphics_descriptor(0x00000, 1)
    dut.display_mode.value = DISPLAY_GRAPHICS
    dut.parameter_ram.value = packed_parameter_ram(area0, area1)
    dut.active_line.value = 1
    await edge(dut)
    await finish_edge()

    assert int(dut.partition_line_count.value) == 1024
    await pulse(dut, "display_advance")
    assert int(dut.dad.value) == 0

    dut.reset_command.value = 1
    await edge(dut)
    await finish_edge()
    dut.reset_command.value = 0
    assert int(dut.partition_active.value) == 0
    assert int(dut.partition_index.value) == 0
    assert int(dut.dad.value) == 0

    dut.active_line.value = 0
    await edge(dut)
    await finish_edge()
    dut.display_mode.value = DISPLAY_INVALID
    dut.active_line.value = 1
    await edge(dut)
    assert int(dut.partition_active.value) == 0
