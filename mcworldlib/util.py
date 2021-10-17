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
    'TPos2D',
    'TPos3D',
    'Pos',
    'ChunkPos',
    'RegionPos',
    'pretty',
]

import enum
import os.path
import platform
import pprint
import time
import typing as t


# platform-dependent minecraft directory paths
if platform.system() == 'Windows':
    MINECRAFT_SAVES_DIR = os.path.expanduser('~/AppData/Roaming/.minecraft/saves')
else:
    MINECRAFT_SAVES_DIR = os.path.expanduser('~/.minecraft/saves')

CHUNK_GRID = (32, 32)  # (X, Z) chunks in each region file = 1024 chunks per region
CHUNK_SIZE = (16, 16)  # (X, Z) blocks in each chunk
SECTION_HEIGHT = 16    # chunk section height in blocks

# Pos stuff...
TPos2D: 't.TypeAlias' = t.Tuple[int, int]
TPos3D: 't.TypeAlias' = t.Tuple[float, float, float]

# Somewhat general, but used only by LazyLoadMap
KT = t.TypeVar('KT', bound=t.Hashable)
VT = t.TypeVar('VT')
Pos2DT = t.TypeVar('Pos2DT', bound=TPos2D)
AnyPath = t.Union[str, bytes, os.PathLike]
LazyFileT = t.Union[AnyPath, VT]


class MCError(Exception):
    """Base exception for business-logic, expected and handled custom exceptions.

    All custom exceptions must be a subclass of this.
    """
    pass


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


class BasePos(tuple):
    """Common methods for *Pos classes

    typing.NamedTuple has issues with multiple inheritance, so formally this is
    not their superclass.
    """
    @property
    def to_integers(self) -> tuple:
        # actually t.Union['Pos', 'ChunkPos', 'RegionPos'], and only used by Pos
        """Coordinates truncated to integers"""
        return self.__class__(*map(int, self))

    def __repr__(self) -> str:
        # works for __str__ too, as tuple does not define __str__
        return '(' + ','.join(f"{int(_): {len(self)+1}}" for _ in self) + ')'


class Pos(t.NamedTuple):
    """Wrapper for a (x, y, z) tuple, with helpful conversions"""
    # Consider officially allowing floats? Otherwise .as_integers makes no sense
    x: int
    y: int
    z: int

    to_integers = BasePos.to_integers
    __repr__ = BasePos.__repr__

    @property
    def as_yzx(self) -> tuple: return self.y, self.x, self.z  # section block notation

    @property
    def as_xzy(self) -> tuple: return self.x, self.z, self.y  # height last

    @property
    def as_section_block(self) -> tuple:
        ipos = self.to_integers  # Required by mod
        return (ipos.y % SECTION_HEIGHT,
                ipos.z % CHUNK_SIZE[1],
                ipos.x % CHUNK_SIZE[0])

    @property
    def section(self) -> int:
        return self.y // SECTION_HEIGHT

    @property
    def column(self) -> 'TPos2D':
        return self.x, self.z

    @property
    def offset(self) -> 'TPos2D':
        """(xc, zc) position coordinates relative to its chunk"""
        # noinspection PyTypeChecker
        return tuple(c % s for c, s in zip(self.column, CHUNK_SIZE))

    @property
    def chunk(self) -> 'ChunkPos':
        return ChunkPos(*(c // s for c, s in zip(self.column, CHUNK_SIZE)))

    @property
    def region(self) -> 'RegionPos':
        """(rx, rz) absolute coordinates of the region containing this position"""
        return self.chunk.region

    @classmethod
    def from_tag(cls, tag: t.Mapping[str, list]) -> 'Pos':  # tag: nbt.Compound
        return cls(*tag['Pos']).to_integers


class RegionPos(t.NamedTuple):
    rx: int
    rz: int

    __repr__ = BasePos.__repr__

    def to_chunk(self, offset: TPos2D = (0, 0)) -> 'ChunkPos':
        return ChunkPos(*(s * g + o for s, g, o in zip(self, CHUNK_GRID, offset)))


class ChunkPos(t.NamedTuple):
    cx: int
    cz: int

    __repr__ = BasePos.__repr__

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

    @classmethod
    def from_nbt_tags(cls, tag: t.Mapping[str, int]) -> 'ChunkPos':
        # tag: nbt.Compound[str, nbt.Int]
        #      cls(*(int(tag[f'{_}Pos']) for _ in ('x', 'z')))
        return cls(int(tag['xPos']),
                   int(tag['zPos']))

    @classmethod
    def from_nbt_array(cls, tag: t.Mapping[str, t.Iterable[int]]) -> 'ChunkPos':
        # tag: nbt.Compound[str, nbt.IntArray]
        return cls(*map(int, tag['Position']))


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
