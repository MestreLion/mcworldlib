# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""Chunks

Exported items:
    Chunk -- Class representing a Chunk's NBT, inherits from ntb.Root
"""

__all__ = ['Chunk']


from . import nbt
from . import entity


# TODO: create an nbt.Schema for it
class Chunk(nbt.Root):
    __slots__ = ()
    _root_name = nbt.Path("''.Level")

    @property
    def entities(self):
        return self.root['Entities']

    @classmethod
    def parse(cls, buff, *args, **kwargs):
        self = super().parse(buff, *args, **kwargs)
        self.root['Entities'] = nbt.List[entity.Entity](
            entity.Entity(_) for _ in self.root.get('Entities', ())
        )
        return self
