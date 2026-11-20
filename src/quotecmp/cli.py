"""Command line entry for the quote comparison sheet."""

from __future__ import annotations

import argparse
import sys

from .core import QuoteError, all_items, load_bids, parse_weights, qty_conflicts, rank, summarize


def main(argv: list[str] | None = None) -> int:
    """Return 0 on success, 1 when quantities differ or a bid is incomplete, 2 on bad input."""
    parser = argparse.ArgumentParser(prog="quotecmp", description="Side-by-side vendor quote comparison")
    sub = parser.add_subparsers(dest="command", required=True)
    cmp_ = sub.add_parser("compare", help="compare quotes and rank the complete bids")
    cmp_.add_argument("file", help="quotes CSV")
    cmp_.add_argument("--weights", help="for example price=0.5,lead=0.3,warranty=0.2 (default 0.6, 0.2, 0.2)")
    args = parser.parse_args(argv)
    try:
        weights = parse_weights(args.weights)
        bids = load_bids(args.file)
    except FileNotFoundError:
        print(f"File not found: {args.file}", file=sys.stderr)
        return 2
    except QuoteError as exc:
        print(f"Bad input: {exc}", file=sys.stderr)
        return 2
    items = all_items(bids)
    vendors = list(bids)
    width = max(len(i) for i in items) + 2
    print(f"{'line total':<{width}}" + "".join(f"{v[:16]:>18}" for v in vendors))
    for item in items:
        cells = []
        totals = {v: bids[v].lines[item].total for v in vendors if item in bids[v].lines}
        low = min(totals.values())
        for v in vendors:
            if v in totals:
                mark = "*" if totals[v] == low and len(totals) > 1 else " "
                cells.append(f"{totals[v]:>16,.2f}{mark} ")
            else:
                cells.append(f"{'NO QUOTE':>18}")
        print(f"{item:<{width}}" + "".join(cells))
    print("(* = lowest line price)")
    summary = summarize(bids)
    problems = qty_conflicts(bids)
    print()
    print(f"{'rank':<5}{'vendor':<22}{'total':>11}{'lead days':>11}{'warranty mo':>13}{'score':>7}")
    ranked = rank(summary, weights)
    for pos, s in enumerate(ranked, start=1):
        print(f"{pos:<5}{s['vendor']:<22}{s['total']:>11,.2f}{s['lead']:>11g}{s['warranty']:>13g}{s['score']:>7.1f}")
    for s in summary:
        if s["missing"]:
            problems.append(f"{s['vendor']} is incomplete, not ranked: no quote for {', '.join(s['missing'])}")
    for note in problems:
        print(f"WARNING: {note}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
