#!/usr/bin/env python3

from collections import Counter
from pprint import pformat

import mcworldlib as mc
world = mc.load("~/install/minecraft/saves/Skyblock 2.1")
chunk = world.regions[mc.OVERWORLD][0, -1][0, 31]

all_blocks = Counter()
for chunk in world.get_chunks(progress=False):
    for section in chunk.get_sections():
        if blocks := [
            mc.util.short_key(block["Name"]) for block in section.get_blocks().values()
        ]:
            print(f"{chunk!r}:\n\t{pformat(Counter(blocks))}")
            all_blocks.update(blocks)

print(f"TOTAL:\n\t{pformat(all_blocks)}")

all_blocks = Counter()
for pos, block in world.get_blocks(progress=False):
    name = mc.util.short_key(block["Name"])
    if name != "air":
        print(f"{pos}: {name}")
    all_blocks.update([name])
print(f"TOTAL:\n\t{pformat(all_blocks)}")
