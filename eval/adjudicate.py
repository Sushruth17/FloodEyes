"""Compare two labellers, report agreement (Cohen's kappa), and build adjudicated.csv.

    python eval/adjudicate.py                 # writes adjudicated.csv + conflicts.csv
    python eval/adjudicate.py --resolve       # after editing conflicts.csv, merge the resolutions

Images either labeller rejected are dropped. Disagreements go to conflicts.csv: discuss them,
fill in `final_band` and `final_car`, then run with --resolve.
"""

import argparse
import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO), str(REPO / "backend")]

from eval.metrics import cohen_kappa  # noqa: E402

LABELS = REPO / "eval" / "labels"
OUT_FIELDS = ["image_id", "depth_band", "car_passable", "notes"]


def read(path: Path) -> dict:
    with open(path) as f:
        return {r["image_id"]: r for r in csv.DictReader(f)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default=str(LABELS / "labeller_a.csv"))
    ap.add_argument("--b", default=str(LABELS / "labeller_b.csv"))
    ap.add_argument("--resolve", action="store_true")
    args = ap.parse_args()

    a, b = read(Path(args.a)), read(Path(args.b))
    common = sorted(set(a) & set(b))
    usable = [i for i in common if "reject" not in (a[i]["depth_band"], b[i]["depth_band"])]

    bands_a = [a[i]["depth_band"] for i in usable]
    bands_b = [b[i]["depth_band"] for i in usable]
    car_ids = [i for i in usable if a[i]["car_passable"] and b[i]["car_passable"]]
    print(f"Labelled by both: {len(common)} · usable: {len(usable)}")
    agree = sum(x == y for x, y in zip(bands_a, bands_b, strict=True))
    print(f"Band agreement: {agree}/{len(usable)} · kappa {cohen_kappa(bands_a, bands_b)}")
    print(
        f"Car agreement kappa: {
            cohen_kappa(
                [a[i]['car_passable'] for i in car_ids], [b[i]['car_passable'] for i in car_ids]
            )
        }"
    )

    resolved = {}
    conflicts_path = LABELS / "conflicts.csv"
    if args.resolve and conflicts_path.exists():
        with open(conflicts_path) as f:
            resolved = {r["image_id"]: r for r in csv.DictReader(f) if r.get("final_band")}

    final, conflicts = [], []
    for i in usable:
        la, lb = a[i], b[i]
        if la["depth_band"] == lb["depth_band"] and la["car_passable"] == lb["car_passable"]:
            final.append(
                {
                    "image_id": i,
                    "depth_band": la["depth_band"],
                    "car_passable": la["car_passable"],
                    "notes": la.get("notes", ""),
                }
            )
        elif i in resolved:
            r = resolved[i]
            final.append(
                {
                    "image_id": i,
                    "depth_band": r["final_band"],
                    "car_passable": r.get("final_car", ""),
                    "notes": "adjudicated",
                }
            )
        else:
            conflicts.append(
                {
                    "image_id": i,
                    "band_a": la["depth_band"],
                    "band_b": lb["depth_band"],
                    "car_a": la["car_passable"],
                    "car_b": lb["car_passable"],
                    "final_band": "",
                    "final_car": "",
                }
            )

    with open(LABELS / "adjudicated.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        w.writeheader()
        w.writerows(final)
    if not args.resolve or conflicts:
        with open(conflicts_path, "w", newline="") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "image_id",
                    "band_a",
                    "band_b",
                    "car_a",
                    "car_b",
                    "final_band",
                    "final_car",
                ],
            )
            w.writeheader()
            w.writerows(conflicts)
    print(f"adjudicated.csv: {len(final)} rows · unresolved conflicts: {len(conflicts)}")


if __name__ == "__main__":
    main()
