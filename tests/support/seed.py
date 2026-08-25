from __future__ import annotations

from dataclasses import dataclass, field
import json
import random
from typing import Any


@dataclass
class SeedContext:
    """Own deterministic randomness and enough context to reproduce a failure."""

    seed: int
    command_sequence: list[dict[str, Any]] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise ValueError("seed must be non-negative")
        self.random = random.Random(self.seed)

    @classmethod
    def parse(cls, text: str) -> "SeedContext":
        return cls(int(text, base=0))

    @property
    def reproduce(self) -> str:
        return f"make test-random GDC_SEED={self.seed}"

    def record_command(self, opcode: int, parameters: list[int]) -> None:
        self.command_sequence.append(
            {
                "opcode": f"0x{opcode:02x}",
                "parameters": [f"0x{value:02x}" for value in parameters],
            }
        )

    def failure_report(
        self,
        *,
        cycle: int,
        expected: Any,
        observed: Any,
        register_state: dict[str, Any] | None = None,
        memory_hash: str | None = None,
    ) -> str:
        report = {
            "seed": self.seed,
            "cycle": cycle,
            "command_sequence": self.command_sequence,
            "parameters": self.parameters,
            "register_state": register_state or {},
            "memory_hash": memory_hash,
            "expected": expected,
            "observed": observed,
            "reproduce": self.reproduce,
        }
        return json.dumps(report, indent=2, sort_keys=True, default=str)
