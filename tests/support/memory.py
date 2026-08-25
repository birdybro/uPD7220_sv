from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import struct
from typing import Iterable


DISPLAY_WORD_COUNT = 1 << 18
WORD_MASK = 0xFFFF
ADDRESS_MASK = DISPLAY_WORD_COUNT - 1


class CycleType(str, Enum):
    DISPLAY = "display"
    RMW = "rmw"
    DMA_READ = "dma_read"
    DMA_WRITE = "dma_write"
    REFRESH = "refresh"
    BLANK = "blank"


class BusOwner(str, Enum):
    DISPLAY = "display"
    DRAWING = "drawing"
    HOST_READ = "host_read"
    HOST_WRITE = "host_write"
    DMA = "dma"
    REFRESH = "refresh"
    NONE = "none"


class DataDirection(str, Enum):
    HIGH_Z = "high_z"
    GDC_TO_MEMORY = "gdc_to_memory"
    MEMORY_TO_GDC = "memory_to_gdc"


@dataclass(frozen=True)
class MemoryTransaction:
    clock: int
    cycle_type: CycleType
    owner: BusOwner
    ale: int
    dbin: int
    address: int
    data_direction: DataDirection
    read_data: int | None
    write_data: int | None
    blank: int
    a16: int
    a17: int

    def __post_init__(self) -> None:
        if self.clock < 0:
            raise ValueError("clock must be non-negative")
        if not 0 <= self.address < DISPLAY_WORD_COUNT:
            raise ValueError("display-memory address exceeds 18 bits")
        for name in ("ale", "dbin", "blank", "a16", "a17"):
            if getattr(self, name) not in (0, 1):
                raise ValueError(f"{name} must be a resolved bit")
        for name in ("read_data", "write_data"):
            value = getattr(self, name)
            if value is not None and not 0 <= value <= WORD_MASK:
                raise ValueError(f"{name} exceeds 16 bits")

    def as_serializable_dict(self) -> dict[str, object]:
        return asdict(self)


class DisplayMemoryModel:
    """Independent 256Kx16 storage and lossless external bus trace."""

    def __init__(self, initial_words: Iterable[int] | None = None) -> None:
        self.words = [0] * DISPLAY_WORD_COUNT
        if initial_words is not None:
            for address, value in enumerate(initial_words):
                if address >= DISPLAY_WORD_COUNT:
                    raise ValueError("initial image is larger than display memory")
                self.words[address] = self._word(value)
        self.transactions: list[MemoryTransaction] = []

    @staticmethod
    def _address(address: int) -> int:
        if not 0 <= address < DISPLAY_WORD_COUNT:
            raise ValueError("display-memory address exceeds 18 bits")
        return address

    @staticmethod
    def _word(value: int) -> int:
        if not 0 <= value <= WORD_MASK:
            raise ValueError("display-memory word exceeds 16 bits")
        return value

    def read(self, address: int) -> int:
        return self.words[self._address(address)]

    def write(self, address: int, value: int, mask: int = WORD_MASK) -> int:
        address = self._address(address)
        value = self._word(value)
        mask = self._word(mask)
        old = self.words[address]
        new = (old & ~mask) | (value & mask)
        self.words[address] = new
        return new

    def record(self, transaction: MemoryTransaction) -> None:
        if self.transactions and transaction.clock < self.transactions[-1].clock:
            raise ValueError("memory trace clock moved backwards")
        self.transactions.append(transaction)

    def sha256(self) -> str:
        digest = hashlib.sha256()
        for word in self.words:
            digest.update(struct.pack("<H", word))
        return digest.hexdigest()

    def clear_trace(self) -> None:
        self.transactions.clear()
