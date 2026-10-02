"""Run the depth agent over the labelled eval set and report metrics.

Example:
    python eval/run_depth_eval.py --models gemini-3.8-flash,gemini-3.5-flash-lite \
        --prompts v1,v2 --split dev

Every model response is cached under eval/results/cache/, so re-running only pays for new calls.
"""

import argparse
import asyncio
import csv
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO), str(REPO / "backend")]

from app.agents.depth import assess_depth  # noqa: E402
from app.config import load_city  # noqa: E402
from app.fusion.passability import car_passable  # noqa: E402
from app.services.media import prepare_image  # noqa: E402
from eval.metrics import EvalRow, compute_metrics, go_no_go  # noqa: E402

EVAL = REPO / "eval"
IMAGES = EVAL / "data" / "images"
RESULTS = EVAL / "results"
CACHE = RESULTS / "cache"


def load_rows(labels_path: Path, split: str) -> list[dict]:
    with open(EVAL / "data" / "manifest.csv") as f:
        manifest = {r["image_id"]: r for r in csv.DictReader(f)}
    with open(labels_path) as f:
        labels = list(csv.DictReader(f))
    rows = []
    for lab in labels:
        meta = manifest.get(lab["image_id"])
        if meta is None:
            print(f"warning: {lab['image_id']} is labelled but missing from manifest.csv")
            continue
        if lab["depth_band"].strip() in ("", "reject"):
            continue
        if split != "all" and meta.get("split", "dev") != split:
            continue
        rows.append({**meta, **lab})
    return rows


def parse_car(value: str) -> bool | None:
    return {"y": True, "n": False}.get(value.strip().lower()[:1])


