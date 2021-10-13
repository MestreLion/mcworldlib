# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""Level.dat

Exported items:
    Level -- Class representing the main file 'level.dat', inherits from nbt.File
"""

__all__ = ['Level']


from . import nbt
from . import player


class Level(nbt.File):
    """level.dat file"""

    __slots__ = (
        'player',
    )

    @property
    def root_name(self):
        """The name of the root nbt tag."""
        return nbt.Path("''.Data")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.player = None

    @classmethod
    def load(cls, filename, **kwargs):
        return super().load(filename, gzipped=True, byteorder='big')

    @classmethod
    def parse(cls, buff, *args, **kwargs):
        self = super().parse(buff, *args, **kwargs)

        # Player
        name = 'Player'
        self.player = player.Player(self.root[name])
        self.player.name = name
        self.player.world = self

        return self
