# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""Level.dat

Exported items:
    Level -- Class representing the main file 'level.dat', inherits from nbt.File
"""

__all__ = ['Level']


from . import nbt


class Level(nbt.File):
    """level.dat file"""
    __slots__ = ()

    @classmethod
    def load(cls, filename):
        return super().load(filename, gzipped=True, byteorder='big')