def cost_usd(model: str, input_tokens: int, output_tokens: int, pricing: dict) -> float | None:
    price = pricing.get(model) or {}
    if price.get("input") is None or price.get("output") is None:
        return None
    return (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000


async def run_one(row, *, city, model, prompt, thinking, media_res, sem, cache_dir, use_cache):
    cache_file = cache_dir / f"{row['image_id']}.json"
    if use_cache and cache_file.exists():
        return json.loads(cache_file.read_text())

    image = prepare_image((IMAGES / row["filename"]).read_bytes())
    res, last_error = None, None
    async with sem:
        for attempt in range(3):
            try:
                res = await assess_depth(
                    image,
                    city,
                    row.get("caption") or None,
                    model=model,
                    prompt_version=prompt,
                    thinking_level=thinking,
                    media_resolution=media_res,
                )
                break
            except Exception as e:  # network / quota errors: retry with backoff
                last_error = e
                await asyncio.sleep(2 ** (attempt + 1))
    if res is None:  # not cached, so a later run retries it
        return {"image_id": row["image_id"], "error": f"call_failed: {last_error}"}

    out = {
        "image_id": row["image_id"],
        "assessment": res.assessment.model_dump() if res.assessment else None,
        "latency_ms": res.latency_ms,
        "input_tokens": res.input_tokens,
        "output_tokens": res.output_tokens,
        "error": res.error,
        "raw_text": res.raw_text if res.error else None,
    }
    cache_file.write_text(json.dumps(out, indent=2))
    return out


def to_eval_row(row: dict, out: dict, city, model: str, pricing: dict) -> EvalRow:
    a = out.get("assessment")
    pred_band: str | None = a["depth_band"] if a else None
    pred_car = car_passable(pred_band, a["water_flow"], city) if a and pred_band else None
    return EvalRow(
        image_id=row["image_id"],
        true_band=row["depth_band"].strip(),
        true_car=parse_car(row.get("car_passable", "")),
        pred_band=pred_band,
        pred_car=pred_car,
        confidence=a["confidence"] if a else None,
        latency_ms=out.get("latency_ms"),
        cost_usd=cost_usd(model, out.get("input_tokens", 0), out.get("output_tokens", 0), pricing)
        if out.get("input_tokens")
        else None,
        error=out.get("error"),
    )


def plot_confusion(metrics: dict, title: str, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = ["<15", "15-30", "30-60", ">60"]
    m = metrics["confusion_matrix"]["rows_true_cols_pred"]
    fig, ax = plt.subplots(figsize=(4.6, 4))
    ax.imshow(m, cmap="Blues")
    ax.set_xticks(range(4), labels)
    ax.set_yticks(range(4), labels)
    ax.set_xlabel("Predicted depth (cm)")
    ax.set_ylabel("Human label (cm)")
    ax.set_title(title, fontsize=9)
    peak = max(max(r) for r in m) or 1
    for i in range(4):
        for j in range(4):
            ax.text(
                j,
                i,
                m[i][j],
                ha="center",
                va="center",
                color="white" if m[i][j] > peak / 2 else "black",
            )
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def write_latest() -> None:
    summaries = sorted(RESULTS.glob("*_summary.json"))
    lines = [
        "# Latest depth eval results",
        "",
        "| Run | Model | Prompt | Split | n | Coverage | Band acc | ±1 band | Car acc | "
        "False-safe | p50 ms | $/1k | Verdict |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for p in summaries[-30:]:
        s = json.loads(p.read_text())
        m = s["metrics"]
        lines.append(
            f"| {s['run']} | {s['model']} | {s['prompt']} | {s['split']} | {m['n_images']} | "
            f"{m['coverage']} | {m['band_accuracy']} | {m['band_within_one']} | "
            f"{m['car_accuracy']} | {m['car_false_safe_rate']} | {m['latency_ms_p50']} | "
            f"{m['cost_usd_per_1000']} | {s['verdict']} |"
        )
    (RESULTS / "LATEST.md").write_text("\n".join(lines) + "\n")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="gemini-3.8-flash")
    ap.add_argument("--prompts", default="v1,v2")
    ap.add_argument("--split", default="dev", choices=["dev", "test", "all"])
    ap.add_argument("--labels", default=str(EVAL / "labels" / "adjudicated.csv"))
    ap.add_argument("--city", default="blr")
    ap.add_argument("--thinking-level", default=None, help="minimal|low|medium|high")
    ap.add_argument("--media-resolution", default=None, help="MEDIA_RESOLUTION_HIGH etc.")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    city = load_city(args.city)
    pricing = yaml.safe_load((EVAL / "pricing.yaml").read_text())
    rows = load_rows(Path(args.labels), args.split)[: args.limit]
    if not rows:
        sys.exit("No labelled rows found. Check manifest.csv, the labels file and --split.")

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    RESULTS.mkdir(exist_ok=True)
    sem = asyncio.Semaphore(args.concurrency)

    for model in args.models.split(","):
        for prompt in args.prompts.split(","):
            thinking = args.thinking_level or "default"
            media = args.media_resolution or "default"
            tag = f"{model}_{prompt}_{thinking}_{media}"
            cache_dir = CACHE / tag
            cache_dir.mkdir(parents=True, exist_ok=True)
            outs = await asyncio.gather(
                *[
                    run_one(
                        r,
                        city=city,
                        model=model,
                        prompt=prompt,
                        thinking=args.thinking_level,
                        media_res=args.media_resolution,
                        sem=sem,
                        cache_dir=cache_dir,
                        use_cache=not args.no_cache,
                    )
                    for r in rows
                ]
            )
            eval_rows = [
                to_eval_row(r, o, city, model, pricing) for r, o in zip(rows, outs, strict=True)
            ]
            metrics = compute_metrics(eval_rows)
            verdict = go_no_go(metrics)

            stem = f"{run_id}_{tag}"
            (RESULTS / f"{stem}_summary.json").write_text(
                json.dumps(
                    {
                        "run": run_id,
                        "model": model,
                        "prompt": prompt,
                        "split": args.split,
                        "thinking_level": args.thinking_level,
                        "media_resolution": args.media_resolution,
                        "verdict": verdict,
                        "metrics": metrics,
                        "rows": [asdict(r) for r in eval_rows],
                    },
                    indent=2,
                )
            )
            plot_confusion(
                metrics,
                f"{model} · prompt {prompt} · n={metrics['n_images']}",
                RESULTS / f"{stem}_confusion.png",
            )

            print(f"\n=== {model} / prompt {prompt} / split {args.split} ===")
            for k in (
                "n_images",
                "n_failed_calls",
                "coverage",
                "band_accuracy",
                "band_within_one",
                "car_accuracy",
                "car_false_safe_rate",
                "car_accuracy_abstain_as_unsafe",
                "latency_ms_p50",
                "latency_ms_p95",
                "cost_usd_per_1000",
            ):
                print(f"  {k:32} {metrics[k]}")
            print(f"  {'VERDICT':32} {verdict}")

    write_latest()
    print(f"\nWrote results to {RESULTS} (summary table: eval/results/LATEST.md)")


if __name__ == "__main__":
    asyncio.run(main())
