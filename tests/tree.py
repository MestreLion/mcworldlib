# This file is part of MCWorldLib
# Copyright (C) 2021 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""Walk and tree-like print for nested, generic container structures

The term Container is used here in a very broad, conceptual meaning: a collection
of elements where each element can also be a Container of at least the same type,
thus supporting arbitrarily deep (but finite) nesting.

By these criteria, all Tuple-, List- and Dict-like structures qualify, while Strings
and Sets don't, as those do not support nesting.

More formally put, a Container in this context is:
- A Collection: sized via len()/__len__ and supporting iteration on elements.
    - Mappings support this via .items() method, Sequences natively do so.
- Indexable: supports retrieving an element by key via []/__getitem__.
   - Not necessarily orderable, as key is not required to be an integer.
   - Sets are not indexable, but could use enumerate() to satisfy this.
- Discoverable: provides a way to iterate all its indexing keys
    - Mappings do so natively, Sequences and Sets via enumerate()
- Nestable: supports elements of the same type as itself.
    - In other words: can be a (single) element of another Container
    - Sets can not qualify this
    - Strings (str/bytes) _could_ qualify, but that's a stretch. And interpreting
      a single character as a Collection (of itself) leads to infinite nesting.
- Distinguishable from a non-Container element, supporting non-Container elements
    - Try to get away with THAT, Strings!
- Not required to support mixed-type Containers, or even all Container types,
  but it must at least support itself.
"""

from collections.abc import Mapping, Sequence, ByteString
from typing import Callable, Tuple, Any, Iterator, Hashable, Union, NamedTuple, Iterable
import typing as t  # for Sequence, Mapping, TypeAlias (Python 3.8+)

# This non-sensical typing is just to illustrate the concepts
Leaf:       't.TypeAlias' = Any  # A.K.A. Non-container, scalar, single value, atomic, etc
Element:    't.TypeAlias' = Union[Leaf, 'Container']  # The reason `str` is not a Container
Key:        't.TypeAlias' = Hashable  # Is always an int for Sequences
Container:  't.TypeAlias' = Union[t.Sequence[Element], t.Mapping[Key, Element]]


def _iter_container(container: Container) -> Iterable[Tuple[Key, Element]]:
    """Default (key, element) iterable for generic containers

    Handles any Sequence and Mapping
    """
    if isinstance(container, Mapping):
        return container.items()
    return enumerate(container)


def _is_container(v: Element) -> bool:
    """Default container test for generic containers

    True for any Sequence or Mapping that is not a String
    (as strings themselves
    """
    return (isinstance(v, (Sequence, Mapping)) and
            not isinstance(v, (str, ByteString)))


def get_element(root: Container, parts: Tuple) -> Element:
    if not parts:
        return root
    return get_element(root[parts[0]], parts[1:])


class Item(NamedTuple):
    element:   Element
    parts:     Tuple
    key:       Key
    idx:       int
    container: bool
    pruned:    bool
    level:     int  # == len(parts)
    parent:    Container
    root:      Container


def walk(
    root:           Container,
    to_prune:       Callable[[Element], bool]  = None,
    iter_container: Callable[[Container], Iterable[Tuple[Key, Element]]] = _iter_container,
    is_container:   Callable[[Element], bool] = _is_container,
    _parts:         Tuple = (),
    _level:         int = 0,  # == len(_parts)
    _root:          Container = None,
) -> Iterator[Item]:
    for idx, (key, element) in enumerate(iter_container(root)):
        container = is_container(element)
        pruned = container and to_prune is not None and to_prune(element)
        _root = root if _root is None else _root
        yield Item(
            element=element,
            parts=_parts,
            key=key,
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
                _parts=_parts + (key,),  # == (*_parts, key)
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
        print(f"{margin}{prefix}{marker} {item.key:2}: {value}")
        previous = item.level
        if expanded and item.level:
            margin += ((" " if last else "│") + " " * (width + offset))


def main():
    import json
    print_tree(json.load(open("../data/New World/advancements/"
                              "8b4accb8-d952-4050-97f2-e00c4423ba92.json")))
    print_tree({((1, 2), "c", ((4, 5, 6), 7, "d"))})  # Works
    print_tree("rodrigo")


if __name__ == '__main__':
    main()
