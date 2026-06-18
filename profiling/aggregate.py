#!/usr/bin/env python3
"""
aggregate.py — merge per-app profile_app.py JSON results into one comparison
table.

Usage:
    python3 aggregate.py results/*.json
    python3 aggregate.py results/*.json --csv summary.csv
"""

import argparse
import csv
import glob
import json
import sys


def load(paths):
    rows = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            rows.append(json.load(f))
    # Sort by total resources so app-1/2/3 line up.
    return sorted(rows, key=lambda r: r.get("total_resources", 0))


def fmt(v):
    return f"{v:.0f}" if isinstance(v, (int, float)) else str(v)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("results", nargs="+", help="JSON files (globs ok)")
    ap.add_argument("--csv", help="Also write a CSV summary here")
    args = ap.parse_args()

    paths = []
    for pattern in args.results:
        paths.extend(glob.glob(pattern))
    if not paths:
        sys.exit("No result files matched.")

    rows = load(paths)

    headers = [
        "app",
        "build",
        "check_type",
        "resources",
        "import_ms",
        "synth_ms",
        "get_type_hints_ms",
        "get_type_hints_calls",
        "check_type_ms",
        "check_type_calls",
        "ipc_ms",
        "register_ms",
    ]

    table = []
    for r in rows:
        a = r["synth"]["attribution"]
        reg = a["register_type"]["cum_ms"] + a["register_reference"]["cum_ms"]
        table.append(
            {
                "app": r["app"],
                "build": r["build"],
                "check_type": r["check_type"],
                "resources": r["total_resources"],
                "import_ms": r["imports"]["total_ms"],
                "synth_ms": r["synth"]["wall_ms"],
                "get_type_hints_ms": a["get_type_hints"]["cum_ms"],
                "get_type_hints_calls": a["get_type_hints"]["calls"],
                "check_type_ms": a["check_type"]["cum_ms"],
                "check_type_calls": a["check_type"]["calls"],
                "ipc_ms": a["kernel_ipc"]["cum_ms"],
                "register_ms": round(reg, 1),
            }
        )

    # Pretty print aligned table.
    widths = {h: max(len(h), *(len(fmt(row[h])) for row in table)) for h in headers}
    line = "  ".join(h.ljust(widths[h]) for h in headers)
    print(line)
    print("  ".join("-" * widths[h] for h in headers))
    for row in table:
        print("  ".join(fmt(row[h]).ljust(widths[h]) for h in headers))

    # Per-resource normalization (helps explain why % savings vary).
    print("\nPer-resource cost (synth_ms / resources, in microseconds):")
    for row in table:
        if row["resources"]:
            us = row["synth_ms"] * 1000.0 / row["resources"]
            print(f"  {row['app']:8s} {us:8.2f} us/resource  (build={row['build']})")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=headers)
            w.writeheader()
            w.writerows(table)
        print(f"\nCSV written to {args.csv}")


if __name__ == "__main__":
    main()
