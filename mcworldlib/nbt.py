# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""NBT handling

Wraps whatever library is used as backend, currently nbtlib

Exported items:
    Compound
    File
    Path
    Root
"""

# No __all__, as being a wrapper it exports everything
#__all__ = [
#    'Compound',
#    'File',
#    'Path',
#    'Root',
#]


# TODO: (and suggest to nbtlib)
# - class Root(Compound): transparently handle the unnamed [''] root tag
#   - improve upon nbtlib.File.root property: self['x'] -> self['']['x']
#   - nbtlib.File, chunk.Chunk and level.Level would inherit from it
#   - completely hide the root from outside, re-add it only on .write()
# - Auto-casting value to tag on assignment based on current type
#   - compound['string'] = 'foo' -> compound['string'] = String('foo')
#   - maybe this is only meant for nbtlib.Schema?
from nbtlib.tag import *  # @UnusedWildImport
from nbtlib.nbt import File as nbtlib_File
from nbtlib.path import Path  # @UnusedImport
from nbtlib.literal.serializer import Serializer


class Root(Compound):
    """Unnamed Compound tag, used as root tag in files and chunks"""
    __slots__ = ()


class File(Root, nbtlib_File):
    # Lame overload so it inherits from Root
    __slots__ = ()


del nbtlib_File
