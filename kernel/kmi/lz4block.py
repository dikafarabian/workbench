#!/usr/bin/env python3

# ======================================================
# 🗜️ KMI — Pure Python LZ4
# ======================================================
# Block and legacy-frame decoders, so the KMI tooling needs no third-party packages.

import struct

LEGACY_MAGIC = 0x184C2102
LEGACY_BLOCK_LIMIT = 8 << 20


def decompress_block(source):
    output = bytearray()
    pos, end = 0, len(source)
    while pos < end:
        token = source[pos]
        pos += 1
        literals = token >> 4
        if literals == 15:
            while True:
                extra = source[pos]
                pos += 1
                literals += extra
                if extra != 255:
                    break
        output += source[pos:pos + literals]
        pos += literals
        if pos >= end:
            break
        offset = source[pos] | (source[pos + 1] << 8)
        pos += 2
        length = token & 15
        if length == 15:
            while True:
                extra = source[pos]
                pos += 1
                length += extra
                if extra != 255:
                    break
        length += 4
        start = len(output) - offset
        if offset == 0 or start < 0:
            raise ValueError("corrupt lz4 block")
        if offset >= length:
            output += output[start:start + length]
        else:
            pattern = bytes(output[start:])
            output += (pattern * (length // offset + 1))[:length]
    return bytes(output)


def decompress_legacy(data):
    output = bytearray()
    pos = 4
    while pos + 4 <= len(data):
        size = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        if size == LEGACY_MAGIC:
            continue
        if size == 0 or pos + size > len(data):
            break
        output += decompress_block(data[pos:pos + size])
        pos += size
    return bytes(output)


def is_legacy(data):
    return data[:4] == struct.pack("<I", LEGACY_MAGIC)
