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
    'Pos',
    'PosXZ',
    'pretty',
]

import collections.abc
import enum
import os.path
import platform
import pprint
import time
import typing


# platform-dependent minecraft directory paths
if platform.system() == 'Windows':
    MINECRAFT_SAVES_DIR = os.path.expanduser('~/AppData/Roaming/.minecraft/saves')
else:
    MINECRAFT_SAVES_DIR = os.path.expanduser('~/.minecraft/saves')

CHUNK_GRID = (32, 32)  # (x, z) chunks in each region file = 1024 chunks per region
CHUNK_SIZE = (16, 16)  # (x, z) blocks in each chunk
SECTION_HEIGHT = 16    # chunk section height in blocks


class MCError(Exception):
    """Base exception for business-logic, expected and handled custom exceptions.

    All custom exceptions must be a subclass of this.
    """
    pass


class Dimension(enum.Enum):
    OVERWORLD =  0
    NETHER    = -1
    END       =  1

    def subfolder(self):
        return '' if self.name == 'OVERWORLD' else f'DIM{self.value}'


class Pos(typing.NamedTuple):
    # Consider officially allowing floats? Otherwise .as_integers makes no sense
    x: int
    y: int
    z: int

    # Rationale for properties, prefixes and return types (just a draft):
    # If meant for explicit type conversion: method to_*()
    # If just presenting the same position in other format/reference: property as_*
    # If ready to be used elsewhere, with little point remaining Pos: -> tuple

    @property
    def as_integers(self) -> 'Pos':
        """Coordinates truncated to integers"""
        return self.__class__(*map(int, self))

    @property
    def as_yzx(self) -> tuple: return self.y, self.x, self.z  # section block notation

    @property
    def as_xzy(self) -> tuple: return self.x, self.z, self.y  # height last

    @property
    def as_section_block(self) -> tuple:
        ipos = self.as_integers  # Required by mod
        return (ipos.y % SECTION_HEIGHT,
                ipos.z % CHUNK_SIZE[1],
                ipos.x % CHUNK_SIZE[0])

    @property
    def as_section(self) -> int:
        return self.y // SECTION_HEIGHT

    @property
    def as_chunk(self) -> 'PosXZ':
        """(cx, cz) absolute coordinates of the chunk containing this position"""
        return self.to_posxz().as_chunk

    @property
    def as_region(self) -> 'PosXZ':
        """(rx, rz) absolute coordinates of the region containing this position"""
        return self.to_posxz().as_region

    @property
    def as_chunk_pos(self) -> 'PosXZ':
        """(xc, zc) position coordinates relative to its chunk"""
        return self.to_posxz().as_chunk_pos

    @property
    def as_region_chunk(self) -> 'PosXZ':
        """(cxr, czr) chunk position coordinates relative to its region"""
        return self.to_posxz().as_region_chunk

    def to_posxz(self) -> 'PosXZ':
        return PosXZ(self.x, self.z)
    as_xz = property(to_posxz)

    @classmethod
    def from_tag(cls, tag):  # tag: nbt.Compound
        return cls(*tag['Pos'])

    def __str__(self):
        return super().__str__(self.as_integers)


# TODO: Use it more!
class PosXZ(typing.NamedTuple):
    x: int
    z: int

    @property
    def as_integers(self) -> 'PosXZ':
        """Coordinates truncated to integers"""
        return self.__class__(*map(int, self))

    @property
    def as_chunk(self) -> 'PosXZ':
        """(cx, cz) absolute coordinates of the chunk containing this position"""
        return self.__class__(*(c // s for c, s in zip(self, CHUNK_SIZE)))
        # or:  PosXZ(self.x // CHUNK_SIZE[0], self.z // CHUNK_SIZE[1])

    @property
    def as_region(self) -> 'PosXZ':
        """(rx, rz) absolute coordinates of the region containing this position"""
        return self.__class__(*(c // g for c, g in zip(self.as_chunk, CHUNK_GRID)))
        # or:  PosXZ(*(c // (s * g) for c, s, g in zip(self, CHUNK_SIZE, CHUNK_GRID)))

    @property
    def as_chunk_pos(self) -> 'PosXZ':
        """(xc, zc) position coordinates relative to its chunk"""
        return self.__class__(*(c % s for c, s in zip(self.as_integers, CHUNK_SIZE)))
        # or:  PosXZ(int(self.x) % CHUNK_SIZE[0], int(self.z) % CHUNK_SIZE[1])

    @property
    def as_region_chunk(self) -> 'PosXZ':
        """(cxr, czr) chunk position coordinates relative to its region"""
        return self.__class__(*(c % g for c, g in zip(self.as_chunk, CHUNK_GRID)))
        # or:  PosXZ(*((c // s) % g for c, s, g in zip(self, CHUNK_SIZE, CHUNK_GRID)))

    def to_pos(self, y: int = 0) -> Pos:
        return Pos(self.x, y, self.z)
    to_xyz = to_pos

    @classmethod
    def from_tag(cls, tag):
        return cls(tag['xPos'], tag['zPos'])

    def __str__(self):
        return super().__str__(self.as_integers)


class LazyFileObjects(collections.abc.MutableMapping):
    """Keyed collection of objects loaded from files lazily on access"""
    __slots__ = (
        '_items',
        '_load_kwargs',
    )
    ItemClass = tuple
    collective = 'items'

    def __init__(self, items=None, **load_kwargs):
        self._items = dict(items) if items is not None else {}
        self._load_kwargs = load_kwargs

    def _load_lazy_object(self, item, **kwargs):
        raise NotImplementedError

    def __getitem__(self, key):
        item = self._items[key]
        if isinstance(item, self.ItemClass):
            return item
        obj = self._load_lazy_object(item, **self._load_kwargs)
        self._items[key] = obj
        return obj

    # ABC boilerplate
    def __iter__(self): return iter(self._items)  # for key in self._items: yield key
    def __len__(self): return len(self._items)
    def __setitem__(self, key, value): self._items[key] = value
    def __delitem__(self, key): del self._items[key]
    def __contains__(self, key): return key in self._items  # optional

    def __str__(self):
        return str(self._items)

    def __repr__(self):
        return f'<{self.__class__.__name__}({len(self)} {self.collective})>'


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


def pretty(obj, indent=4):
    if hasattr(obj, 'pretty'):
        print(obj.pretty(indent=indent))
    else:
        pprint.pprint(obj, indent=indent)
