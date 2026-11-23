#!/usr/bin/env python3

# ======================================================
# 📚 KMI — Reference Builder
# ======================================================
# Builds a device KMI reference from the stock ROM images: exported symbol CRCs of the
# stock kernel plus every CRC the stock modules were built against.
# Usage: reference.py --name NAME --boot boot.img [--vendor-boot vendor_boot.img]
#        [--erofs vendor_dlkm.img --erofs system_dlkm.img] [--out kernel/kmi/ref]

import argparse
import json
import os
import sys

import erofs
import image
import ko
import symvers


def collect_modules(args):
    modules = {}
    if args.vendor_boot:
        for name, content in image.vendor_boot_modules(args.vendor_boot).items():
            modules[f"vendor_boot/{name}"] = content
    for path in args.erofs:
        label = os.path.splitext(os.path.basename(path))[0]
        files, skipped = erofs.extract_files(path)
        if skipped:
            sys.exit(f"[error] {path}: {len(skipped)} files could not be read")
        for name, content in files.items():
            if name.endswith(".ko"):
                modules[f"{label}/{os.path.basename(name)}"] = content
    return modules


def main():
    parser = argparse.ArgumentParser(description="Build a KMI reference from stock ROM images")
    parser.add_argument("--name", required=True)
    parser.add_argument("--boot", required=True)
    parser.add_argument("--vendor-boot")
    parser.add_argument("--erofs", action="append", default=[])
    parser.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "ref"))
    args = parser.parse_args()

    kernel = image.load_kernel(args.boot)
    table, _ = symvers.extract(kernel)
    release = image.kernel_release(kernel)
    modules = collect_modules(args)

    module_exports = set()
    for content in modules.values():
        module_exports |= ko.exports(content)

    kernel_imports, unresolved, conflicts = {}, set(), set()
    for content in modules.values():
        for name, crc in ko.imports(content):
            if name in table:
                if kernel_imports.setdefault(name, crc) != crc:
                    conflicts.add(name)
            elif name not in module_exports:
                unresolved.add(name)

    directory = os.path.join(args.out, args.name)
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, "symvers.tsv"), "w") as handle:
        handle.writelines(f"{crc:#010x}\t{name}\n" for name, crc in sorted(table.items()))
    with open(os.path.join(directory, "imports.tsv"), "w") as handle:
        handle.writelines(f"{crc:#010x}\t{name}\n" for name, crc in sorted(kernel_imports.items()))
    meta = {
        "name": args.name,
        "kernel_release": release,
        "kmi_tag": image.kmi_tag(release),
        "module_layout": f"{table['module_layout']:#010x}",
        "kernel_symbols": len(table),
        "kernel_imports": len(kernel_imports),
        "modules": len(modules),
        "unresolved_in_stock": sorted(unresolved),
        "conflicting_imports": sorted(conflicts),
    }
    with open(os.path.join(directory, "meta.json"), "w") as handle:
        json.dump(meta, handle, indent=2)
        handle.write("\n")
    print(json.dumps({key: value for key, value in meta.items() if not isinstance(value, list)}, indent=2))
    print(f"unresolved in stock: {len(unresolved)} | conflicting: {len(conflicts)} -> {directory}")


if __name__ == "__main__":
    main()
