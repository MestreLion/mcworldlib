# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""Level.dat

Exported items:
    Level -- Class representing the main file 'level.dat', inherits from nbt.File
"""

from __future__ import annotations

__all__ = ['Level']

import logging
import typing as t

from . import nbt
from . import player

log = logging.getLogger(__name__)
T = t.TypeVar('T', bound='Level')


class Level(nbt.File):
    """level.dat file"""

    __slots__ = (
        'world',
    )

    _paths = {
        'player': 'Player',
    }

    def __init__(self, *args, world=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.world = world

    @property
    def player(self) -> nbt.Compound: return self.data_root[self._paths['player']]
    @player.setter
    def player(self, value: nbt.Compound): self.data_root[self._paths['player']] = value

    @classmethod
    def load(cls, filename, **kwargs):
        return super().load(filename, gzipped=True, byteorder='big', **kwargs)

    @classmethod
    def parse(cls: t.Type[T], buff, *args, world=None, **kwargs) -> T:
        # noinspection PyTypeChecker
        # https://youtrack.jetbrains.com/issue/PY-47271
        self: T = super().parse(buff, *args, **kwargs)
        # Can't rely on Compound.parse() to pass args to init()
        self.world = world

        try:
            # FIXME: This will overwrite self.player property !!!
            self.player = player.Player(self.player, level=self)
        except KeyError:
            log.warning("Level has no Player, possibly malformed: %s", self.filename)

        return self
