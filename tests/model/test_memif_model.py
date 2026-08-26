from __future__ import annotations

import pytest

from model.upd7220_model import (
    MemoryBusCycleKind,
    MemoryBusDirection,
    MemoryBusEdge,
    memory_bus_cycle_trace,
)


def compact(sample: object) -> tuple[object, ...]:
    return (
        sample.edge,
        sample.clock_cycle,
        sample.ale,
        sample.dbin_n,
        sample.direction,
        sample.ad_value,
        sample.read_sample,
        sample.complete,
    )


def test_display_cycle_half_edge_table() -> None:
    trace = memory_bus_cycle_trace(
        MemoryBusCycleKind.DISPLAY, 0x31234, read_data=0xBEEF
    )
    assert tuple(map(compact, trace)) == (
        (MemoryBusEdge.RISING, 1, True, True,
         MemoryBusDirection.GDC_ADDRESS, 0x1234, False, False),
        (MemoryBusEdge.FALLING, 1, False, True,
         MemoryBusDirection.GDC_ADDRESS, 0x1234, False, False),
        (MemoryBusEdge.RISING, 2, False, True,
         MemoryBusDirection.MEMORY_READ, 0xBEEF, False, False),
        (MemoryBusEdge.FALLING, 2, False, True,
         MemoryBusDirection.MEMORY_READ, 0xBEEF, True, False),
        (MemoryBusEdge.RISING, 3, True, True,
         MemoryBusDirection.HIGH_Z, None, False, True),
    )
    assert {(sample.a16, sample.a17) for sample in trace} == {(1, 1)}


def test_rmw_cycle_half_edge_table_and_no_contention() -> None:
    trace = memory_bus_cycle_trace(
        MemoryBusCycleKind.RMW,
        0x255AA,
        read_data=0xA55A,
        write_data=0x5AA5,
    )
    assert len(trace) == 9
    assert [sample.clock_cycle for sample in trace] == [1, 1, 2, 2, 3, 3, 4, 4, 5]
    assert [sample.dbin_n for sample in trace] == [
        True, True, True, False, False, True, True, True, True
    ]
    assert [sample for sample in trace if sample.read_sample] == [trace[5]]
    assert trace[5].edge is MemoryBusEdge.FALLING
    assert trace[5].clock_cycle == 3
    assert trace[6].direction is MemoryBusDirection.GDC_WRITE
    assert trace[6].ad_value == 0x5AA5
    assert trace[7].direction is MemoryBusDirection.GDC_WRITE
    assert all(
        sample.dbin_n
        or sample.direction is MemoryBusDirection.MEMORY_READ
        for sample in trace
    )


@pytest.mark.parametrize(
    ("address", "read_data", "write_data"),
    ((-1, 0, 0), (1 << 18, 0, 0), (0, -1, 0), (0, 0, 1 << 16)),
)
def test_trace_rejects_out_of_range_values(
    address: int, read_data: int, write_data: int
) -> None:
    with pytest.raises(ValueError):
        memory_bus_cycle_trace(
            MemoryBusCycleKind.RMW,
            address,
            read_data=read_data,
            write_data=write_data,
        )
