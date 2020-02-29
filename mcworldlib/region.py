# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""Region files and its chunks.

Exported items:
    RegionChunk -- Chunk in a Region, inherits from chunk.Chunk
    RegionFile  -- Collection of RegionChunks in an Region file, inherits from MutableMapping
"""

__all__ = ['RegionFile']  # Not worth exporting RegionChunk yet


import collections.abc
import gzip
import io
import os.path
import re
import struct
import zlib

import numpy

from . import chunk
from . import util as u


# https://minecraft.gamepedia.com/Region_file_format
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


class RegionError(u.MCError): pass
class ChunkError(u.MCError): pass


class Regions(collections.abc.MutableMapping):
    """Collection of RegionFiles with lazy loading on access"""
    __slots__ = (
        '_regions',
    )
    def __init__(self, **regions):
        self._regions = regions

    def __getitem__(self, key):
        region = self._regions[key]
        if isinstance(region, RegionFile):
            return region
        self._regions[key] = RegionFile.load(region)
        return self._regions[key]

    # ABC boilerplate
    def __iter__(self): return iter(self._regions)  # for key in self._regions: yield key
    def __len__(self): return len(self._regions)
    def __setitem__(self, key, value): self._regions[key] = value
    def __delitem__(self, key): del self._regions[key]
    def __contains__(self, key): return key in self._regions  # optional

    def __str__(self):
        return str(self._regions)

    def __repr__(self):
        return f'<{self.__class__.__name__}({len(self)} regions)>'


class RegionFile(collections.abc.MutableMapping):
    """Collection of Chunks in Region file in Anvil (.mca) file format.

    Attributes:
        filename -- The name of the file
        pos      -- Position (rx, rz) coordinates of Region in World
    """
    __slots__ = (
        '_chunks',
        'filename',
        'pos',
    )
    _re_filename = re.compile(r"r\.(?P<rx>-?\d+)\.(?P<rz>-?\d+)\.mca")

    def __init__(self, **chunks):
        self._chunks:   dict   = chunks
        self.filename:  str    = None
        self.pos:       tuple  = ()

    @property
    def chunks(self):
        """Convenience to handle chunks as sequence instead of mapping"""
        return self.values()
    @chunks.setter
    def chunks(self, chunks):
        self._chunks = {chunk.pos: chunk for chunk in chunks}

    @classmethod
    def load(cls, filename):
        """Load region file from a path."""
        return cls.parse(open(filename, 'rb'))

    @classmethod
    def parse(cls, buff):
        """Parse region from file-like object, build an instance and return it

        https://minecraft.gamepedia.com/Region_file_format
        """
        self = cls()

        self.filename = getattr(buff, 'name', None)
        self.pos = self.pos_from_filename(self.filename)

        count = self._max_chunks()
        header = struct.Struct(CHUNK_HEADER_FMT)  # pre-compile here, outside chunk loop
        locations  = numpy.fromfile(buff, dtype=f'>u{CHUNK_LOCATION_BYTES}',  count=count)
        timestamps = numpy.fromfile(buff, dtype=f'>u{CHUNK_TIMESTAMP_BYTES}', count=count)
        for index, (location, timestamp) in enumerate(zip(locations, timestamps)):
            if location == 0:
                continue

            pos = self._position_from_index(index)  # (x, z)
            offset, sector_count = self._unpack_location(location)

            buff.seek(offset)
            chunk = RegionChunk.parse(buff, header=header)

            # TODO: Replace asserts with proper Exceptions and/or logging

            # ~2001-09-09 GMT
            assert timestamp  > 1000000000, \
                f'Invalid timestamp for chunk {pos}: {timestamp} ({u.isodate(timestamp)})'

            # Sometimes Minecraft saves sector_count + 1 when chunk length
            # (including header) is an exact multiple of SECTOR_BYTES
            assert chunk.sector_count <= sector_count <= chunk.sector_count + 1, \
                f'Length mismatch for region {self.pos} in chunk {pos}:' \
                f' region header declares {sector_count} {SECTOR_BYTES}-byte sectors,' \
                f' but chunk data required {chunk.sector_count}.'

            chunk.region = self
            chunk.pos = pos
            chunk.offset = offset
            chunk.timestamp = timestamp

            self[pos] = chunk

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
        if not self:  # no chunks
            return 0

        #TODO: be smart and do not overwrite the whole file
        #      Use chunk.dirty and a good (re-)allocation algorithm
        count = self._max_chunks()
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

        # Pad the last chunk
        pad = num_sectors(length) * SECTOR_BYTES - length
        if pad:
            buff.seek(offset - pad)
            written += buff.write(b'\x00' * pad)

        buff.seek(0)
        written += buff.write( locations.tobytes())
        written += buff.write(timestamps.tobytes())
        return written

    def get_chunk(self, cx, cz):
        """Return the chunk at world chunk coordinate (cx, cz)

        For local, region coordinates simply use region[x, z]
        """
        if not self.pos:
            raise RegionError(f"Invalid region position coordinates: {self.pos!r}")
        cpos = (cx - self.pos[0] * u.CHUNK_GRID[0],
                cz - self.pos[1] * u.CHUNK_GRID[1])
        if not ((0, 0) <= cpos < u.CHUNK_GRID):
            raise RegionError(
                f"Chunk at world ({cx}, {cz}) does not belong to this region {self.pos}."
                f" Try region ({cx//u.CHUNK_GRID[0]}, {cz//u.CHUNK_GRID[0]})."
            )
        return self[cpos]

    @classmethod
    def pos_from_filename(cls, filename):
        if not filename:
            return None

        m = re.fullmatch(cls._re_filename, os.path.basename(filename))
        if not m:
            return None

        return (int(m.group('rx')), int(m.group('rz')))

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
    def _index_from_position(pos):
        """Helper to get the location array index from a (x, z) chunk position"""
        return pos[0] + u.CHUNK_GRID[0] * pos[1]

    @staticmethod
    def _position_from_index(index):
        """Helper to get the (x, z) chunk position from a location array index"""
        return tuple(reversed(divmod(index, u.CHUNK_GRID[0])))

    @staticmethod
    def _max_chunks():
        """Just a helper for DRY"""
        return u.CHUNK_GRID[0] * u.CHUNK_GRID[1]  # 1024

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

    def pretty(self, indent=4):
        s0 = '\n' + indent * ' '
        s1 = f',{s0}'
        return '{' + s0 + s1.join(f'{k}: {v}' for k, v in self.items()) + '\n}'

    def __str__(self):
        return str(self._chunks)

    def __repr__(self):
        basename = ""
        if self.filename:
            basename = f'{os.path.basename(self.filename)}: '
        return f'<{self.__class__.__name__}({basename}{len(self)} chunks)>'


class RegionChunk(chunk.Chunk):
    """Chunk in a Region.

    Being in a Region extends Chunk with several extra attributes:
    region       -- parent RegionFile which this Chunk belongs to
    pos          -- (x, z) relative position in Region, also its key in region mapping
    offset       --
    sector_count --
    timestamp    --
    compression  --
    dirty        --
    """
    __slots__ = (
        'region',
        'pos',
        'offset',
        'sector_count',
        'timestamp',
        'compression',
        'dirty',
    )
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

    def __init__(self, *args, **tags):
        super().__init__(*args, **tags)
        self.region:        RegionFile  = None
        self.pos:           tuple       = ()  # (x, z)
        self.offset:        int         = 0
        self.sector_count:  int         = 0
        self.timestamp:     int         = 0
        self.compression:   int         = COMPRESSION_NONE  # = 0
        self.dirty:         bool        = True  # For now

    @property
    def world_pos(self):
        return (int(self.root['xPos']),
                int(self.root['zPos']))

    @classmethod
    def parse(cls,
        buff,  # bytes or file-like buffer
        *args,
        header: struct.Struct = None,
        **kwargs
    ):
        # header as optional argument is just a performance improvement that allows
        # Struct format to be pre-compiled by caller, outside the loop
        if header is None:
            header = struct.Struct(CHUNK_HEADER_FMT)

        if not hasattr(buff, 'read'):  # assume bytes data
            buff = io.BytesIO(buff)

        length, compression = header.unpack(buff.read(header.size))
        length -= CHUNK_COMPRESSION_BYTES  # already read

        assert compression in COMPRESSION_TYPES, \
            f'invalid compression type for chunk, must be one of' \
            f' {COMPRESSION_TYPES}: {compression}'

        data = cls.decompress[compression](buff.read(length))
        self = super().parse(io.BytesIO(data), *args, **kwargs)

        self.sector_count = num_sectors(length + header.size)
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
            self.timestamp = u.now()
        assert size == header.size + length
        return size

    def __str__(self):
        """Just like NTBExplorer!"""
        return (f"<Chunk {list(self.pos)}"
                f" in world at {self.world_pos}"
                f" saved on {u.isodate(self.timestamp)}>")

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


# Just a convenience wrapper
load = RegionFile.load
