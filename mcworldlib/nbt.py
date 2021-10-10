# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""NBT handling

Wraps whatever library is used as backend, currently nbtlib
"""

# No __all__, as being a wrapper it exports all imported names from the backend
# and all the ones defined here

import io
import zlib

# TODO: (and suggest to nbtlib)
# - class Root(Compound): transparently handle the unnamed [''] root tag
#   - improve upon nbtlib.File.root property: self['x'] -> self['']['x']
#   - nbtlib.File, chunk.Chunk and level.Level would inherit from it
#   - completely hide the root from outside, re-add it only on .write()
# - Auto-casting value to tag on assignment based on current type
#   - compound['string'] = 'foo' -> compound['string'] = String('foo')
#   - maybe this is only meant for nbtlib.Schema?
# - String.__str__() should not quote or escape
# noinspection PyProtectedMember
from nbtlib.tag import Base as _Base   # Not in nbtlib.tag.__all__
from nbtlib.tag import *  # @UnusedWildImport
from nbtlib.nbt import File as _File
from nbtlib.path import Path  # @UnusedImport
from nbtlib.literal.serializer import serialize_tag as _serialize_tag


class Root(Compound):
    """Unnamed Compound tag, used as root tag in files and chunks"""
    # Should contain the following from nbtlib_File:
    # root_name()
    # root_name.setter()
    # root()
    # root.setter()
    # __repr__()

    __slots__ = ()
    _root_name: Path = None

    def __new__(cls, *args, **kwargs):
        self = super().__new__(cls, *args, **kwargs)
        # If a subclass defines _root_name, use it instead of the default
        if cls._root_name:
            cls.root_name = property(lambda _: _._root_name)
        return self

    # The following are copy-pasted from nbtlib.File

    @property
    def root_name(self):
        """The name of the root nbt tag."""
        return next(iter(self), None)

    @root_name.setter
    def root_name(self, value):
        self[value] = self.pop(self.root_name)

    @property
    def root(self):
        """The root nbt tag of the file."""
        return self[self.root_name]

    @root.setter
    def root(self, value):
        self[self.root_name] = value


# Overrides and extensions

class File(Root, _File):
    # Lame overload so it inherits from Root
    __slots__ = ()

    @classmethod
    def load_mcc(cls, filename):
        with open(filename, 'rb') as buff:
            data = io.BytesIO(zlib.decompress(buff.read()))
        return cls.from_buffer(data)


def _pretty(self, indent=4):
    return _serialize_tag(self, indent=indent)


_Base.pretty = _pretty
String.__str__ = lambda self: str.__str__(self)


# Convenience shortcut
load_mcc = File.load_mcc
