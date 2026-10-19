"""Build eval/ui/purchases.html: purchase history, PM memory, and recommendations with confidence.

Usage:
  python3 eval/purchases/build_page.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "eval" / "purchases"))
import db as purchases_db  # noqa: E402
import recommender as R  # noqa: E402

OUT = ROOT / "eval" / "ui" / "purchases.html"
# (vendor, plan, slug for the judged claims)
CASES = [("Trello", "Premium", "trello"), ("Asana", "Starter", "asana"), ("ClickUp", "Business", "clickup"),
         ("Jira", "Standard", "jira"), ("Linear", "Plus", "linear"), ("YouTrack", "Per-user starting price", "youtrack")]


def build() -> None:
    memory = R.load_memory()
    db = purchases_db.connect()
    purchases = [dict(r) for r in db.execute("SELECT * FROM purchases ORDER BY vendor, purchased_on DESC")]
    db.close()
    recs = []
    for vendor, plan, slug in CASES:
        out = R.recommend(vendor, plan, slug, memory=memory, today=date.today())
        recs.append({"vendor": vendor, "plan": plan, **out})
    data = {"memory": memory, "purchases": purchases, "recommendations": recs,
            "memory_file": "eval/purchases/pm_memory.md"}
    payload = json.dumps(data, default=str).replace("</", "<\\/")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(TEMPLATE.replace("__DATA__", payload))
    print(f"wrote {OUT}")


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Purchase recommendations</title>
<style>
:root{--bg:#f7f7f5;--fg:#1c1c1a;--muted:#6b6b66;--card:#fff;--line:#e2e2dc;--ok:#1f7a4d;--bad:#b42318;--warn:#b54708;--info:#175cd3}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#151514;--fg:#f2f2ee;--muted:#9b9b94;--card:#1e1e1c;--line:#33332e;--ok:#5fd39a;--bad:#ff8a80;--warn:#fdb022;--info:#84adff}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1080px;margin:0 auto;padding:28px 16px 72px}
h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:32px 0 10px}
.lead{color:var(--muted);margin:0 0 18px;max-width:760px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-bottom:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.big{font-size:26px;font-weight:650}.label{color:var(--muted);font-size:13px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top;font-size:14px}
th{font-size:12px;color:var(--muted);text-transform:uppercase}tr:last-child td{border-bottom:0}
.rec{font-weight:650}.renew{color:var(--ok)}.negotiate{color:var(--warn)}.review_alternatives,.insufficient_data{color:var(--bad)}
.bar{height:8px;border-radius:4px;background:var(--line);overflow:hidden;margin-top:6px}.bar>div{height:100%;background:var(--info)}
pre{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px;font:13px/1.5 ui-monospace,Menlo,monospace;white-space:pre-wrap}
.muted{color:var(--muted);font-size:13px}.pill{display:inline-block;padding:1px 8px;border-radius:999px;border:1px solid var(--line);font-size:12px}
@media (max-width:640px){th,td{font-size:13px}}
</style></head>
<body><main>
<h1>Purchase recommendations</h1>
<p class="lead">Each recommendation compares the current verified price and the judged evidence with the last purchase and the PM's memory. The confidence score is the product of the factors shown; a low factor means less certainty.</p>

<h2>Recommendations</h2>
<div id="recs"></div>

<h2>Past purchases</h2>
<div style="overflow-x:auto"><table><thead><tr><th>Vendor</th><th>Plan</th><th>Unit price</th><th>Unit / billing</th><th>Seats</th><th>Purchased</th><th>Price verified</th><th>Source / note</th></tr></thead><tbody id="purch"></tbody></table></div>

<h2>PM memory</h2>
<p class="muted">This is the memory the recommender reads. It is edited in <code id="memfile"></code> as <code>key: value</code> lines. The page shows what the recommender used.</p>
<div id="memory"></div>
</main>
<script>
const D = __DATA__;
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const pct = x => Math.round(x * 100) + "%";
const name = k => k.replace(/_/g, " ");

function recs() {
  document.getElementById("recs").innerHTML = D.recommendations.map(r => {
    const f = Object.entries(r.factors).map(([k, v]) =>
      `<div style="margin:4px 0"><span class="label">${esc(name(k))}</span> ${v.toFixed(2)}<div class="bar"><div style="width:${Math.round(v*100)}%"></div></div></div>`).join("");
    const last = r.last_purchase ? `${esc(r.last_purchase.unit_price)} on ${esc(r.last_purchase.purchased_on)} (${r.last_purchase.price_verified ? "verified" : "illustrative"})` : "none";
    const cur = r.current_price ? `${esc(r.current_price.amount)} ${esc(r.current_price.unit)} (checked ${esc(String(r.current_price.checked_at).slice(0,10))})` : "no verified price";
    return `<div class="card">
      <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px">
        <div><strong>${esc(r.vendor)} ${esc(r.plan)}</strong><div class="muted">Last purchase: ${last} · Current: ${cur}</div></div>
        <div style="text-align:right"><div class="rec ${esc(r.recommendation)}">${esc(name(r.recommendation))}</div><div class="label">confidence</div><div class="big">${r.confidence.toFixed(2)}</div></div>
      </div>
      <div class="grid" style="margin-top:10px"><div>${f}</div><div><div class="label">Reasons</div><ul style="margin:4px 0;padding-left:18px">${r.reasons.map(x => `<li>${esc(x)}</li>`).join("")}</ul></div></div>
    </div>`;
  }).join("");
}

function purchases() {
  document.getElementById("purch").innerHTML = D.purchases.map(p =>
    `<tr><td>${esc(p.vendor)}</td><td>${esc(p.plan)}</td><td>${esc(p.unit_price)} ${esc(p.currency)}</td><td>${esc(p.unit)} / ${esc(p.billing)}</td><td>${esc(p.seats)}</td><td>${esc(p.purchased_on)}</td><td>${p.price_verified ? "yes" : "<span style='color:var(--warn)'>no</span>"}</td><td class="muted">${esc(p.note)}${p.price_source ? ` <a href="${esc(p.price_source)}">source</a>` : ""}</td></tr>`).join("");
}

function memory() {
  document.getElementById("memfile").textContent = D.memory_file;
  document.getElementById("memory").innerHTML = `<div class="card"><table><thead><tr><th>Key</th><th>Value</th></tr></thead><tbody>${
    Object.entries(D.memory).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(Array.isArray(v) ? v.join(", ") : v)}</td></tr>`).join("")}</tbody></table></div>`;
}

recs(); purchases(); memory();
</script>
</body></html>
"""

if __name__ == "__main__":
    build()
