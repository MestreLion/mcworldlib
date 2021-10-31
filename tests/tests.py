#!/usr/bin/env python3

import io
import logging
import os.path
import sys

import mcworldlib as mc


logging.basicConfig(level=logging.DEBUG, format='%(levelname)-6s: %(message)s')


def load_world(name='data/New World'):
    """Common function for all methods"""
    return mc.load(sys.argv[1] if len(sys.argv) > 1 else name)


def load_region():
    filename = os.path.join(mc.MINECRAFT_SAVES_DIR, 'New World/region/r.1.1.mca')
    return mc.load_region(sys.argv[1] if len(sys.argv) > 1 else filename)


def show_region(r=None):
    r = r or load_region()
    for _, c in enumerate(r.values()):
        print(f'{c}\t{c!r}')
    print(repr(r))
    return r


def write_chunk():
    r = load_region()
    with io.BytesIO() as f:
        size = r[(0, 0)].write(f)
        print(size)
        print(f.getvalue())


def write_region():
    r = load_region()
    with io.BytesIO() as f:
        size = r.write(f)
        print(size)
        print(f.getvalue())


def save_region():
    r = show_region()
    r.save('teste.mca')
    r = mc.anvil.load_region('teste.mca')
    show_region(r)


def diamonds():
    import os
    from mcworldlib.anvil import RegionFile
    from nbtlib import String
    saves_dir = os.path.expanduser('~/.minecraft/saves/New World/region')
    found = False
    for file in os.listdir(saves_dir):
        if not file.endswith('.mca'): continue
        region = RegionFile.load(os.path.join(saves_dir, file))
        sections = 0
        for chunk in region.values():
            for section in chunk['']['Level']['Sections']:
                for block in section.get('Palette', []):
                    if block['Name'] == 'minecraft:grass_block':
                        block['Name'] = String('minecraft:diamond_block')
                        if 'Properties' in block:
                            del block['Properties']
                        sections += 1
                        found = True
                        break
        if sections:
            print(f'Sections with grass blocks found in {file}')
            region.save()
    if found:
        print(f'All grass blocks converted to diamonds. Happy "mining"!')


def new_diamonds():
    world = mc.load('New World')

    for item in world.level['Data']['Player']['Inventory']:
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
            print(f'All grass blocks converted to diamonds. Happy "mining"!')
            region.save()


def entities():
    r = load_region()
    for c in r.values():
        if c.data_root['Entities']:
            print(repr(c))
            print(repr(c.entities))
            for e in c.entities:
                print(e)
            break


def maps():
    w = load_world('MestreLion')
    r = w.regions[2, 1]
    print(r[11, 22].data_root['TileEntities'][32]['Items'][5])


def player_pos():
    w = load_world()
    print(w.player.get_chunk())


def blocks(w=None):
    if w is None:
        w = mc.load('New World')

    for chunk in [w.player.get_chunk()]:  # w.get_chunks(False):
        print(chunk)
        print()
        for Y, palette, indexes in chunk.get_blocks():
            print(f"SECTION Y={Y}")
            for i, p in enumerate(palette):
                bid = p['Name']
                props = f" {p['Properties']}" if p.get('Properties') else ""
                print(f"{i:2d} = {block_name(bid)} [{bid}]{props}")
            print()
            for y, sector_slice in enumerate(indexes, Y * mc.util.SECTION_HEIGHT):
                print(f"y={y}")
                print(sector_slice)
                print()
            print()
        print()


def block_name(bid):
    return bid.split(':', 1)[-1].replace('_', ' ').title()


def block_symbol(bid, length=3):
    name = block_name(bid)
    words = name.split()[:length]
    symbol = "".join(_[0] for _ in words)
    if len(words) < length:
        symbol += words[-1][1:1 + length - len(words)]
    return symbol


def chests():
    w = load_world('MestreLion')
    for chunk in [w.player.get_chunk()]:  # w.get_chunks(False):
        print(chunk)
        print()
        for pos in (
            (-9000, 53, -1510),
            (-8998, 53, -1512),
            (-8996, 53, -1510),
            (-8998, 53, -1508),
            (-8998, 51, -1510),
        ):
            b = w.get_block_at(pos)
            bid = b['Name']
            props = f" {b['Properties']}" if b.get('Properties') else ""
            print(f"{pos}: {block_name(bid)} [{bid}]{props}")


def github():
    world = load_world('MestreLion')
    block = world.get_block_at((100, 60, 100))
    print(block)


def inventory_diamonds(world=None, save=False):
    if not world: world = load_world()

    inventory = world.player.inventory

    # Easily loop each item as if the inventory were a list. In fact, it *is*!
    for item in inventory:
        print(f"Slot {item['Slot']:3}: {item['Count']:2} x {item['id']}")

    # free_slots = set(range(9, 36)) - set(item['Slot'] for item in inventory)
    free_slots = set(range(36)) - set(item['Slot'] for item in inventory)
    for slot in free_slots:
        print(f"Adding 64 blocks of Diamond to inventory slot {slot}")
        item = mc.Compound({
            'Slot': mc.Byte(slot),
            'id': mc.String('minecraft:diamond_block'),  # Sweet!
            'Count': mc.Byte(64),  # Enough for you?
        })
        inventory.append(item)  # yup, it's THAT simple!

    for slot in free_slots:
        item = mc.Compound(
            Slot=mc.Byte(slot),
            id=mc.String('minecraft:diamond_block'),
            Count=mc.Byte(64)
        )
        inventory.append(item)  # yup, it's THAT simple
        print(f"Added to inventory: {item}")

    if save:
        world.save()


def readme(world=None, save=False):
    if not world: world = load_world()
    inventory_diamonds(world=world, save=save)
    chunks = world.entities[mc.OVERWORLD][0, 0]
    for chunk in chunks.values():
        for entity in chunk.entities:
            print(entity)


def pretty():
    world = load_world()
    mc.pretty(world.regions)
    for region in world.regions.items():
        print(region)


def lost_maps():
    pass


def tree_tests():
    import mcworldlib.tree
    mcworldlib.tree.tests()


tree_tests()
