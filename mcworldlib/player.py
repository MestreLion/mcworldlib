# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""Player and its Inventory

Exported items:
    Player -- Class representing a player
"""

__all__ = ['Player']

from . import nbt


class Player(nbt.Compound):
    __slots__ = ('name')

    def __init__(self, *args, name=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name or 'Player'

    @property
    def inventory(self):
        return self['Inventory']
