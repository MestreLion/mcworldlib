# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""Region MCA files in Anvil format

Exported items:
    RegionChunk -- Chunk in a Region, inherits from chunk.Chunk
    RegionFile  -- Collection of RegionChunks in an Region file, inherits from MutableMapping
"""
# Named 'anvil' just to let 'region' free for usage without 'import as'
# Wish the chunk module had a similar uncommon alternative...

__all__ = [
    'RegionFile',
    'Regions',
    'RegionChunk',
    'load_region',
]

import collections.abc
import gzip
import io
import logging
import os.path
import pathlib
import re
import struct
import typing as t
import zlib

import numpy

from . import chunk as c
from . import util as u


# Constants
# https://minecraft.gamepedia.com/Region_file_format
CHUNK_LOCATION_BYTES = 4  # Chunk offset and sector count. Must be power of 2
CHUNK_TIMESTAMP_BYTES = 4  # Unix timestamp, seconds after epoch.
CHUNK_SECTOR_COUNT_BYTES = 1  # Assumed to be the least significant from CHUNK_LOCATION_BYTES
CHUNK_COMPRESSION_BYTES = 1  # Must match last element in CHUNK_HEADER_FMT
CHUNK_HEADER_FMT = '>IB'  # Struct format. Chunk length (4 bytes) and compression type (1 byte)
SECTOR_BYTES = 4096  # Could possibly be derived from CHUNK_GRID and CHUNK_*_BYTES

# Compression used for NBT data in dat, mca (region), and mcc (external chunk) files
# Do not convert to Enum, really not worth it until Python 3.7 and its _ignore
COMPRESSION_GZIP = 1  # GZip (RFC1952) (unused in practice)
COMPRESSION_ZLIB = 2  # Zlib (RFC1950)
COMPRESSION_NONE = 3  # Uncompressed. Mentioned in the wiki, unused in practice
COMPRESSION_TYPES = (
    COMPRESSION_GZIP,
    COMPRESSION_ZLIB,
    COMPRESSION_NONE,
)

log = logging.getLogger(__name__)
T = t.TypeVar('T', bound=c.Chunk)
RT = t.TypeVar('RT', bound='AnvilFile')


class RegionError(u.MCError): pass
class ChunkError(u.MCError): pass


class AnvilFile(collections.abc.MutableMapping):
    """Collection of Chunks in Anvil (.mca) file format.

    Should be completely agnostic about Worlds and Dimensions
    and hence unaware of Pos. For that, see RegionFile subclass

    Attributes:
        filename -- The name of the file
    """
    __slots__ = (
        '_chunks',
        'filename',
    )

    MAX_CHUNKS = u.CHUNK_GRID[0] * u.CHUNK_GRID[1]  # 1024
    MAX_CHUNK_SIZE = SECTOR_BYTES * (2**(8 * CHUNK_SECTOR_COUNT_BYTES) - 1)  # ~1MiB

    def __init__(self, chunks: dict = None, *, filename: str = None):
        self._chunks:   dict   = dict(chunks or {})
        self.filename:  str    = filename or ""

    @property
    def chunks(self):
        """Convenience to handle chunks as sequence instead of mapping"""
        return self.values()

    @chunks.setter
    def chunks(self, chunks):
        self._chunks = {_.pos: _ for _ in chunks}

    @classmethod
    def load(cls: t.Type[RT], filename, **initkw) -> RT:
        """Load anvil file from a path"""
        initkw['filename'] = filename
        with open(filename, 'rb') as buff:
            return cls.parse(buff, **initkw)

    @classmethod
    def parse(cls: t.Type[RT], buff: t.BinaryIO, **initkw) -> RT:
        """Parse region from file-like object, build an instance and return it

        https://minecraft.gamepedia.com/Region_file_format
        """
        self: RT = cls(**initkw)
        if not self.filename:
            self.filename = getattr(buff, 'name', "")

        log.debug("Loading Region: %s", self.filename)
        locations  = u.numpy_fromfile(buff, dtype=f'>u{CHUNK_LOCATION_BYTES}',  count=self.MAX_CHUNKS)
        timestamps = u.numpy_fromfile(buff, dtype=f'>u{CHUNK_TIMESTAMP_BYTES}', count=self.MAX_CHUNKS)
        for index, (location, timestamp) in enumerate(zip(locations, timestamps)):
            if location == 0:
                continue

            pos = self._position_from_index(index)
            offset, sector_count = self._unpack_location(location)
            chunk_msg = ("chunk %s at offset %s in %r", pos, offset, self.filename)

            if offset > self.MAX_CHUNK_SIZE * self.MAX_CHUNKS:  # ~1GiB
                raise RegionError(f"Invalid offset for {chunk_msg[0] % chunk_msg[1:]},"
                                  f" max is {self.MAX_CHUNK_SIZE * self.MAX_CHUNKS}")

            # timestamp should be after ~2001-09-09 GMT
            if timestamp < 1000000000:
                log.warning(f"Invalid timestamp for {chunk_msg[0]}: %s (%s)",
                            *chunk_msg[1:], timestamp, u.isodate(timestamp))

            buff.seek(offset)
            try:
                chunk = RegionChunk.parse(buff, region=self, pos=pos, timestamp=timestamp)
            except ChunkError as e:
                log.error(f"Could not parse {chunk_msg[0]}: %s", *chunk_msg[1:], e)
                continue

            # Warn when sector_count does not match expected as declared in the
            # region header. Minecraft may count the compression byte twice in
            # chunk length, so when the actual length is an exact multiple of
            # SECTOR_BYTES, we might have sector_count 1 sector over the expected.
            if sector_count not in (chunk.sector_count, chunk.sector_count + 1):
                log.warning(
                    f"Length mismatch in {chunk_msg[0]}: region header declares"
                    " %s %s-byte sectors, but chunk data required %s.",
                    *chunk_msg[1:], sector_count, SECTOR_BYTES, chunk.sector_count
                )

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

        locations  = numpy.zeros(self.MAX_CHUNKS, dtype=f'>u{CHUNK_LOCATION_BYTES}')
        timestamps = numpy.zeros(self.MAX_CHUNKS, dtype=f'>u{CHUNK_TIMESTAMP_BYTES}')

        offset = locations.nbytes + timestamps.nbytes  # initial, in bytes
        written = 0
        length = 0
        for pos, chunk in self.items():
            buff.seek(offset)

            length = chunk.write(buff, *args, **kwargs)
            written += length

            index = self._index_from_position(pos)
            location = self._pack_location(offset, length)
            locations[index] = location
            timestamps[index] = chunk.timestamp

            offset += num_sectors(length) * SECTOR_BYTES

        # Pad the last chunk
        pad = num_sectors(length) * SECTOR_BYTES - length
        if pad:
            buff.seek(offset - pad)
            written += buff.write(b'\x00' * pad)

        buff.seek(0)
        written += buff.write(locations.tobytes())
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

    # Even if the following methods deal with Positions, avoid the temptation
    # to add them to PosXZ.as_/from_. Best to keep region-related formulas here

    @staticmethod
    def _index_from_position(pos: u.ChunkPos) -> int:
        """Helper to get the location array index from a (cxr, czr) chunk offset"""
        return pos.cx + u.CHUNK_GRID[0] * pos.cz

    @staticmethod
    def _position_from_index(index) -> u.ChunkPos:
        """Helper to get the (cxr, czr) chunk offset from a location array index"""
        return u.ChunkPos(*reversed(divmod(index, u.CHUNK_GRID[0])))

    # ABC boilerplate
    def __getitem__(self, key): return self._chunks[key]
    def __iter__(self): return iter(self._chunks)  # for key in self._chunks: yield key
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


class RegionFile(AnvilFile):
    """Collection of Chunks in a World Dimension.

    Being in a World extends AnvilFile with extra attributes and properties:
    regions   -- Collection this region belongs to. Derives world, dimension and category
    world     -- parent World that contains this region
    dimension -- Dimension this region is located: Overworld, Nether, End
    category  -- The subfolder in its Dimension: region, poi, entities, etc
    pos       -- (x, z) relative position in World, also its key in dimension mapping
                 Derived from filename by Regions.load_from_path()
    """
    __slots__ = (
        'regions',
        'pos',
    )
    _re_filename = re.compile(r"r\.(?P<rx>-?\d+)\.(?P<rz>-?\d+)\.mca")

    def __init__(self, *args, regions: 'Regions' = None, pos: u.TPos2D = None, **kw):
        super().__init__(*args, **kw)
        self.regions: Regions     = regions
        self.pos:     u.RegionPos = pos and u.RegionPos(*pos)

    @property
    def world(self):
        return getattr(self.regions, 'world', None)

    @property
    def dimension(self):
        return getattr(self.regions, 'dimension', None)

    @property
    def category(self):
        return getattr(self.regions, 'category', "")

    @classmethod
    def pos_from_filename(cls, filename) -> u.RegionPos:
        m = re.fullmatch(cls._re_filename, os.path.basename(filename))
        if not m:
            raise RegionError(f"Not a valid Region filename: {filename}")

        return u.RegionPos(*map(int, m.groups()))


class Regions(u.LazyLoadFileMap[u.RegionPos, RegionFile]):
    """Collection of RegionFiles"""
    # If Dimension becomes a 1st class citizen, world can be read from dimension
    collective = 'regions'

    __slots__ = (
        'world',
        'dimension',
        'path',
    )

    def __init__(self, regions: 'Regions' = None):
        super().__init__(regions)
        self.path      = ""
        self.dimension = None
        self.world     = None

    @property
    def category(self):
        """Directory basename, i.e, the last component of path"""
        if not self.path:
            return ""
        return os.path.basename(self.path)

    def _is_loaded(self, pos, item) -> bool:
        return isinstance(item, RegionFile)

    def _load_item(self, pos: u.TPos2D, path: u.AnyPath
                   ) -> t.Tuple[u.RegionPos, RegionFile]:
        region: 'RegionFile' = RegionFile.load(path, regions=self, pos=pos)
        return region.pos, region

    @classmethod
    def load(cls, world, dimension: u.Dimension, category: str) -> 'Regions':
        path = os.path.join(world.path, dimension.subfolder(), category)
        self = cls.load_from_path(path)
        self.world = world
        self.dimension = dimension
        return self

    @classmethod
    def load_from_path(cls, path: u.AnyPath, recursive=False) -> 'Regions':
        log.debug("Loading data in %s", path)
        self = cls()

        glob = f"{'**/' if recursive else ''}r.*.*.mca"
        for filepath in pathlib.Path(path).glob(glob):
            if not filepath.is_file():
                continue
            try:
                pos = RegionFile.pos_from_filename(filepath)
            except RegionError as e:
                log.warning("Ignoring file: %s", e)
                continue
            self[pos] = filepath

        return self


class RegionChunk(c.Chunk):
    """Chunk in a Region.

    Being in a Region extends Chunk with several extra attributes:
    region       -- parent RegionFile which this Chunk belongs to
    pos          -- (x, z) relative position in Region, also its key in region mapping
    sector_count -- Chunk size, in data sectors (4096 bytes)
    timestamp    -- Last saved, set only by Minecraft client
    compression  -- Chunk data compression type. Currently only Zlib is used
    external     -- If chunk data is in external (.mcc) file
    dirty        -- If data was changed and needs saving. Currently unused
    """
    # TODO: be smart and do not overwrite the whole file
    #       Use chunk.dirty and a good (re-)allocation algorithm
    # Ideas for handling dirty data and partial save:
    # - On load, save hash of uncompressed chunk data
    # - Create __getitem__ access sentinels for regions in Regions and chunks in RegionFile
    # - On __setitem__ and __delitem__ of both, create a dirty sentinel
    # - Save regions and chunks that are dirty. If accessed, check hash to decide
    # - If chunk sector_count is not greater, use same offset
    __slots__ = (
        'region',
        'pos',
        'sector_count',
        'timestamp',
        'compression',
        'external',
        'dirty',
    )
    CHUNK_HEADER = struct.Struct(CHUNK_HEADER_FMT)
    COMPRESSION_BITS = 8 * CHUNK_COMPRESSION_BYTES - 1  # = 7
    COMPRESSION_MASK = 2 ** COMPRESSION_BITS - 1  # 0b01111111 = 127

    compress = {
        COMPRESSION_GZIP: gzip.compress,
        COMPRESSION_ZLIB: zlib.compress,
        COMPRESSION_NONE: lambda _: _,
    }
    decompress = {
        COMPRESSION_GZIP: gzip.decompress,
        COMPRESSION_ZLIB: zlib.decompress,
        COMPRESSION_NONE: lambda _: _,
    }

    # noinspection PyTypeChecker
    def __init__(self, *args, **tags):
        super().__init__(*args, **tags)
        self.region:        RegionFile  = None
        self.pos:           u.ChunkPos  = None
        self.timestamp:     int         = 0
        self.sector_count:  int         = 0  # only used by AnvilFile.parse()
        self.compression:   int         = COMPRESSION_ZLIB  # Minecraft default
        self.external:      bool        = False  # MCC files
        self.dirty:         bool        = True  # For now

    @property
    def world_pos(self) -> u.ChunkPos:
        if not self.region or not self.region.pos:
            return self.pos
        return self.region.pos.to_chunk(self.pos)

    @classmethod
    def parse(cls: t.Type[T], buff,
              region: AnvilFile = None, pos=None, timestamp=None,
              *args, **kwargs) -> T:
        """
        https://minecraft.fandom.com/wiki/Region_file_format#Chunk_data
        https://www.reddit.com/r/technicalminecraft/comments/e4wxb6/
        """
        if not hasattr(buff, 'read'):  # assume bytes data
            buff = io.BytesIO(buff)

        header = buff.read(cls.CHUNK_HEADER.size)
        try:
            length, compression = cls.CHUNK_HEADER.unpack(header)
            length -= CHUNK_COMPRESSION_BYTES  # already read
        except struct.error as e:
            raise ChunkError(f"chunk header has {len(header)} bytes" +
                             (f"({''.join(f'{_:X}' for _ in header)})"
                              if header else "") + f", {e}")

        external, compression = cls._unpack_compression(compression)
        if compression not in COMPRESSION_TYPES:
            raise ChunkError('Invalid compression type, must be one of'
                             f' {COMPRESSION_TYPES}: {compression}')

        if external:
            raise ChunkError('External MCC data file is not yet supported')

        data = cls.decompress[compression](buff.read(length))
        self: T = super().parse(io.BytesIO(data), *args, **kwargs)

        self.region = region
        self.pos = pos
        self.timestamp = timestamp
        self.sector_count = num_sectors(length + cls.CHUNK_HEADER.size)
        self.compression = compression
        self.external = external

        return self

    def write(self, buff, *args, update_timestamp=False, **kwargs) -> int:
        with io.BytesIO() as b:
            super().write(b, *args, **kwargs)
            data = self.compress[self.compression](b.getbuffer())
        length = len(data)
        size  = buff.write(
            self.CHUNK_HEADER.pack(length + CHUNK_COMPRESSION_BYTES,
                                   self._pack_compression(self.external,
                                                          self.compression)))
        size += buff.write(data)
        if update_timestamp:
            self.timestamp = u.now()
        assert size == self.CHUNK_HEADER.size + length
        return size

    @classmethod
    def _unpack_compression(cls, compression):
        """Helper to extract chunk external flag and compression type"""
        # endless bitwise operations...
        return (bool(compression >> cls.COMPRESSION_BITS),
                compression & cls.COMPRESSION_MASK)

    @classmethod
    def _pack_compression(cls, external, compression):
        """Helper to pack external flag and compression type"""
        # Python stdlib really needs bit structs...
        return (int(external) << cls.COMPRESSION_BITS) | compression

    def __str__(self):
        """Just like NTBExplorer!"""
        return (f"<Chunk [{', '.join(f'{_:2}' for _ in self.pos)}]"
                f" from Region {self.region.pos or ()}"
                f" in world at {self.world_pos}"
                f" saved on {u.isodate(self.timestamp)}>")

    def __repr__(self):
        return f'<{self.__class__.__name__}({self.pos}, {self.world_pos}, {self.timestamp})>'


def num_sectors(size):
    """Helper to calculate the number of sectors in size bytes"""
    # Faster than math.ceil(size / SECTOR_BYTES)
    # Used by AnvilFile and RegionChunk
    sectors = (size // SECTOR_BYTES)
    if size % SECTOR_BYTES:
        sectors += 1
    return sectors


# Just a convenience wrapper
load_region = RegionFile.load
