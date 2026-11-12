import pathlib
import sys

BROKEN = "policydb->latest_granting = old_pol->latest_granting + 1;"
FIXED = "pol->latest_granting = old_pol->latest_granting + 1;"


def main():
    source = pathlib.Path(sys.argv[1])
    content = source.read_text()
    if BROKEN not in content:
        print(f"{source.name} has no stray policydb generation update, skipping.")
        sys.exit(0)
    source.write_text(content.replace(BROKEN, FIXED))
    print(f"{source.name} patched successfully.")


if __name__ == "__main__":
    main()
