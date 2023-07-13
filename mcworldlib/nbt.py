# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""NBT handling

Wraps whatever library is used as backend, currently nbtlib
"""

# No __all__, as being a wrapper it exports all imported names from the backend
# and all the ones defined here

# Delete ALL imported and declared names not meant for export, see the end of file
import io      as _io
import logging as _logging
import typing  as t
import zlib    as _zlib

# TODO: (and suggest to nbtlib)
# - Auto-casting value to tag on assignment based on current type
#   - compound['string'] = 'foo' -> compound['string'] = String('foo')
#   - maybe this is only meant for nbtlib.Schema?

# not in nbtlib.tag.__all__ and only used in Root
# noinspection PyProtectedMember
from nbtlib.tag import (
    BYTE as _BYTE,
    read_numeric as _read_numeric,
    read_string as _read_string,
    write_numeric as _write_numeric,
    write_string as _write_string,
)

from nbtlib.tag import *
from nbtlib.tag import Array  # Not in __all__, but used by others
from nbtlib.nbt import File as _File  # intentionally not importing load
from nbtlib.path import Path
from nbtlib.literal.serializer import serialize_tag as _serialize_tag

from . import tree as _tree

_log = _logging.getLogger(__name__)

# Concrete and (meant to be) instantiable tags, i.e. no Base, Numeric, End, etc
AnyTag: 't.TypeAlias' = t.Union[
    Byte,
    Short,
    Int,
    Long,
    Float,
    Double,
    ByteArray,
    String,
    List,
    Compound,
    IntArray,
    LongArray,
]
ContainerTag: 't.TypeAlias' = t.Union[
    List,
    Compound,
    Array,
]
TagKey: 't.TypeAlias' = t.Union[str, int]

RT = t.TypeVar('RT', bound='Root')


class Root(Compound):
    """Unnamed Compound tag, the root tag in files and chunks"""

    __slots__ = (
        'root_name',
    )

    def __init__(self, *args, root_name: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self.root_name: str = root_name

    @property
    def data_root(self) -> Compound:
        """Root itself or the child containing all data apart from DataVersion.

        A convenience shortcut for root compounds that contains just DataVersion
        and another tag, and all relevant data is in that tag, as is the case for
        most Minecraft data:
        'Data'  in level.dat (with DataVersion *inside* it)
        'data'  in <dim>/data/*.dat files (idcounts, map_*, raids*)
        'Level' in chunks from <dim>/region/*.mca anvil files, 'region' category

        Known NBT with no sole child, data is at root along with DataVersion:
        - chunks from <dim>/*/*.mca anvil files, 'entities' and 'poi' categories
        """
        return self._data_root[1]

    @property
    def data_root_key(self) -> str:
        """data_root key, if any"""
        return self._data_root[0]

    @property
    def _data_root(self) -> t.Tuple[str, Compound]:
        tags = self.keys() - {'DataVersion'}
        if not len(tags) == 1:
            return "", self
        name = next(iter(tags))
        # FIXME: Should make sure it's actually a Compound and not just AnyTag
        return name, self[name]

    # Copy parse() and write() methods from _File

    @classmethod
    def parse(cls: t.Type[RT], fileobj, byteorder='big') -> RT:
        """Override :meth:`nbtlib.tag.Base.parse` for nbt files."""
        # For the typing dance, see https://stackoverflow.com/a/44644576/624066
        tag_id = _read_numeric(_BYTE, fileobj, byteorder)
        if not tag_id == cls.tag_id:
            # Possible issues with a non-Compound root:
            # - root_name might not be in __slots__(), and thus not assignable
            # - not returning a superclass might be surprising and have side effects
            raise TypeError(
                f"Non-Compound root tag is not supported: {cls.get_tag(tag_id)}"
            )
        name = _read_string(fileobj, byteorder)
        self: RT = super().parse(fileobj, byteorder)
        self.root_name = name
        return self

    def write(self, fileobj, byteorder="big"):
        """Override :meth:`nbtlib.tag.Base.write` for nbt files."""
        _write_numeric(_BYTE, self.tag_id, fileobj, byteorder)
        _write_string(self.root_name, fileobj, byteorder)
        super().write(fileobj, byteorder)

    def __repr__(self):
        key, data = self._data_root  # save refs for efficiency
        if key:
            key = f" ({len(data)} in {key!r})"
        name = f" {self.root_name!r}" if self.root_name else ""
        return f'<{self.__class__.__name__}{name} tags: {len(self)}{key}>'


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
        self = cls.parse(data)
        self.filename = filename
        return self

    def __repr__(self):
        name = self.__class__.__name__
        return super().__repr__().replace(f"<{name}", f"<{name} {self.filename!r}", 1)


class FQTag(t.NamedTuple):
    """Fully qualified Tag, as yielded by the walk family of functions.

    See deep_walk() for the description of each member.
    """
    tag:          AnyTag
    path:         Path
    key:          TagKey
    idx:          int
    is_container: bool
    is_collapsed: bool
    level:        int
    parent:       ContainerTag
    root:         ContainerTag


def walk(root: AnyTag, sort: bool = False) -> t.Iterator[FQTag]:
    """deep_walk() wrapper with different defaults

    Only walk into Compound, List of Compound, and Lists of List. Any other tag,
    including Arrays and Lists of other types, are considered leaf tags and not
    recurred into.

    If :sort:, sort Compound keys case-insensitively. If not, do not sort keys at
    all, yielding tags by insertion order.
    """
    yield from deep_walk(
        root,
        collapse=lambda tag: (not isinstance(tag, (List[List], List[Compound]))
                              and isinstance(tag, (Array, List))),
        key_sorted=str.lower if sort else None,
    )


def deep_walk(
    root:       AnyTag,
    key_sorted: t.Callable[[t.Tuple[str, AnyTag]], t.Any] = None,  # SupportsLessThan
    collapse:   t.Callable[[AnyTag], bool]  = None,
    _path:      Path = Path(),
    _level:     int = 0,  # == len(path)
    _root:      ContainerTag = None,
) -> t.Iterator[FQTag]:
    """Yield a data tuple about each child of a root container tag, recursively.

    Yielded tuple contains the following information:
     - Tag: currently yielded tag
     - Path: NBT Path location for the parent tag. See description below for details.
     - Key: tag's location in its parent. See description below for details.
     - Idx: tag's order in the enumeration of its parent's children. Same as Key if in List
     - Container: If tag is a (mutable) container, i.e, Compound, List or Array
     - Collapsed: If container tag will not be recurred into, as set by the collapse function
     - Level: nesting/recursion level. 0 for root's immediate children. Same as len(Path)
     - Parent: tag's parent. Same as Path[Key]
     - Root: the original root from the initial deep_walk() call

    The root tag itself is not a yielded tag, and it is only considered a container
    if it is a Compound, a List of Compounds, or a List of Lists. Any other tag,
    including Arrays and Lists of other types, are considered leaf tags and not
    recurred into.

    Key will be a string if parent is a Compound, or an integer if List. It is
    the tag name (or index) location in its (immediate) parent tag, so:
        parent[key] == tag

    Path is the parent tag location in the root tag, compatible with the format
    described at https://minecraft.fandom.com/wiki/NBT_path_format. That holds
    true even when path is empty, i.e., when the parent tag is root. So:
        root[path][name] == root[path[name]] == tag

    Collapse is a function that takes a container tag and returns if the tag
    should be collapsed, i.e. not walked into, skipping its children. The tag
    itself will still be yielded.

    Key_sorted is a function that takes a (name, tag) to be passed to sorted()
    as its key argument, to control sorting order of Compounds' items. If None,
    sorted() will not be called.
    """
    for data in _tree.walk(
        root,
        to_prune=collapse,
        iter_container=_tree.iter_nbt(key_sorted),
        is_container=_tree.is_nbt_container,
    ):
        yield FQTag(
            tag          = data.element,
            path         = _tree.get_element(Path(), data.keys[:-1]),  # Clever, but inefficient
            key          = data.keys[-1],  # noqa, Hashable is too broad for KeyType
            idx          = data.idx,
            is_container = data.container,
            is_collapsed = data.pruned,
            level        = len(data.keys) - 1,
            parent       = data.parent,  # noqa, Collection is too broad for CompountType
            root         = data.root,    # noqa, same reason
        )


def nbt_explorer(root: AnyTag, root_name: str = None, width: int = 2) -> None:
    """Walk NBT just like NBT Explorer!

    - Compounds first, then Lists (of all types), then leaf values. Arrays last
    - Case insensitive sorting on key names
    - Include item count for Compounds, Lists and Arrays
    - Arrays collapsed as leaves
    """
    def sort_key(item):
        return (
            # if "not" looks confusing, remember False comes before True when sorting
            not isinstance(item[1], Compound),
            not isinstance(item[1], List),
            isinstance(item[1], Array),
            item[0].lower(),
        )
    iterator = _tree.walk(
        root,
        to_prune=lambda _: isinstance(_, Array),
        iter_container=_tree.iter_nbt(sort_key),
        is_container=_tree.is_nbt_container,
    )
    _tree.print_tree(
        (),
        iterator=iterator,
        noun_plural="entries", noun_singular="entry",
        fmt_container="{length} {noun}",
        show_root_as=root_name,
        width=width,
        indent_first_gen=False,
    )


# Add .pretty() method to all NBT tags
Base.pretty = lambda self, indent=4: _serialize_tag(self, indent=indent)

Base.is_leaf = property(
    fget=lambda _: not isinstance(_, (Compound, List, Array)),
    doc="If this tag an immutable tag and not a Mutable Collection."
        " Non-leaves are the containers excluding String: Compound, List, Array")

# Remove _File methods copied to Root so super() calls from File works properly
del _File.parse
del _File.write

# Convenience shortcuts
load_mcc = File.load_mcc
load_dat = File.load

del t
