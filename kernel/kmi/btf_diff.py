#!/usr/bin/env python3

# ======================================================
# 🧬 KMI — BTF layout diff against the stock ROM
# ======================================================
# Usage: btf_diff.py --reference kernel/kmi/ref/NAME --image Image [--limit N]
# Parses the BTF embedded in both kernels and prints the structs, unions and
# enums whose real memory layout differs. CRC-only noise is ignored.

import argparse
import gzip
import os
import re
import struct
import sys

BTF_HEADER = re.compile(rb"\x9f\xeb\x01\x00\x18\x00\x00\x00")
KIND_NAMES = {4: "struct", 5: "union", 6: "enum", 19: "enum"}
PRIORITY = (
    "task_struct", "mm_struct", "page", "folio", "vm_area_struct", "vm_struct", "device",
    "dma_buf", "dma_buf_attachment", "sg_table", "scatterlist", "kmem_cache", "zone",
    "pglist_data", "address_space", "inode", "file", "module", "bio", "request_queue",
    "net_device", "sk_buff", "sock", "cgroup", "css_set", "mem_cgroup", "lruvec",
)
WIDTH_MASK = (1 << 32) - 1


def find_btf(data):
    for match in BTF_HEADER.finditer(data):
        start = match.start()
        _, _, _, hdr_len, type_off, type_len, str_off, str_len = struct.unpack_from("<HBBIIIII", data, start)
        if type_off == 0 and str_off == type_len and 0 < type_len < 1 << 28 and 0 < str_len < 1 << 26:
            return data[start: start + hdr_len + str_off + str_len]
    return None


class Btf:
    def __init__(self, blob):
        _, _, _, hdr_len, type_off, type_len, str_off, str_len = struct.unpack_from("<HBBIIIII", blob, 0)
        self.strings = blob[hdr_len + str_off: hdr_len + str_off + str_len]
        self.types = [None]
        position = hdr_len + type_off
        end = position + type_len
        while position < end:
            name_off, info, size_type = struct.unpack_from("<III", blob, position)
            position += 12
            kind = (info >> 24) & 0x1F
            vlen = info & 0xFFFF
            kind_flag = info >> 31
            extra = None
            if kind == 1:
                extra = struct.unpack_from("<I", blob, position)[0]
                position += 4
            elif kind == 3:
                extra = struct.unpack_from("<III", blob, position)
                position += 12
            elif kind in (4, 5):
                extra = [struct.unpack_from("<III", blob, position + 12 * i) for i in range(vlen)]
                position += 12 * vlen
            elif kind == 6:
                extra = [struct.unpack_from("<Ii", blob, position + 8 * i) for i in range(vlen)]
                position += 8 * vlen
            elif kind == 13:
                position += 8 * vlen
            elif kind in (14, 17):
                position += 4
            elif kind == 15:
                position += 12 * vlen
            elif kind == 19:
                extra = []
                for i in range(vlen):
                    n, lo, hi = struct.unpack_from("<III", blob, position + 12 * i)
                    extra.append((n, lo | (hi << 32)))
                position += 12 * vlen
            self.types.append((self.name(name_off), kind, kind_flag, size_type, extra))
        self.layouts = {}

    def name(self, offset):
        end = self.strings.index(b"\0", offset)
        return self.strings[offset:end].decode("utf-8", "replace")

    def describe(self, type_id, depth=0):
        if type_id == 0:
            return "void"
        name, kind, _, size_type, extra = self.types[type_id]
        if kind == 1:
            return f"{name}/{size_type}"
        if kind == 2:
            return "*" + (self.describe(size_type, depth + 1) if depth < 3 else "?")
        if kind == 3:
            return f"[{extra[2]}]" + self.describe(extra[0], depth + 1)
        if kind in (4, 5):
            if name:
                return f"{KIND_NAMES[kind]} {name}/{size_type}"
            return f"anon {KIND_NAMES[kind]}/{size_type}:" + ",".join(self.layout_members(type_id, depth + 1))
        if kind in (6, 19):
            return f"enum {name}/{size_type}"
        if kind == 7:
            return f"fwd {name}"
        if kind in (8, 9, 10, 11, 18):
            return self.describe(size_type, depth + 1)
        return f"kind{kind}"

    def layout_members(self, type_id, depth=0):
        name, kind, kind_flag, size_type, members = self.types[type_id]
        result = []
        for member_name, member_type, offset in members:
            if kind_flag:
                bit_offset, bit_size = offset & 0xFFFFFF, offset >> 24
            else:
                bit_offset, bit_size = offset, 0
            result.append(f"{self.name(member_name)}@{bit_offset}:{bit_size}={self.describe(member_type, depth)}")
        return result

    def collect(self):
        layouts = {}
        for type_id in range(1, len(self.types)):
            name, kind, _, size_type, extra = self.types[type_id]
            if not name or kind not in (4, 5, 6, 19):
                continue
            key = (KIND_NAMES[kind], name)
            if kind in (4, 5):
                if not extra:
                    continue
                signature = (size_type, tuple(self.layout_members(type_id)))
            else:
                signature = (size_type, tuple((self.name(n), v) for n, v in extra))
            layouts.setdefault(key, set()).add(signature)
        return layouts


