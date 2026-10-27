import pathlib
import sys

COMMENT = "/* fall through */"
STATEMENT = "fallthrough;"


def main():
    source = pathlib.Path(sys.argv[1])
    content = source.read_text()
    if COMMENT not in content:
        print(f"{source.name} has no fall-through comment, skipping.")
        sys.exit(0)
    source.write_text(content.replace(COMMENT, STATEMENT))
    print(f"{source.name} patched successfully.")


if __name__ == "__main__":
    main()
