# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""Miscellaneous functions and classes.

Exported items:
    Pos   -- Class representing a (x, y, z) 3D position coordinate, inherits from NamedTuple
    PosXZ -- Class representing a (x, z)    2D position coordinate, inherits from NamedTuple
"""

__all__ = [
    'MINECRAFT_SAVES_DIR',
    'MCError',
    'Dimension',
    'AnyPath',
    'TPos2D',
    'TPos3D',
    'BasePos',
    'Pos',
    'FlatPos',
    'ChunkPos',
    'RegionPos',
    'pretty',
]

import enum
import functools
import io
import os.path
import platform
import pprint
import time
import typing as t

import numpy


# platform-dependent minecraft directory paths
if platform.system() == 'Windows':
    MINECRAFT_SAVES_DIR: str = os.path.expanduser('~/AppData/Roaming/.minecraft/saves')
else:
    MINECRAFT_SAVES_DIR: str = os.path.expanduser('~/.minecraft/saves')

CHUNK_GRID = (32, 32)  # (X, Z) chunks in each region file = 1024 chunks per region
CHUNK_SIZE = (16, 16)  # (X, Z) blocks in each chunk
SECTION_HEIGHT = 16    # chunk section height in blocks
MINECRAFT_KEY_PREFIX = "minecraft"  # Prefix for built-in minecraft Ids and Names

# General type aliases
AnyPath = t.Union[str, os.PathLike]
AnyFile = t.Union[AnyPath, t.BinaryIO]

# Pos stuff...
NumT = t.TypeVar('NumT', int, float)
TPos:   't.TypeAlias' = t.Tuple[NumT, ...]            # Any 2D/3D *Pos
TPos2D: 't.TypeAlias' = t.Tuple[int, int]             # FlatPos, ChunkPos, etc
TPos3D: 't.TypeAlias' = t.Tuple[float, float, float]  # Pos

# Somewhat general, but mostly used only by LazyLoadMap
T = t.TypeVar('T')
KT = t.TypeVar('KT', bound=t.Hashable)
VT = t.TypeVar('VT')
Pos2DT = t.TypeVar('Pos2DT', bound=TPos2D)
LazyFileT = t.Union[AnyPath, VT]

# To avoid importing nbt
CompoundT = t.Dict[str, VT]


class MCError(Exception):
    """Base class for custom exceptions, with errno and %-formatting for args.

    All modules in this package raise this (or a subclass) for all
    explicitly raised, business-logic, expected or handled exceptions
    """
    def __init__(self, msg: object = "", *args, errno: int = 0):
        super().__init__((str(msg) % args) if args else msg)
        self.errno = errno


class InvalidPath(MCError, ValueError):
    def __init__(self, msg: object = "", *args, **kwargs):
        super().__init__(f"Invalid path: {msg}", *args, **kwargs)


class Dimension(enum.Enum):
    # Changed from IDs to namespace in Minecraft 1.16 (2230 < DataVersion < 2586)
    OVERWORLD  =  0
    THE_NETHER = -1
    THE_END    =  1

    # Aliases
    NETHER     = -1
    END        =  1

    def subfolder(self):
        return '' if self.name == 'OVERWORLD' else f'DIM{self.value}'

    @classmethod
    def from_nbt(cls, dimension) -> 'Dimension':
        if isinstance(dimension, int):
            return cls(dimension)
        return cls[dimension.split(':')[-1].upper()]  # Ewww!


class BasePos(TPos):
    """Common methods for *Pos classes

    typing.NamedTuple has issues with multiple inheritance, so formally this is
    not their superclass.
    """
    @property
    def as_integers(self) -> TPos[int]:
        # actually t.Union['Pos', 'ChunkPos', 'RegionPos'], and only used by Pos
        """New Position of the same type with coordinates truncated to integers"""
        return self.__class__(*map(int, self))

    @property
    def filepart(self) -> str:
        return ".".join(map(str, self))

    @staticmethod
    def from_xz_tags(cls, parent: CompoundT[int], suffix: str = 'Pos') -> 'TPos2D':
        """Read from an NBT Compound containing x<suffix> and z<suffix> coord tags"""
        # tag: nbt.Compound[str, nbt.Int]
        # Not worth parametrizing ('x', 'z') for now
        # https://github.com/JetBrains/intellij-community/pull/1655
        # noinspection PyTypeChecker
        return cls(int(parent['x' + suffix]),
                   int(parent['z' + suffix]))
        # return cls(*(int(tag[f'{_}{suffix}']) for _ in ('x', 'z')))

    @staticmethod  # actually classmethod
    def from_array_tag(cls,
                       tag: CompoundT[t.Iterable[NumT]],
                       name: str = 'Position',
                       cast: t.Callable[[t.Any], NumT] = int) -> 'TPos':
        """Read from an NBT Compound <tag> containing a coords List/Array tag named <name>"""
        # tag: nbt.Compound[str, nbt.IntArray]
        # https://github.com/JetBrains/intellij-community/pull/1655
        # noinspection PyTypeChecker
        return cls(*map(cast, tag[name]))

    def __repr__(self, width: t.Union[int, t.Iterable[int]] = 3) -> str:
        # Example usage:
        # __repr__ = functools.partialmethod(BasePos.__repr__, width=2)
        # If this ever becomes a true superclass, convert width to class attribute
        # __repr__ works for __str__ too only because tuple does not define __str__
        if isinstance(width, int):
            width = (width,) * len(self)
        return '(' + ','.join(f"{int(c): {w}}" for c, w in zip(self, width)) + ')'


class Pos(t.NamedTuple):  # TPos3D
    """(x, y, z) tuple of absolute world coordinates, with helpful conversions"""
    x: float
    y: float
    z: float

    as_integers = BasePos.as_integers
    __repr__ = functools.partialmethod(BasePos.__repr__, width=(5, 3, 5))

    @property
    def as_yzx(self) -> TPos3D: return self.y, self.x, self.z  # section block notation

    @property
    def as_xzy(self) -> TPos3D: return self.x, self.z, self.y  # height last

    @property
    def as_section_block(self) -> TPos3D:  # TPos3D[int] if it were parametrized
        ipos = self.as_integers  # Required by mod
        return (ipos.y % SECTION_HEIGHT,
                ipos.z % CHUNK_SIZE[1],
                ipos.x % CHUNK_SIZE[0])

    @property
    def section(self) -> int:
        return int(self.y // SECTION_HEIGHT)

    @property
    def column(self) -> 'FlatPos':
        return FlatPos(int(self.x), int(self.z))

    @property
    def offset(self) -> 'FlatPos':
        """(xc, zc) position coordinates relative to its chunk"""
        return self.column.offset

    @property
    def chunk(self) -> 'ChunkPos':
        return ChunkPos(*(c // s for c, s in zip(self.column, CHUNK_SIZE)))

    @property
    def region(self) -> 'RegionPos':
        """(rx, rz) absolute coordinates of the region containing this position"""
        return self.chunk.region

    @classmethod
    def from_tag(cls, tag):
        return BasePos.from_array_tag(cls, tag, name='Pos', cast=float)


class FlatPos(t.NamedTuple):  # TPos2D
    """(x, z) tuple of integer coordinates, absolute or offset (relative to chunk)"""
    x: int
    z: int

    from_tag = classmethod(BasePos.from_xz_tags)
    __repr__ = functools.partialmethod(BasePos.__repr__, width=5)

    @property
    def offset(self) -> 'FlatPos':
        """(xc, zc) position coordinates relative to its chunk"""
        return self.__class__(*(c % s for c, s in zip(self, CHUNK_SIZE)))


class RegionPos(t.NamedTuple):  # TPos2D
    """(rx, rz) tuple of region coordinates"""
    rx: int
    rz: int

    filepart = BasePos.filepart
    __repr__ = functools.partialmethod(BasePos.__repr__, width=3)

    def to_chunk(self, offset: TPos2D = (0, 0)) -> 'ChunkPos':
        return ChunkPos(*(s * g + o for s, g, o in zip(self, CHUNK_GRID, offset)))


class ChunkPos(t.NamedTuple):  # TPos2D
    """(cx, cz) tuple of chunk coordinates, absolute or offset (relative to region)"""
    cx: int
    cz: int

    filepart = BasePos.filepart
    __repr__ = functools.partialmethod(BasePos.__repr__, width=4)
    from_xz_tags   = classmethod(BasePos.from_xz_tags)
    from_array_tag = classmethod(BasePos.from_array_tag)

    @property
    def offset(self) -> 'ChunkPos':
        """(cxr, czr) chunk position coordinates relative to its region.

        If you also need region coordinates, consider using .region_and_offset()
        that efficiently calculates both.
        """
        return self.__class__(*(c % g for c, g in zip(self, CHUNK_GRID)))

    @property
    def region(self) -> RegionPos:
        """(rx, rz) absolute coordinates of the region containing this chunk.

        If you also need the chunk offset, consider using .region_and_offset()
        that efficiently calculates both.
        """
        return RegionPos(*(c // g for c, g in zip(self, CHUNK_GRID)))

    @property
    def region_and_offset(self) -> t.Tuple[RegionPos, 'ChunkPos']:
        """((rx, rz), (cxr, czr)) region and chunk offset coordinates of this chunk"""
        region, chunk = zip(*(divmod(c, g) for c, g in zip(self, CHUNK_GRID)))
        return RegionPos(*region), self.__class__(*chunk)


class LazyLoadMap(t.MutableMapping[KT, VT]):
    """Mapping of objects lazily loaded on access"""
    __slots__ = (
        '_items',
    )
    collective: str = 'items'  # Collective noun for the items, used in __repr__()

    def __init__(self, items: t.Optional['LazyLoadMap'] = None) -> None:
        # As implementations use KT=TPos2D, no benefit in allowing **kwargs
        self._items: t.Dict[KT, VT] = {}
        if items is not None:
            self._items.update(items)

    def _is_loaded(self, key: KT, item: VT) -> bool:
        raise NotImplementedError

    def _load_item(self, key: KT, item: VT) -> t.Optional[t.Tuple[KT, VT]]:
        raise NotImplementedError

    def __getitem__(self, key: KT) -> VT:
        if key not in self._items:
            raise KeyError(key)
        value: VT = self._items[key]
        if self._is_loaded(key, value):
            return value
        item = self._load_item(key, value)
        if item is not None:
            key, value = item
            self[key] = value
        return value

    # ABC boilerplate
    def __iter__(self):            return iter(self._items)
    def __len__(self):             return len(self._items)
    def __setitem__(self, key, v): self._items[key] = v
    def __delitem__(self, key):    del self._items[key]
    def __contains__(self, key):   return key in self._items  # optional

    def pretty(self, indent=4):
        # Access self._items directly to avoid loading items
        return pprint.pformat(self._items, indent=indent)

    def __str__(self):
        return str(self._items)

    def __repr__(self):
        return f'<{self.__class__.__name__}({len(self)} {self.collective})>'


class LazyLoadFileMap(LazyLoadMap[Pos2DT, LazyFileT]):
    def _is_loaded(self, key: Pos2DT, item: LazyFileT) -> bool:
        raise NotImplementedError

    def _load_item(self, key: Pos2DT, item: AnyPath) -> t.Optional[t.Tuple[Pos2DT, VT]]:
        raise NotImplementedError


def full_key(key: str) -> str:
    """Add 'minecraft:' prefix to key if contains no prefix."""
    return key if ":" in key else ":".join((MINECRAFT_KEY_PREFIX, key))


def short_key(key: str) -> str:
    """Remove 'minecraft:' prefix from key if it starts with the prefix."""
    if key.startswith(f"{MINECRAFT_KEY_PREFIX}:"):
        return key[len(MINECRAFT_KEY_PREFIX) + 1 :]
    return key


def isodate(secs: int) -> str:
    """Return a formatted date string in local time from a timestamp

    Example: isodate(1234567890) -> '2009-02-13 21:31:30'
    """
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(secs))


def now() -> int:
    """Return current time as a timestamp (seconds since epoch)

    Example: now() -> 1576027129 (if called on 2019-12-11 01:18:49 GMT)
    """
    return int(time.time())


def pretty(obj, indent=4) -> None:
    """Prints a pretty representation of obj"""
    try:
        f = obj.pretty
    except AttributeError:
        return pprint.pprint(obj, indent=indent)

    print(f(indent=indent))


def numpy_fromfile(file: AnyFile, dtype=float, count: int = -1):
    """numpy.fromfile() wrapper, handling io.BytesIO file-like streams.

    Numpy requires open files to be actual files on disk, i.e., must support
    file.fileno(), so it fails with file-like streams such as io.BytesIO().

    If numpy.fromfile() fails due to no file.fileno() support, this wrapper
    reads the required bytes from file and redirects the call to
    numpy.frombuffer().

    See https://github.com/numpy/numpy/issues/2230
    """
    # From numpy 1.20 onwards: dtype: numpy.typing.DTypeLike
    try:
        return numpy.fromfile(file, dtype=dtype, count=count)
    except io.UnsupportedOperation as e:
        if not (e.args and e.args[0] == 'fileno' and isinstance(file, io.IOBase)):
            raise  # Nothing I can do about it
        dtype = numpy.dtype(dtype)
        buffer = file.read(dtype.itemsize * count)
        return numpy.frombuffer(buffer, dtype=dtype, count=count)
