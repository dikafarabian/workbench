#!/usr/bin/env python3

# ======================================================
# 🧬 SuSFS — de-inline official kernel patch
# ======================================================
# Strips KernelSU inline hooks and SELinux hunks from the official SuSFS kernel patch
# Source: https://github.com/midori01/gki_ksu_workflow (susfs_deinlined.sh v2.1.1, GPL-3.0-or-later, midori01)

import sys
import os
import re

def read_patch(filename):
    try:
        with open(filename, "r", encoding="utf-8", errors="replace") as f:
            return f.read().replace("\r\n", "\n")
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found!", file=sys.stderr)
        sys.exit(1)

def split_patch(content):
    parts = re.split(r"(?=^diff --git )", content, flags=re.MULTILINE)
    return parts[1:]

def get_target_file(patch):
    for line in patch.split("\n"):
        if line.startswith("+++ b/"):
            return line[6:].split("\t")[0].strip()
    return None

def get_body(patch):
    lines = patch.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("@@"):
            return lines[:i], lines[i:]
    return lines, []

def remove_duplicate_plus_empty(lines):
    result = []
    prev_plus_empty = False
    for line in lines:
        is_plus_empty = (line.strip() == "+")
        if is_plus_empty and prev_plus_empty:
            continue
        result.append(line)
        prev_plus_empty = is_plus_empty
    return result

def strip_comment(l):
    s = l.strip()
    for marker in ["//", "/*"]:
        idx = s.find(marker)
        if idx != -1:
            s = s[:idx].strip()
    return s

def get_directive(l):
    s = strip_comment(l)
    if not s.startswith("+"):
        return ""
    return s[1:].lstrip()

def is_if(l):
    d = get_directive(l)
    return d.startswith("#if")

def is_else(l):
    d = get_directive(l)
    return d.startswith("#else") or d.startswith("#elif")

def is_endif(l):
    d = get_directive(l)
    return d.startswith("#endif")

def is_ksu_susfs_if(line):
    return bool(re.match(
        r"^\+\s*#\s*if(?:def\s+CONFIG_KSU_SUSFS\b|\s+(?:defined\s*\(\s*|IS_ENABLED\s*\(\s*)?CONFIG_KSU_SUSFS\s*\)?)\s*$",
        line
    ))

def is_ksu_susfs_ifndef(line):
    return bool(re.match(
        r"^\+\s*#\s*(?:ifndef\s+CONFIG_KSU_SUSFS\b|if\s+!(?:defined\s*\(\s*|IS_ENABLED\s*\(\s*)?CONFIG_KSU_SUSFS\s*\)?)\s*$",
        line
    ))

def process_normal_file(body, target):
    result = []
    i = 0
    while i < len(body):
        line = body[i]
        clean_line = strip_comment(line)

        if is_ksu_susfs_if(clean_line):
            block_end = i + 1
            depth = 1
            else_idx = -1
            endif_idx = -1
            has_include = False

            while block_end < len(body) and depth > 0:
                cur_line = body[block_end]
                if is_if(cur_line):
                    depth += 1
                elif is_else(cur_line) and depth == 1:
                    else_idx = block_end
                elif is_endif(cur_line):
                    depth -= 1
                    if depth == 0:
                        endif_idx = block_end
                        break
                if "#include" in cur_line:
                    has_include = True
                block_end += 1

            if endif_idx == -1:
                endif_idx = block_end - 1

            block_lines = body[i : endif_idx + 1]
            block_text = "\n".join(block_lines)

            if has_include and else_idx == -1:
                remaining = "\n".join(body[endif_idx + 1:])
                if "CONFIG_KSU_SUSFS_" in remaining:
                    result.extend(body[i : endif_idx + 1])
                i = endif_idx + 1
                continue

            has_ksu = bool(re.search(r"\b(?:ksu_|__ksu_)", block_text))
            has_susfs = bool(re.search(r"\b(?:susfs_|SUSFS_)", block_text))

            if has_susfs and not has_ksu:
                result.extend(body[i : endif_idx + 1])
                i = endif_idx + 1
                continue

            if else_idx > 0 and endif_idx > 0:
                result.extend(body[else_idx + 1 : endif_idx])
            i = endif_idx + 1
            continue

        if is_ksu_susfs_ifndef(clean_line):
            block_end = i + 1
            depth = 1
            else_idx = -1
            endif_idx = -1

            while block_end < len(body) and depth > 0:
                cur_line = body[block_end]
                if is_if(cur_line):
                    depth += 1
                elif is_else(cur_line) and depth == 1:
                    else_idx = block_end
                elif is_endif(cur_line):
                    depth -= 1
                    if depth == 0:
                        endif_idx = block_end
                        break
                block_end += 1

            if endif_idx == -1:
                endif_idx = block_end - 1

            if else_idx > 0 and endif_idx > 0:
                result.extend(body[i + 1 : else_idx])
            elif endif_idx > 0:
                result.extend(body[i + 1 : endif_idx])
            i = endif_idx + 1
            continue

        result.append(line)
        i += 1

    return result

