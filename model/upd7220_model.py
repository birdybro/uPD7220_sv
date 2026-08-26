"""Independent, edge-steppable architectural model of the uPD7220 family.

The model describes programmer-visible state and documented transactions. It is
deliberately organized around commands and architectural effects rather than RTL
modules or state machines.
"""

from __future__ import annotations

from array import array
from collections import deque
from dataclasses import asdict, dataclass
from enum import Enum, IntEnum
import hashlib
import json
import struct
from typing import Any, Iterable


DISPLAY_WORD_COUNT = 1 << 18
DISPLAY_ADDRESS_MASK = DISPLAY_WORD_COUNT - 1
WORD_MASK = 0xFFFF
BYTE_MASK = 0xFF
FIFO_CAPACITY = 16


class ModelError(RuntimeError):
    """Base class for architectural-model errors."""


class PowerOnStateError(ModelError):
    """Raised when software observes state documented as invalid before RESET."""


class FifoOverflowError(ModelError):
    """Raised when an electrically legal host model attempts a seventeenth byte."""


class FifoUnderflowError(ModelError):
    """Raised when a FIFO consumer requests unavailable data."""


class GdcVariant(IntEnum):
    UPD7220 = 0
    INTEL_82720 = 1
    UPD7220A = 2


class FifoDirection(str, Enum):
    WRITE_TO_GDC = "write_to_gdc"
    READ_FROM_GDC = "read_from_gdc"


class CommandState(str, Enum):
    IDLE = "idle"
    PARAMETERS = "parameters"
    READ_RESPONSE = "read_response"


class CommandKind(str, Enum):
    RESET = "reset"
    SYNC = "sync"
    VSYNC = "vsync"
    CCHAR = "cchar"
    START = "start"
    BCTRL = "bctrl"
    ZOOM = "zoom"
    CURS = "curs"
    PRAM = "pram"
    PITCH = "pitch"
    WDAT = "wdat"
    MASK = "mask"
    FIGS = "figs"
    FIGD = "figd"
    GCHRD = "gchrd"
    RDAT = "rdat"
    CURD = "curd"
    LPRD = "lprd"
    DMAR = "dmar"
    DMAW = "dmaw"


@dataclass(frozen=True)
class CommandDecode:
    kind: CommandKind | None
    parameter_limit: int
    repeats_parameter_group: bool = False


@dataclass(frozen=True)
class ParserEvent:
    started: CommandKind | None = None
    started_opcode: int | None = None
    parameter: tuple[CommandKind, int, int] | None = None
    completed_opcode: int | None = None
    interrupted_opcode: int | None = None
    unknown_opcode: int | None = None
    unexpected_parameter: int | None = None


def decode_command(opcode: int) -> CommandDecode:
    """Decode the base 7220/82720 Figure 12 command map."""
    if not 0 <= opcode <= BYTE_MASK:
        raise ValueError("opcode exceeds eight bits")
    exact = {
        0x00: (CommandKind.RESET, 8),
        0x4B: (CommandKind.CCHAR, 3),
        0x6B: (CommandKind.START, 0),
        0x46: (CommandKind.ZOOM, 1),
        0x49: (CommandKind.CURS, 3),
        0x47: (CommandKind.PITCH, 1),
        0x4A: (CommandKind.MASK, 2),
        0x4C: (CommandKind.FIGS, 11),
        0x6C: (CommandKind.FIGD, 0),
        0x68: (CommandKind.GCHRD, 0),
        0xE0: (CommandKind.CURD, 0),
        0xC0: (CommandKind.LPRD, 0),
    }
    if opcode in exact:
        kind, limit = exact[opcode]
        return CommandDecode(kind, limit, kind is CommandKind.WDAT)
    if opcode in (0x0E, 0x0F):
        return CommandDecode(CommandKind.SYNC, 8)
    if opcode in (0x6E, 0x6F):
        return CommandDecode(CommandKind.VSYNC, 0)
    if opcode in (0x0C, 0x0D):
        return CommandDecode(CommandKind.BCTRL, 0)
    if 0x70 <= opcode <= 0x7F:
        return CommandDecode(CommandKind.PRAM, 16 - (opcode & 0x0F))

    transfer_type = (opcode >> 3) & 0x03
    if transfer_type == 0x01:
        return CommandDecode(None, 0)
    family = opcode & 0xE4
    if family == 0x20:
        return CommandDecode(
            CommandKind.WDAT,
            2 if transfer_type == 0 else 1,
            repeats_parameter_group=True,
        )
    if family == 0x24:
        return CommandDecode(CommandKind.DMAW, 0)
    if family == 0xA0:
        return CommandDecode(CommandKind.RDAT, 0)
    if family == 0xA4:
        return CommandDecode(CommandKind.DMAR, 0)
    return CommandDecode(None, 0)


