"""Local labelling tool. Each labeller runs their own copy and never sees the other's labels.

    python eval/label_server.py --labeller a      # then open http://localhost:8765
    python eval/label_server.py --labeller b --port 8766

Keys: 1-4 depth band, 0 no reference object, y/n car passable, x reject image, ←/→ navigate.
Labels are saved to eval/labels/labeller_<name>.csv on every change.
"""

import argparse
import csv
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "eval" / "data"
LABELS_DIR = REPO / "eval" / "labels"
FIELDS = ["image_id", "depth_band", "car_passable", "notes"]

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Flood Eyes labelling</title>
<style>
 body{margin:0;font:15px system-ui;background:#111;color:#eee;display:flex;height:100vh}
 #img{flex:1;display:flex;align-items:center;justify-content:center;background:#000}
 #img img{max-width:100%;max-height:100vh}
 #side{width:340px;padding:16px;overflow:auto}
 button{display:block;width:100%;margin:4px 0;padding:8px;border:1px solid #444;background:#222;
   color:#eee;border-radius:6px;text-align:left;cursor:pointer}
 button.on{background:#2563eb;border-color:#2563eb}
 textarea{width:100%;height:60px;background:#222;color:#eee;border:1px solid #444}
 .muted{color:#999;font-size:13px}
</style></head><body><div id="img"><img id="pic"></div><div id="side">
<div id="pos" class="muted"></div><h3 id="title"></h3>
<b>Depth band</b> <span class="muted">(deepest drivable road surface)</span>
<div id="bands"></div><b>Can a typical car drive through?</b><div id="car"></div>
<b>Notes</b><textarea id="notes"></textarea>
<button onclick="go(-1)">← Prev</button><button onclick="go(1)">Next →</button>
<p class="muted">Keys: 1-4 band · 0 no reference · y/n car · x reject · ←/→</p>
<p class="muted" id="done"></p></div>
<script>
const BANDS=[["lt15","1 · below 15 cm"],["15to30","2 · 15-30 cm"],["30to60","3 · 30-60 cm"],
 ["gt60","4 · above 60 cm"],["insufficient_evidence","0 · no usable reference"],["reject","x · reject image"]];
const CARS=[["Y","y · yes"],["N","n · no"]];
let items=[],labels={},i=0;
async function load(){items=await (await fetch('/api/items')).json();
 labels=await (await fetch('/api/labels')).json();
 i=Math.max(0,items.findIndex(x=>!labels[x.image_id]));if(i<0)i=0;render();}
function cur(){return labels[items[i].image_id]||{image_id:items[i].image_id,depth_band:"",car_passable:"",notes:""}}
function render(){const it=items[i],l=cur();
 document.getElementById('pic').src='/img/'+encodeURIComponent(it.filename);
 document.getElementById('pos').textContent=(i+1)+' / '+items.length;
 document.getElementById('title').textContent=it.image_id;
 document.getElementById('bands').innerHTML=BANDS.map(([v,t])=>`<button class="${l.depth_band==v?'on':''}" onclick="set('depth_band','${v}')">${t}</button>`).join('');
 document.getElementById('car').innerHTML=CARS.map(([v,t])=>`<button class="${l.car_passable==v?'on':''}" onclick="set('car_passable','${v}')">${t}</button>`).join('');
 document.getElementById('notes').value=l.notes||'';
 document.getElementById('done').textContent=Object.keys(labels).length+' labelled';}
async function set(k,v){const l=cur();l[k]=v;if(k=='depth_band'&&(v=='reject'||v=='insufficient_evidence'))l.car_passable='';
 labels[l.image_id]=l;await save(l);render();}
async function save(l){await fetch('/api/label',{method:'POST',body:JSON.stringify(l)});}
function go(d){const l=cur();l.notes=document.getElementById('notes').value;if(labels[l.image_id])save(l);
 i=Math.min(items.length-1,Math.max(0,i+d));render();}
document.addEventListener('keydown',e=>{if(e.target.tagName=='TEXTAREA')return;
 const k=e.key.toLowerCase(),m={'1':'lt15','2':'15to30','3':'30to60','4':'gt60','0':'insufficient_evidence','x':'reject'};
 if(m[k])set('depth_band',m[k]);else if(k=='y')set('car_passable','Y');else if(k=='n')set('car_passable','N');
 else if(e.key=='ArrowRight')go(1);else if(e.key=='ArrowLeft')go(-1);});
load();
</script></body></html>"""


def make_handler(labels_path: Path):
    def read_labels() -> dict:
        if not labels_path.exists():
            return {}
        with open(labels_path) as f:
            return {r["image_id"]: r for r in csv.DictReader(f)}

    def write_labels(labels: dict) -> None:
        with open(labels_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(sorted(labels.values(), key=lambda r: r["image_id"]))

    class Handler(BaseHTTPRequestHandler):
        def _send(self, body: bytes, ctype: str, status: int = 200):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                self._send(PAGE.encode(), "text/html; charset=utf-8")
            elif self.path == "/api/items":
                with open(DATA / "manifest.csv") as f:
                    items = [
                        {"image_id": r["image_id"], "filename": r["filename"]}
                        for r in csv.DictReader(f)
                    ]
                self._send(json.dumps(items).encode(), "application/json")
            elif self.path == "/api/labels":
                self._send(json.dumps(read_labels()).encode(), "application/json")
            elif self.path.startswith("/img/"):
                path = DATA / "images" / Path(unquote(self.path[5:])).name
                if path.exists():
                    self._send(path.read_bytes(), "image/jpeg")
                else:
                    self._send(b"not found", "text/plain", 404)
            else:
                self._send(b"not found", "text/plain", 404)

        def do_POST(self):
            if self.path != "/api/label":
                return self._send(b"not found", "text/plain", 404)
            row = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            labels = read_labels()
            labels[row["image_id"]] = {k: row.get(k, "") for k in FIELDS}
            write_labels(labels)
            self._send(b"{}", "application/json")

        def log_message(self, *args):
            pass

    return Handler


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labeller", required=True)
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    labels_path = LABELS_DIR / f"labeller_{args.labeller}.csv"
    print(f"Labelling as '{args.labeller}' → {labels_path}\nOpen http://localhost:{args.port}")
    ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(labels_path)).serve_forever()


if __name__ == "__main__":
    main()
