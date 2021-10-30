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
from typing import Callable, Tuple, Any, Iterator, Hashable, Union, NamedTuple, Iterable
import typing as t  # for Collection, Sequence and TypeAlias (Python 3.8+)

# This non-sensical typing is just to illustrate the concepts
# The inability to have leaf elements is the main reason `str` is not a Container
Leaf:       't.TypeAlias' = Any  # Non-container, scalar, single value, etc
Element:    't.TypeAlias' = Union[Leaf, 'Container']
Key:        't.TypeAlias' = Hashable  # For Sequences, always an int index
Container:  't.TypeAlias' = t.Collection[Element]


def _iter_container(container: Container) -> Iterable[Tuple[Key, Element]]:
    """Default (key, element) iterable for generic containers.

    Handles Mappings via .items(), otherwise use enumerate().
    """
    if isinstance(container, Mapping):
        return container.items()
    return enumerate(container)


def _is_container(v: Element) -> bool:
    """Default container test for generic containers.

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
    level:     int  # == len(keys)
    parent:    Container
    root:      Container


def walk(
    root:           Container,
    to_prune:       Callable[[Element], bool]  = None,
    iter_container: Callable[[Container], Iterable[Tuple[Key, Element]]] = _iter_container,
    is_container:   Callable[[Element], bool] = _is_container,
    _keys:          Tuple = (),
    _level:         int = 0,  # == len(_keys)
    _root:          Container = None,
) -> Iterator[Item]:
    for idx, (key, element) in enumerate(iter_container(root)):
        container = is_container(element)
        pruned = container and to_prune is not None and to_prune(element)
        _root = root if _root is None else _root
        _keys = _keys + (key,)  # == (*_keys, key)
        yield Item(
            element=element,
            keys=_keys,
            idx=idx,
            container=container,
            pruned=pruned,
            level=_level,
            parent=root,
            root=_root,
        )
        if container and not pruned:
            yield from walk(
                root=element,
                to_prune=to_prune,
                _keys=_keys,
                _level=_level + 1,
                _root=_root,
            )


def print_tree(root: Container, width: int = 2, offset: int = 0) -> None:
    # Useful symbols: │┊⦙ ├ └╰ ┐╮ ─┈ ┬⊟⊞ ⊕⊖⊙⊗⊘
    margin = ""
    previous = 0
    for item in walk(root):
        value = f"{len(item.element)} elements" if item.container else item.element
        expanded = item.container and not item.pruned and len(item.element) > 0
        last  = item.idx == len(item.parent) - 1
        prefix = (("╰" if last else "├") + ("─" * width)) if item.level else ""
        if item.level < previous:
            margin = margin[:-(width + 1 + offset) * (previous - item.level)]
        marker = (
            "⊟" if expanded  else
            "⊕" if item.pruned else
            "⊞" if item.container else
            "─"  # leaf
        )
        print(f"{margin}{prefix}{marker} {item.keys[-1]:2}: {value}")
        previous = item.level
        if expanded and item.level:
            margin += ((" " if last else "│") + " " * (width + offset))


def main():
    import json
    import mcworldlib as mc
    print_tree(json.load(open("../data/New World/advancements/"
                              "8b4accb8-d952-4050-97f2-e00c4423ba92.json")))
    print_tree(mc.load_dat("../data/New World/level.dat"))
    print_tree([{((1, 2), "c", ((4, 5, 6), 7, "d"))}])
    print_tree("rodrigo")


if __name__ == '__main__':
    main()
