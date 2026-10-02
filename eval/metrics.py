"""Pure metric functions for the depth evaluation. No I/O, so they are easy to test."""

from collections import Counter
from dataclasses import dataclass
from statistics import median

from app.models.depth import BANDS


@dataclass
class EvalRow:
    image_id: str
    true_band: str  # one of BANDS or "insufficient_evidence"
    true_car: bool | None  # human label: can a typical car drive through? None = unsure
    pred_band: str | None  # None when the call failed
    pred_car: bool | None
    confidence: float | None = None
    latency_ms: int | None = None
    cost_usd: float | None = None
    error: str | None = None


def _rate(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round(pct / 100 * (len(ordered) - 1))))
    return ordered[idx]


def confusion_matrix(rows: list[EvalRow]) -> list[list[int]]:
    """4x4 over BANDS: matrix[true][pred], answered rows with a measurable truth only."""
    m = [[0] * len(BANDS) for _ in BANDS]
    for r in rows:
        if r.true_band in BANDS and r.pred_band in BANDS:
            m[BANDS.index(r.true_band)][BANDS.index(r.pred_band)] += 1
    return m


def macro_f1(matrix: list[list[int]]) -> float | None:
    f1s = []
    for i in range(len(matrix)):
        tp = matrix[i][i]
        fp = sum(matrix[r][i] for r in range(len(matrix))) - tp
        fn = sum(matrix[i]) - tp
        if tp + fp + fn == 0:
            continue
        f1s.append(2 * tp / (2 * tp + fp + fn))
    return round(sum(f1s) / len(f1s), 4) if f1s else None


def compute_metrics(rows: list[EvalRow]) -> dict:
    total = len(rows)
    failed = sum(1 for r in rows if r.pred_band is None)
    answered = [r for r in rows if r.pred_band in BANDS]
    measurable = [r for r in rows if r.true_band in BANDS]
    scored = [r for r in answered if r.true_band in BANDS]
    unanswerable = [r for r in rows if r.true_band == "insufficient_evidence"]

    exact = sum(1 for r in scored if r.pred_band == r.true_band)
    within1 = sum(
        1 for r in scored if abs(BANDS.index(r.pred_band) - BANDS.index(r.true_band)) <= 1
    )
    matrix = confusion_matrix(rows)

    # Car passability on rows where both human and model gave a verdict.
    car = [r for r in rows if r.true_car is not None and r.pred_car is not None]
    car_correct = sum(1 for r in car if r.pred_car == r.true_car)
    truly_impassable = [r for r in car if r.true_car is False]
    truly_passable = [r for r in car if r.true_car is True]
    false_safe = sum(1 for r in truly_impassable if r.pred_car is True)
    false_unsafe = sum(1 for r in truly_passable if r.pred_car is False)

    # Conservative view: an abstention is treated as "do not drive".
    car_all = [r for r in rows if r.true_car is not None]
    car_all_correct = sum(
        1 for r in car_all if (r.pred_car if r.pred_car is not None else False) == r.true_car
    )

    calibration = {}
    for name, lo, hi in (("low", 0.0, 0.4), ("medium", 0.4, 0.75), ("high", 0.75, 1.01)):
        bucket = [r for r in scored if r.confidence is not None and lo <= r.confidence < hi]
        calibration[name] = {
            "n": len(bucket),
            "band_accuracy": _rate(
                sum(1 for r in bucket if r.pred_band == r.true_band), len(bucket)
            ),
        }

    latencies = [r.latency_ms for r in rows if r.latency_ms is not None]
    costs = [r.cost_usd for r in rows if r.cost_usd is not None]
    mean_cost = sum(costs) / len(costs) if costs else None

    return {
        "n_images": total,
        "n_failed_calls": failed,
        "coverage": _rate(len([r for r in answered if r.true_band in BANDS]), len(measurable)),
        "band_accuracy": _rate(exact, len(scored)),
        "band_within_one": _rate(within1, len(scored)),
        "band_macro_f1": macro_f1(matrix),
        "confusion_matrix": {"labels": list(BANDS), "rows_true_cols_pred": matrix},
        "abstained_on_unanswerable": _rate(
            sum(1 for r in unanswerable if r.pred_band == "insufficient_evidence"),
            len(unanswerable),
        ),
        "car_n": len(car),
        "car_accuracy": _rate(car_correct, len(car)),
        "car_false_safe_rate": _rate(false_safe, len(truly_impassable)),
        "car_false_unsafe_rate": _rate(false_unsafe, len(truly_passable)),
        "car_accuracy_abstain_as_unsafe": _rate(car_all_correct, len(car_all)),
        "calibration": calibration,
        "latency_ms_p50": median(latencies) if latencies else None,
        "latency_ms_p95": _percentile(latencies, 95),
        "cost_usd_per_image": round(mean_cost, 6) if mean_cost is not None else None,
        "cost_usd_per_1000": round(mean_cost * 1000, 2) if mean_cost is not None else None,
    }


def go_no_go(metrics: dict) -> str:
    acc, fsr = metrics.get("car_accuracy"), metrics.get("car_false_safe_rate")
    if acc is None:
        return "NO DATA"
    if acc >= 0.80 and (fsr is None or fsr <= 0.10):
        return "GO"
    if acc >= 0.70:
        return "CONDITIONAL GO"
    return "PIVOT"


def cohen_kappa(a: list[str], b: list[str]) -> float | None:
    """Agreement between two labellers beyond chance."""
    if len(a) != len(b) or not a:
        return None
    n = len(a)
    observed = sum(1 for x, y in zip(a, b, strict=True) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    if expected == 1:
        return 1.0
    return round((observed - expected) / (1 - expected), 4)
