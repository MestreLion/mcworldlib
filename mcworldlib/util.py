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


# noinspection PyRedundantParentheses
class Pos(typing.NamedTuple):
    x: int
    y: int
    z: int

    # Maybe should return Pos instances instead of regular tuples?
    def as_xzy(self): return (self.x, self.z, self.y)
    def as_yxz(self): return (self.y, self.x, self.z)
    def as_xz(self):  return (self.x, self.z)

    def to_section_block(self):
        return (self.y % SECTION_HEIGHT,
                self.z % CHUNK_SIZE[1],
                self.x % CHUNK_SIZE[0])

    def to_section(self):
        return self.y // SECTION_HEIGHT

    def to_chunk(self):
        return (self.x // CHUNK_SIZE[0],
                self.z // CHUNK_SIZE[1])

    def to_region(self):
        cx, cz = self.to_chunk()
        return (cx // CHUNK_GRID[0],
                cz // CHUNK_GRID[1])

    def to_int(self): return (int(self.x), int(self.y), int(self.z))

    @classmethod
    def from_tag(cls, tag):
        return cls(*tag['Pos'])

    def __str__(self):
        return str(self.to_int())


# TODO: Use it everywhere!
# noinspection PyRedundantParentheses
class PosXZ(typing.NamedTuple):
    x: int
    z: int

    def as_zx(self):  return (self.z, self.x)

    def to_int(self): return (int(self.x), int(self.z))

    @classmethod
    def from_tag(cls, tag):
        return cls(tag['xPos'], tag['zPos'])

    def __str__(self):
        return str(self.to_int())


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
