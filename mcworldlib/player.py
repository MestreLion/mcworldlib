# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""Player and its Inventory

Exported items:
    Player -- Class representing a player
"""

__all__ = ['Player']

from . import nbt
from . import util as u


class Player(nbt.Compound):
    __slots__ = ('name', 'world')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = 'Player'
        self.world = None

    @property
    def inventory(self):
        return self['Inventory']

    def get_chunk(self):
        """The chunk containing the player location"""
        if not self.world:
            return None

        return self.world.get_chunk_at(self['Pos'], u.Dimension(self['Dimension']))