def parse_hunk_header(line):
    match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)", line)
    if not match:
        return None
    return (
        int(match.group(1)),
        int(match.group(2)) if match.group(2) else 1,
        int(match.group(3)),
        int(match.group(4)) if match.group(4) else 1,
        match.group(5)
    )

def format_hunk_header(old_start, old_total, new_start, new_total, suffix):
    old_str = f"-{old_start}" if old_total == 1 else f"-{old_start},{old_total}"
    new_str = f"+{new_start}" if new_total == 1 else f"+{new_start},{new_total}"
    return f"@@ {old_str} {new_str} @@{suffix}"

def clean_body(body):
    cleaned = []
    i = 0
    cumulative_delta = 0
    while i < len(body):
        line = body[i]

        if line.startswith("@@"):
            hunk_lines = []
            j = i + 1
            while j < len(body):
                if body[j].startswith("@@") or body[j].startswith("diff --git"):
                    break
                hunk_lines.append(body[j])
                j += 1

            while hunk_lines and hunk_lines[-1] == "":
                hunk_lines.pop()

            ins_all = sum(1 for l in hunk_lines if l.startswith("+") and not l.startswith("+++"))
            dels_all = sum(1 for l in hunk_lines if l.startswith("-") and not l.startswith("---"))

            ins_meaningful = sum(1 for l in hunk_lines 
                                if l.startswith("+") and not l.startswith("+++") and l.strip() != "+")
            dels_meaningful = sum(1 for l in hunk_lines 
                                 if l.startswith("-") and not l.startswith("---") and l.strip() != "-")

            if ins_meaningful == 0 and dels_meaningful == 0:
                i = j
                continue

            header_info = parse_hunk_header(line)
            if header_info:
                old_start, _, _, _, suffix = header_info
                context = sum(1 for l in hunk_lines if l.startswith(" ") or l == "")
                old_total = dels_all + context
                new_total = ins_all + context
                new_start = old_start + cumulative_delta
                cumulative_delta += (new_total - old_total)
                cleaned.append(format_hunk_header(old_start, old_total, new_start, new_total, suffix))
                cleaned.extend(hunk_lines)
                i = j
                continue

        cleaned.append(line)
        i += 1

    return cleaned

def has_real_changes(body):
    for line in body:
        stripped = line.strip()
        if line.startswith("+") and not line.startswith("+++") and stripped != "+":
            return True
        if line.startswith("-") and not line.startswith("---") and stripped != "-":
            return True
    return False

HOOK_PATTERN = re.compile(r"\b(ksu_handle_\w+|ksu_hook_\w+)\b")

def find_unique_hooks(lines):
    hooks = []
    for line in lines:
        if line.startswith("+") and not line.startswith("+++"):
            for m in HOOK_PATTERN.findall(line):
                if m not in hooks:
                    hooks.append(m)
    return sorted(hooks)

