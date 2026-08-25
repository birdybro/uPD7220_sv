from __future__ import annotations

import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge


@cocotb.test()
async def verilator_clock_reset_and_combinational_smoke(dut: object) -> None:
    seed = int(os.environ.get("GDC_SEED", "0x7220"), base=0)
    rng = random.Random(seed)
    dut._log.info("deterministic seed=%d", seed)

    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start())

    dut.rst_n.value = 0
    dut.enable.value = 0
    dut.data_i.value = 0
    for _ in range(2):
        await RisingEdge(dut.clk)
    assert int(dut.edge_count.value) == 0

    dut.rst_n.value = 1
    dut.enable.value = 1
    expected_count = 0
    for _ in range(8):
        value = rng.randrange(256)
        dut.data_i.value = value
        await RisingEdge(dut.clk)
        expected_count += 1
        await cocotb.triggers.ReadOnly()
        assert int(dut.edge_count.value) == expected_count, (
            f"seed={seed} expected edge_count={expected_count} "
            f"observed={int(dut.edge_count.value)}"
        )
        assert int(dut.data_o.value) == (value ^ 0xA5)
        await cocotb.triggers.Timer(1, unit="ps")
