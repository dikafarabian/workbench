#!/usr/bin/env python3

# ======================================================
# 🖼️ KMI — Kernel and Boot Image Loader
# ======================================================
# Extracts the raw kernel from Image / lz4-legacy / gzip / Android boot images (v0-v4)
# and the module files from a vendor_boot ramdisk.

import gzip
import os
import re
import struct

import lz4block as lz4

BOOT_MAGIC = b"ANDROID!"
VENDOR_BOOT_MAGIC = b"VNDRBOOT"
RELEASE_PATTERN = re.compile(rb"Linux version (\S+)")
KMI_TAG_PATTERN = re.compile(r"android\d+-\d+")


def unpack(data):
    if lz4.is_legacy(data):
        return lz4.decompress_legacy(data)
    if data[:2] == b"\x1f\x8b":
        return gzip.decompress(data)
    return data


def load_kernel(path):
    with open(path, "rb") as handle:
        data = handle.read()
    if data[:8] == BOOT_MAGIC:
        version = struct.unpack_from("<I", data, 40)[0]
        page = 4096 if version >= 3 else struct.unpack_from("<I", data, 36)[0]
        size = struct.unpack_from("<I", data, 8)[0]
        data = data[page:page + size]
    return unpack(data)


def kernel_release(image):
    match = RELEASE_PATTERN.search(image)
    return match.group(1).decode() if match else ""


def kmi_tag(release):
    match = KMI_TAG_PATTERN.search(release)
    return match.group(0) if match else ""


def cpio_files(archive, wanted=(".ko",)):
    files, pos = {}, 0
    while pos + 110 <= len(archive) and archive[pos:pos + 6] == b"070701":
        fields = [int(archive[pos + 6 + 8 * index:pos + 14 + 8 * index], 16) for index in range(13)]
        mode, size, name_size = fields[1], fields[6], fields[11]
        name = archive[pos + 110:pos + 110 + name_size - 1].decode()
        pos = (pos + 110 + name_size + 3) & ~3
        if name == "TRAILER!!!":
            break
        if mode & 0o170000 == 0o100000 and name.endswith(wanted):
            files[name] = archive[pos:pos + size]
        pos = (pos + size + 3) & ~3
    return files


def vendor_boot_modules(path):
    with open(path, "rb") as handle:
        data = handle.read()
    if data[:8] != VENDOR_BOOT_MAGIC:
        raise ValueError(f"{path}: not a vendor_boot image")
    version, page = struct.unpack_from("<II", data, 8)
    ramdisk_size = struct.unpack_from("<I", data, 24)[0]
    header_size = struct.unpack_from("<I", data, 28 + 2048 + 4 + 16)[0]
    dtb_size = struct.unpack_from("<I", data, 28 + 2048 + 4 + 16 + 4)[0]
    align = lambda value: (value + page - 1) // page * page
    ramdisk = data[align(header_size):align(header_size) + ramdisk_size]
    fragments = [(0, ramdisk_size)]
    if version >= 4:
        table_offset = align(header_size) + align(ramdisk_size) + align(dtb_size)
        count, entry_size = struct.unpack_from("<II", data, 28 + 2048 + 4 + 16 + 4 + 4 + 8 + 4)
        fragments = []
        for index in range(count):
            size, offset = struct.unpack_from("<II", data, table_offset + index * entry_size)
            fragments.append((offset, size))
    modules = {}
    for offset, size in fragments:
        archive = unpack(ramdisk[offset:offset + size])
        modules.update(cpio_files(archive))
    return {os.path.basename(name): content for name, content in modules.items()}