def member_key(index, member):
    name = member.split("=", 1)[0].split("@")[0]
    return name or f"<anon{index}>"


def summarize(kind, old, new):
    old_size, old_members = old
    new_size, new_members = new
    lines = []
    if old_size != new_size:
        lines.append(f"size {old_size} -> {new_size}")
    if kind == "enum":
        old_values, new_values = dict(old_members), dict(new_members)
        for name in old_values:
            if name not in new_values:
                lines.append(f"removed {name}={old_values[name]}")
            elif (old_values[name] & WIDTH_MASK) != (new_values[name] & WIDTH_MASK):
                lines.append(f"changed {name}={old_values[name]} -> {new_values[name]}")
        for name in new_values:
            if name not in old_values:
                lines.append(f"added   {name}={new_values[name]}")
        return lines
    old_map = {member_key(i, m): m for i, m in enumerate(old_members)}
    new_map = {member_key(i, m): m for i, m in enumerate(new_members)}
    for name in old_map:
        if name not in new_map:
            lines.append(f"removed {old_map[name]}")
    for name in new_map:
        if name not in old_map:
            lines.append(f"added   {new_map[name]}")
        elif old_map[name] != new_map[name]:
            lines.append(f"changed {old_map[name]} -> {new_map[name]}")
    return lines


def diff(stock, ours):
    own, nested = [], []
    for key in sorted(set(stock) & set(ours)):
        if stock[key] == ours[key]:
            continue
        only_old = sorted(stock[key] - ours[key])
        only_new = sorted(ours[key] - stock[key])
        if not only_old or not only_new:
            continue
        try:
            lines = summarize(key[0], only_old[0], only_new[0])
        except (AttributeError, IndexError, TypeError, ValueError) as error:
            lines = [f"layout differs (summary failed: {error})"]
        if key[0] == "enum" and not lines:
            continue
        structural = any(not line.startswith("changed") for line in lines) or key[0] == "enum"
        (own if structural else nested).append((key, lines))
    return own, nested


def load_reference(reference_dir):
    with gzip.open(os.path.join(reference_dir, "btf.bin.gz"), "rb") as handle:
        return Btf(handle.read())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--limit", type=int, default=400)
    args = parser.parse_args()

    with open(args.image, "rb") as handle:
        blob = find_btf(handle.read())
    if blob is None:
        print("btf: no BTF found in the built image — enable CONFIG_DEBUG_INFO_BTF")
        return 0

    stock = load_reference(args.reference).collect()
    ours = Btf(blob).collect()
    own, nested = diff(stock, ours)
    print(f"btf: {len(stock)} stock types, {len(ours)} built types, "
          f"{len(set(stock) & set(ours))} shared")
    print(f"btf: {len(own)} types differ in their own layout, {len(nested)} only through a nested type")
    for key, lines in own[: args.limit]:
        added = sum(1 for line in lines if line.startswith("added"))
        removed = sum(1 for line in lines if line.startswith("removed"))
        changed = sum(1 for line in lines if line.startswith("changed"))
        size = next((line for line in lines if line.startswith("size")), "")
        print(f"  {key[0]} {key[1]}: {size} +{added} -{removed} ~{changed}")
    print("btf: details for key types")
    for key, lines in own + nested:
        if key[1] in PRIORITY:
            print(f"  {key[0]} {key[1]}")
            for line in lines[:8]:
                print(f"      {line[:220]}")
    if nested:
        print("btf: nested-only: " + ", ".join(k[1] for k, _ in nested))
    return 0


if __name__ == "__main__":
    sys.exit(main())
