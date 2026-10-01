import json
import sys

from .errors import InputError
from .report import build_report


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        print("usage: python -m geofence_report <input.json> <output.json>", file=sys.stderr)
        return 2
    input_path, output_path = argv
    try:
        with open(input_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read input JSON: {exc}", file=sys.stderr)
        return 2
    try:
        report = build_report(data)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
