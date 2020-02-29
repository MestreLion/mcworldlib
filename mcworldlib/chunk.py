# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""Chunks

Exported items:
    Chunk -- Class representing a Chunk's NBT, inherits from ntb.Root
"""

__all__ = ['Chunk']


import numpy

from . import nbt
from . import entity
from . import util as u


# TODO: create an nbt.Schema for it
class Chunk(nbt.Root):
    __slots__ = ()
    _root_name = nbt.Path("''.Level")

    BS_MIN_BITS = 4  # BlockState index minimum bits
    BS_INDEXES = u.CHUNK_SIZE[0] * u.CHUNK_SIZE[1] * u.SECTION_HEIGHT  # 16 * 16 * 16 = 4096

    @property
    def entities(self):
        return self.root['Entities']

    @classmethod
    def parse(cls, buff, *args, **kwargs):
        self = super().parse(buff, *args, **kwargs)
        self.root['Entities'] = nbt.List[entity.Entity](
            entity.Entity.subclass(_) for _ in self.root.get('Entities', ())
        )
        return self

    def get_blocks(self):
        """Yield a (Y, Palette, BlockState Indexes Array) tuple for every chunk section.

        Y: Y "level" of the section, the section "index" (NOT the NBT section index!)
        Palette, Indexes: See get_section_blocks()
        """
        blocks = {}
        for section in self.root['Sections']:
            Y = int(section['Y'])
            palette, indexes = self.get_section_blocks(Y, _section=section)
            if palette:
                blocks[Y] = palette, indexes
        for Y in sorted(blocks):
            yield (Y, *blocks[Y])

    def get_section_blocks(self, Y:int, _section=None):
        """Return a (Palette, BlockState Indexes Array) tuple for a chunk section.

        Palette: NBT List of Block States, straight from NBT data
        Indexes: 16 x 16 x 16 numpy.ndarray, in YZX order, of indexes matching Palette's
        """
        section = _section
        if not section:
            for section in self.root.get('Sections', []):
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
        PACK_BITS = data.itemsize * 8  # 64 bits for each Long Array element
        def bits_per_index(data, palette):
            """the size required to represent the largest index (minimum of 4 bits)"""
            def bits_from_data(data): return len(data) * PACK_BITS // self.BS_INDEXES
            if not palette:
                # Infer from data length (not the way described by Wiki!)
                return bits_from_data(data)
            bits = max(self.BS_MIN_BITS, (len(palette) - 1).bit_length())
            assert bits == bits_from_data(data), \
                f"BlockState bits mismatch: {bits} != {bits_from_data(data)}"
            return bits
        bits = bits_per_index(data, palette)
        # Adapted from Amulet-Core's decode_long_array()
        # https://github.com/Amulet-Team/Amulet-Core/blob/develop/amulet/utils/world_utils.py
        indexes = numpy.packbits(
            numpy.pad(
                numpy.unpackbits(
                        data[::-1].astype(f">i{PACK_BITS//8}").view(f"uint{PACK_BITS//8}")
                    ).reshape(-1, bits),
                [(0, 0), (PACK_BITS - bits, 0)],
                "constant",
            )
        ).view(dtype=">q")[::-1]
        return indexes

    def _encode_blockstates(self, data: numpy.ndarray, palette) -> numpy.ndarray:
        """WIP

        Encode an long array (from BlockStates or Heightmaps)
        :param array: A numpy array of the data to be encoded.
        :return: Encoded array as numpy array
        """
        array = data.astype(">q")
        bits_per_entry = max(int(numpy.amax(array)).bit_length(), 2)
        return numpy.packbits(
            numpy.unpackbits(numpy.ascontiguousarray(array[::-1]).view("uint8")).reshape(
                -1, 64
            )[:, -bits_per_entry:]
        ).view(dtype=">q")[::-1]
