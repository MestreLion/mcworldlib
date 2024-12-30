# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""Chunks

Exported items:
    Chunk -- Class representing a Chunk's NBT, inherits from ntb.Root
"""

from __future__ import annotations

__all__ = [
    "Chunk",
    "ChunkSection",
]

import math

import numpy

from . import nbt
from . import entity
from . import util as u
from .util import typing as t

T = t.TypeVar('T', bound='Chunk')
SectionCoords: t.TypeAlias = tuple[int, int, int]  # (y, z, x)
Block: t.TypeAlias = nbt.Compound
BlockDict: t.TypeAlias = dict["BlockPos", Block]
BlockTuple: t.TypeAlias = tuple["BlockPos", Block]

class ChunkSectionError(u.MCError): pass


# TODO: create an nbt.Schema for it
class Chunk(nbt.Root):
    """Base class for Minecraft Chunks.

    This is a Region-less, "free" chunk, not tied to any particular World,
    but it might be sensitive to its own DataVersion.

    For the Region-(thus World-)aware chunk, use anvil.RegionChunk.
    """
    __slots__ = ()

    BS_MIN_BITS = 4  # BlockState index minimum bits
    BS_INDEXES = u.CHUNK_SIZE[0] * u.CHUNK_SIZE[1] * u.SECTION_HEIGHT  # 16 * 16 * 16 = 4096

    @classmethod
    def parse(cls: t.Type[T], *args, **kwargs) -> T:
        # noinspection PyTypeChecker
        self: T = super().parse(*args, **kwargs)
        # In Entities Lists, replace plain Compound with an Entity (subclass) instance
        for i, e in enumerate(self.entities or []):
            self.entities[i] = entity.Entity.subclass(e)
        return self

    @property
    def data_version(self) -> int | None:
        """DataVersion of the Chunk.

        If set to None it will delete any existing NBT entry.

        See <https://minecraft.wiki/w/Data_version>
        """
        if data_version := self.get("DataVersion") is None:
            return data_version
        return data_version.unpack()

    @data_version.setter
    def data_version(self, value: int | None) -> None:
        if value is None:
            self.pop("DataVersion", None)
        else:
            self["DataVersion"] = nbt.Int(value)

    @property
    def entities(self):
        return self.data_root.get('Entities', None)

    @entities.setter
    def entities(self, value: nbt.List[nbt.Compound]):
        self.data_root['Entities'] = value

    def get_sections(self) -> t.Iterator[ChunkSection]:
        """Iterator of chunk sections as ChunkSection instances."""
        return (ChunkSection(_, chunk=self) for _ in self.data_root.get("Sections", []))

    def get_section(self, Y:int) -> ChunkSection | None:
        """ChunkSection of the given Y-section, or None if not found."""
        for section in self.get_sections():
            if section.Y == Y:
                return section
        return None

    def get_blocks(self) -> t.Iterator[BlockTuple]:
        for section in self.get_sections():
            yield from section.get_blocks().items()

    def _decode_blockstates(self, data, palette=None):
        """Decode an NBT BlockStates LongArray to a block state indexes array"""

        # LongArray in nbtlib is numpy.ndarray(..., dtype=">i8"), so itemsize = 8 bytes
        pack_bits = data.itemsize * 8  # 64 bits for each Long Array element

        def bits_per_index():
            """the size required to represent the largest index (minimum of 4 bits)"""
            def bits_from_data(): return len(data) * pack_bits // self.BS_INDEXES
            if not palette:
                # Infer from data length (not the way described by Wiki!)
                return bits_from_data()
            bit_length = max(self.BS_MIN_BITS, (len(palette) - 1).bit_length())
            assert bit_length == bits_from_data(), \
                f"BlockState bits mismatch: {bit_length} != {bits_from_data()}"
            return bit_length

        LONG_BITS = 64
        bits = bits_per_index()
        padding_per_long = LONG_BITS % bits
        # Adapted from Amulet-Core's decode_long_array()
        # https://github.com/Amulet-Team/Amulet-Core/blob/1.0/amulet/utils/world_utils.py
        indexes = numpy.packbits(
            numpy.pad(
                numpy.unpackbits(
                    data[::-1].astype(f">i{pack_bits//8}").view(f"uint{pack_bits//8}").unpack()
                ).reshape(-1, LONG_BITS)[:, padding_per_long:LONG_BITS].reshape(-1, bits),
                [(0, 0), (pack_bits - bits, 0)],
                "constant",
            )
        ).view(dtype=">q")[::-1][:self.BS_INDEXES]
        return indexes

    # noinspection PyMethodMayBeStatic
    def _encode_blockstates(self, data: numpy.ndarray, _palette) -> numpy.ndarray:
        """WIP

        Encode a long array (from BlockStates or Heightmaps)
        :param data: A numpy array of the data to be encoded.
        :return: Encoded array as numpy array
        """
        array = data.astype(">q")
        bits_per_entry = max(int(numpy.amax(array)).bit_length(), 2)
        return numpy.packbits(
            numpy.unpackbits(numpy.ascontiguousarray(array[::-1]).view("uint8")).reshape(
                -1, 64
            )[:, -bits_per_entry:]
        ).view(dtype=">q")[::-1]

# WIP
class ChunkSection(nbt.Compound):
    """Collection of blocks in a chunk Y-section."""
    __slots__ = (
        "chunk",
        "_blocks",
    )

    BS_SHAPE: SectionCoords = (u.SECTION_HEIGHT, *reversed(u.CHUNK_SIZE[:2]))  # (16, 16, 16)
    NUM_BLOCKS: int = math.prod(BS_SHAPE)  # 4096

    def __init__(self, *args, chunk: Chunk | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.chunk: Chunk = chunk
        self._blocks: BlockDict = {}

    @property
    def Y(self) -> int:
        return self["Y"].unpack()

    @Y.setter
    def Y(self, value: int) -> None:
        self["Y"] = nbt.Int(value)

    def get_blocks(self) -> BlockDict:
        if not self._blocks:
            if (length := len(blocks := self._decode_blocks())) not in {self.NUM_BLOCKS, 0}:
                chunk_str = f"{self.chunk!r}, "
                raise ChunkSectionError(
                    "Section blocks mismatch in %sY=%s: %s blocks, expected %s",
                    chunk_str,
                    self.Y,
                    length,
                    self.NUM_BLOCKS
                )
            self._blocks = blocks
        return self._blocks  # palette[int(indexes[coords.as_section_block])]

    def _decode_blocks(self) -> BlockDict:
        palette = self.get("Palette", [])
        match len(palette):
            case 0: return {}
            case 1: return {
                BlockPos.from_section(coords, self.Y): Block(palette[0])
                for coords in numpy.ndindex(self.BS_SHAPE)
            }
        states = self._decode_blockstates(self["BlockStates"], len(palette))
        return {
            BlockPos.from_section(coords, self.Y): Block(palette[int(idx)])
            # Alternative: ... in zip(numpy.ndindex(self.BS_SHAPE), states)
            for coords, idx in numpy.ndenumerate(states.reshape(self.BS_SHAPE, copy=False))
        }

    # FIXME: Stub until #17 is merged and Chunk._decode_blockstates() is pasted here
    def _decode_blockstates(self, data, palette_length: int | None = None) -> numpy.ndarray:
        # https://www.reddit.com/r/AskProgramming/comments/145y28g/comment/jnq7wyg/
        dummy_palette = None if palette_length is None else range(palette_length)
        return self.chunk._decode_blockstates(data, palette=dummy_palette)


# TODO: Maybe should be in util?
class BlockPos(t.NamedTuple):
    """(x, y, z) tuple of integer coordinates, absolute or offset (relative to chunk)."""
    x: int
    y: int
    z: int

    __repr__ = u.BasePos.__repr__

    @classmethod
    def from_section(cls: t.Self, coords: SectionCoords, Y: int | None = None) -> t.Self:
        # A.K.A "from_yzx()"
        return cls(
            coords[2],
            coords[0] + (0 if Y is None else Y) * u.SECTION_HEIGHT,
            coords[1],
        )

    def to_world(self, chunk_world_pos: u.ChunkPos = (0, 0)) -> t.Self:
        offset = tuple(math.prod(_) for _ in zip(u.CHUNK_SIZE, chunk_world_pos))
        return self.__class__(self.x + offset[0], self.y, self.z + offset[1])
