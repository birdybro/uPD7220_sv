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


class HorizontalPhase(str, Enum):
    FRONT_PORCH = "front_porch"
    SYNC = "sync"
    BACK_PORCH = "back_porch"
    ACTIVE = "active"


class VerticalPhase(str, Enum):
    FRONT_PORCH = "front_porch"
    SYNC = "sync"
    BACK_PORCH = "back_porch"
    ACTIVE = "active"


class DisplayMode(IntEnum):
    MIXED = 0
    GRAPHICS = 1
    CHARACTER = 2
    INVALID = 3


class MemoryBusCycleKind(str, Enum):
    DISPLAY = "display"
    RMW = "rmw"
    REFRESH = "refresh"


class MemoryBusEdge(str, Enum):
    RISING = "rising"
    FALLING = "falling"


class MemoryBusDirection(str, Enum):
    HIGH_Z = "high_z"
    GDC_ADDRESS = "gdc_address"
    MEMORY_READ = "memory_read"
    GDC_WRITE = "gdc_write"


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


@dataclass(frozen=True)
class DisplayPartition:
    start_address: int
    line_count: int
    image: bool
    wide: bool


@dataclass(frozen=True)
class MemoryBusTraceSample:
    edge: MemoryBusEdge
    clock_cycle: int
    ale: bool
    dbin_n: bool
    direction: MemoryBusDirection
    ad_value: int | None
    a16: int
    a17: int
    read_sample: bool = False
    complete: bool = False


