from eval.metrics import EvalRow, cohen_kappa, compute_metrics, go_no_go


def row(i, tb, tc, pb, pc, conf=0.8):
    return EvalRow(
        image_id=str(i),
        true_band=tb,
        true_car=tc,
        pred_band=pb,
        pred_car=pc,
        confidence=conf,
        latency_ms=1000 + i,
        cost_usd=0.002,
    )


def test_perfect_predictions():
    rows = [row(1, "lt15", True, "lt15", True), row(2, "30to60", False, "30to60", False)]
    m = compute_metrics(rows)
    assert m["band_accuracy"] == 1.0
    assert m["car_accuracy"] == 1.0
    assert m["car_false_safe_rate"] == 0.0
    assert m["coverage"] == 1.0
    assert go_no_go(m) == "GO"


def test_false_safe_is_counted_against_impassable_only():
    rows = [
        row(1, "30to60", False, "15to30", True),  # dangerous miss
        row(2, "gt60", False, "gt60", False),
        row(3, "lt15", True, "15to30", False),  # over-cautious
        row(4, "lt15", True, "lt15", True),
    ]
    m = compute_metrics(rows)
    assert m["car_false_safe_rate"] == 0.5
    assert m["car_false_unsafe_rate"] == 0.5
    assert m["car_accuracy"] == 0.5
    assert m["band_within_one"] == 1.0
    assert go_no_go(m) == "PIVOT"


def test_abstention_lowers_coverage_not_accuracy():
    rows = [
        row(1, "lt15", True, "lt15", True),
        row(2, "30to60", False, "insufficient_evidence", None),
        row(3, "insufficient_evidence", None, "insufficient_evidence", None),
    ]
    m = compute_metrics(rows)
    assert m["coverage"] == 0.5
    assert m["band_accuracy"] == 1.0
    assert m["abstained_on_unanswerable"] == 1.0
    assert m["car_accuracy_abstain_as_unsafe"] == 1.0


def test_failed_calls_are_reported():
    rows = [row(1, "lt15", True, None, None)]
    m = compute_metrics(rows)
    assert m["n_failed_calls"] == 1
    assert go_no_go(m) == "NO DATA"


def test_cohen_kappa():
    assert cohen_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    assert cohen_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"]) == 0.0
