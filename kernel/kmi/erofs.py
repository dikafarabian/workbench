#!/usr/bin/env python3

# ======================================================
# 📦 KMI — Minimal EROFS Reader
# ======================================================
# Reads flat and compact-LZ4 EROFS images such as
# vendor_dlkm.img and system_dlkm.img. Compressed or chunked files are
# reported and skipped.

import struct
import sys

import lz4block

SUPER_OFFSET = 1024
SUPER_MAGIC = 0xE0F5E1E2
LAYOUT_FLAT_PLAIN = 0
LAYOUT_FLAT_INLINE = 2
LAYOUT_COMPRESSED_COMPACT = 3
CLUSTER_PLAIN = 0
CLUSTER_HEAD1 = 1
CLUSTER_NONHEAD = 2
CLUSTER_HEAD2 = 3
ADVISE_COMPACTED_2B = 0x1
ADVISE_BIG_PCLUSTER = 0x6
TYPE_REGULAR = 1
TYPE_DIRECTORY = 2


class ErofsImage:
    def __init__(self, path):
        with open(path, "rb") as handle:
            self.data = handle.read()
        magic = struct.unpack_from("<I", self.data, SUPER_OFFSET)[0]
        if magic != SUPER_MAGIC:
            raise ValueError(f"{path}: not an EROFS image")
        self.block_bits = self.data[SUPER_OFFSET + 12]
        self.block_size = 1 << self.block_bits
        self.root_nid = struct.unpack_from("<H", self.data, SUPER_OFFSET + 14)[0]
        self.meta_block = struct.unpack_from("<I", self.data, SUPER_OFFSET + 40)[0]
        self.skipped = []

    def inode(self, nid):
        offset = self.meta_block * self.block_size + nid * 32
        fmt = struct.unpack_from("<H", self.data, offset)[0]
        xattr_count = struct.unpack_from("<H", self.data, offset + 2)[0]
        mode = struct.unpack_from("<H", self.data, offset + 4)[0]
        extended = fmt & 1
        layout = (fmt >> 1) & 7
        if extended:
            size = struct.unpack_from("<Q", self.data, offset + 8)[0]
            raw_block = struct.unpack_from("<I", self.data, offset + 16)[0]
            header = 64
        else:
            size = struct.unpack_from("<I", self.data, offset + 8)[0]
            raw_block = struct.unpack_from("<I", self.data, offset + 16)[0]
            header = 32
        xattr_size = 12 + (xattr_count - 1) * 4 if xattr_count else 0
        return {"offset": offset, "mode": mode, "layout": layout, "size": size,
                "raw_block": raw_block, "tail": offset + header + xattr_size}

    def read(self, nid):
        node = self.inode(nid)
        size, layout = node["size"], node["layout"]
        if layout == LAYOUT_FLAT_PLAIN:
            start = node["raw_block"] * self.block_size
            return self.data[start:start + size]
        if layout == LAYOUT_FLAT_INLINE:
            full = (size // self.block_size) * self.block_size
            start = node["raw_block"] * self.block_size
            tail = size - full
            return self.data[start:start + full] + self.data[node["tail"]:node["tail"] + tail]
        if layout == LAYOUT_COMPRESSED_COMPACT:
            return self.read_compact(node)
        return None

    def compact_heads(self, node):
        header = (node["tail"] + 7) & ~7
        advise = struct.unpack_from("<H", self.data, header + 4)[0]
        if advise & ADVISE_BIG_PCLUSTER:
            return None
        lcluster_bits = self.block_bits + (self.data[header + 7] & 7)
        if lcluster_bits != 12:
            return None
        base_offset = header + 8
        total = -(-node["size"] // self.block_size)
        initial_4b = (32 - base_offset % 32) // 4
        if initial_4b == 8:
            initial_4b = 0
        compact_2b = ((total - initial_4b) // 16) * 16 if advise & ADVISE_COMPACTED_2B and initial_4b < total else 0
        lobits = max(lcluster_bits, 12)
        heads = []
        for lcn in range(total):
            index, shift = lcn, 2
            position = base_offset
            if index < initial_4b:
                position += index * 4
            else:
                position += initial_4b * 4
                index -= initial_4b
                if index < compact_2b:
                    shift = 1
                    position += index * 2
                else:
                    position += compact_2b * 2 + (index - compact_2b) * 4
            vcnt = 2 if shift == 2 else 16
            pack = vcnt << shift
            pack_base = position - position % pack
            slot = (position - pack_base) >> shift
            encode_bits = (pack - 4) * 8 // vcnt

            def decode(entry):
                value = struct.unpack_from("<I", self.data, pack_base + (encode_bits * entry) // 8)[0] >> ((encode_bits * entry) & 7)
                return value & ((1 << lobits) - 1), (value >> lobits) & 3

            offset, kind = decode(slot)
            if kind == CLUSTER_NONHEAD:
                continue
            blocks = 1
            cursor = slot
            while cursor > 0:
                cursor -= 1
                value, entry_kind = decode(cursor)
                if entry_kind == CLUSTER_NONHEAD:
                    cursor -= value
                if cursor >= 0:
                    blocks += 1
            block = struct.unpack_from("<I", self.data, pack_base + pack - 4)[0] + blocks
            heads.append((lcn * self.block_size + offset, kind, block))
        return heads

    def read_compact(self, node):
        heads = self.compact_heads(node)
        if heads is None:
            return None
        output = bytearray()
        for index, (start, kind, block) in enumerate(heads):
            end = heads[index + 1][0] if index + 1 < len(heads) else node["size"]
            raw = self.data[block * self.block_size:(block + 1) * self.block_size]
            if kind == CLUSTER_PLAIN:
                output += raw[:end - start]
            else:
                output += lz4block.decompress_block(raw.lstrip(b"\0"))[:end - start]
        return bytes(output) if len(output) == node["size"] else None

    def entries(self, nid):
        raw = self.read(nid)
        result = []
        for block_start in range(0, len(raw), self.block_size):
            block = raw[block_start:block_start + self.block_size]
            first_name = struct.unpack_from("<H", block, 8)[0]
            count = first_name // 12
            records = [struct.unpack_from("<QHBB", block, index * 12) for index in range(count)]
            for index, (child, name_off, kind, _) in enumerate(records):
                end = records[index + 1][1] if index + 1 < count else len(block)
                name = block[name_off:end].split(b"\0")[0].decode(errors="replace")
                if name not in (".", ".."):
                    result.append((name, child, kind))
        return result

    def walk(self, nid=None, prefix=""):
        nid = self.root_nid if nid is None else nid
        for name, child, kind in self.entries(nid):
            path = f"{prefix}/{name}" if prefix else name
            if kind == TYPE_DIRECTORY:
                yield from self.walk(child, path)
            elif kind == TYPE_REGULAR:
                yield path, child


def extract_files(image_path, suffixes=(".ko",), extras=("modules.load", "modules.dep")):
    image = ErofsImage(image_path)
    files = {}
    for path, nid in image.walk():
        base = path.rsplit("/", 1)[-1]
        if base.endswith(suffixes) or base in extras:
            content = image.read(nid)
            if content is None:
                image.skipped.append(path)
            else:
                files[path] = content
    return files, image.skipped


if __name__ == "__main__":
    found, skipped = extract_files(sys.argv[1])
    print(f"files: {len(found)} | skipped (compressed): {len(skipped)}")
    for path in sorted(found)[:10]:
        print(f"  {path} ({len(found[path])} bytes)")
