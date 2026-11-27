"""Command-line entry point for the DXF Viewport Analyzer."""

import argparse
import json
import sys

import ezdxf

from src.analyzer import analyze_dxf, format_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analyze paper-space viewports in a DXF drawing.",
    )
    parser.add_argument("dxf", help="path to the .dxf file (quote it if it contains spaces)")
    parser.add_argument(
        "--json", metavar="FILE", nargs="?", const="-",
        help="write the report as JSON to FILE (or to stdout if FILE is omitted)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="show all viewport properties in the text report",
    )
    args = parser.parse_args(argv)

    try:
        report = analyze_dxf(args.dxf)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except (ezdxf.DXFStructureError, IOError) as exc:
        print(f"Error: could not read DXF file: {exc}", file=sys.stderr)
        return 2

    if args.json:
        data = json.dumps(report.to_dict(), indent=2)
        if args.json == "-":
            print(data)
        else:
            with open(args.json, "w", encoding="utf-8") as f:
                f.write(data + "\n")
            print(f"JSON report written to {args.json}")
    else:
        print(format_report(report, verbose=args.verbose))

    return 0


if __name__ == "__main__":
    sys.exit(main())
