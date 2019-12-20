# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""Entities and associated classes

Exported items:
    Entity -- Class representing an Entity with ID, ultimately inherits from nbt.Compound
"""

__all__ = [
    'Entity',
]


from . import nbt
from . import util as u


# TODO: create an nbt.Schema for it
class BaseEntity(nbt.Compound):
    """Base class for all entities"""
    __slots__ = ()


class Entity(BaseEntity):
    """Base for all Entities with id"""
    __slots__ = ()

    @property
    def name(self):
        return self['id'].split(':', 1)[-1].replace('_', ' ').title()

    @property
    def pos(self):
        return u.Pos(*self['Pos'])

    def __str__(self):
        return f'{self.name} at {self.pos}'