@dataclass(frozen=True)
class FifoEntry:
    value: int
    is_command: bool

    def __post_init__(self) -> None:
        if not 0 <= self.value <= BYTE_MASK:
            raise ValueError("FIFO value exceeds eight bits")


@dataclass(frozen=True)
class EdgeInputs:
    dack: bool = False
    light_pen: bool = False
    external_vsync: bool = False


@dataclass
class SyncRegisters:
    display_mode: int | None = None
    framing_mode: int | None = None
    dynamic_refresh: bool | None = None
    retrace_only_drawing: bool | None = None
    active_words: int | None = None
    hsync_width: int | None = None
    vsync_width: int | None = None
    horizontal_front_porch: int | None = None
    horizontal_back_porch: int | None = None
    vertical_front_porch: int | None = None
    active_lines: int | None = None
    vertical_back_porch: int | None = None


@dataclass
class FigureRegisters:
    figure_type: int | None = None
    direction: int | None = None
    dc: int | None = None
    d: int | None = None
    d1: int | None = None
    d2: int | None = None
    dm: int | None = None
    graphics_drawing: bool | None = None


@dataclass
class CursorCharacteristics:
    lines_per_row: int | None = None
    enabled: bool | None = None
    top_line: int | None = None
    bottom_line: int | None = None
    blink_rate: int | None = None