def process_patch(patch):
    target = get_target_file(patch)
    if not target:
        return None, None

    orig_lines = patch.split("\n")
    orig_hunks = sum(1 for l in orig_lines if l.startswith("@@"))
    orig_hooks = find_unique_hooks(orig_lines)

    if target.startswith("security/"):
        info = {
            "target": target,
            "status": "DROP",
            "reason": "selinux",
            "orig_hunks": orig_hunks,
            "kept_hunks": 0,
            "orig_hooks": orig_hooks,
            "dropped_hooks": orig_hooks,
            "remaining_hooks": [],
        }
        return None, info

    header, body = get_body(patch)
    if not body:
        info = {
            "target": target,
            "status": "DROP",
            "reason": "empty",
            "orig_hunks": orig_hunks,
            "kept_hunks": 0,
            "orig_hooks": orig_hooks,
            "dropped_hooks": orig_hooks,
            "remaining_hooks": [],
        }
        return None, info

    new_body = process_normal_file(body, target)
    new_body = clean_body(new_body)

    if not has_real_changes(new_body):
        info = {
            "target": target,
            "status": "DROP",
            "reason": "stripped" if orig_hooks else "no_changes",
            "orig_hunks": orig_hunks,
            "kept_hunks": 0,
            "orig_hooks": orig_hooks,
            "dropped_hooks": orig_hooks,
            "remaining_hooks": [],
        }
        return None, info

    remaining_hooks = find_unique_hooks(new_body)
    dropped_hooks = [h for h in orig_hooks if h not in remaining_hooks]
    kept_hunks = sum(1 for l in new_body if l.startswith("@@"))

    info = {
        "target": target,
        "status": "KEEP",
        "reason": None,
        "orig_hunks": orig_hunks,
        "kept_hunks": kept_hunks,
        "orig_hooks": orig_hooks,
        "dropped_hooks": dropped_hooks,
        "remaining_hooks": remaining_hooks,
    }

    return "\n".join(header + new_body), info

def main():
    if len(sys.argv) < 2:
        print("Usage: deinline.py <input_patch> [output_patch]", file=sys.stderr)
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "deinlined.patch"

    content = read_patch(input_file)
    file_patches = split_patch(content)

    if not file_patches:
        print("Error: No diff --git sections found in patch!", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {len(file_patches)} files...")

    results = []
    for patch in file_patches:
        res, info = process_patch(patch)
        if info:
            results.append((res, info))

    if not results:
        print("Error: No valid patches found!", file=sys.stderr)
        sys.exit(1)

    processed = []
    removed = []

    for res, info in results:
        status = info["status"]
        tgt = info["target"]

        orig_h = info["orig_hunks"]
        kept_h = info["kept_hunks"]
        drop_h = orig_h - kept_h
        h_word = "hunk" if orig_h == 1 else "hunks"

        if status == "KEEP":
            processed.append(res.rstrip("\n"))
        else:
            removed.append(tgt)

        print(f"  [{status}] {tgt} ({drop_h}/{orig_h} {h_word} dropped)")

    if not processed:
        print("Error: No file patches remain after processing!", file=sys.stderr)
        sys.exit(1)

    out_dir = os.path.dirname(os.path.abspath(output_file))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(processed))
        f.write("\n")

    print("\nSummary:")
    total_orig_hunks = sum(info["orig_hunks"] for _, info in results)
    total_kept_hunks = sum(info["kept_hunks"] for _, info in results)
    total_dropped_hunks = total_orig_hunks - total_kept_hunks

    print(f"  Total files: {len(results)} ({len(processed)} kept, {len(removed)} dropped)")
    print(f"  Total hunks: {total_orig_hunks} ({total_kept_hunks} kept, {total_dropped_hunks} dropped)")

    all_dropped_hook_files = [info for _, info in results if info["dropped_hooks"]]
    total_hooks_dropped = sum(len(info["dropped_hooks"]) for info in all_dropped_hook_files)
    dropped_files = [info for _, info in results if info["status"] == "DROP"]

    if dropped_files:
        print(f"  Dropped files ({len(dropped_files)}):")
        for info in dropped_files:
            print(f"    - {info['target']}")
    else:
        print("  Dropped files: 0")

    if total_hooks_dropped > 0:
        print(f"  Stripped inline hooks ({total_hooks_dropped}):")
        for info in all_dropped_hook_files:
            h_names = ", ".join(re.sub(r"^(?:ksu_handle_|ksu_hook_)", "", h) for h in info["dropped_hooks"])
            cnt = len(info["dropped_hooks"])
            print(f"    - {info['target']} ({cnt}): {h_names}")
    else:
        print("  Stripped inline hooks: 0")

    print(f"\nDone! Successfully written to: {output_file}")

if __name__ == "__main__":
    main()
