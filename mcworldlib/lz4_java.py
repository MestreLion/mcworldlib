# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>
# first implemented by Commandcracker

"""Lz4-Java Block format

Exported items:
    compress    -- Compress data using LZ4 with the lz4-java custom block header
    decompress  -- Decompress data compressed with the lz4-java block format
    xxhash32    -- Compute a 32-bit xxHash checksum compatible with lz4-java's hashing scheme
"""

# For a quick explanation of LZ4-Java in Minecraft, see:
# https://minecraft.wiki/w/Minecraft_Wiki:Projects/wiki.vg_merge/Map_Format#LZ4_Compression

# For detailed information on the LZ4 block format:
# https://github.com/lz4/lz4/blob/dev/doc/lz4_Block_format.md

__all__ = [
    'compress',
    'decompress',
    'xxhash32'
]

import struct

import lz4.block
import xxhash

XXHASH_SEED = 0x9747b28c
MAGIC = b"LZ4Block"
COMPRESSION_METHOD_LZ4 = 0x20
COMPRESSION_METHOD_RAW = 0x10
DEFAULT_COMPRESSION_LEVEL = 6

class LZ4JCompressionError(IOError):
    pass

def compress(data: bytes, compression_level: int = DEFAULT_COMPRESSION_LEVEL) -> bytes:
    """
    Compresses data in the lz4-java block format

    Vanilla Minecraft is always using compression level 6,
    so we don't need to implement "compressionLevel" to decide which to use

    Reference implementation:
        https://github.com/lz4/lz4-java/blob/master/src/java/net/jpountz/lz4/LZ4BlockOutputStream.java
    """
    # Don't include store_size otherwise it will add an <I32 with the file size at the start
    compressed = lz4.block.compress(data, compression=compression_level, store_size=False)
    compressed_len = len(compressed)
    decompressed_len = len(data)
    checksum = xxhash32(data)

    if compressed_len >= decompressed_len:
        token = COMPRESSION_METHOD_RAW | compression_level
        compressed_len = decompressed_len
        compressed = data
    else:
        token = COMPRESSION_METHOD_LZ4 | compression_level

    header = (
        MAGIC +
        struct.pack("B", token) +
        struct.pack("<i", compressed_len) +
        struct.pack("<i", decompressed_len) +
        struct.pack("<i", checksum)
    )

    return header + compressed


def decompress(data: bytes, verify_hash: bool = True) -> bytes:
    """
    Decompresses data encoded in the lz4-java block format

    Reference implementation:
        https://github.com/lz4/lz4-java/blob/master/src/java/net/jpountz/lz4/LZ4BlockInputStream.java
    """
    if not data.startswith(MAGIC):
        raise LZ4JCompressionError("Missing LZ4Block magic header.")

    token = struct.unpack("B", data[8:9])[0]
    compression_method = token & 0xF0
    compressed_len = struct.unpack("<i", data[9:13])[0]
    decompressed_len = struct.unpack("<i", data[13:17])[0]
    checksum_expected = struct.unpack("<i", data[17:21])[0]
    read_data = data[21:21+compressed_len]
    read_data_len = len(read_data)

    if compression_method == COMPRESSION_METHOD_LZ4:
        if read_data_len != compressed_len:
            raise LZ4JCompressionError("Truncated compressed data.")

        final_data = lz4.block.decompress(read_data, uncompressed_size=decompressed_len)
    elif compression_method == COMPRESSION_METHOD_RAW:
        if read_data_len != decompressed_len and read_data_len != compressed_len:
            raise LZ4JCompressionError("Truncated compressed data.")

        final_data = read_data
    else:
        raise LZ4JCompressionError("Unsupported compression method.")

    if verify_hash:
        checksum_actual = xxhash32(final_data)

        if checksum_actual != checksum_expected:
            raise LZ4JCompressionError(f"Checksum mismatch: expected {checksum_expected:#x}, got {checksum_actual:#x}")

    return final_data


def xxhash32(data: bytes) -> int:
    """
    Computes a 32-bit xxHash of the given data using the LZ4-Java hash seed and
    returns it as LZ4-Java does, by clearing the highest 4 bits
    and keeping only the lower 28 bits of the hash value.
    """
    return xxhash.xxh32(data, seed=XXHASH_SEED).intdigest() & 0x0FFFFFFF