class GdcModel:
    """Architectural state advanced one rising 2xWCLK edge at a time."""

    def __init__(
        self,
        variant: GdcVariant = GdcVariant.UPD7220,
        display_memory: Iterable[int] | None = None,
    ) -> None:
        self.variant = GdcVariant(variant)
        self.display_memory = array("H", [0]) * DISPLAY_WORD_COUNT
        if display_memory is not None:
            for address, value in enumerate(display_memory):
                if address >= DISPLAY_WORD_COUNT:
                    raise ValueError("display-memory image exceeds 256K words")
                self.display_memory[address] = self._word(value)

        # Programmer-visible parameters are unspecified at power-up and retained
        # by the base RESET command unless optional RESET parameters replace them.
        self.parameter_ram = bytearray(16)
        self.parameter_ram_known = False
        self.sync = SyncRegisters()
        self.figure = FigureRegisters()
        self.cursor_characteristics = CursorCharacteristics()
        self.ead: int | None = None
        self.dad: int | None = None
        self.dad_dot: int | None = None
        self.lad: int | None = None
        self.mask: int | None = None
        self.pattern: int | None = None
        self.pitch: int | None = None
        self.display_zoom: int | None = None
        self.graphics_character_zoom: int | None = None

        self.edge_count = 0
        self.word_time_count = 0
        self.word_half = 0
        self.last_inputs = EdgeInputs()
        self.has_reset = False
        self.idle = True
        self.display_enabled = False
        self.horizontal_blank = False
        self.vertical_blank = False
        self.vertical_sync = False
        self.dma_active = False
        self.drawing_active = False
        self.light_pen_detected = False
        self.vertical_blank_status_select = False
        self.command_state = CommandState.IDLE
        self.active_command_kind: CommandKind | None = None
        self.active_command_opcode: int | None = None
        self.next_parameter_index = 0
        self.active_parameter_limit = 0
        self.active_repeats_parameter_group = False
        self.fifo_direction = FifoDirection.WRITE_TO_GDC
        self._fifo: deque[FifoEntry] = deque()
        self.data_register: int | None = None
        self.read_refill_count = 0

    @staticmethod
    def _word(value: int) -> int:
        if not 0 <= value <= WORD_MASK:
            raise ValueError("display-memory word exceeds 16 bits")
        return value

    @staticmethod
    def _address(address: int) -> int:
        if not 0 <= address < DISPLAY_WORD_COUNT:
            raise ValueError("display-memory address exceeds 18 bits")
        return address

    @property
    def fifo_occupancy(self) -> int:
        return len(self._fifo)

    @property
    def fifo_entries(self) -> tuple[FifoEntry, ...]:
        return tuple(self._fifo)

    def reset_command(self) -> None:
        """Execute base opcode 00h without optional synchronization parameters."""
        self.has_reset = True
        self.idle = True
        self.display_enabled = False
        self.horizontal_blank = False
        self.vertical_blank = False
        self.vertical_sync = False
        self.dma_active = False
        self.drawing_active = False
        self.light_pen_detected = False
        self.command_state = CommandState.IDLE
        self.active_command_kind = None
        self.active_command_opcode = None
        self.next_parameter_index = 0
        self.active_parameter_limit = 0
        self.active_repeats_parameter_group = False
        self.fifo_direction = FifoDirection.WRITE_TO_GDC
        self._fifo.clear()
        self.data_register = None
        self.read_refill_count = 0

        # RESET initializes internal timing counters, but the primary data sheet
        # explicitly says it does not modify already loaded parameters.
        self.edge_count = 0
        self.word_time_count = 0
        self.word_half = 0
        self.last_inputs = EdgeInputs()

    def step_edge(self, inputs: EdgeInputs = EdgeInputs()) -> dict[str, Any]:
        """Advance one rising edge of 2xWCLK and return an immutable snapshot."""
        self.last_inputs = inputs
        self.edge_count += 1
        self.word_half ^= 1
        if self.word_half == 0:
            self.word_time_count += 1
        if self.fifo_direction is FifoDirection.READ_FROM_GDC:
            if self.data_register is None and self.read_refill_count:
                self.read_refill_count -= 1
                if self.read_refill_count == 0:
                    if not self._fifo:
                        raise ModelError("FIFO refill completed without ring data")
                    self.data_register = self._fifo.popleft().value
            elif self.data_register is None and self._fifo:
                self.read_refill_count = 4
        return self.architectural_state()

    def host_write(self, value: int, *, is_command: bool) -> None:
        """Place a tagged host byte in the CPU-to-GDC FIFO."""
        if not 0 <= value <= BYTE_MASK:
            raise ValueError("host byte exceeds eight bits")
        if is_command and value == 0x00:
            # RESET is decoded by dedicated hardware ahead of the FIFO. It
            # cannot be blocked by FIFO state and is not stored in the ring.
            self.reset_command()
            self.command_state = CommandState.PARAMETERS
            self.active_command_kind = CommandKind.RESET
            self.active_command_opcode = 0x00
            self.next_parameter_index = 0
            self.active_parameter_limit = 8
            self.active_repeats_parameter_group = False
            return
        if self.fifo_direction is FifoDirection.READ_FROM_GDC:
            if not is_command:
                raise ModelError("only a command byte can terminate FIFO read mode")
            self._fifo.clear()
            self.fifo_direction = FifoDirection.WRITE_TO_GDC
            self.command_state = CommandState.IDLE
            self.data_register = None
            self.read_refill_count = 0
        if len(self._fifo) == FIFO_CAPACITY:
            self._fifo.popleft()
        self._fifo.append(FifoEntry(value=value, is_command=is_command))

    def command_processor_read(self) -> FifoEntry:
        if self.fifo_direction is not FifoDirection.WRITE_TO_GDC or not self._fifo:
            raise FifoUnderflowError("no CPU-to-GDC FIFO byte is available")
        return self._fifo.popleft()

    def parser_step(self) -> ParserEvent:
        """Consume one CPU-to-GDC FIFO byte and advance command parsing."""
        entry = self.command_processor_read()
        if entry.is_command:
            interrupted = self.active_command_opcode
            decoded = decode_command(entry.value)
            if decoded.kind is None:
                self.command_state = CommandState.IDLE
                self.active_command_kind = None
                self.active_command_opcode = None
                self.next_parameter_index = 0
                self.active_parameter_limit = 0
                self.active_repeats_parameter_group = False
                return ParserEvent(
                    interrupted_opcode=interrupted,
                    unknown_opcode=entry.value,
                )

            self.active_command_kind = decoded.kind
            self.active_command_opcode = entry.value
            self.next_parameter_index = 0
            self.active_parameter_limit = decoded.parameter_limit
            self.active_repeats_parameter_group = decoded.repeats_parameter_group
            if decoded.parameter_limit == 0:
                self.command_state = CommandState.IDLE
                self.active_command_kind = None
                self.active_command_opcode = None
                return ParserEvent(
                    started=decoded.kind,
                    started_opcode=entry.value,
                    completed_opcode=entry.value,
                    interrupted_opcode=interrupted,
                )

            self.command_state = CommandState.PARAMETERS
            return ParserEvent(
                started=decoded.kind,
                started_opcode=entry.value,
                interrupted_opcode=interrupted,
            )

        if self.command_state is not CommandState.PARAMETERS:
            return ParserEvent(unexpected_parameter=entry.value)
        if self.active_command_kind is None or self.active_command_opcode is None:
            raise ModelError("parameter state has no active command")

        kind = self.active_command_kind
        opcode = self.active_command_opcode
        index = self.next_parameter_index
        parameter = (kind, index, entry.value)
        if self.active_repeats_parameter_group:
            self.next_parameter_index = (index + 1) % self.active_parameter_limit
            return ParserEvent(parameter=parameter)

        self.next_parameter_index += 1
        if self.next_parameter_index == self.active_parameter_limit:
            self.command_state = CommandState.IDLE
            self.active_command_kind = None
            self.active_command_opcode = None
            self.next_parameter_index = 0
            return ParserEvent(parameter=parameter, completed_opcode=opcode)
        return ParserEvent(parameter=parameter)

    def begin_read_response(self) -> None:
        """Perform the FIFO turnaround caused by RDAT, CURD, or LPRD."""
        self._fifo.clear()
        self.fifo_direction = FifoDirection.READ_FROM_GDC
        self.command_state = CommandState.READ_RESPONSE
        self.data_register = None
        self.read_refill_count = 0

    def response_write(self, value: int) -> None:
        if self.fifo_direction is not FifoDirection.READ_FROM_GDC:
            raise ModelError("read response requires FIFO read direction")
        if len(self._fifo) == FIFO_CAPACITY:
            raise FifoOverflowError("host FIFO is full")
        self._fifo.append(FifoEntry(value=value, is_command=False))
        if self.data_register is None and self.read_refill_count == 0:
            self.read_refill_count = 4

    def host_read_fifo(self) -> int:
        if self.fifo_direction is not FifoDirection.READ_FROM_GDC or self.data_register is None:
            raise FifoUnderflowError("no GDC-to-CPU FIFO byte is available")
        value = self.data_register
        self.data_register = None
        if self._fifo:
            self.read_refill_count = 4
        return value

    def status(self) -> int:
        if not self.has_reset:
            raise PowerOnStateError("FIFO/status flags are not meaningful before RESET")
        sr6 = self.horizontal_blank
        if self.variant is GdcVariant.UPD7220A and self.vertical_blank_status_select:
            sr6 = self.vertical_blank
        data_ready = (
            self.fifo_direction is FifoDirection.READ_FROM_GDC
            and self.data_register is not None
        )
        return (
            (int(self.light_pen_detected) << 7)
            | (int(sr6) << 6)
            | (int(self.vertical_sync) << 5)
            | (int(self.dma_active) << 4)
            | (int(self.drawing_active) << 3)
            | (int(not self._fifo) << 2)
            | (int(len(self._fifo) == FIFO_CAPACITY) << 1)
            | int(data_ready)
        )

    def read_memory(self, address: int) -> int:
        return self.display_memory[self._address(address)]

    def write_memory(self, address: int, value: int) -> None:
        self.display_memory[self._address(address)] = self._word(value)

    def memory_sha256(self) -> str:
        digest = hashlib.sha256()
        block_words = 4096
        for start in range(0, DISPLAY_WORD_COUNT, block_words):
            block = self.display_memory[start : start + block_words]
            digest.update(struct.pack(f"<{len(block)}H", *block))
        return digest.hexdigest()

    def architectural_state(self) -> dict[str, Any]:
        return {
            "variant": self.variant.name,
            "edge_count": self.edge_count,
            "word_time_count": self.word_time_count,
            "word_half": self.word_half,
            "has_reset": self.has_reset,
            "idle": self.idle,
            "display_enabled": self.display_enabled,
            "status": self.status() if self.has_reset else None,
            "fifo_direction": self.fifo_direction.value,
            "fifo": [asdict(entry) for entry in self._fifo],
            "data_register": self.data_register,
            "read_refill_count": self.read_refill_count,
            "command_state": self.command_state.value,
            "active_command_kind": (
                self.active_command_kind.value if self.active_command_kind else None
            ),
            "active_command_opcode": self.active_command_opcode,
            "next_parameter_index": self.next_parameter_index,
            "ead": self.ead,
            "dad": self.dad,
            "dad_dot": self.dad_dot,
            "lad": self.lad,
            "mask": self.mask,
            "pattern": self.pattern,
            "pitch": self.pitch,
            "display_zoom": self.display_zoom,
            "graphics_character_zoom": self.graphics_character_zoom,
            "sync": asdict(self.sync),
            "figure": asdict(self.figure),
            "cursor_characteristics": asdict(self.cursor_characteristics),
            "parameter_ram": self.parameter_ram.hex() if self.parameter_ram_known else None,
            "memory_sha256": self.memory_sha256(),
        }

    def state_sha256(self) -> str:
        encoded = json.dumps(
            self.architectural_state(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
