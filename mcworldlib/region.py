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

from nbtlib import Compound, Path


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
        for index, (location, timestamp) in enumerate(zip(locations, timestamps)):
            if location == 0:
                continue

            pos = self._position_from_index(index)  # (x, z)
            offset, sector_count = self._unpack_location(location)

            buff.seek(offset)
            length, compression = header.unpack(buff.read(header.size))
            length -= CHUNK_COMPRESSION_BYTES  # already read
            sectors = num_sectors(length + header.size)

            # ~2001-09-09 GMT
            assert timestamp  > 1000000000, \
                f'invalid timestamp for chunk {pos}: {timestamp} ({isodate(timestamp)})'
            assert sector_count == sectors, \
                f'length mismatch in chunk {pos}: length={length}, but sectors={sector_count}' \
                f' (should be {sectors} for {SECTOR_BYTES}-byte sectors)'
            assert compression in COMPRESSION_TYPES, \
                f'invalid compression type for chunk {pos}, must be one of' \
                f' {COMPRESSION_TYPES}: {compression}'

            self[pos] = RegionChunk.parse(
                buff,
                length,
                region=self,
                pos=pos,
                timestamp=timestamp,
                compression=compression,
            )
        return self

    def save(self, filename=None, *args, **kwargs):
        """Write the file at the specified location."""
        if filename is None:
            filename = self.filename

        if filename is None:
            raise ValueError('No filename specified')

        with open(filename, 'wb') as buff:
            self.write(buff, *args, **kwargs)

    def write(self, buff, *args, **kwargs):
        #TODO: be smart and do not overwrite the whole file
        #      Use chunk.dirty and a good (re-)allocation algorithm
        count = CHUNK_GRID[0] * CHUNK_GRID[1]  # 1024
        locations  = numpy.zeros(count, dtype=f'>u{CHUNK_LOCATION_BYTES}')
        timestamps = numpy.zeros(count, dtype=f'>u{CHUNK_TIMESTAMP_BYTES}')

        offset = locations.nbytes + timestamps.nbytes  # initial, in bytes
        written = 0
        for pos, chunk in self.items():
            buff.seek(offset)

            length = chunk.write(buff, *args, **kwargs)
            written += length

            index = self._index_from_position(pos)
            location = self._pack_location(offset, length)
            locations[ index] = location
            timestamps[index] = chunk.timestamp

            offset += num_sectors(length) * SECTOR_BYTES

        # Pad the last chunk.
        pad = num_sectors(length) * SECTOR_BYTES - length
        if pad:
            buff.seek(offset - pad)
            written += buff.write(b'\x00' * pad)

        buff.seek(0)
        written += buff.write( locations.tobytes())
        written += buff.write(timestamps.tobytes())
        return written

    @staticmethod
    def _unpack_location(location):
        """Helper to extract chunk offset (in bytes) and sector_count from location."""
        # hackish bitwise operations needed as neither struct nor numpy handle 3-byte integers
        return ((location >> (8 *    CHUNK_SECTOR_COUNT_BYTES)) * SECTOR_BYTES,
                (location  & (8 * 2**CHUNK_SECTOR_COUNT_BYTES - 1)))

    @staticmethod
    def _pack_location(offset, length):
        """Helper to pack chunk offset (in bytes) and length to location format."""
        # more hackish bitwise operations
        return ((num_sectors(offset) << (8 *    CHUNK_SECTOR_COUNT_BYTES)) |
                (num_sectors(length)  & (8 * 2**CHUNK_SECTOR_COUNT_BYTES - 1)))

    @staticmethod
    def _chunk_positions():
        """Convenience iterator on chunk positions"""
        return ((x, z)
                for x in range(CHUNK_GRID[0])
                for z in range(CHUNK_GRID[1]))

    @staticmethod
    def _index_from_position(pos):
        """Helper to get the location array index from a (x, z) chunk position"""
        return pos[0] + CHUNK_GRID[0] * pos[1]

    @staticmethod
    def _position_from_index(index):
        """Helper to get the (x, z) chunk position from a location array index"""
        return tuple(reversed(divmod(index, CHUNK_GRID[0])))

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
    compress = {
        COMPRESSION_NONE: lambda _:_,
        COMPRESSION_GZIP: gzip.compress,
        COMPRESSION_ZLIB: zlib.compress,
    }
    decompress = {
        COMPRESSION_NONE: lambda _:_,
        COMPRESSION_GZIP: gzip.decompress,
        COMPRESSION_ZLIB: zlib.decompress,
    }

    def __init__(self, **tags):
        self.region = None
        self.pos = ()
        self.timestamp = 0
        self.compression = COMPRESSION_NONE
        super().__init__(**tags)

    @property
    def world_pos(self):
        return (int(self.get(Path("''.Level.xPos"))),
                int(self.get(Path("''.Level.zPos"))))

    @classmethod
    def parse(cls,
        data,  # bytes or file-like buffer
        length: int = -1,
        *args,
        region : RegionFile = None,
        pos : tuple = (),  # (x, z) relative to region
        timestamp : int = 0,  # default is actually now()
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
        self.timestamp = timestamp or now()
        self.compression = compression

        return self

    def write(self, buff, *args, update_timestamp=False, **kwargs) -> int:
        with io.BytesIO() as b:
            super().write(b, *args, **kwargs)
            data = self.compress[self.compression](b.getbuffer())
        length = len(data)
        header = struct.Struct(CHUNK_HEADER_FMT)
        size  = buff.write(header.pack(length + CHUNK_COMPRESSION_BYTES, self.compression))
        size += buff.write(data)
        if update_timestamp:
            self.timestamp = now()
        assert size == header.size + length
        return size

    def __str__(self):
        """Just like NTBExplorer!"""
        return (f"<Chunk {list(self.pos)}"
                f" in world at {self.world_pos}"
                f" saved on {isodate(self.timestamp)}>")

    def __repr__(self):
        return f'<{self.__class__.__name__}({self.pos}, {self.world_pos}, {self.timestamp})>'


def num_sectors(size):
    """Helper to calculate the number of sectors in size bytes"""
    # Faster than math.ceil(size / SECTOR_BYTES)
    # Not a RegionFile static method so its other static methods can call this
    sectors = (size // SECTOR_BYTES)
    if (size % SECTOR_BYTES):
        sectors += 1
    return sectors


def isodate(secs:int) -> str:
    """Return a formated date string in local time from a timestamp

    Example: isodate(1234567890) -> '2009-02-13 21:31:30'
    """
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(secs))


def now() -> int:
    """Return current time as a timestamp (seconds since epoch)

    Example: now() -> 1576027129 (if called on 2019-12-11 01:18:49 GMT)
    """
    return int(time.time())

# Just a convenience wrapper
load = RegionFile.load
