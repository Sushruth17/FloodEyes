"""Pull openly licensed flood photos from Wikimedia Commons into the eval set.

Each image is appended to eval/data/manifest.csv with its source URL, licence and author, so
attribution is never lost. Reject unusable images later in the labelling tool.

Examples:
    python eval/fetch_commons.py --search "flooded street car India" --limit 30
    python eval/fetch_commons.py --category "Floods in Chennai" --limit 40
"""

import argparse
import csv
import re
import sys
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "eval" / "data"
IMAGES = DATA / "images"
MANIFEST = DATA / "manifest.csv"
FIELDS = [
    "image_id",
    "filename",
    "source_url",
    "license",
    "author",
    "city",
    "caption",
    "split",
    "notes",
]

API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "FloodEyesEval/0.1 (hackathon research; contact via repo)"}
ALLOWED = re.compile(r"^(cc0|cc[- ]by(-sa)?[- ][\d.]+.*|public domain|pd.*)$", re.I)


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def query(params: dict) -> list[dict]:
    base = {
        "action": "query",
        "format": "json",
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime",
        "iiurlwidth": 1600,
    }
    r = httpx.get(API, params={**base, **params}, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return list((r.json().get("query") or {}).get("pages", {}).values())


def load_manifest() -> list[dict]:
    if not MANIFEST.exists():
        return []
    with open(MANIFEST) as f:
        return list(csv.DictReader(f))


def main() -> None:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--search")
    src.add_argument("--category")
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--city", default="")
    args = ap.parse_args()

    if args.search:
        pages = query(
            {
                "generator": "search",
                "gsrsearch": args.search,
                "gsrnamespace": 6,
                "gsrlimit": min(args.limit, 50),
            }
        )
    else:
        pages = query(
            {
                "generator": "categorymembers",
                "gcmtitle": f"Category:{args.category}",
                "gcmtype": "file",
                "gcmlimit": min(args.limit, 50),
            }
        )

    rows = load_manifest()
    known = {r["source_url"] for r in rows}
    # Never reuse an ID: rows may have been removed, so count from the highest existing one.
    next_id = max((int(r["image_id"][3:]) for r in rows), default=0) + 1
    IMAGES.mkdir(parents=True, exist_ok=True)
    added = skipped_licence = 0

    for page in pages:
        info = (page.get("imageinfo") or [{}])[0]
        if info.get("mime") not in ("image/jpeg", "image/png"):
            continue
        meta = info.get("extmetadata", {})
        licence = strip_html(meta.get("LicenseShortName", {}).get("value", ""))
        if not ALLOWED.match(licence):
            skipped_licence += 1
            continue
        url = info.get("descriptionurl", "")
        if url in known:
            continue
        image_id = f"img{next_id:04d}"
        filename = f"{image_id}.jpg"
        img = httpx.get(info.get("thumburl") or info["url"], headers=HEADERS, timeout=60)
        if img.status_code != 200:
            continue
        (IMAGES / filename).write_bytes(img.content)
        rows.append(
            {
                "image_id": image_id,
                "filename": filename,
                "source_url": url,
                "license": licence,
                "author": strip_html(meta.get("Artist", {}).get("value", ""))[:120],
                "city": args.city,
                "caption": "",
                "split": "dev",
                "notes": page.get("title", "")[:120],
            }
        )
        known.add(url)
        next_id += 1
        added += 1

    with open(MANIFEST, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(
        f"Added {added} images ({skipped_licence} skipped for licence). Manifest: {len(rows)} rows."
    )


if __name__ == "__main__":
    sys.exit(main())
