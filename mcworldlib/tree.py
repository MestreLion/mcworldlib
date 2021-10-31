# This file is part of MCWorldLib
# Copyright (C) 2021 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""Walk and tree-like print for nested, generic container structures

The term Container is used here in a very broad, conceptual meaning: a collection
of elements where each element can also be a Container, thus supporting nesting.

By these criteria, all Tuple-, List- and Dict-like structures qualify, while Sets
supports very limited element types. Strings could qualify, but as they support a
single element type (themselves), cannot nest, and require special handling to
avoid infinite recursion (1-char strings iterate themselves), they're usually not
treated as a container.

More formally put, a Container in this context is any Collection, sized via len()
and supporting iteration on elements and keys. Mappings support this via .items()
method, Sequences natively do so via enumerate().

Being such a Collection is the only actual requirement for walk(), but to be useful
Containers should also be indexable, i.e., support retrieving an element by key
via []. Sequences and Mappings are, Sequences having their integer index as key.
Sets can be cast to Sequence to satisfy this.
"""

from collections.abc import Collection, Sequence, Mapping, ByteString
from typing import (
    Callable, Tuple, Any, Iterator, Hashable, Union, NamedTuple, Iterable, Optional
)
import typing as t  # for Collection, Sequence and TypeAlias (Python 3.8+)

from . import nbt


# This non-sensical typing is just to illustrate the concepts
# The inability to have leaf elements is the main reason `str` is not a Container
Leaf:       't.TypeAlias' = Any  # Non-container, scalar, single value, etc
Element:    't.TypeAlias' = Union[Leaf, 'Container']
Key:        't.TypeAlias' = Hashable  # For Sequences, always an int index
Container:  't.TypeAlias' = t.Collection[Element]


def basic_iter(container: Container) -> Iterable[Tuple[Key, Element]]:
    """General use (key, element) iterable for containers.

    Handles Mappings via .items(), otherwise use enumerate().
    """
    if isinstance(container, Mapping):
        return container.items()
    return enumerate(container)


def basic_container(v: Element) -> bool:
    """General use container test.

    True for any Collection that is not a String (str/bytes).
    """
    return isinstance(v, Collection) and not isinstance(v, (str, ByteString))


def get_element(root: Container, keys: t.Sequence[Key]) -> Element:
    """Retrieve an element from a deeply nested root container"""
    if not keys:
        return root
    if not isinstance(root, (Sequence, Mapping)):  # Actually supports __getitem__
        root = tuple(root)
    # Hashable as Key type is too broad for Sequence, so checkers may complain
    return get_element(root[keys[0]], keys[1:])  # noqa


class Item(NamedTuple):
    element:   Element
    keys:      t.Sequence[Key]
    idx:       int
    container: bool
    pruned:    bool
    parent:    Container
    root:      Container


def walk(
    element:        Container,
    to_prune:       Callable[[Element], bool]  = None,
    iter_container: Callable[[Container], Iterable[Tuple[Key, Element]]] = basic_iter,
    is_container:   Callable[[Element], bool] = basic_container,
    _keys:          Tuple = (),
    _root:          Container = None,
) -> Iterator[Item]:
    if _root is None:
        # Root area
        _root = element
        ...  # reserved for the future. yield root perhaps?
        # Do not iterate non-containers
        if not is_container(element):
            return
    for idx, (key, child) in enumerate(iter_container(element)):
        container = is_container(child)
        pruned = container and to_prune is not None and to_prune(child)
        keys = _keys + (key,)  # == (*_keys, key)
        yield Item(
            element=child,
            keys=keys,
            idx=idx,
            container=container,
            pruned=pruned,
            parent=element,
            root=_root,
        )
        if container and not pruned:
            yield from walk(
                element=child,
                to_prune=to_prune,
                iter_container=iter_container,
                is_container=is_container,
                _keys=keys,
                _root=_root,
            )


def print_tree(root: Container, *, width: int = 2, line_offset: int = 0,
               show_root_as: Any = None, indent_first_gen: bool = True,
               noun_plural: str = "items", noun_singular: str = "item",
               fmt_container: str = "{length} {noun}",
               fmt_leaf: str = "{item.element}",
               do_print: bool = True,
               iterator: Iterator[Item] = None) -> Optional[str]:
    # Useful symbols: │┊⦙ ├ └╰ ┐╮ ─┈ ┬⊟⊞ ⊕⊖⊙⊗⊘
    margin = ""
    previous = 0
    if show_root_as is not None:
        print(show_root_as)
    if iterator is None:
        iterator = walk(root)
    lines = []
    for item in iterator:
        level = len(item.keys)
        if not indent_first_gen:
            level -= 1
        siblings = len(item.parent)
        idx_width = len(str(siblings - 1))
        last  = item.idx == siblings - 1
        prefix = (("╰" if last else "├") + ("─" * width)) if level > 0 else ""
        if level < previous:
            margin = margin[:-(width + 1 + line_offset) * (previous - level)]
        if item.container:
            length = len(item.element)
            expanded = not item.pruned and length > 0
            noun = noun_singular if length == 1 else noun_plural
        else:
            length = 0
            expanded = False
            noun = noun_singular
        marker = (
            "⊟" if expanded  else
            "⊕" if item.pruned else
            "⊞" if item.container else
            "─"  # leaf
        )
        value = (fmt_container if item.container else fmt_leaf).format(**locals())
        line = f"{margin}{prefix}{marker} {item.keys[-1]:{idx_width}}: {value}"
        if do_print:
            print(line)
        else:
            lines.append(line)
        previous = level
        if expanded and level > 0:
            margin += ((" " if last else "│") + " " * (width + line_offset))
    if do_print:
        return "\n".join(lines)


def print_walk(root):
    """Simple visualizer for data yielded from walk"""
    print("\n".join("\t" * (len(_.keys) - 1) +
                    ".".join(map(str, _.keys)) +
                    ": " + (f"{len(_.element)} elements"
                            if _.container else repr(_.element))
                    for _ in walk(root)))


# ----------------------------------
# Specialized walkers

def iter_nbt(sort_key: t.Callable[[t.Tuple[str, 'nbt.AnyTag']], t.Any] = None):
    def _iter_nbt(tag: Collection) -> Iterable[Tuple['nbt.TagKey', 'nbt.AnyTag']]:
        if isinstance(tag, nbt.Compound):
            itertags = tag.items()
            if sort_key is None:
                return itertags
            return sorted(itertags, key=sort_key)
        return enumerate(tag)
    return _iter_nbt
    # Wow, 4 de-indenting returns in a row!!! Have you ever seen that?


def is_nbt_container(tag: 'nbt.AnyTag') -> bool:
    # noinspection PyUnresolvedReferences
    return not tag.is_leaf


def nbt_explorer(data, root_name: str = None):
    def sort(item: Tuple[str, nbt.AnyTag]) -> Tuple:
        return (
            # if "not" looks confusing, remember False comes before True when sorting
            not isinstance(item[1], nbt.Compound),
            not isinstance(item[1], nbt.List),
            isinstance(item[1], nbt.Array),
            item[0].lower(),
        )
    iterator = walk(
        data,
        to_prune=lambda _: isinstance(_, nbt.Array),
        is_container=lambda _: not _.is_leaf,
        iter_container=iter_nbt(sort),
    )
    print_tree(
        (),
        iterator=iterator,
        noun_plural="entries", noun_singular="entry",
        fmt_container="{length} {noun}",
        show_root_as=root_name,
    )


def tests():
    import json
    for data in (
        json.load(open("../data/New World/advancements/"
                       "8b4accb8-d952-4050-97f2-e00c4423ba92.json")),
        nbt.load_dat("../data/New World/level.dat"),
        [{"x": 1, "y": 2}, "a", ((4, {"z": 5}, "b"), 6, "c")],
        "rodrigo",
    ):
        print("=" * 70)
        print_walk(data)
        print("-" * 70)
        print_tree(data, show_root_as=data.__class__.__name__)
        if isinstance(data, nbt.File):
            print("*" * 70)
            nbt_explorer(data, root_name="level.dat")
