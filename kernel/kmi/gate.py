#!/usr/bin/env python3

# ======================================================
# 🚦 KMI — Clean Gate
# ======================================================
# Verifies that a built kernel keeps the stock KMI the vendor modules were built against.
#   L0  KMI generation tag (e.g. android14-11), checked when the release string carries it
#   L1  module_layout CRC
#   L2  CRC of every kernel symbol imported by stock modules
#   L3  CRC of every symbol exported by the stock kernel (strict)
# Usage: gate.py --reference kernel/kmi/ref/NAME --image Image [--report FILE] [--no-strict]
# Exit status: 0 = clean, 1 = KMI mismatch, 2 = usage or parse error.

import argparse
import json
import os
import sys

import image
import symvers


def load_table(path):
    table = {}
    with open(path) as handle:
        for line in handle:
            crc, name = line.rstrip("\n").split("\t")
            table[name] = int(crc, 16)
    return table


def compare(expected, actual):
    missing = sorted(name for name in expected if name not in actual)
    changed = sorted(name for name in expected if name in actual and actual[name] != expected[name])
    return missing, changed


def describe(label, total, missing, changed, limit, expected, actual):
    state = "PASS" if not missing and not changed else "FAIL"
    print(f"[{state}] {label}: {total - len(missing) - len(changed)}/{total} match | missing {len(missing)} | crc changed {len(changed)}")
    for name in changed[:limit]:
        print(f"        {name}: want {expected[name]:#010x} have {actual[name]:#010x}")
    for name in missing[:limit]:
        print(f"        {name}: not exported")
    return state == "PASS"


def main():
    parser = argparse.ArgumentParser(description="KMI clean gate")
    parser.add_argument("--reference", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--report")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--no-strict", action="store_true")
    args = parser.parse_args()

    with open(os.path.join(args.reference, "meta.json")) as handle:
        meta = json.load(handle)
    try:
        kernel = image.load_kernel(args.image)
        actual, _ = symvers.extract(kernel)
    except (OSError, ValueError) as error:
        print(f"[error] kmi gate: {error}", file=sys.stderr)
        sys.exit(2)

    release = image.kernel_release(kernel)
    tag = image.kmi_tag(release)
    results = []

    if tag:
        ok = tag == meta["kmi_tag"]
        print(f"[{'PASS' if ok else 'FAIL'}] L0 KMI generation: {tag} (stock {meta['kmi_tag']}) | {release}")
        results.append(ok)
    else:
        print(f"[SKIP] L0 KMI generation: release carries no tag | {release}")

    layout = actual.get("module_layout")
    ok = layout is not None and f"{layout:#010x}" == meta["module_layout"]
    shown = f"{layout:#010x}" if layout is not None else "missing"
    print(f"[{'PASS' if ok else 'FAIL'}] L1 module_layout: {shown} (stock {meta['module_layout']})")
    results.append(ok)

    imports = load_table(os.path.join(args.reference, "imports.tsv"))
    missing, changed = compare(imports, actual)
    results.append(describe("L2 module imports", len(imports), missing, changed, args.limit, imports, actual))
    report = {"imports": {"missing": missing, "changed": changed}}

    if not args.no_strict:
        stock = load_table(os.path.join(args.reference, "symvers.tsv"))
        missing, changed = compare(stock, actual)
        results.append(describe("L3 strict exports", len(stock), missing, changed, args.limit, stock, actual))
        report["strict"] = {"missing": missing, "changed": changed}

    if args.report:
        with open(args.report, "w") as handle:
            json.dump(report, handle, indent=2)

    print("KMI gate:", "CLEAN" if all(results) else "FAILED")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
