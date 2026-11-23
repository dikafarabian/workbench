#!/usr/bin/env python3

# ======================================================
# 🧩 KMI — Kernel Module Reader
# ======================================================
# Minimal ELF64 reader for .ko files: imported symbols with CRCs and exported symbols.

import struct

VERSION_ENTRY_SIZE = 64
EXPORT_PREFIX = "__ksymtab_"
NOT_EXPORTS = {"__ksymtab_strings"}


def _sections(data):
    shoff = struct.unpack_from("<Q", data, 0x28)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 0x3A)
    raw = []
    for index in range(shnum):
        base = shoff + index * shentsize
        name, kind = struct.unpack_from("<II", data, base)
        offset, size, link = struct.unpack_from("<QQI", data, base + 0x18)
        raw.append((name, kind, offset, size, link))
    names_offset = raw[shstrndx][2]
    result = {}
    for name, kind, offset, size, link in raw:
        label = data[names_offset + name:data.index(b"\0", names_offset + name)].decode()
        result[label] = (kind, offset, size, link, raw)
    return result


def imports(data):
    sections = _sections(data)
    if "__versions" not in sections:
        return []
    _, offset, size, _, _ = sections["__versions"]
    entries = []
    for position in range(offset, offset + size, VERSION_ENTRY_SIZE):
        crc = struct.unpack_from("<Q", data, position)[0] & 0xFFFFFFFF
        name = data[position + 8:position + VERSION_ENTRY_SIZE].split(b"\0")[0].decode()
        entries.append((name, crc))
    return entries


def exports(data):
    sections = _sections(data)
    if ".symtab" not in sections:
        return set()
    _, offset, size, link, raw = sections[".symtab"]
    strings_offset = raw[link][2]
    result = set()
    for position in range(offset, offset + size, 24):
        name_index = struct.unpack_from("<I", data, position)[0]
        start = strings_offset + name_index
        name = data[start:data.index(b"\0", start)].decode()
        if name.startswith(EXPORT_PREFIX) and name not in NOT_EXPORTS:
            result.add(name[len(EXPORT_PREFIX):])
    return result
