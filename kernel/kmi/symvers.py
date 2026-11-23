#!/usr/bin/env python3

# ======================================================
# 🔑 KMI — Exported Symbol CRC Extractor
# ======================================================
# Recovers the exported-symbol CRC table (Module.symvers equivalent) straight from a
# raw arm64 kernel Image by walking __ksymtab / __ksymtab_gpl and the __kcrctab pair
# that follows them. Usage: symvers.py <Image|boot.img> [output.tsv]

import struct
import sys
from array import array

import image

ENTRY_SIZE = 12
MIN_ENTRIES = 1000
IDENTIFIER_BYTES = frozenset(b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.")
MAX_NAME_LENGTH = 160
MAX_VALUE_OFFSET = 1 << 28


def read_identifier(data, position):
    if not 0 < position < len(data) or data[position - 1] in IDENTIFIER_BYTES:
        return None
    end = data.find(b"\0", position, position + MAX_NAME_LENGTH)
    if end <= position:
        return None
    name = data[position:end]
    return name.decode() if all(byte in IDENTIFIER_BYTES for byte in name) else None


def valid_entry(data, start):
    if start < 0 or start + ENTRY_SIZE > len(data):
        return None
    value, name_rel, namespace_rel = struct.unpack_from("<iii", data, start)
    if abs(value) > MAX_VALUE_OFFSET:
        return None
    name = read_identifier(data, start + 4 + name_rel)
    if name is None:
        return None
    namespace_position = start + 8 + namespace_rel
    if not 0 < namespace_position < len(data):
        return None
    if data[namespace_position] != 0 and read_identifier(data, namespace_position) is None:
        return None
    return name


def locate_anchor(data, symbol=b"module_layout"):
    needle = b"\0" + symbol + b"\0"
    cursor = data.find(needle)
    words = array("i")
    words.frombytes(data[:len(data) - len(data) % 4])
    while cursor != -1:
        string_position = cursor + 1
        for index in range(1, len(words)):
            if index * 4 + words[index] == string_position and valid_entry(data, (index - 1) * 4):
                return (index - 1) * 4
        cursor = data.find(needle, cursor + 1)
    raise ValueError("module_layout export not found")


def symbol_run(data, anchor):
    first = anchor
    while valid_entry(data, first - ENTRY_SIZE):
        first -= ENTRY_SIZE
    last = anchor
    while valid_entry(data, last + ENTRY_SIZE):
        last += ENTRY_SIZE
    names = [valid_entry(data, position) for position in range(first, last + ENTRY_SIZE, ENTRY_SIZE)]
    if len(names) < MIN_ENTRIES:
        raise ValueError("kernel symbol table too small")
    return first, names


def extract(data):
    anchor = locate_anchor(data)
    first, names = symbol_run(data, anchor)
    split = next((index for index in range(1, len(names)) if names[index] < names[index - 1]), len(names))
    crc_start = first + len(names) * ENTRY_SIZE
    crcs = struct.unpack_from(f"<{len(names)}I", data, crc_start)
    return dict(zip(names, crcs)), split


def main():
    data = image.load_kernel(sys.argv[1])
    table, split = extract(data)
    print(f"{len(table)} symbols (gpl split at {split}), module_layout={table['module_layout']:#010x}", file=sys.stderr)
    lines = [f"{crc:#010x}\t{name}" for name, crc in sorted(table.items())]
    output = "\n".join(lines) + "\n"
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w") as handle:
            handle.write(output)
    else:
        sys.stdout.write(output)


if __name__ == "__main__":
    main()
