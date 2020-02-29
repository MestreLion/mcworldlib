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

import tqdm

from . import level
from . import nbt
from . import region
from . import util as u


class WorldNotFoundError(u.MCError, IOError): pass


class World(level.Level):
    """Save directory and all related files and objects"""

    __slots__ = (
        'path',
        'regions',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.path = ""
        self.regions = region.Regions()

    @property
    def name(self):
        return str(self.root.get('LevelName', os.path.basename(self.path)))
    @name.setter
    def name(self, value):
        self.root['LevelName'] = nbt.String(value)

    @property
    def level(self):
        """Somewhat redundant API shortcut, as for now World *is* a Level"""
        return self.root

    @property
    def chunk_count(self):
        return sum(len(_) for _ in self.regions)

    def get_chunks(self, progress=True):
        regions = self.regions.values()
        if progress:
            regions = tqdm.tqdm(regions)
        for region in regions:
            for chunk in region.values():
                yield chunk

    def get_chunk_at(self, pos):
        if not isinstance(pos, u.Pos):
            pos = u.Pos(*pos)
        return self.regions[pos.to_region()].get_chunk(*pos.to_chunk())

    def get_block_at(self, pos):
        if not isinstance(pos, u.Pos):
            pos = u.Pos(*pos)
        chunk = self.get_chunk_at(pos)
        palette, indexes = chunk.get_section_blocks(pos.to_section())
        if not palette:
            return None
        return palette[int(indexes[pos.to_section_block()])]

    def get_player(self, name=None):
        """Get a named player (server) or the world default player"""
        # Single Player
        if name is None or name == 'Player':
            try:
                return self.player
            except Exception:
                raise u.MCError("Player not found in world '%s': %s" %
                                (self.name, name))
        # Multiplayer
        raise NotImplementedError

    @classmethod
    def load(cls, path, progress=True):
        # /level.dat and directory path
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
        else:
            # Last chance: try path as name of a minecraft save dir
            path = os.path.join(u.MINECRAFT_SAVES_DIR, path)
            if os.path.isdir(path):
                self = super().load(os.path.join(path, 'level.dat'))
                self.path = path
            else:
                self = cls()  # blank world
                raise WorldNotFoundError(f"World not found: {path}")

        # /region
        self.regions = region.Regions()
        regiondir = os.path.join(self.path, 'region')  # Overworld
        regions = os.listdir(regiondir)
        if progress:
            regions = tqdm.tqdm(
                regions,
                desc = f"Loading World '{self.name}'",
                unit = " Region",
            )
        for filename in regions:
            path = os.path.join(regiondir, filename)
            pos = region.RegionFile.pos_from_filename(path)
            self.regions[pos] = path

        # ...

        return self


load = World.load
