# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""Chunks

Exported items:
    Chunk -- Class representing a Chunk's NBT, inherits from ntb.Root
"""

__all__ = ['Chunk']

import numpy
import typing as t

from . import nbt
from . import entity
from . import util as u

T = t.TypeVar('T', bound='Chunk')


# TODO: create an nbt.Schema for it
class Chunk(nbt.Root):
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
    def entities(self):
        return self.data_root.get('Entities', None)

    @entities.setter
    def entities(self, value: nbt.List[nbt.Compound]):
        self.data_root['Entities'] = value

    def get_blocks(self):
        """Yield a (Y, Palette, BlockState Indexes Array) tuple for every chunk section.

        Y: Y "level" of the section, the section "index" (NOT the NBT section index!)
        Palette, Indexes: See get_section_blocks()
        """
        blocks = {}
        for section in self.data_root['Sections']:
            # noinspection PyPep8Naming
            Y = int(section['Y'])
            palette, indexes = self.get_section_blocks(Y, _section=section)
            if palette:
                blocks[Y] = palette, indexes
        for Y in sorted(blocks):
            yield (Y, *blocks[Y])

    # noinspection PyPep8Naming
    def get_section_blocks(self, Y: int, _section=None):
        """Return a (Palette, BlockState Indexes Array) tuple for a chunk section.

        Palette: NBT List of Block States, straight from NBT data
        Indexes: 16 x 16 x 16 numpy.ndarray, in YZX order, of indexes matching Palette's
        """
        section = _section
        if not section:
            for section in self.data_root.get('Sections', []):
                if section.get('Y') == Y:
                    break
            else:
                return None, None

        if 'Palette' not in section or 'BlockStates' not in section:
            return None, None

        palette = section['Palette']
        indexes = self._decode_blockstates(section['BlockStates'], palette)
        return palette, indexes.reshape((u.SECTION_HEIGHT, *reversed(u.CHUNK_SIZE)))

    def _decode_blockstates(self, data, palette=None):
        """Decode an NBT BlockStates LongArray to a block state indexes array"""
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

        bits = bits_per_index()
        # Adapted from Amulet-Core's decode_long_array()
        # https://github.com/Amulet-Team/Amulet-Core/blob/develop/amulet/utils/world_utils.py
        indexes = numpy.packbits(
            numpy.pad(
                numpy.unpackbits(
                        data[::-1].astype(f">i{pack_bits//8}").view(f"uint{pack_bits//8}")
                    ).reshape(-1, bits),
                [(0, 0), (pack_bits - bits, 0)],
                "constant",
            )
        ).view(dtype=">q")[::-1]
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
