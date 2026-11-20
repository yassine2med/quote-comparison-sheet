"""Compare vendor quotes line by line and rank complete bids."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field

REQUIRED = ["vendor", "item", "qty", "unit_price", "lead_time_days", "warranty_months"]
DEFAULT_WEIGHTS = {"price": 0.6, "lead": 0.2, "warranty": 0.2}


class QuoteError(ValueError):
    """Raised for bad input data or bad weights."""


@dataclass(frozen=True)
class Line:
    vendor: str
    item: str
    qty: float
    unit_price: float
    lead_time_days: float
    warranty_months: float

    @property
    def total(self) -> float:
        return self.qty * self.unit_price


@dataclass
class Bid:
    vendor: str
    lines: dict[str, Line] = field(default_factory=dict)


def parse_weights(text: str | None) -> dict[str, float]:
    """Parse 'price=0.5,lead=0.3,warranty=0.2'. Weights must sum to 1."""
    if not text:
        return dict(DEFAULT_WEIGHTS)
    weights = {}
    for part in text.split(","):
        key, _, value = part.partition("=")
        key = key.strip()
        if key not in DEFAULT_WEIGHTS:
            raise QuoteError(f"unknown weight '{key}'; use price, lead, warranty")
        try:
            weights[key] = float(value)
        except ValueError as exc:
            raise QuoteError(f"weight '{key}' is not a number") from exc
    if set(weights) != set(DEFAULT_WEIGHTS):
        raise QuoteError("give all three weights: price, lead, warranty")
    if any(w < 0 for w in weights.values()) or abs(sum(weights.values()) - 1) > 1e-9:
        raise QuoteError("weights must be zero or more and add up to 1")
    return weights


def load_bids(path: str) -> dict[str, Bid]:
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise QuoteError(f"missing column(s): {', '.join(missing)}")
        rows = list(reader)
    bids: dict[str, Bid] = {}
    for i, row in enumerate(rows, start=2):
        vendor, item = row["vendor"].strip(), row["item"].strip()
        if not vendor or not item:
            raise QuoteError(f"line {i}: vendor and item are required")
        try:
            nums = [float(row[k]) for k in REQUIRED[2:]]
        except (TypeError, ValueError) as exc:
            raise QuoteError(f"line {i}: qty, unit_price, lead_time_days and warranty_months must be numbers") from exc
        if any(n < 0 for n in nums) or nums[0] == 0:
            raise QuoteError(f"line {i}: values cannot be negative and qty must be above zero")
        bid = bids.setdefault(vendor, Bid(vendor))
        if item in bid.lines:
            raise QuoteError(f"line {i}: {vendor} quoted '{item}' twice")
        bid.lines[item] = Line(vendor, item, *nums)
    if not bids:
        raise QuoteError("no quote rows found")
    return bids


def all_items(bids: dict[str, Bid]) -> list[str]:
    seen: list[str] = []
    for bid in bids.values():
        for item in bid.lines:
            if item not in seen:
                seen.append(item)
    return seen


def qty_conflicts(bids: dict[str, Bid]) -> list[str]:
    """Items where vendors quoted different quantities (an unfair comparison)."""
    notes = []
    for item in all_items(bids):
        qtys = {b.lines[item].qty for b in bids.values() if item in b.lines}
        if len(qtys) > 1:
            notes.append(f"'{item}' quoted with different quantities: {sorted(qtys)}")
    return notes


def summarize(bids: dict[str, Bid]) -> list[dict]:
    """Per vendor: total, worst lead time, shortest warranty, missing items."""
    items = all_items(bids)
    out = []
    for bid in bids.values():
        missing = [i for i in items if i not in bid.lines]
        lines = list(bid.lines.values())
        out.append({
            "vendor": bid.vendor,
            "total": sum(l.total for l in lines),
            "lead": max(l.lead_time_days for l in lines),
            "warranty": min(l.warranty_months for l in lines),
            "missing": missing,
        })
    return out


def rank(summary: list[dict], weights: dict[str, float]) -> list[dict]:
    """Score complete bids 0 to 100: cheapest, fastest and longest warranty score 1 in each part."""
    complete = [s for s in summary if not s["missing"]]
    if not complete:
        return []
    low_total = min(s["total"] for s in complete)
    low_lead = min(s["lead"] for s in complete)
    top_warranty = max(s["warranty"] for s in complete)
    ranked = []
    for s in complete:
        price = low_total / s["total"] if s["total"] else 1.0
        lead = low_lead / s["lead"] if s["lead"] else 1.0
        warranty = s["warranty"] / top_warranty if top_warranty else 1.0
        score = 100 * (weights["price"] * price + weights["lead"] * lead + weights["warranty"] * warranty)
        ranked.append(dict(s, score=round(score, 1)))
    ranked.sort(key=lambda s: (-s["score"], s["total"]))
    return ranked
