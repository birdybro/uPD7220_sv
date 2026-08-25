from __future__ import annotations

from cocotb.triggers import RisingEdge

from tests.support.memory import (
    BusOwner,
    CycleType,
    DataDirection,
    DisplayMemoryModel,
    MemoryTransaction,
)


class DisplayMemoryBusMonitor:
    """Record every resolved edge of the split display-memory interface."""

    def __init__(self, dut: object, model: DisplayMemoryModel) -> None:
        self.dut = dut
        self.model = model
        self.clock = 0

    async def sample_edge(
        self,
        *,
        cycle_type: CycleType,
        owner: BusOwner,
        address: int,
        read_data: int | None = None,
        write_data: int | None = None,
    ) -> None:
        await RisingEdge(self.dut.clk_2x)
        self.clock += 1
        output_enable = int(self.dut.mem_ad_oe.value)
        dbin = int(self.dut.mem_dbin_n.value)
        if output_enable:
            direction = DataDirection.GDC_TO_MEMORY
        elif dbin == 0:
            direction = DataDirection.MEMORY_TO_GDC
        else:
            direction = DataDirection.HIGH_Z
        self.model.record(
            MemoryTransaction(
                clock=self.clock,
                cycle_type=cycle_type,
                owner=owner,
                ale=int(self.dut.mem_ale.value),
                dbin=dbin,
                address=address,
                data_direction=direction,
                read_data=read_data,
                write_data=write_data,
                blank=int(self.dut.blank.value),
                a16=int(self.dut.mem_a16.value),
                a17=int(self.dut.mem_a17.value),
            )
        )
