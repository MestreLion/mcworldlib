# mcworldlib
Yet another library to manipulate Minecraft data, inspired by pymclevel

```py
>>> import mcworldlib as mc
>>> world = mc.load('New World')
>>> mc.pretty(world)
{
    "": {
        Data: {
            WanderingTraderSpawnChance: 75,
            RandomSeed: 1593845888518578062L,
            generatorName: "default",
            BorderCenterZ: 0.0d,
            Difficulty: 2b,
            BorderSizeLerpTime: 0L,
            raining: 0b,
            DimensionData: {
                1: {
                    DragonFight: {
                        Gateways: [16, 15, 7, 8, 5, 18, 14, 0, 11, 17, 6, 19, 13, 4, 12, 10, 3, 2, 1, 9],
                        DragonKilled: 1b,
                        PreviouslyKilled: 1b
                    }
                }
            },
            Time: 119768L,
            GameType: 0,
            MapFeatures: 1b,
...
>>> mc.pretty(world.regions)
{   (-2, -3): <RegionFile(r.-2.-3.mca: 242 chunks)>,
    (-2, -2): <RegionFile(r.-2.-2.mca: 443 chunks)>,
    (-2, -1): <RegionFile(r.-2.-1.mca: 416 chunks)>,
    (-2, 0): <RegionFile(r.-2.0.mca: 321 chunks)>,
    (-1, -3): <RegionFile(r.-1.-3.mca: 576 chunks)>,
    (-1, -2): <RegionFile(r.-1.-2.mca: 1024 chunks)>,
    (-1, -1): <RegionFile(r.-1.-1.mca: 1024 chunks)>,
    (-1, 0): <RegionFile(r.-1.0.mca: 768 chunks)>,
    (0, -3): <RegionFile(r.0.-3.mca: 405 chunks)>,
    (0, -2): <RegionFile(r.0.-2.mca: 1013 chunks)>,
    (0, -1): <RegionFile(r.0.-1.mca: 1024 chunks)>,
    (0, 0): <RegionFile(r.0.0.mca: 637 chunks)>,
    (1, -2): <RegionFile(r.1.-2.mca: 56 chunks)>,
    (1, -1): <RegionFile(r.1.-1.mca: 64 chunks)>,
    (1, 0): <RegionFile(r.1.0.mca: 3 chunks)>}

>>> region = world.regions[1,0]
>>> mc.pretty(region)
{
    (0, 0): <Chunk [0, 0] in world at (32, 0) saved on 2019-12-11 08:39:51>,
    (1, 0): <Chunk [1, 0] in world at (33, 0) saved on 2019-12-11 08:39:44>,
    (0, 1): <Chunk [0, 1] in world at (32, 1) saved on 2019-12-11 08:39:51>
}

>>> chunk = region[0,1]
>>> mc.pretty(chunk)
{
    "": {
        Level: {
            Status: "structure_starts",
            zPos: 1,
            LastUpdate: 41328L,
            InhabitedTime: 0L,
            xPos: 32,
            Heightmaps: {},
            TileEntities: [],
            Entities: [],
...
```

Another not so noble usage example:

```
import mcworldlib as mc

world = mc.load('New World')

for item in world['']['Data']['Player']['Inventory']:
    item['id'] = mc.String('minecraft:diamond_block')
    item['Count'] = mc.Byte(64)

world.save()

for region in world.regions.values():
    found = False
    for chunk in region.values():
        for section in chunk['']['Level']['Sections']:
            for block in section.get('Palette', []):
                if block['Name'] == 'minecraft:grass_block':
                    block['Name'] = mc.String('minecraft:diamond_block')
                    if 'Properties' in block:
                        del block['Properties']
                    found = True
                    break
    if found:
        region.save()
```
