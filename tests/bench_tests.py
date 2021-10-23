import io
import hashlib
import json
import sys
import time
# import timeit  # Soon...
import typing as t
import zlib

import msgpack
import msgpack_numpy
msgpack_numpy.patch()
del msgpack_numpy
import ujson
import xxhash

import mcworldlib as mc


def measure(f: t.Callable, *a, **k):
    """Lame wall time"""
    def info(data):
        out = f"{type(data)}"
        try: out += f" ({len(data):,})"
        except TypeError: pass
        return out
    t0 = time.time()
    result = f(*a, **k)
    t1 = time.time()
    print(f"{t1 - t0: 8.4f}\t{f.__qualname__}\t-> {info(result)}")
    return result


def loadfile(path):
    """Get disk I/O out of the equation"""
    with open(path, 'rb') as f:
        data = measure(f.read)
    return io.BytesIO(data)


# ------------------------------------------------------
# Hashing

# Slow for non-crypto, weak for crypto. Poor MD5!
def md5(data: bytes) -> bytes:
    return hashlib.md5(data).digest()


# For xxHash, always using the one-shot versions,
# faster than xxh*(data).digest()

def xxh64(data: bytes) -> bytes:
    return xxhash.xxh64_digest(data)


def xxh3(data: bytes) -> bytes:
    return xxhash.xxh3_64_digest(data)


def xxh128(data: bytes) -> bytes:
    return xxhash.xxh3_128_digest(data)


def obj_hash(obj: object) -> int:
    """Hash anything that contains only list, dict and hashable types"""
    def freeze(o):
        if isinstance(o, dict):
            return frozenset({k: freeze(v) for k, v in o.items()}.items())
        if isinstance(o, list):
            return tuple([freeze(v) for v in o])
        return o
    return hash(freeze(obj))


# --------------------------------------------------------------------------
# Serializers

def mpack(obj: object) -> bytes:
    return msgpack.packb(obj)


def write(tag: mc.AnyTag) -> bytes:
    f = io.BytesIO()
    tag.write(f)
    return f.getvalue()


def snbt(data: mc.AnyTag) -> str:
    return str(data)


def jsonobj(obj: object) -> str:
    return json.dumps(obj)


def jsontag(tag: mc.AnyTag) -> str:
    obj = measure(unpack, tag)
    return measure(json.dumps, obj)


def ultrajson(obj: object) -> str:
    return ujson.dumps(obj)


def objjson(_obj: object) -> bytes: ...  # ojson
def picking(_obj: object) -> bytes: ...
def walk(_tag: mc.AnyTag) -> t.Tuple: ...


# --------------------------------------------------------------------------
# Data Sources

def load_region() -> mc.RegionFile:
    filename = '../data/r.2.4.mca'
    f = measure(loadfile, filename)
    return measure(mc.RegionFile.parse, f, filename=filename)


def load_mcc() -> mc.Root:
    # Not using File.load_mcc() directly to decouple zlib and parse timings
    data = measure(loadfile, '../data/c.-96.-8.mcc').getvalue()
    data = measure(zlib.decompress, data)
    return measure(mc.Root.parse, io.BytesIO(data))


def unpack(tag: mc.AnyTag) -> object:
    ...
    return tag


# --------------------------------------------------------------------------
# Main

def main():
    print("Collecting data")
    chunk: mc.Root = measure(load_mcc)
    region: t.Dict[mc.ChunkPos, mc.RegionChunk] = measure(load_region)

    # A "SuperCompound" of all region chunks just to test nbt.write
    chunks: t.Dict[str, mc.Root]  # key = str(chunk.pos)
    chunks = measure(mc.Root, {str(k): mc.Compound(v) for k, v in region.items()})

    sources = (
        ("MCC Chunk", chunk),
        ("SuperCompound", chunks)
    )

    if '--verify' in sys.argv:
        print("\nIntegrity checks")
        for label, data in sources:
            assert msgpack.unpackb(mpack(data)) == data
            print(f"OK: msg_pack/unpack({label})")
            assert data.parse(io.BytesIO(write(data))) == data
            print(f"OK: write/parse({label})")

    print("\nSerializing tests")
    for label, data in sources:
        print(label)
        # Already ordered from Best to Worst
        measure(mpack, data)
        measure(write, data)
        # measure(snbt, data)

    print("\nHashing tests")
    for label, data in ((_[0], mpack(_[1])) for _ in sources):
        print(label)
        measure(xxh3, data)
        measure(xxh128, data)
        measure(xxh64, data)
        measure(hash, data)
        measure(md5, data)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass

# Collecting data
#   0.0015	BufferedReader.read	-> <class 'bytes'> (3,379,200)
#   0.0015	loadfile	-> <class '_io.BytesIO'>
#   0.0364	decompress	-> <class 'bytes'> (24,460,279)
#   5.8933	Chunk.parse	-> <class 'mcworldlib.chunk.Chunk'> (2)
#   5.9327	load_mcc	-> <class 'mcworldlib.chunk.Chunk'> (2)
#   0.0027	BufferedReader.read	-> <class 'bytes'> (7,405,568)
#   0.0028	loadfile	-> <class '_io.BytesIO'>
#   1.5220	AnvilFile.parse	-> <class 'mcworldlib.anvil.RegionFile'> (1,024)
#   1.5248	load_region	-> <class 'mcworldlib.anvil.RegionFile'> (1,024)
#   0.0000	Compound	-> <class 'nbtlib.tag.Compound'> (1,024)
#
# Serializing tests
# MCC Chunk
#   0.2101	mpack	-> <class 'bytes'> (21,875,554)
#   2.0058	write	-> <class 'bytes'> (24,460,279)
#   4.0491	snbt	-> <class 'str'> (31,037,955)
# SuperCompound
#   0.1697	mpack	-> <class 'bytes'> (39,606,077)
#   1.0542	write	-> <class 'bytes'> (5,089,152)
#  38.8854	snbt	-> <class 'str'> (90,493,140)
#
# Hashing tests
# MCC Chunk
#   0.0012	xxh3	-> <class 'bytes'> (8)
#   0.0013	xxh128	-> <class 'bytes'> (16)
#   0.0022	xxh64	-> <class 'bytes'> (8)
#   0.0083	hash	-> <class 'int'>
#   0.0289	md5	-> <class 'bytes'> (16)
# SuperCompound
#   0.0022	xxh3	-> <class 'bytes'> (8)
#   0.0023	xxh128	-> <class 'bytes'> (16)
#   0.0032	xxh64	-> <class 'bytes'> (8)
#   0.0150	hash	-> <class 'int'>
#   0.0523	md5	-> <class 'bytes'> (16)
