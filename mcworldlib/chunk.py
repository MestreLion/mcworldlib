# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""Chunks

Exported items:
    Chunk -- Class representing a Chunk's NBT, inherits from ntb.Root
"""

__all__ = ['Chunk']


from . import nbt


# TODO: create an nbt.Schema for it
class Chunk(nbt.Root):
    __slots__ = ()
