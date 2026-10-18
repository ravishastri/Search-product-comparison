"""Build eval/ui/index.html: starter vs evaluator, with the enhancements and their measured effect.

Reads results that already exist on disk. A missing result is shown as "pending", not as zero.
The page is a single file with the data embedded, so it opens by double-click.

Usage:
  python3 eval/build_ui.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "eval" / "ui" / "index.html"


def load(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def enhancements_table() -> list[dict]:
    """Parse the shortcomings table in ENHANCEMENTS.md so the page matches the document."""
    text = (ROOT / "ENHANCEMENTS.md").read_text()
    rows = []
    for line in text.splitlines():
        m = re.match(r"^\| (\d+) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \|$", line)
        if m:
            rows.append({"n": m.group(1), "shortcoming": m.group(2), "change": m.group(4),
                         "status": m.group(6)})
    return rows


def build() -> None:
    starter_claims = load(ROOT / "eval/runs/starter/claims.json")
    starter_llm = load(ROOT / "eval/results/starter-llm.json")
    evaluator_det = load(ROOT / "eval/results/linear-20261018-143031.json")
    evaluator_llm = load(ROOT / "eval/results/linear-20261018-143031-llm.json")

    data = {
        "product": "Linear",
        "starter": {
            "claims": starter_claims["claims"] if starter_claims else [],
            "llm": starter_llm,
        },
        "evaluator": {
            "deterministic": evaluator_det,
            "llm": evaluator_llm,
        },
        "enhancements": enhancements_table(),
    }
    payload = json.dumps(data).replace("</", "<\\/")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(TEMPLATE.replace("__DATA__", payload))
    print(f"wrote {OUT}")


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Starter vs evaluator</title>
<style>
:root{--bg:#fafaf9;--fg:#1c1c1a;--muted:#6b6b66;--card:#fff;--line:#e4e4df;--ok:#1f7a4d;--bad:#b42318;--warn:#b54708;--info:#175cd3}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#161615;--fg:#f2f2ee;--muted:#9b9b94;--card:#1f1f1d;--line:#34342f;--ok:#5fd39a;--bad:#ff8a80;--warn:#fdb022;--info:#84adff}}
:root[data-theme="dark"]{--bg:#161615;--fg:#f2f2ee;--muted:#9b9b94;--card:#1f1f1d;--line:#34342f;--ok:#5fd39a;--bad:#ff8a80;--warn:#fdb022;--info:#84adff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:32px 0 12px}
.sub{color:var(--muted);margin:0 0 16px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
.big{font-size:26px;font-weight:600}.label{color:var(--muted);font-size:13px}
.pending{color:var(--muted);font-style:italic}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top;font-size:14px}
th{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.03em}
tr:last-child td{border-bottom:0}
.tag{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;border:1px solid var(--line)}
.supported{color:var(--ok)}.contradicted,.unverified_evidence{color:var(--bad)}.not_stated,.no_source_text{color:var(--warn)}
.controls{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}
select,input{font:inherit;padding:6px 8px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg)}
.wrap{overflow-x:auto}.muted{color:var(--muted)}a{color:var(--info)}
.bar{height:8px;border-radius:4px;background:var(--line);overflow:hidden}.bar>div{height:100%;background:var(--ok)}
@media (max-width:640px){th,td{font-size:13px}}
</style></head>
<body><main>
<h1>Starter vs evaluator</h1>
<p class="sub" id="sub"></p>

<h2>Scorecard</h2>
<div class="grid" id="cards"></div>
<p class="muted" style="font-size:13px">Starter numbers are from an LLM judge that reads the full text of each cited page. Evaluator numbers are from the same judge, once it has run on that brief. Cards show "pending" until a result exists. The judge is the same model that wrote the answers, and it has not yet been checked against hand labels.</p>

<h2>Enhancements and what they changed</h2>
<div class="wrap"><table><thead><tr><th>#</th><th>Starter shortcoming</th><th>What we changed</th><th>Status</th></tr></thead><tbody id="enh"></tbody></table></div>

<h2>Claims judged</h2>
<div class="controls">
  <select id="sys"><option value="starter">Starter</option><option value="evaluator">Evaluator</option></select>
  <select id="verdict"><option value="">All verdicts</option><option>supported</option><option>contradicted</option><option>not_stated</option><option>unverified_evidence</option><option>no_source_text</option></select>
  <input id="q" placeholder="Search claims" size="24">
</div>
<div class="wrap"><table><thead><tr><th>Claim</th><th>Verdict</th><th>Evidence (verbatim from the page)</th></tr></thead><tbody id="claims"></tbody></table></div>

<h2>Problems found and fixes</h2>
<p class="muted">The full list, with status for each, is in <code>ENHANCEMENTS.md</code> under "Problems found in runs, and fixes" and "Runs after the key fix".</p>
</main>
<script>
const D = __DATA__;
const pct = x => x == null ? null : Math.round(x * 100) + "%";
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

function card(label, value, note, bar) {
  const v = value == null ? '<span class="pending">pending</span>' : esc(value);
  const b = (bar != null && value != null) ? `<div class="bar" style="margin-top:6px"><div style="width:${Math.round(bar*100)}%"></div></div>` : "";
  return `<div class="card"><div class="label">${esc(label)}</div><div class="big">${v}</div>${b}<div class="label">${esc(note)}</div></div>`;
}

function scorecard() {
  const s = D.starter, e = D.evaluator;
  const sl = s.llm && s.llm.summary, el = e.llm && e.llm.summary, ed = e.deterministic && e.deterministic.summary;
  const starterCited = s.claims.length ? s.claims.filter(c => c.urls && c.urls.length).length / s.claims.length : null;
  const cards = [
    card("Starter: claims extracted", s.claims.length || null, "from the free-text answer"),
    card("Starter: support rate", sl ? pct(sl.support_rate) : null, sl ? `${sl.supported} of ${sl.claims} supported` : "LLM judge pending", sl && sl.support_rate),
    card("Starter: contradicted", sl ? sl.contradicted : null, "source says something different"),
    card("Starter: claims with a link", starterCited != null ? pct(starterCited) : null, "share of claims that cite a URL"),
    card("Evaluator: claims", ed ? ed.claims : null, "brief claims with source IDs"),
    card("Evaluator: claims with valid IDs", ed ? pct(ed.cited_ids_valid) : null, "cited source exists", ed && ed.cited_ids_valid),
    card("Evaluator: prices in cited text", ed ? pct(ed.prices_in_cited_text) : null, "deterministic check", ed && ed.prices_in_cited_text),
    card("Evaluator: support rate", el ? pct(el.support_rate) : null, el ? `${el.supported} of ${el.claims} supported` : "LLM judge pending", el && el.support_rate),
  ];
  document.getElementById("cards").innerHTML = cards.join("");
}

function enhancementRows() {
  document.getElementById("enh").innerHTML = D.enhancements.map(r =>
    `<tr><td>${esc(r.n)}</td><td>${esc(r.shortcoming)}</td><td>${esc(r.change)}</td><td>${esc(r.status)}</td></tr>`).join("");
}

function claimRows() {
  const sys = document.getElementById("sys").value;
  const want = document.getElementById("verdict").value;
  const q = document.getElementById("q").value.toLowerCase();
  let rows, note;
  if (sys === "starter") {
    const judged = D.starter.llm ? D.starter.llm.claims : null;
    note = judged ? "" : "The starter judge has not run yet, so only the extracted claims are shown.";
    rows = judged || D.starter.claims.map(c => ({text: c.text, verdict: "pending", evidence: (c.urls||[]).join(" ")}));
  } else {
    const judged = D.evaluator.llm ? D.evaluator.llm.claims : null;
    note = judged ? "" : "The evaluator judge has not run yet for this brief.";
    rows = judged || [];
  }
  rows = rows.filter(r => (!want || r.verdict === want) && (!q || (r.text||"").toLowerCase().includes(q)));
  const body = rows.map(r => `<tr><td>${esc(r.text)}</td><td class="${esc(r.verdict)}">${esc(r.verdict)}</td><td class="muted">${esc(r.evidence)}</td></tr>`).join("");
  document.getElementById("claims").innerHTML = body || `<tr><td colspan="3" class="muted">${esc(note) || "No claims match."}</td></tr>`;
}

document.getElementById("sub").textContent = `Product: ${D.product}. Same question for both systems, same judge, same ground truth.`;
scorecard(); enhancementRows(); claimRows();
["sys","verdict","q"].forEach(id => document.getElementById(id).addEventListener("input", claimRows));
</script>
</body></html>
"""

if __name__ == "__main__":
    build()
