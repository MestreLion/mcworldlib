# mcworldlib - Minecraft World Library

Yet another library to manipulate Minecraft data, inspired by the now-defunct
[pymclevel](https://github.com/mcedit/pymclevel), building on top of the amazing
[nbtlib](https://github.com/vberlier/nbtlib).

Focused on making the bridge between the on-disk save files and directory structure
and their NBT content, much like [NBTExplorer](https://github.com/jaquadro/NBTExplorer),
presenting all World data in a structured, convenient way so other tools can build
on top of it and add more _semantics_ to that data.

---
Features
--------
- Read and write `.dat` [NBT](https://minecraft.wiki/w/NBT_format)
  files, both uncompressed and gzip-compressed.
- Read and write `.mca`/`.mcr` [Anvil](https://minecraft.wiki/w/Anvil_file_format)
  region files, lazily loading their contents only when the data is actually
  requested, also monitoring content changes to efficiently save back to disk
  only the needed files.
- Read and write `.mcc` [external](https://www.reddit.com/r/technicalminecraft/comments/e4wxb6)
  chunk files, loading from there when indicated by the chunk header in the `.mca`
  region file, and automatically selecting the appropriate format on save:
  external `mcc` if the chunk data outgrows its previous maximum size (~1 MB),
  and back to the `mca` if it shrinks enough to fit there again.

---
Usage
-----

### Reading world data

You can open a Minecraft World by several ways:
- Path to a `level.dat` _**file**_, or its open file-like _**stream**_ object;
- Path to a world _**directory**_, containing the `level.dat` file at its root,
  as in the example below;
- World _**name**_, i.e, the directory basename of a world in the platform-dependent
  default Minecraft `saves/` path. By default, it is the in-game world name.

```pycon
>>> import mcworldlib as mc
>>> world = mc.load('data/New World')
>>> # Most classes have a pretty print. In many cases, their NBT data.
>>> mc.pretty(world.level)
{
    Data: {
        WanderingTraderSpawnChance: 25,
        BorderCenterZ: 0.0d,
        Difficulty: 2b,
        ...
        SpawnAngle: 0.0f,
        version: 19133,
        BorderSafeZone: 5.0d,
        LastPlayed: 1633981265600L,
        BorderWarningTime: 15.0d,
        ScheduledEvents: [],
        LevelName: "New World",
        BorderSize: 59999968.0d,
        DataVersion: 2730,
        DataPacks: {
            Enabled: ["vanilla"],
            Disabled: ["Fabric Mods"]
        }
    }
}

```

`World.dimensions` is a dictionary mapping each dimension to categorized Region files:
```pycon
>>> mc.pretty(world.dimensions)
{   <Dimension.OVERWORLD: 0>: {   'entities': <Regions(6 regions)>,
                                  'poi': <Regions(0 regions)>,
                                  'region': <Regions(6 regions)>},
    <Dimension.THE_NETHER: -1>: {   'entities': <Regions(0 regions)>,
                                    'poi': <Regions(0 regions)>,
                                    'region': <Regions(0 regions)>},
    <Dimension.THE_END: 1>: {   'entities': <Regions(0 regions)>,
                                'poi': <Regions(0 regions)>,
                                'region': <Regions(0 regions)>}}

```

And `World.regions` is handy view of that dictionary containing only the 'region'
category, similarly with `World.entities` and `World.poi`:
```pycon
>>> mc.pretty(world.regions)
{   <Dimension.OVERWORLD: 0>: <Regions(6 regions)>,
    <Dimension.THE_NETHER: -1>: <Regions(0 regions)>,
    <Dimension.THE_END: 1>: <Regions(0 regions)>}

>>> regions = world.regions[mc.OVERWORLD]
>>> regions is world.dimensions[mc.OVERWORLD]['region']
True

```

`Regions` is a dict-like collection of `.mca` Anvil region files, grouped in
"categories" that match their sub-folder in a given the dimension, such as
`/entities`, `/poi`, and of course `/region`.

The dictionary keys are region coordinate tuples, and the values represent Region
files. Files are lazily loaded, so initially the values contain only their path:

```pycon
>>> mc.pretty(regions)
{   ( -2, -1): PosixPath('data/New World/region/r.-2.-1.mca'),
    ( -2,  0): PosixPath('data/New World/region/r.-2.0.mca'),
    ( -1, -1): PosixPath('data/New World/region/r.-1.-1.mca'),
    ( -1,  0): PosixPath('data/New World/region/r.-1.0.mca'),
    (  0, -1): PosixPath('data/New World/region/r.0.-1.mca'),
    (  0,  0): PosixPath('data/New World/region/r.0.0.mca')}

```

They are automatically loaded when you first access them:
```pycon
>>> regions[0, 0]
<RegionFile(r.0.0.mca: 167 chunks)>

```

A `RegionFile` is a dictionary of chunks, and each `Chunk` contains its NBT data:

```pycon
>>> region = regions[-2, 0]
>>> mc.pretty(region)
{
    (  18,   0): <Chunk [18,  0] from Region ( -2,  0) in world at ( -46,   0) saved on 2021-10-11 16:39:17>,
    (  28,   0): <Chunk [28,  0] from Region ( -2,  0) in world at ( -36,   0) saved on 2021-10-11 16:40:50>,
    (  29,   0): <Chunk [29,  0] from Region ( -2,  0) in world at ( -35,   0) saved on 2021-10-11 16:40:50>,
    ...
    (  29,  31): <Chunk [29, 31] from Region ( -2,  0) in world at ( -35,  31) saved on 2021-10-11 16:40:14>,
    (  30,  31): <Chunk [30, 31] from Region ( -2,  0) in world at ( -34,  31) saved on 2021-10-11 16:40:14>,
    (  31,  31): <Chunk [31, 31] from Region ( -2,  0) in world at ( -33,  31) saved on 2021-10-11 16:40:14>
}

>>> chunk = region[30, 31]
>>> mc.pretty(chunk)  # alternatively, print(chunk.pretty())
{
    Level: {
        Status: "structure_starts",
        zPos: 31,
        LastUpdate: 4959L,
        InhabitedTime: 0L,
        xPos: -34,
        Heightmaps: {},
        TileEntities: [],
        Entities: [],
        ...
    },
    DataVersion: 2730
}

```

You can fetch a chunk by several means, using for example:
- Its key in their region dictionary, using relative coordinates, as the examples above.
- Their absolute _(cx, cz)_ chunk position: `world.get_chunk((cx, cz))`
- An absolute _(x, y, z)_ world position contained in it: `world.get_chunk_at((x, y, z))`
- The player current location: `world.player.get_chunk()`

```pycon
>>> for chunk in (
...     world.get_chunk((-34, 21)),
...     world.get_chunk_at((100, 60, 100)),
...     world.player.get_chunk(),
... ):
...     print(chunk)
...
<Chunk [30, 21] from Region ( -2,  0) in world at ( -34,  21) saved on 2021-10-11 16:40:50>
<Chunk [ 6,  6] from Region (  0,  0) in world at (   6,   6) saved on 2021-10-11 16:40:50>
<Chunk [18,  0] from Region ( -1,  0) in world at ( -14,   0) saved on 2021-10-11 16:40:48>

```

Get the block info at any coordinate:
```pycon
>>> block = world.get_block_at((100, 60, 100))
>>> print(block)
Compound({'Name': String('minecraft:stone')})

```

Remember the automatic, lazy-loading feature of `Regions`? In the above examples
a few chunks from distinct regions were accessed. So what is the state of the
`regions` dictionary now?

```pycon
>>> mc.pretty(regions)
  {   ( -2, -1): PosixPath('data/New World/region/r.-2.-1.mca'),
      ( -2,  0): <RegionFile(r.-2.0.mca: 133 chunks)>,
      ( -1, -1): PosixPath('data/New World/region/r.-1.-1.mca'),
      ( -1,  0): <RegionFile(r.-1.0.mca: 736 chunks)>,
      (  0, -1): PosixPath('data/New World/region/r.0.-1.mca'),
      (  0,  0): <RegionFile(r.0.0.mca: 167 chunks)>}

```

As promised, only the accessed region files were actually loaded, automatically.

### Editing world data

Reading and modifying the Player's inventory is quite easy:

```pycon
>>> inventory = world.player.inventory  # A handy shortcut
>>> inventory is world.level['Data']['Player']['Inventory']
True
>>> # Easily loop each item as if the inventory is a list. In fact, it *is*!
>>> for item in inventory:
...     print(f"Slot {item['Slot']:3}: {item['Count']:2} x {item['id']}")
Slot   0:  1 x minecraft:stone_axe
Slot   1:  1 x minecraft:stone_pickaxe
Slot   2:  1 x minecraft:wooden_axe
Slot   3:  1 x minecraft:stone_shovel
Slot   4:  1 x minecraft:crafting_table
Slot   5: 37 x minecraft:coal
Slot   6:  8 x minecraft:dirt
Slot  11:  2 x minecraft:oak_log
Slot  12:  5 x minecraft:cobblestone
Slot  13:  2 x minecraft:stick
Slot  28:  1 x minecraft:wooden_pickaxe

```

How about some **diamonds**?
Get 64 *blocks* of it in each one of your free inventory slots!

```pycon
>>> backup = mc.List[mc.Compound](inventory[:])  # soon just inventory.copy()
>>> free_slots = set(range(36)) - set(item['Slot'] for item in inventory)
>>> for slot in free_slots:
...     print(f"Adding 64 blocks of Diamond to inventory slot {slot}")
...     item = mc.Compound({
...         'Slot':  mc.Byte(slot),
...         'id':    mc.String('minecraft:diamond_block'),  # Sweet!
...         'Count': mc.Byte(64),  # Enough for you?
...     })
...     inventory.append(item)  # Yup, it's THAT simple!
...
Adding 64 blocks of Diamond to inventory slot 7
Adding 64 blocks of Diamond to inventory slot 8
Adding 64 blocks of Diamond to inventory slot 9
Adding 64 blocks of Diamond to inventory slot 10
Adding 64 blocks of Diamond to inventory slot 14
...
Adding 64 blocks of Diamond to inventory slot 35

>>> # Go on, we both know you want it. I won't judge you.
>>> world.save('data/tests/diamonds')

>>> # Revert it so it doesn't mess with other examples
>>> world.player.inventory = backup

```
Have fun, you millionaire!

More fun things to do:
```pycon
>>> chunks = world.entities[mc.OVERWORLD][0, 0]
>>> for chunk in chunks.values():
...     for entity in chunk.entities:
...         print(entity)
...
Chest Minecart at (  81,  18,  21)
Chest Minecart at (  80,  18,  37)
Chest Minecart at (   2,  38, 112)
Sheep at (  36,  70, 116)
Sheep at (  33,  69, 120)
Sheep at (  37,  70, 116)
Item: 3 String at (  14,  25, 152)
Item: 2 String at (  14,  25, 153)
Chicken at (  13,  64, 158)
Chicken at (  12,  64, 156)
Chicken at (   7,  64, 153)
Item: 1 String at (   0,  35, 167)
Cow at (   1,  65, 184)
Cow at (  11,  64, 186)
Chest Minecart at (  17,  32, 187)
Item: 3 String at (  39,  35, 195)
Donkey at (  56,  70, 202)
Donkey at (  57,  71, 203)
Donkey at (  56,  70, 201)
Chicken at (   6,  64, 217)

```

How about some NBT Explorer nostalgia?

```pycon
>>> mc.nbt_explorer(world.level)
⊟ Data: 42 entries
├──⊞ CustomBossEvents: 0 entries
├──⊟ DataPacks: 2 entries
│  ├──⊟ Disabled: 1 entry
│  │  ╰─── 0: Fabric Mods
│  ╰──⊟ Enabled: 1 entry
│     ╰─── 0: vanilla
...
├──⊟ Player: 37 entries
│  ├──⊟ abilities: 7 entries
│  │  ├─── flying: Byte(0)
...
│  │  ╰─── walkSpeed: Float(0.10000000149011612)
│  ├──⊟ Brain: 1 entry
│  │  ╰──⊞ memories: 0 entries
...
│  ├──⊟ Inventory: 11 entries
│  │  ├──⊟  0: 4 entries
│  │  │  ├──⊟ tag: 1 entry
│  │  │  │  ╰─── Damage: Int(0)
│  │  │  ├─── Count: Byte(1)
│  │  │  ├─── id: minecraft:stone_axe
│  │  │  ╰─── Slot: Byte(0)
...
│  │  ╰──⊟ 10: 4 entries
│  │     ├──⊟ tag: 1 entry
│  │     │  ╰─── Damage: Int(18)
│  │     ├─── Count: Byte(1)
│  │     ├─── id: minecraft:wooden_pickaxe
│  │     ╰─── Slot: Byte(28)
...
│  ├─── XpTotal: Int(37)
│  ╰──⊕ UUID: 4 entries
├──⊟ Version: 3 entries
│  ├─── Id: Int(2730)
│  ├─── Name: 1.17.1
│  ╰─── Snapshot: Byte(0)
...
├──⊞ ScheduledEvents: 0 entries
├──⊟ ServerBrands: 1 entry
│  ╰─── 0: fabric
├─── allowCommands: Byte(0)
...
├─── WanderingTraderSpawnDelay: Int(19200)
╰─── WasModded: Byte(1)

```
You want to click that tree, don't you? Sweet `Array` "icon" for `UUID`!

Test yourself all the examples in this document:

    python3 -m doctest -f -o ELLIPSIS -o NORMALIZE_WHITESPACE README.md
    git checkout data/

---
Contributing
------------

Patches are welcome! Fork, hack, request pull! Here is a succinct to-do list:

- **Better documentation**: Improve this `README`, document classes, methods and
  attributes, perhaps adding sphinx-like in-code documentation, possibly hosting
  at [Read the Docs](https://readthedocs.org/). Add more in-depth usage scenarios.

- **Installer**: Test and improve current `setup.cfg`, possibly uploading to Pypi.

- **Tests**: Expand [doctest](https://docs.python.org/3/library/doctest.html)
  usage, add at least [unittest](https://docs.python.org/3/library/unittest.html).

- **Semantics**: Give semantics to some NBT data, providing methods to manipulate
  blocks, entities and so on.

- **CLI**: Add a command-line interface for commonly used operations.

See the [To-Do List](./TODO.txt) for more updated technical information and
planned features.

If you find a bug or have any enhancement request, please open a
[new issue](https://github.com/MestreLion/mcworldlib/issues/new)


Author
------

Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>

License and Copyright
---------------------
```
Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>.

License GPLv3+: GNU GPL version 3 or later <http://gnu.org/licenses/gpl.html>.

This is free software: you are free to change and redistribute it.

There is NO WARRANTY, to the extent permitted by law.
```
