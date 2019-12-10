# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""Region files and its chunks.

Exported attributes:
    load        -- Helper function to load mca/mcr files, alias to RegionFile.load()
    Chunk       -- Chunk's NBT, inherits inherits from `nbtlib.Compound`
    RegionChunk -- Chunk in a Region, inherits from `Chunk`
    RegionFile  -- Collection of RegionChunks in an Region file, inherits from `MutableMapping`
"""

__all__ = ['load', 'RegionFile']  # Not worth exporting RegionChunk yet


import collections.abc
import gzip
import io
import os.path
import struct
import time
import zlib

import numpy

from nbtlib import Compound


# https://minecraft.gamepedia.com/Region_file_format
CHUNK_GRID = (32, 32)  # (x, z) chunks in each region file = 1024 chunks per region
CHUNK_LOCATION_BYTES = 4  # Chunk offset and sector count. Must be power of 2
CHUNK_TIMESTAMP_BYTES = 4  # Unix timestamp, seconds after epoch.
CHUNK_SECTOR_COUNT_BYTES = 1  # Assumed to be the least significants from CHUNK_LOCATION_BYTES
CHUNK_COMPRESSION_BYTES = 1  # Must match last element in CHUNK_HEADER_FMT
CHUNK_HEADER_FMT = '>IB'  # Struct format. Chunk length (4 bytes) and compression type (1 byte)
SECTOR_BYTES = 4096  # Could possibly be derived from CHUNK_GRID and CHUNK_*_BYTES

# Could be an Enum, but not worth it
COMPRESSION_NONE = 0  # Not in spec
COMPRESSION_GZIP = 1  # GZip (RFC1952) (unused in practice)
COMPRESSION_ZLIB = 2  # Zlib (RFC1950)
COMPRESSION_TYPES = (
#   COMPRESSION_NONE,
    COMPRESSION_GZIP,
    COMPRESSION_ZLIB,
)


class RegionFile(collections.abc.MutableMapping):
    """Collection of Chunks in Region file in Anvil (.mca) file format.

    Attributes:
        filename -- The name of the file
    """
    def __init__(self, **chunks):
        self._chunks = chunks
        self.filename = None

    @classmethod
    def from_buffer(cls, buff):
        """Load region file from a file-like object."""
        self = cls.parse(buff)
        self.filename = getattr(buff, 'name', self.filename)
        return self

    @classmethod
    def load(cls, filename):
        """Load region file from a path."""
        with open(filename, 'rb') as buff:
            return cls.from_buffer(buff)

    @classmethod
    def parse(cls, buff):
        """Parse a buffer data in Region format, build an instance and return it
        https://minecraft.gamepedia.com/Region_file_format
        """
        self = cls()
        count = CHUNK_GRID[0] * CHUNK_GRID[1]  # 1024
        header = struct.Struct(CHUNK_HEADER_FMT)
        locations  = numpy.fromfile(buff, dtype=f'>u{CHUNK_LOCATION_BYTES}',  count=count)
        timestamps = numpy.fromfile(buff, dtype=f'>u{CHUNK_TIMESTAMP_BYTES}', count=count)
        for pos in ((x, z) for x in range(CHUNK_GRID[0]) for z in range(CHUNK_GRID[1])):
            location  = locations[ pos[0] + CHUNK_GRID[0] * pos[1]]
            timestamp = timestamps[pos[0] + CHUNK_GRID[0] * pos[1]]

            if location == 0:
                continue

            offset = location >> (8 * CHUNK_SECTOR_COUNT_BYTES)
            sector_count = location & (8 * 2**CHUNK_SECTOR_COUNT_BYTES - 1)
            buff.seek(offset * SECTOR_BYTES)
            length, compression = header.unpack(buff.read(header.size))

            # ~2001-09-09 GMT
            assert timestamp  > 1000000000, \
                f'invalid timestamp for chunk {pos}: {timestamp} ({isodate(timestamp)})'
            assert 0 < length <= CHUNK_COMPRESSION_BYTES + (sector_count * SECTOR_BYTES), \
                f'invalid timestamp for chunk {pos}: {length}'
            assert compression in COMPRESSION_TYPES, \
                f'invalid compression type for chunk {pos}, must be one of ' \
                f'{COMPRESSION_TYPES}: {compression}'

            self[pos] = RegionChunk.parse(
                buff,
                length - CHUNK_COMPRESSION_BYTES,
                region=self,
                pos=pos,
                timestamp=timestamp,
                compression=compression,
            )
        return self

    def save(self, filename=None):
        """Write the file at the specified location."""
        if filename is None:
            filename = self.filename

        if filename is None:
            raise ValueError('No filename specified')

        with open(filename, 'wb') as buff:
            self.write(buff)

    def write(self, buff):
        raise NotImplementedError  # yet

    def __str__(self):
        return str(self._chunks)

    def __repr__(self):
        basename = ""
        if self.filename:
            basename = f'{os.path.basename(self.filename)}: '
        return f'<{self.__class__.__name__}({basename}{len(self)} chunks)>'

    # ABC boilerplate
    def __getitem__(self, key): return self._chunks[key]
    def __iter__(self): return iter(self._chunks)  # for key in self._ckunks: yield key
    def __len__(self): return len(self._chunks)
    def __setitem__(self, key, value): self._chunks[key] = value
    def __delitem__(self, key): del self._chunks[key]
    def __contains__(self, key): return key in self._chunks  # optional

    # Context Manager boilerplate
    def __enter__(self): return self
    def __exit__(self, exc_type, exc_val, exc_tb): self.save()  # @UnusedVariable


# TODO: make it an nbtlib.Schema
class Chunk(Compound):
    pass


class RegionChunk(Chunk):
    """Chunk in a Region.

    Being in a Region extends Chunk with several extra attributes:
    region      -- parent RegionFile which this Chunk belongs to
    pos         -- (x, z) relative position in Region, also its key in region.chunks
    timestamp   --
    compression --
    """
    decompress = {
        COMPRESSION_NONE: lambda _:_,
        COMPRESSION_GZIP: gzip.decompress,
        COMPRESSION_ZLIB: zlib.decompress,
    }

    @classmethod
    def parse(cls,
        data,  # bytes or file-like buffer
        length: int = -1,
        *args,
        region : RegionFile = None,
        pos : tuple = (),  # (x, z) relative to region
        timestamp : int = None,  # could be time.gmtime(timestamp)
        compression : int = COMPRESSION_ZLIB,
        **kwargs
    ):
        assert (not pos or
                (len(pos) == len(CHUNK_GRID) and (0, 0) <= pos < CHUNK_GRID)), \
               f'invalid position for grid {CHUNK_GRID}: {pos}'
        if hasattr(data, 'read'):  # assume file-like
            data = data.read(length)
        data = cls.decompress[compression](data)

        self = super().parse(io.BytesIO(data), *args, **kwargs)
        self.region = region
        self.pos = pos
        self.timestamp = timestamp
        self.compression = compression

        return self


def isodate(secs:int) -> str:
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(secs))


# Just a convenience wrapper
load = RegionFile.load