def memory_bus_cycle_trace(
    kind: MemoryBusCycleKind,
    address: int,
    *,
    read_data: int,
    write_data: int = 0,
) -> tuple[MemoryBusTraceSample, ...]:
    """Return the primary-diagram half-edge trace for one memory cycle.

    This oracle is a declarative timing table rather than a stateful copy of
    the RTL. The final sample is the following rising edge, when ALE has
    returned high and the completed cycle has released AD.
    """
    selected_kind = MemoryBusCycleKind(kind)
    if not 0 <= address < DISPLAY_WORD_COUNT:
        raise ValueError("display-memory address exceeds 18 bits")
    if not 0 <= read_data <= WORD_MASK:
        raise ValueError("display-memory read data exceeds 16 bits")
    if not 0 <= write_data <= WORD_MASK:
        raise ValueError("display-memory write data exceeds 16 bits")

    last_cycle = 4 if selected_kind is MemoryBusCycleKind.RMW else 2
    samples: list[MemoryBusTraceSample] = []
    for clock_cycle in range(1, last_cycle + 1):
        for edge in (MemoryBusEdge.RISING, MemoryBusEdge.FALLING):
            if clock_cycle == 1:
                direction = MemoryBusDirection.GDC_ADDRESS
                ad_value = address & WORD_MASK
            elif selected_kind is MemoryBusCycleKind.DISPLAY and clock_cycle == 2:
                direction = MemoryBusDirection.MEMORY_READ
                ad_value = read_data
            elif selected_kind is MemoryBusCycleKind.RMW and (
                (clock_cycle == 2 and edge is MemoryBusEdge.FALLING)
                or (clock_cycle == 3 and edge is MemoryBusEdge.RISING)
            ):
                direction = MemoryBusDirection.MEMORY_READ
                ad_value = read_data
            elif selected_kind is MemoryBusCycleKind.RMW and clock_cycle == 4:
                direction = MemoryBusDirection.GDC_WRITE
                ad_value = write_data
            else:
                direction = MemoryBusDirection.HIGH_Z
                ad_value = None

            dbin_n = not (
                selected_kind is MemoryBusCycleKind.RMW
                and (
                    (clock_cycle == 2 and edge is MemoryBusEdge.FALLING)
                    or (clock_cycle == 3 and edge is MemoryBusEdge.RISING)
                )
            )
            samples.append(
                MemoryBusTraceSample(
                    edge=edge,
                    clock_cycle=clock_cycle,
                    ale=clock_cycle == 1 and edge is MemoryBusEdge.RISING,
                    dbin_n=dbin_n,
                    direction=direction,
                    ad_value=ad_value,
                    a16=(address >> 16) & 1,
                    a17=(address >> 17) & 1,
                    read_sample=(
                        edge is MemoryBusEdge.FALLING
                        and (
                            (selected_kind is MemoryBusCycleKind.DISPLAY
                             and clock_cycle == 2)
                            or (selected_kind is MemoryBusCycleKind.RMW
                                and clock_cycle == 3)
                        )
                    ),
                )
            )

    samples.append(
        MemoryBusTraceSample(
            edge=MemoryBusEdge.RISING,
            clock_cycle=last_cycle + 1,
            ale=True,
            dbin_n=True,
            direction=MemoryBusDirection.HIGH_Z,
            ad_value=None,
            a16=(address >> 16) & 1,
            a17=(address >> 17) & 1,
            complete=True,
        )
    )
    return tuple(samples)


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
        self.parameter_ram_known_mask = 0
        self.sync = SyncRegisters()
        self.sync_parameter_bytes = bytearray(8)
        self.sync_parameter_known_mask = 0
        self.sync_master: bool | None = None
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
        self.falling_edge_count = 0
        self.word_time_count = 0
        self.word_half = 0
        self.word_time_ce = False
        self.last_inputs = EdgeInputs()
        self.has_reset = False
        self.idle = True
        self.display_enabled = False
        self.horizontal_blank = False
        self.horizontal_sync = False
        self.blank = True
        self.horizontal_word_position = 0
        self.horizontal_phase: HorizontalPhase | None = None
        self.vertical_line_position = 0
        self.vertical_phase: VerticalPhase | None = None
        self._timing_display_enabled = False
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
        self.display_partition_active = False
        self.display_partition_index = 0
        self.display_partition_count = 0
        self.display_partition_line_index = 0
        self.display_partition_line_count = 1
        self.display_character_scanline = 0
        self.display_partition_start_address = 0
        self.display_line_base = 0
        self.display_partition_image = False
        self.display_partition_graphics = False
        self.display_partition_wide = False
        self.display_repeat = False
        self.display_address_mode: DisplayMode | None = None
        self.refresh_counter = 0

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
        self.horizontal_sync = False
        self.blank = True
        self.horizontal_word_position = 0
        self.horizontal_phase = None
        self.vertical_line_position = 0
        self.vertical_phase = None
        self._timing_display_enabled = False
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
        self.display_partition_active = False
        self.display_partition_index = 0
        self.display_partition_count = 0
        self.display_partition_line_index = 0
        self.display_partition_line_count = 1
        self.display_character_scanline = 0
        self.display_partition_start_address = 0
        self.display_line_base = 0
        self.dad = 0
        self.display_partition_image = False
        self.display_partition_graphics = False
        self.display_partition_wide = False
        self.display_repeat = False
        self.display_address_mode = None
        self.refresh_counter = 0

        # RESET initializes internal timing counters, but the primary data sheet
        # explicitly says it does not modify already loaded parameters.
        self.edge_count = 0
        self.falling_edge_count = 0
        self.word_time_count = 0
        self.word_half = 0
        self.word_time_ce = False
        self.last_inputs = EdgeInputs()

    def step_edge(self, inputs: EdgeInputs = EdgeInputs()) -> dict[str, Any]:
        """Advance one rising edge of 2xWCLK and return an immutable snapshot."""
        self.last_inputs = inputs
        self.edge_count += 1
        previous_half = self.word_half
        self.word_half ^= 1
        self.word_time_ce = bool(previous_half)
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

    def step_falling_edge(self) -> dict[str, Any]:
        """Advance the falling 2xWCLK edge that follows the last rising edge.

        The vendor TCO timing is referenced to this edge for HSYNC and BLANK.
        Horizontal timing uses one absolute word position rather than mirroring
        the RTL's interval-state implementation.
        """
        self.falling_edge_count += 1
        self._timing_display_enabled = self.display_enabled and not self.idle
        horizontal_counts = self._horizontal_counts()
        line_advance = False
        if horizontal_counts is not None:
            total_words = sum(horizontal_counts)
            line_advance = self.word_time_ce and (
                self.horizontal_word_position == total_words - 1
            )
            if self.word_time_ce:
                self.horizontal_word_position = (
                    self.horizontal_word_position + 1
                ) % total_words
            self._update_horizontal_outputs(horizontal_counts)
        else:
            self.horizontal_phase = None
            self.horizontal_sync = False
            self.horizontal_blank = False

        vertical_counts = self._vertical_counts()
        if vertical_counts is not None:
            if line_advance:
                self.vertical_line_position = (
                    self.vertical_line_position + 1
                ) % sum(vertical_counts)
            self._update_vertical_outputs(vertical_counts)
        else:
            self.vertical_phase = None
            self.vertical_sync = False
            self.vertical_blank = False

        self.blank = (
            self.horizontal_blank
            or self.vertical_blank
            or not self._timing_display_enabled
        )
        return self.architectural_state()

    def _horizontal_counts(self) -> tuple[int, int, int, int] | None:
        hfp = self.sync.horizontal_front_porch
        sync = self.sync.hsync_width
        hbp = self.sync.horizontal_back_porch
        active = self.sync.active_words
        if hfp is None or sync is None or hbp is None or active is None:
            return None
        typed_counts = (hfp, sync, hbp, active)
        if any(count <= 0 for count in typed_counts):
            raise ModelError("horizontal timing intervals must be positive")
        return typed_counts

    def _update_horizontal_outputs(self, counts: tuple[int, int, int, int]) -> None:
        hfp, sync, hbp, _active = counts
        position = self.horizontal_word_position
        if position < hfp:
            self.horizontal_phase = HorizontalPhase.FRONT_PORCH
        elif position < hfp + sync:
            self.horizontal_phase = HorizontalPhase.SYNC
        elif position < hfp + sync + hbp:
            self.horizontal_phase = HorizontalPhase.BACK_PORCH
        else:
            self.horizontal_phase = HorizontalPhase.ACTIVE
        self.horizontal_sync = self.horizontal_phase is HorizontalPhase.SYNC
        self.horizontal_blank = self.horizontal_phase is not HorizontalPhase.ACTIVE

    def _vertical_counts(self) -> tuple[int, int, int, int] | None:
        vfp = self.sync.vertical_front_porch
        sync = self.sync.vsync_width
        vbp = self.sync.vertical_back_porch
        active = self.sync.active_lines
        if vfp is None or sync is None or vbp is None or active is None:
            return None
        typed_counts = (vfp, sync, vbp, active)
        if any(count <= 0 for count in typed_counts):
            raise ModelError("vertical timing intervals must be positive")
        return typed_counts

    def _update_vertical_outputs(self, counts: tuple[int, int, int, int]) -> None:
        vfp, sync, vbp, _active = counts
        position = self.vertical_line_position
        if position < vfp:
            self.vertical_phase = VerticalPhase.FRONT_PORCH
        elif position < vfp + sync:
            self.vertical_phase = VerticalPhase.SYNC
        elif position < vfp + sync + vbp:
            self.vertical_phase = VerticalPhase.BACK_PORCH
        else:
            self.vertical_phase = VerticalPhase.ACTIVE
        self.vertical_sync = self.vertical_phase is VerticalPhase.SYNC
        self.vertical_blank = self.vertical_phase is not VerticalPhase.ACTIVE

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
            if decoded.kind is CommandKind.SYNC:
                self.display_enabled = bool(entry.value & 1)
            elif decoded.kind is CommandKind.VSYNC:
                self.sync_master = bool(entry.value & 1)
            elif decoded.kind is CommandKind.START:
                self.idle = False
                self.display_enabled = True
            elif decoded.kind is CommandKind.BCTRL:
                self.display_enabled = bool(entry.value & 1)
            elif decoded.kind is CommandKind.CURD:
                if self.ead is None or self.mask is None:
                    raise PowerOnStateError("CURD requires programmed cursor state")
                response = (
                    self.ead & BYTE_MASK,
                    (self.ead >> 8) & BYTE_MASK,
                    (self.ead >> 16) & 0x03,
                    self.mask & BYTE_MASK,
                    (self.mask >> 8) & BYTE_MASK,
                )
                self.begin_read_response()
                for value in response:
                    self.response_write(value)
                return ParserEvent(
                    started=decoded.kind,
                    started_opcode=entry.value,
                    completed_opcode=entry.value,
                    interrupted_opcode=interrupted,
                )
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
        if kind in (CommandKind.RESET, CommandKind.SYNC):
            self.load_sync_parameter(index, entry.value)
        elif kind is CommandKind.PITCH and index == 0:
            self.pitch = entry.value
        elif kind is CommandKind.CURS:
            if index == 0:
                current = 0 if self.ead is None else self.ead
                self.ead = (current & 0x3FF00) | entry.value
            elif index == 1:
                current = 0 if self.ead is None else self.ead
                self.ead = (current & 0x300FF) | (entry.value << 8)
            elif index == 2:
                current = 0 if self.ead is None else self.ead
                self.ead = (current & 0x0FFFF) | ((entry.value & 0x03) << 16)
                self.dad_dot = entry.value >> 4
                self.mask = 1 << self.dad_dot
        elif kind is CommandKind.MASK:
            current = 0 if self.mask is None else self.mask
            if index == 0:
                self.mask = (current & 0xFF00) | entry.value
            elif index == 1:
                self.mask = (current & 0x00FF) | (entry.value << 8)
        elif kind is CommandKind.PRAM:
            address = (opcode & 0x0F) + index
            if not 0 <= address < 16:
                raise ModelError("PRAM parameter address exceeded RA15")
            self.parameter_ram[address] = entry.value
            self.parameter_ram_known_mask |= 1 << address
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

    def load_sync_parameter(self, index: int, value: int) -> None:
        """Load one RESET/SYNC byte and update fields whose bytes are known."""
        if not 0 <= index < 8:
            raise ValueError("SYNC parameter index must be in P1 through P8")
        if not 0 <= value <= BYTE_MASK:
            raise ValueError("SYNC parameter exceeds eight bits")
        self.sync_parameter_bytes[index] = value
        self.sync_parameter_known_mask |= 1 << index
        parameters = self.sync_parameter_bytes
        known = self.sync_parameter_known_mask

        if known & 0x01:
            p1 = parameters[0]
            self.sync.display_mode = ((p1 >> 4) & 0x02) | ((p1 >> 1) & 0x01)
            self.sync.framing_mode = ((p1 >> 2) & 0x02) | (p1 & 0x01)
            self.sync.dynamic_refresh = bool(p1 & 0x04)
            self.sync.retrace_only_drawing = bool(p1 & 0x10)
        if known & 0x02:
            self.sync.active_words = parameters[1] + 2
            self.pitch = self.sync.active_words & BYTE_MASK
        if known & 0x04:
            self.sync.hsync_width = (parameters[2] & 0x1F) + 1
        if (known & 0x0C) == 0x0C:
            raw_vsync = ((parameters[3] & 0x03) << 3) | (parameters[2] >> 5)
            self.sync.vsync_width = raw_vsync or 32
        if known & 0x08:
            self.sync.horizontal_front_porch = (parameters[3] >> 2) + 1
        if known & 0x10:
            self.sync.horizontal_back_porch = (parameters[4] & 0x3F) + 1
        if known & 0x20:
            raw_vfp = parameters[5] & 0x3F
            self.sync.vertical_front_porch = raw_vfp or 64
        if (known & 0xC0) == 0xC0:
            raw_lines = ((parameters[7] & 0x03) << 8) | parameters[6]
            self.sync.active_lines = raw_lines or 1024
        if known & 0x80:
            raw_vbp = parameters[7] >> 2
            self.sync.vertical_back_porch = raw_vbp or 64

    def _current_display_mode(self) -> DisplayMode:
        if self.sync.display_mode is None:
            raise PowerOnStateError("display mode has not been programmed")
        return DisplayMode(self.sync.display_mode)

    @staticmethod
    def _partition_count(mode: DisplayMode) -> int:
        if mode is DisplayMode.CHARACTER:
            return 4
        if mode in (DisplayMode.GRAPHICS, DisplayMode.MIXED):
            return 2
        return 0

    def decode_display_partition(
        self, index: int, mode: DisplayMode | None = None
    ) -> DisplayPartition:
        """Decode one four-byte RA descriptor without caching live PRAM.

        The display sequencer calls this only when an area begins. This keeps
        the model independent of the RTL's combinational decoder and captures
        the documented ability to rewrite a later area during the current one.
        """
        selected_mode = self._current_display_mode() if mode is None else mode
        count = self._partition_count(selected_mode)
        if not 0 <= index < count:
            raise ValueError("partition index is not present in this display mode")
        first = index * 4
        required_mask = 0x0F << first
        if self.parameter_ram_known_mask & required_mask != required_mask:
            raise PowerOnStateError("display partition contains unknown PRAM bytes")
        p0, p1, p2, p3 = self.parameter_ram[first : first + 4]
        if selected_mode is DisplayMode.CHARACTER:
            start_address = ((p1 & 0x1F) << 8) | p0
        else:
            start_address = ((p2 & 0x03) << 16) | (p1 << 8) | p0
        raw_lines = ((p3 & 0x3F) << 4) | (p2 >> 4)
        return DisplayPartition(
            start_address=start_address,
            line_count=raw_lines or 1024,
            image=bool(p3 & 0x40),
            wide=bool(p3 & 0x80),
        )

    @staticmethod
    def _normalize_display_address(address: int, mode: DisplayMode) -> int:
        masks = {
            DisplayMode.CHARACTER: 0x1FFF,
            DisplayMode.MIXED: 0xFFFF,
            DisplayMode.GRAPHICS: 0x3FFFF,
        }
        if mode not in masks:
            return 0
        return address & masks[mode]

    def _load_display_partition(self, index: int, mode: DisplayMode) -> None:
        descriptor = self.decode_display_partition(index, mode)
        address = self._normalize_display_address(descriptor.start_address, mode)
        self.display_partition_index = index
        self.display_partition_line_index = 0
        self.display_partition_line_count = descriptor.line_count
        self.display_character_scanline = 0
        self.display_partition_start_address = address
        self.display_line_base = address
        self.dad = address
        self.display_partition_image = descriptor.image
        self.display_partition_graphics = (
            mode is DisplayMode.GRAPHICS
            or (mode is DisplayMode.MIXED and descriptor.image)
        )
        self.display_partition_wide = descriptor.wide
        self.display_repeat = False
        self.display_address_mode = mode

    def start_active_display(self) -> None:
        """Fetch area zero at the transition into the active vertical interval."""
        mode = self._current_display_mode()
        self.display_partition_count = self._partition_count(mode)
        if self.display_partition_count == 0:
            self.display_partition_active = False
            return
        self._load_display_partition(0, mode)
        self.display_partition_active = True

    def start_display_line(self) -> None:
        """Advance the partition/row state at the next active line boundary."""
        if not self.display_partition_active or self.display_address_mode is None:
            return
        if (
            self.display_partition_line_index + 1
            >= self.display_partition_line_count
        ):
            index = self.display_partition_index + 1
            if index >= self.display_partition_count:
                index = 0
            mode = self._current_display_mode()
            self.display_partition_count = self._partition_count(mode)
            self._load_display_partition(index, mode)
            return

        self.display_partition_line_index += 1
        pitch = 0 if self.pitch is None else self.pitch
        mode = self.display_address_mode
        if self.display_partition_graphics:
            self.display_line_base = self._normalize_display_address(
                self.display_line_base + pitch, mode
            )
            self.dad = self.display_line_base
            self.display_character_scanline = 0
            return

        lines_per_row = self.cursor_characteristics.lines_per_row or 1
        if self.display_character_scanline + 1 >= lines_per_row:
            self.display_line_base = self._normalize_display_address(
                self.display_line_base + pitch, mode
            )
            self.dad = self.display_line_base
            self.display_character_scanline = 0
        else:
            self.dad = self.display_line_base
            self.display_character_scanline += 1

    def advance_display_slot(self) -> None:
        """Advance DAD for one display-memory access opportunity."""
        if not self.display_partition_active or self.display_address_mode is None:
            return
        if self.display_partition_image and not self.display_repeat:
            self.display_repeat = True
            return
        self.display_repeat = False
        amount = 2 if self.display_partition_wide else 1
        current_dad = 0 if self.dad is None else self.dad
        self.dad = self._normalize_display_address(
            current_dad + amount, self.display_address_mode
        )

    def accept_display_fetch(self) -> int:
        """Return the current DAD and advance it for one accepted bus cycle."""
        if not self.display_partition_active or self.dad is None:
            raise ModelError("display fetch requires an active partition")
        address = self.dad
        self.advance_display_slot()
        return address

    def execute_basic_wdat_word_replace(
        self, data: int, *, direction: int = 0
    ) -> tuple[int, int, int]:
        """Execute the initial TT=word/MOD=replace/DC=0 WDAT subset.

        The return value is ``(address, old_word, new_word)``. Graphics mode
        expands WDAT P1 bit zero across the word; character mode uses all 16
        parameter bits. Nonzero DIR and mixed-mode GD selection arrive with
        the FIGS and complete-WDAT milestones.
        """
        data = self._word(data)
        self.pattern = data
        if direction != 0:
            raise ModelError("basic WDAT supports only FIGS direction zero")
        if self.ead is None or self.mask is None or self.pitch is None:
            raise PowerOnStateError("WDAT requires EAD, MASK, and PITCH")
        mode = self._current_display_mode()
        if mode is DisplayMode.GRAPHICS:
            operation_pattern = WORD_MASK if data & 1 else 0
        elif mode is DisplayMode.CHARACTER:
            operation_pattern = data
        else:
            raise ModelError("basic WDAT does not select mixed-mode area type")

        address = self.ead
        old_word = self.read_memory(address)
        new_word = (old_word & ~self.mask) | (operation_pattern & self.mask)
        self.write_memory(address, new_word)
        self.ead = (address + self.pitch) & DISPLAY_ADDRESS_MASK
        return address, old_word, new_word

    @property
    def refresh_request(self) -> bool:
        """Whether the current raster slot must issue a refresh cycle."""
        return bool(self.sync.dynamic_refresh and self.horizontal_sync)

    def accept_refresh_cycle(self) -> int:
        """Return AD0-AD7 for one accepted HSYNC refresh and advance it."""
        if not self.refresh_request:
            raise ModelError("refresh cycle requires enabled horizontal sync")
        address = self.refresh_counter
        self.refresh_counter = (self.refresh_counter + 1) & BYTE_MASK
        return address

    def end_active_display(self) -> None:
        self.display_partition_active = False
        self.display_repeat = False

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
            "falling_edge_count": self.falling_edge_count,
            "word_time_count": self.word_time_count,
            "word_half": self.word_half,
            "word_time_ce": self.word_time_ce,
            "has_reset": self.has_reset,
            "idle": self.idle,
            "display_enabled": self.display_enabled,
            "horizontal_word_position": self.horizontal_word_position,
            "horizontal_phase": (
                self.horizontal_phase.value if self.horizontal_phase else None
            ),
            "horizontal_sync": self.horizontal_sync,
            "horizontal_blank": self.horizontal_blank,
            "vertical_line_position": self.vertical_line_position,
            "vertical_phase": (
                self.vertical_phase.value if self.vertical_phase else None
            ),
            "vertical_sync": self.vertical_sync,
            "vertical_blank": self.vertical_blank,
            "blank": self.blank,
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
            "refresh_counter": self.refresh_counter,
            "sync": asdict(self.sync),
            "sync_parameter_bytes": [
                self.sync_parameter_bytes[index]
                if self.sync_parameter_known_mask & (1 << index)
                else None
                for index in range(8)
            ],
            "sync_master": self.sync_master,
            "figure": asdict(self.figure),
            "cursor_characteristics": asdict(self.cursor_characteristics),
            "parameter_ram": [
                self.parameter_ram[index]
                if self.parameter_ram_known_mask & (1 << index)
                else None
                for index in range(16)
            ],
            "parameter_ram_known_mask": self.parameter_ram_known_mask,
            "display_partition_active": self.display_partition_active,
            "display_partition_index": self.display_partition_index,
            "display_partition_count": self.display_partition_count,
            "display_partition_line_index": self.display_partition_line_index,
            "display_partition_line_count": self.display_partition_line_count,
            "display_character_scanline": self.display_character_scanline,
            "display_partition_start_address": self.display_partition_start_address,
            "display_partition_image": self.display_partition_image,
            "display_partition_graphics": self.display_partition_graphics,
            "display_partition_wide": self.display_partition_wide,
            "memory_sha256": self.memory_sha256(),
        }

    def state_sha256(self) -> str:
        encoded = json.dumps(
            self.architectural_state(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
