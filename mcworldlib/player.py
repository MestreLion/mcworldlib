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
    __slots__ = ('name', 'level')

    def __init__(self, *args, name='Player', level=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name
        self.level = level

    @property
    def inventory(self) -> nbt.List[nbt.Compound]: return self['Inventory']
    @inventory.setter
    def inventory(self, value: nbt.List[nbt.Compound]): self['Inventory'] = value

    def get_chunk(self):
        """The chunk containing the player location"""
        if not (self.level and self.level.world):
            return None

        return self.level.world.get_chunk_at(self['Pos'],
                                             u.Dimension.from_nbt(self['Dimension']))
