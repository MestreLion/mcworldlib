# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""NBT handling

Wraps whatever library is used as backend, currently nbtlib
"""

# No __all__, as being a wrapper it exports all imported names from the backend
# and all the ones defined here

import io as _io
import logging as _logging
import zlib as _zlib

# TODO: (and suggest to nbtlib)
# - Auto-casting value to tag on assignment based on current type
#   - compound['string'] = 'foo' -> compound['string'] = String('foo')
#   - maybe this is only meant for nbtlib.Schema?

# not in nbtlib.tag.__all__ and only used here
# noinspection PyProtectedMember
from nbtlib.tag import (
    Base as _Base,
    BYTE as _BYTE,
    read_numeric  as _read_numeric,
    read_string   as _read_string,
    write_numeric as _write_numeric,
    write_string  as _write_string,
)
from nbtlib.tag import *
# noinspection PyUnresolvedReferences
from nbtlib.nbt import File as _File, load as load_dat  # could be File.load
# noinspection PyUnresolvedReferences
from nbtlib.path import Path
from nbtlib.literal.serializer import serialize_tag as _serialize_tag


_log = _logging.getLogger(__name__)


class Root(Compound):
    """Unnamed Compound tag, used as root tag in files and chunks"""
    # Should contain the following from nbtlib_File:
    # __repr__()

    __slots__ = (
        'root_name',
    )

    def __init__(self, root_name: str = "", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.root_name: str = root_name

    @property
    def data_root(self):
        """The sole root child tag containing all data apart from DataVersion.

        If there is no such tag, return root itself
        """
        tags = set(self.keys()) - {'DataVersion'}

        # 'Data'  in level.dat (with DataVersion *inside* it)
        # 'data'  in <dim>/data/*.dat files (idcounts, map_*, raids*)
        # 'Level' in chunks from <dim>/region/*.mca anvil files, 'region' category
        if len(tags) == 1:
            return self[next(iter(tags))]

        # No sole child, data is at root along with with DataVersion
        # - chunks from <dim>/*/*.mca anvil files, 'entities' and 'poi' categories
        return self

    @property
    def root(self):
        """Deprecated, just use self directly."""
        _log.warning(".root is deprecated, just access its contents directly")
        return self

    @classmethod
    def parse(cls, buff, byteorder='big'):
        tag_id = _read_numeric(_BYTE, buff, byteorder)
        if not tag_id == cls.tag_id:
            # Possible issues with a non-Compound root:
            # - root_name might not be in __slots__(), and thus not assignable
            # - not returning a superclass might be surprising and have side-effects
            raise TypeError("Non-Compound root tags is not supported:"
                            f"{cls.get_tag(tag_id)}")
        name = _read_string(buff, byteorder)
        self = super().parse(buff, byteorder)
        self.root_name = name
        return self

    def write(self, buff, byteorder='big'):
        _write_numeric(_BYTE, self.tag_id, buff, byteorder)
        _write_string(getattr(self, 'root_name', "") or "", buff, byteorder)
        super().write(buff, byteorder)


# Overrides and extensions

class File(Root, _File):
    # Lame overload so it inherits from Root
    __slots__ = ()

    @classmethod
    def load(cls, filename, gzipped=True, *args, **kwargs):
        # make gzipped an optional argument, defaulting to True
        return super().load(filename, gzipped=gzipped, *args, **kwargs)

    @classmethod
    def load_mcc(cls, filename):
        with open(filename, 'rb') as buff:
            data = _io.BytesIO(_zlib.decompress(buff.read()))
        return cls.from_buffer(data)


# Add .pretty() method to all NBT tags
_Base.pretty = lambda self, indent=4: _serialize_tag(self, indent=indent)

# Fix String.__str__. Not needed in modern nbtlib versions
String.__str__ = lambda self: str.__str__(self)

# Convenience shortcut
load_mcc = File.load_mcc
