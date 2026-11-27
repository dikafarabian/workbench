#!/usr/bin/env python3

# ======================================================
# 🧬 KMI — Changed type finder
# ======================================================
# Usage: changed_types.py --reference kernel/kmi/ref/NAME --report FILE --symtypes DIR [--limit N]
# Reads genksyms .symtypes dumps (KBUILD_SYMTYPES=1) and the gate report.
# A type used by any symbol whose CRC still matches the stock ROM is unchanged,
# so every changed type must sit outside that set; leaf types in what remains
# were modified directly.

import argparse
import json
import os
import re
import sys

TYPE_REF = re.compile(r"\b[a-z]#[A-Za-z0-9_.$]+")


def load_symtypes(root):
    definitions = {}
    files = 0
    for directory, _, names in os.walk(root):
        for name in names:
            if not name.endswith(".symtypes"):
                continue
            files += 1
            with open(os.path.join(directory, name), errors="replace") as handle:
                for line in handle:
                    key, _, body = line.rstrip("\n").partition(" ")
                    if not body:
                        continue
                    if key not in definitions or len(body) > len(definitions[key]):
                        definitions[key] = body
    return definitions, files


def load_reference_names(reference_dir):
    names = set()
    with open(os.path.join(reference_dir, "symvers.tsv")) as handle:
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2:
                names.add(parts[1])
    return names


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--symtypes", required=True)
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    definitions, files = load_symtypes(args.symtypes)
    if not definitions:
        print("types: no .symtypes found — nothing to analyse")
        return 0

    with open(args.report) as handle:
        report = json.load(handle)
    scope = report.get("strict") or report["imports"]
    changed = set(scope["changed"])
    missing = set(scope["missing"])
    unchanged = load_reference_names(args.reference) - changed - missing

    refs = {key: set(TYPE_REF.findall(body)) for key, body in definitions.items()}

    safe = set()
    stack = [t for sym in unchanged for t in refs.get(sym, ())]
    while stack:
        node = stack.pop()
        if node in safe:
            continue
        safe.add(node)
        stack.extend(refs.get(node, ()))

    changed_symbols = [s for s in changed if s in refs]
    suspects = set()
    stack = [t for sym in changed_symbols for t in refs[sym] if t not in safe]
    while stack:
        node = stack.pop()
        if node in suspects:
            continue
        suspects.add(node)
        stack.extend(t for t in refs.get(node, ()) if t not in safe)

    leaves = {t for t in suspects if not any(c in suspects for c in refs.get(t, ()))}

    affected = {t: 0 for t in leaves}
    own_declaration = []
    for sym in changed_symbols:
        seen = set()
        stack = [t for t in refs[sym] if t in suspects]
        if not stack:
            own_declaration.append(sym)
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            stack.extend(c for c in refs.get(node, ()) if c in suspects)
        for leaf in leaves & seen:
            affected[leaf] += 1

    print(f"types: {files} symtypes files, {len(definitions)} entries")
    print(f"types: {len(changed_symbols)}/{len(changed)} changed symbols have type data, "
          f"{len(unchanged)} unchanged symbols pin {len(safe)} types as stable")
    print(f"types: {len(suspects)} suspect types, {len(leaves)} modified directly")
    print(f"types: {len(own_declaration)} changed symbols differ only in their own declaration")
    for leaf in sorted(leaves, key=lambda t: -affected[t])[: args.limit]:
        body = definitions.get(leaf, "")
        print(f"  {leaf}  affects {affected[leaf]} symbols  {body[:240]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
