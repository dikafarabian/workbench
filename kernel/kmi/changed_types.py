#!/usr/bin/env python3

# ======================================================
# 🧬 KMI — Changed type finder
# ======================================================
# Usage: changed_types.py --reference kernel/kmi/ref/NAME --report FILE --symtypes DIR [--limit N]
# Reads genksyms .symtypes dumps (KBUILD_SYMTYPES=1) and the gate report.
# Every type is fingerprinted per file with its children expanded, because the
# same name can be fully expanded in one file and opaque in another.
# A type version used by a symbol whose CRC still matches the stock ROM is
# unchanged; leaf type versions left over in the changed symbols were modified.

import argparse
import hashlib
import json
import os
import re
import sys

sys.setrecursionlimit(20000)

TYPE_REF = re.compile(r"[a-z]#[A-Za-z0-9_.$]+")


def parse_file(path):
    definitions = {}
    with open(path, errors="replace") as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            key, _, body = line.rstrip("\n").partition(" ")
            if body:
                definitions[key] = body
    return definitions


def fingerprint_file(definitions):
    children = {key: [t for t in body.split(" ") if TYPE_REF.fullmatch(t) and t != key]
                for key, body in definitions.items()}
    memo = {}

    def fingerprint(key, stack):
        if key in memo:
            return memo[key]
        body = definitions.get(key)
        if body is None or key in stack:
            return key
        stack.add(key)
        parts = [fingerprint(tok, stack) if TYPE_REF.fullmatch(tok) and tok != key else tok
                 for tok in body.split(" ")]
        stack.discard(key)
        digest = hashlib.blake2b(" ".join(parts).encode(), digest_size=8).hexdigest()
        memo[key] = f"{key}@{digest}"
        return memo[key]

    return children, fingerprint


def closure(start, children):
    seen = set()
    stack = list(start)
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(children.get(node, ()))
    return seen


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

    with open(args.report) as handle:
        report = json.load(handle)
    scope = report.get("strict") or report["imports"]
    changed = set(scope["changed"])
    missing = set(scope["missing"])
    unchanged = load_reference_names(args.reference) - changed - missing

    files = 0
    symbols = {}
    type_children = {}
    type_name = {}
    type_body = {}
    for directory, _, names in os.walk(args.symtypes):
        for name in names:
            if not name.endswith(".symtypes"):
                continue
            files += 1
            definitions = parse_file(os.path.join(directory, name))
            children, fingerprint = fingerprint_file(definitions)
            for key, body in definitions.items():
                if "#" in key.split(" ")[0] and TYPE_REF.fullmatch(key):
                    version = fingerprint(key, set())
                    if version not in type_children:
                        type_children[version] = {fingerprint(c, set()) for c in children[key]}
                        type_body[version] = body
                elif key in changed or key in unchanged:
                    reach = closure(children[key], children)
                    symbols[key] = ({fingerprint(r, set()) for r in reach}, body)

    if not symbols:
        print("types: no .symtypes found — nothing to analyse")
        return 0

    safe = set()
    for sym in unchanged:
        if sym in symbols:
            safe |= symbols[sym][0]

    suspects = set()
    own_declaration = []
    for sym in changed:
        if sym not in symbols:
            continue
        found = symbols[sym][0] - safe
        suspects |= found
        if not found:
            own_declaration.append(sym)

    leaves = {v for v in suspects
              if not any(c in suspects for c in type_children.get(v, ()))}

    affected = {v: 0 for v in leaves}
    for sym in changed:
        if sym in symbols:
            for leaf in leaves & symbols[sym][0]:
                affected[leaf] += 1

    print(f"types: {files} symtypes files, {len(symbols)} exported symbols with type data")
    print(f"types: {len(unchanged & set(symbols))} unchanged symbols pin {len(safe)} type versions as stable")
    print(f"types: {len(suspects)} suspect type versions, {len(leaves)} modified directly")
    print(f"types: {len(own_declaration)}/{len(changed & set(symbols))} changed symbols have no suspect type")
    for leaf in sorted(leaves, key=lambda v: -affected[v])[: args.limit]:
        print(f"  {leaf.split('@')[0]}  affects {affected[leaf]} symbols  {type_body.get(leaf, '')[:240]}")
    for sym in sorted(own_declaration)[:8]:
        print(f"  decl {sym}: {symbols[sym][1][:200]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
