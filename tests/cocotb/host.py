from __future__ import annotations

from dataclasses import dataclass

from cocotb.triggers import RisingEdge, Timer


@dataclass(frozen=True)
class HostTiming:
    phase_ns: float = 1.0
    strobe_ns: float = 120.0
    recovery_ns: float = 800.0


class HostBusDriver:
    """Drive the split-bus core interface using asynchronous host strobes."""

    def __init__(self, dut: object, timing: HostTiming = HostTiming()) -> None:
        self.dut = dut
        self.timing = timing
        self.dut.host_rd_n.value = 1
        self.dut.host_wr_n.value = 1
        self.dut.host_a0.value = 0
        self.dut.host_db_i.value = 0

    async def align_to_clock(self, offset_ns: float | None = None) -> None:
        await RisingEdge(self.dut.clk_2x)
        await Timer(self.timing.phase_ns if offset_ns is None else offset_ns, unit="ns")

    async def write(self, *, command: bool, value: int, offset_ns: float | None = None) -> None:
        await self.align_to_clock(offset_ns)
        self.dut.host_a0.value = int(command)
        self.dut.host_db_i.value = value & 0xFF
        self.dut.host_wr_n.value = 0
        await Timer(self.timing.strobe_ns, unit="ns")
        self.dut.host_wr_n.value = 1
        await Timer(self.timing.recovery_ns, unit="ns")

    async def write_command(self, value: int, offset_ns: float | None = None) -> None:
        await self.write(command=True, value=value, offset_ns=offset_ns)

    async def write_parameter(self, value: int, offset_ns: float | None = None) -> None:
        await self.write(command=False, value=value, offset_ns=offset_ns)

    async def read(self, *, fifo: bool, offset_ns: float | None = None) -> int:
        await self.align_to_clock(offset_ns)
        self.dut.host_a0.value = int(fifo)
        self.dut.host_rd_n.value = 0
        await Timer(self.timing.strobe_ns, unit="ns")
        if int(self.dut.host_db_oe.value) != 1:
            raise AssertionError("DUT did not enable host data during RD")
        value = int(self.dut.host_db_o.value)
        self.dut.host_rd_n.value = 1
        await Timer(self.timing.recovery_ns, unit="ns")
        return value

    async def read_status(self, offset_ns: float | None = None) -> int:
        return await self.read(fifo=False, offset_ns=offset_ns)

    async def read_fifo(self, offset_ns: float | None = None) -> int:
        return await self.read(fifo=True, offset_ns=offset_ns)
