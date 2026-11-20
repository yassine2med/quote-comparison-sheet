import pytest

from quotecmp.cli import main
from quotecmp.core import QuoteError, all_items, load_bids, parse_weights, qty_conflicts, rank, summarize

W = {"price": 0.6, "lead": 0.2, "warranty": 0.2}


def test_default_weights():
    assert parse_weights(None) == W


def test_custom_weights():
    assert parse_weights("price=0.5,lead=0.3,warranty=0.2")["lead"] == 0.3


def test_weights_must_sum_to_one():
    with pytest.raises(QuoteError, match="add up to 1"):
        parse_weights("price=0.5,lead=0.5,warranty=0.5")


def test_unknown_weight():
    with pytest.raises(QuoteError, match="unknown weight"):
        parse_weights("cost=1")


def test_partial_weights():
    with pytest.raises(QuoteError, match="all three"):
        parse_weights("price=1")


def test_load_example():
    bids = load_bids("examples/quotes.csv")
    assert list(bids) == ["Northline Supply", "Bayview Mechanical", "Capital Climate", "Delta Facility Parts"]
    assert len(all_items(bids)) == 3


def test_vendor_totals():
    s = {x["vendor"]: x for x in summarize(load_bids("examples/quotes.csv"))}
    assert s["Northline Supply"]["total"] == 4 * 850 + 6 * 310 + 10 * 145
    assert s["Bayview Mechanical"]["lead"] == 21
    assert s["Bayview Mechanical"]["warranty"] == 6


def test_incomplete_bid_flagged_and_unranked():
    s = {x["vendor"]: x for x in summarize(load_bids("examples/quotes.csv"))}
    assert s["Delta Facility Parts"]["missing"] == ["Economizer actuator"]
    names = [r["vendor"] for r in rank(list(s.values()), W)]
    assert "Delta Facility Parts" not in names


def test_ranking_order_default():
    ranked = rank(summarize(load_bids("examples/quotes.csv")), W)
    assert ranked[0]["vendor"] == "Capital Climate"


def test_price_only_weights_pick_cheapest_complete():
    ranked = rank(summarize(load_bids("examples/quotes.csv")), parse_weights("price=1,lead=0,warranty=0"))
    assert ranked[0]["vendor"] == "Bayview Mechanical" and ranked[0]["score"] == 100.0


def test_scores_between_0_and_100():
    for r in rank(summarize(load_bids("examples/quotes.csv")), W):
        assert 0 < r["score"] <= 100


def test_qty_conflict_detected():
    assert len(qty_conflicts(load_bids("examples/quotes_qty_mismatch.csv"))) == 1
    assert qty_conflicts(load_bids("examples/quotes.csv")) == []


def test_duplicate_line_rejected(tmp_path):
    p = tmp_path / "q.csv"
    p.write_text("vendor,item,qty,unit_price,lead_time_days,warranty_months\nA,x,1,1,1,1\nA,x,1,1,1,1\n")
    with pytest.raises(QuoteError, match="twice"):
        load_bids(str(p))


def test_non_numeric_rejected(tmp_path):
    p = tmp_path / "q.csv"
    p.write_text("vendor,item,qty,unit_price,lead_time_days,warranty_months\nA,x,one,1,1,1\n")
    with pytest.raises(QuoteError, match="numbers"):
        load_bids(str(p))


def test_cli_exit_codes(capsys):
    assert main(["compare", "examples/quotes.csv"]) == 1
    assert "NO QUOTE" in capsys.readouterr().out
    assert main(["compare", "missing.csv"]) == 2
    assert main(["compare", "examples/quotes.csv", "--weights", "bad"]) == 2


def test_cli_clean_comparison_returns_zero(tmp_path, capsys):
    p = tmp_path / "q.csv"
    p.write_text("vendor,item,qty,unit_price,lead_time_days,warranty_months\nA,x,2,5,3,12\nB,x,2,6,2,12\n")
    assert main(["compare", str(p)]) == 0
    assert "WARNING" not in capsys.readouterr().out
