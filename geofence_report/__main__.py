"""CLI: python -m geofence_report <input.json> <output.json>"""

import json
import sys

from .core import InputError, build_report, load_input


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: python -m geofence_report <input.json> <output.json>",
              file=sys.stderr)
        return 2
    input_path, output_path = argv
    try:
        data = load_input(input_path)
        report = build_report(data)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: cannot read {input_path}: {exc}", file=sys.stderr)
        return 1
    # Only write the output after the whole report validated and built.
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
