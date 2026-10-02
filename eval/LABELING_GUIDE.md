# Labelling guide: flood depth eval

Two people label every photo **independently**. Don't look at each other's labels or at any model
output until both of you are done. Our headline accuracy is only as good as these labels.

## What to label
For each photo, judge the **deepest part of the drivable road you can see**: the carriageway, not
footpaths, drains, ditches, or fields. If the road surface isn't visible at all, judge the water
where vehicles would drive.

### Depth band
| Key | Band | Visual cues (roughly) |
|---|---|---|
| 1 | below 15 cm | Below a scooter floorboard; ankle-deep on an adult; kerbs still visible |
| 2 | 15-30 cm | Up to a car wheel's hub centre; mid-shin; kerb tops submerged |
| 3 | 30-60 cm | Above the hub, up to the top of a car tyre; up to the knee; auto-rickshaw floor wet |
| 4 | above 60 cm | Above car tyres; thigh-deep or more; water at car door handles or bus wheel mid-height |
| 0 | no usable reference | No object of known height touches the water, or the waterline can't be seen |
| x | reject | Not a street flood, a duplicate, a screenshot with heavy text overlay, or unusable quality |

Use the reference heights in [`backend/cities/blr.yaml`](../backend/cities/blr.yaml). If the depth is
right on a boundary, **pick the deeper band**, since that's what we want the model to do too.

### Can a typical car drive through? (y / n)
Imagine an ordinary hatchback driven carefully through the deepest part of the road shown.
- **y** if the water is below about 30 cm and isn't flowing strongly.
- **n** if it's 30 cm or deeper, **or** visibly fast-flowing water at any depth, **or** you'd tell a
  family member not to drive through it.
- Leave it blank when you chose 0 or x.

## Process
1. Start the tool: `backend/.venv/bin/python eval/label_server.py --labeller a` (your teammate uses
   `--labeller b --port 8766`), then open the printed URL.
2. Label with the keyboard: `1-4`/`0`/`x` for the band, `y`/`n` for the car, arrow keys to move.
3. Add a short note when unsure ("depth hard to judge, car far away").
4. When both of you are done, run `eval/adjudicate.py`. It prints agreement (Cohen's kappa) and
   lists disagreements in `eval/labels/conflicts.csv`. Discuss each one, fill in `final_band` and
   `final_car`, then run `eval/adjudicate.py --resolve`.

## Target set (Depth-40)
- About **10 photos per band**, plus **about 4** with no usable reference (band 0).
- A mix of day and night, cars, two-wheelers, people, and buses; India and Southeast Asia.
- Licences recorded in `eval/data/manifest.csv` (filled in automatically by `fetch_commons.py`).
  Only CC0, CC BY, CC BY-SA, public-domain, or our own photos.
- Hold out about 60 extra photos as the **test split** (`split=test` in the manifest) for Day 12.
  Never tune prompts on them.
