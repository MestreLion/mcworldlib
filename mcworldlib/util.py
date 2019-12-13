# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""Miscellaneous functions and classes.

Exported items:
    Pos   -- Class representing a (x, y, z) 3D position coordinate, inherits from NamedTuple
    PosXZ -- Class representing a (x, z)    2D position coordinate, inherits from NamedTuple
"""

__all__ = [
    'Pos',
    'PosXZ',
    'pretty',
]


import time
import pprint
import typing


class Pos(typing.NamedTuple):
    x: int
    y: int
    z: int

    # Maybe should return Pos instances instead of regular tuples?
    def as_xzy(self): return (self.x, self.z, self.y)
    def as_yxz(self): return (self.y, self.x, self.z)
    def as_xz (self): return (self.x, self.z)


#TODO: Use it everywhere!
class PosXZ(typing.NamedTuple):
    x: int
    z: int
    def as_zx (self): return (self.z, self.xz)



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


def pretty(obj, indent=4):
    if hasattr(obj, 'pretty'):
        print(obj.pretty(indent=indent))
    else:
        pprint.pprint(obj, indent=indent)
