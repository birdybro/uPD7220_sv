from __future__ import annotations

import hashlib

import pytest

from tests.support.memory import (
    BusOwner,
    CycleType,
    DataDirection,
    DisplayMemoryModel,
    MemoryTransaction,
)
from tests.support.seed import SeedContext


def test_memory_masking_and_hash_are_deterministic() -> None:
    memory = DisplayMemoryModel([0xAAAA])
    assert memory.write(0, 0x0F0F, mask=0x00FF) == 0xAA0F

    expected_image = b"\x0f\xaa" + b"\x00\x00" * ((1 << 18) - 1)
    assert memory.sha256() == hashlib.sha256(expected_image).hexdigest()


def test_memory_trace_records_complete_transaction() -> None:
    memory = DisplayMemoryModel()
    transaction = MemoryTransaction(
        clock=12,
        cycle_type=CycleType.RMW,
        owner=BusOwner.DRAWING,
        ale=0,
        dbin=1,
        address=0x23456,
        data_direction=DataDirection.GDC_TO_MEMORY,
        read_data=0x1234,
        write_data=0x5678,
        blank=1,
        a16=0,
        a17=1,
    )
    memory.record(transaction)
    assert memory.transactions == [transaction]
    assert transaction.as_serializable_dict()["address"] == 0x23456


def test_memory_trace_rejects_time_reversal() -> None:
    memory = DisplayMemoryModel()
    common = {
        "cycle_type": CycleType.DISPLAY,
        "owner": BusOwner.DISPLAY,
        "ale": 1,
        "dbin": 1,
        "address": 0,
        "data_direction": DataDirection.HIGH_Z,
        "read_data": None,
        "write_data": None,
        "blank": 0,
        "a16": 0,
        "a17": 0,
    }
    memory.record(MemoryTransaction(clock=2, **common))
    with pytest.raises(ValueError, match="backwards"):
        memory.record(MemoryTransaction(clock=1, **common))


def test_seed_context_reports_reproduction_state() -> None:
    context = SeedContext.parse("0x7220")
    context.record_command(0x46, [0x01, 0x02])
    report = context.failure_report(cycle=19, expected=3, observed=4, memory_hash="abc")

    assert context.seed == 0x7220
    assert context.random.randrange(1 << 32) == 798259021
    assert '"opcode": "0x46"' in report
    assert '"cycle": 19' in report
    assert f"GDC_SEED={0x7220}" in report
