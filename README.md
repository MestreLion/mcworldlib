# mcworldlib
Yet another library to manipulate Minecraft data,
inspired by [pymclevel](https://github.com/mcedit/pymclevel),
building on top of the amazing [nbtlib](https://github.com/vberlier/nbtlib).

```pycon
>>> import mcworldlib as mc
>>> world = mc.load('New World')  # Use level.dat path, save folder or World name.
>>> mc.pretty(world)  # Many classes have a pretty print. In some cases, their NBT data.
INFO  : Loading World 'New World': /home/rodrigo/.minecraft/saves/New World
{
    "": {
        Data: {
            WanderingTraderSpawnChance: 25,
            BorderCenterZ: 0.0d,
            Difficulty: 2b,
            BorderSizeLerpTime: 0L,
            raining: 0b,
            Time: 128L,
            GameType: 0,
            ServerBrands: ["fabric"],
            BorderCenterX: 0.0d,
            BorderDamagePerBlock: 0.2d,
            BorderWarningBlocks: 5.0d,
            ...
            ScheduledEvents: [],
            LevelName: "New World",
            BorderSize: 60000000.0d,
            DataVersion: 2730,
            DataPacks: {
                Enabled: ["vanilla", "Fabric Mods"],
                Disabled: []
            }
        }
    }
}

>>> mc.pretty(world.regions)  # Regions are a dictionary of coordinates and objects
{   (-2, -1): '/home/rodrigo/.minecraft/saves/New World/region/r.-2.-1.mca',
    (-2, 0): '/home/rodrigo/.minecraft/saves/New World/region/r.-2.0.mca',
    (-2, 1): '/home/rodrigo/.minecraft/saves/New World/region/r.-2.1.mca',
    ...
    (1, 0): '/home/rodrigo/.minecraft/saves/New World/region/r.1.0.mca',
    (1, 1): '/home/rodrigo/.minecraft/saves/New World/region/r.1.1.mca',
    (1, 2): '/home/rodrigo/.minecraft/saves/New World/region/r.1.2.mca'}

>>> region = world.regions[1,0]  # A Region is a dictionary of chunks
>>> mc.pretty(region)
{
    (0, 0): <Chunk [0, 0] in world at (32, 0) saved on 2021-10-08 07:38:33>,
    (1, 0): <Chunk [1, 0] in world at (33, 0) saved on 2021-10-08 07:38:33>,
    (2, 0): <Chunk [2, 0] in world at (34, 0) saved on 2021-10-08 07:38:33>,
    ...
    (29, 31): <Chunk [29, 31] in world at (61, 31) saved on 2021-10-08 07:39:35>,
    (30, 31): <Chunk [30, 31] in world at (62, 31) saved on 2021-10-08 07:39:31>,
    (31, 31): <Chunk [31, 31] in world at (63, 31) saved on 2021-10-08 07:39:27>
}

>>> chunk = region[0,1]
>>> mc.pretty(chunk)  # alternatively, print(chunk.pretty())
{
    "": {
        Level: {
            Status: "full",
            zPos: 1,
            LastUpdate: 63326L,
            InhabitedTime: 0L,
            xPos: 32,
            TileEntities: [],
            isLightOn: 1b,
            TileTicks: [],
            ...
            Entities: []
        },
        DataVersion: 2730
    }
}

>>> for chunk in (                          # You can fetch a chunk by several ways:
...     world.get_chunk_at((120, 63, 42)),  # At an absolute (X, Y, Z) coordinate
...     world.player.get_chunk(),           # The chunk the player is in
... ):
...     print(chunk)
...
<Chunk [7, 2] in world at (7, 2) saved on 2021-10-08 07:41:44>
<Chunk [29, 3] in world at (29, 35) saved on 2021-10-08 07:41:45>

>>> block = world.get_block_at((100, 60, 100))  # Get the block info at any coordinate!
>>> print(block)
{Name: "minecraft:sand"}
```

Reading and modifying the Player's inventory is quite easy:
```python
import mcworldlib as mc
world = mc.load('New World')
inventory = world.player.inventory
# The above is a shortcut for world.root['Data']['Player']['Inventory']

# Easily loop each item as if the inventory were a list. In fact, it *is*!
for item in inventory:
    print(f"Slot {item['Slot']:3}: {item['Count']:2} x {item['id']}")
```
```
INFO  : Loading World 'New World': /home/rodrigo/.minecraft/saves/New World
Slot   0:  1 x minecraft:diamond_sword
Slot   1:  1 x minecraft:bow
Slot   2:  1 x minecraft:diamond_pickaxe
Slot   3:  1 x minecraft:diamond_pickaxe
Slot   8: 64 x minecraft:torch
Slot   9:  1 x minecraft:filled_map
Slot  17:  8 x minecraft:arrow
Slot  26: 35 x minecraft:birch_log
Slot  27:  1 x minecraft:diamond_axe
Slot  28:  1 x minecraft:diamond_shovel
Slot  35:  5 x minecraft:ender_chest
Slot 100:  1 x minecraft:diamond_boots
Slot 101:  1 x minecraft:diamond_leggings
Slot 102:  1 x minecraft:diamond_chestplate
Slot 103:  1 x minecraft:diamond_helmet
Slot -106: 62 x minecraft:cooked_beef
```

How about some **diamonds**?
Get 64 *blocks* of it in each one of your free inventory slots!

```python
free_slots = set(range(9, 36)) - set(item['Slot'] for item in inventory)
for slot in free_slots:
    item = mc.Compound({
        'Slot':  mc.Byte(slot),
        'id':    mc.String('minecraft:diamond_block'),  # Sweet!
        'Count': mc.Byte(64),  # Enough for you?
    })
    inventory.append(item)  # yup, it's THAT simple!

world.save()
```
Have fun, you millionaire!
