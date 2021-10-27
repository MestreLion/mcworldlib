# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""Minecraft World save directory. The top level hierarchy.

Exported items:
    load  -- Helper function to load a world. Alias to World.load()
    World -- Class representing a Minecraft World save directory and associated data.
"""

__all__ = [
    'OVERWORLD',
    'THE_NETHER',
    'THE_END',
    'World',
    'load',
]


import logging
import os.path
import pathlib
import typing as t

import tqdm

from . import anvil
from . import level
from . import nbt
from . import util as u

log = logging.getLogger(__name__)

OVERWORLD  = u.Dimension.OVERWORLD
THE_NETHER = u.Dimension.THE_NETHER
THE_END    = u.Dimension.THE_END


class WorldNotFoundError(u.MCError, IOError): pass


class World:
    """Save directory and all related files and objects"""

    __slots__ = (
        'path',
        'dimensions',
        'level',
    )

    # A.K.A Dimension subdirs
    categories: t.Tuple[str, ...] = (
        'region',
        'entities',
        'poi'
    )
    _level_file = "level.dat"

    def __init__(
        self, path: u.AnyPath    = None, *,
        levelobj:   level.Level  = None,
        dimensions: dict         = None
    ):
        self.path:       u.AnyPath   = path
        self.level:      level.Level = levelobj
        self.dimensions: \
            t.Dict[u.Dimension, t.Dict[str, anvil.Regions]] = dict(dimensions or {})

    @property
    def name(self) -> str:
        return str(getattr(self.level, 'data_root', {}
                           ).get('LevelName', getattr(self.path, 'name', "")))

    @name.setter
    def name(self, value):
        self.level.data_root['LevelName'] = nbt.String(value)

    @property
    def regions(self):
        """Re-shaped dimensions dictionary containing only Region data"""
        return self._category_dict('region')

    @property
    def entities(self):
        """Re-shaped dimensions dictionary containing only Entities data"""
        return self._category_dict('entities')

    @property
    def poi(self):
        """Re-shaped dimensions dictionary containing only Point-of-Interest data"""
        return self._category_dict('poi')

    @property
    def player(self):
        """The Single Player """
        return self.level.player

    @property
    def chunk_count(self):  # FIXME!
        return sum(len(_) for _ in self.regions)

    def get_chunks(self, progress=True, dimension=OVERWORLD, category='region'):
        """Yield all chunks in a given dimension and category, Overworld Regions by default"""
        regions = self.dimensions[dimension][category].values()
        if progress:
            regions = tqdm.tqdm(regions)
        for region in regions:
            for chunk in region.values():
                yield chunk

    def get_all_chunks(self, progress=True
                       ) -> t.Iterator[t.Tuple[u.Dimension, str, anvil.RegionChunk]]:
        """Yield (dimension, category, chunk) for all chunks

         In all dimensions and categories
         """
        dimensions = self.dimensions.keys()
        if progress:
            dimensions = tqdm.tqdm(dimensions)
        for dimension in dimensions:
            for category in self.categories:
                for chunk in self.get_chunks(progress=progress,
                                             dimension=dimension,
                                             category=category):
                    yield dimension, category, chunk

    def get_chunk(self, chunk_coords: u.TPos2D,
                  dimension=OVERWORLD, category='region') -> anvil.RegionChunk:
        """Return the chunk at coordinates (cx, cz)"""
        if not isinstance(chunk_coords, u.ChunkPos):
            chunk_coords = u.ChunkPos(*chunk_coords)
        region, chunk = chunk_coords.region_and_offset
        try:
            # noinspection PyTypeChecker
            return self.dimensions[dimension][category][region][chunk]
        except KeyError:
            raise anvil.ChunkError(f"Chunk does not exist: {chunk_coords}"
                                   f" [Region {region}, offset {chunk}]")

    def get_chunk_at(self, coords: u.TPos3D,
                     dimension=OVERWORLD, category='region') -> anvil.RegionChunk:
        if not isinstance(coords, u.Pos):
            coords = u.Pos(*coords)
        return self.get_chunk(coords.chunk, dimension=dimension, category=category)

    def get_block_at(self, coords: u.TPos3D, dimension=OVERWORLD):
        if not isinstance(coords, u.Pos):
            coords = u.Pos(*coords)
        chunk = self.get_chunk_at(coords, dimension=dimension, category='region')
        palette, indexes = chunk.get_section_blocks(Y=coords.section)
        if not palette:
            return None
        return palette[int(indexes[coords.as_section_block])]

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

    def save(self, path: u.AnyPath = None):
        # TODO: Save the Regions!
        self.level.save()

    def walk(self, progress=False) -> t.Iterator[t.Tuple[os.PathLike,
                                                         t.Union[level.Level,
                                                                 anvil.RegionFile],
                                                         nbt.Root,
                                                         nbt.FQTag]]:
        """Perform nbt.walk() for every NBT Root in the entire World.

        Yield (File Source, Path, NBT Root, Walk Data) for every tag.

        Path might not be a real path, but derived from Source and NBT Root.
        The real path can (usually) be obtained from Source.filename.

        NBT Root will be the same object as Source if it's a file like level.dat,
        or distinct such as chunks and their regions. A region is a file but not
        an NBT tag, and a chunk is an NBT Root but not a file of its own.

        For now, only yields from World.level and from Regions in World.dimensions
        """
        def relpath(*paths):
            return pathlib.Path(*paths).relative_to(self.path)

        for data in nbt.walk(self.level):
            yield relpath(self.level.filename), self.level, self.level, tuple(data[:4])

        for dimension, category, chunk in self.get_all_chunks(progress=progress):
            region = chunk.region
            pos = f"c.{chunk.pos.filepart}@{chunk.world_pos.filepart}"
            fspath = relpath(chunk.region.filename, pos)
            for data in nbt.walk(chunk):
                yield fspath, region, chunk, tuple(data[:4])

    @classmethod
    def load(cls, path: u.AnyPath, **kwargs):
        self: 'World' = cls()

        # /level.dat and directory path
        if hasattr(path, 'name'):
            # Assume file-like buffer to level.dat
            self.path  = os.path.dirname(path.name)
            self.level = level.Level.parse(path)
        elif os.path.isfile(path):
            # Assume level.dat itself
            self.path  = os.path.dirname(path)
            self.level = level.Level.load(path, **kwargs)
        elif os.path.isdir(path):
            # Assume directory containing level.dat
            self.path  = path
            self.level = level.Level.load(os.path.join(path, 'level.dat'), **kwargs)
        else:
            # Last chance: try path as name of a minecraft save dir
            path = os.path.expanduser(os.path.join(u.MINECRAFT_SAVES_DIR, path))
            if os.path.isdir(path):
                self.path  = path
                self.level = level.Level.load(os.path.join(path, 'level.dat'), **kwargs)
            else:
                raise WorldNotFoundError(f"World not found: {path}")
        # Can't rely on nbtlib.File.load() to pass args to parse()
        self.level.world = self

        log.info("Loading World '%s': %s", self.name, self.path)

        # Dimensions and their Region files and associated data
        # /region, /DIM-1/region, /DIM1/region
        # TODO: Read custom dimensions! /dimensions/<prefix>/<name>/region
        for dimension in u.Dimension:
            self.dimensions[dimension] = {}
            for category in self.categories:
                self.dimensions[dimension][category] = anvil.Regions.load(self, dimension, category)

        # ...

        return self

    def _category_dict(self, category):
        return {k: v.get(category, {}) for k, v in self.dimensions.items()}

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.name!r} at {self.path!r}>'


load = World.load
