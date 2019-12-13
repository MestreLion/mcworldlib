# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""Minecraft World save directory. The top level hierarchy.

Exported items:
    load  -- Helper function to load a world. Alias to World.load()
    World -- Class representing a Minecraft World save directory and associated data.
"""

__all__ = ['load', 'World']


import os.path

from . import level
from . import region


class World(level.Level):
    """Save directory and all related files and objects"""
    __slots__ = (
        'path',
        'regions'
    )

    @classmethod
    def load(cls, path):
        # /level.dat
        if hasattr(path, 'name'):
            # Assume file-like buffer to level.dat
            self = cls.parse(path)
            self.path = os.path.dirname(path.name)
        elif os.path.isfile(path):
            # Assume level.dat itself
            self = super().load(path)
            self.path = os.path.dirname(path)
        elif os.path.isdir(path):
            # Assume directory containing level.dat
            self = super().load(os.path.join(path, 'level.dat'))
            self.path = path

        # /region
        self.regions = {}
        regiondir = os.path.join(self.path, 'region')  # Overworld
        for filename in os.listdir(regiondir):
            path = os.path.join(regiondir, filename)
            pos = region.RegionFile.pos_from_filename(path)
            if not pos:
                continue
            self.regions[pos] = region.RegionFile.load(path)

        # ...

        return self


load = World.load
