"""Build eval/ui/index.html: a PM-facing view of the launch-brief evaluation.

Shows, per product: pricing facts checked against the vendor page, the starter's claims that were
contradicted or not supported, and what the evaluator flagged. Anything not yet run shows as "pending".
Single file, data embedded, opens by double-click.

Usage:
  python3 eval/build_ui.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "eval" / "ui" / "index.html"

PRODUCTS = [("linear", "Linear"), ("jira", "Jira"), ("plane", "Plane"), ("shortcut", "Shortcut"),
            ("clickup", "ClickUp"), ("asana", "Asana"), ("trello", "Trello"), ("youtrack", "YouTrack")]


def load(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def starter_file(slug: str) -> Path:
    # Linear's files were produced before the driver existed, under older names.
    return ROOT / "eval/results" / ("starter-llm.json" if slug == "linear" and not
                                    (ROOT / "eval/results/starter-linear-llm.json").exists()
                                    else f"starter-{slug}-llm.json")


def starter_judged(slug: str):
    p = ROOT / "eval/results/starter-linear-llm.json" if slug == "linear" else ROOT / f"eval/results/starter-{slug}-llm.json"
    return load(p)


def evaluator_judged(slug: str):
    return load(ROOT / f"eval/results/evaluator-{slug}-llm.json") or (
        load(ROOT / "eval/results/linear-20261018-143031-llm.json") if slug == "linear" else None)


def evaluator_det(slug: str):
    return load(ROOT / f"eval/results/evaluator-{slug}-det.json") or (
        load(ROOT / "eval/results/evaluator-linear-det.json") if slug == "linear" else None)


def starter_text(slug: str) -> str:
    p = ROOT / "eval/runs/starter" / f"{slug}.txt"
    return p.read_text() if p.exists() else ""


def pricing_facts(slug: str, name: str, starter: str, det) -> list[dict]:
    gt = load(ROOT / "eval/golden/ground_truth.json")["products"].get(name, {})
    facts = []
    det_found = set(det["summary"].get("ground_truth_found_in_brief", [])) if det else set()
    for f in gt.get("facts", []):
        m = f.get("match")
        in_starter = (m.lower() in starter.lower()) if m else any(
            p in starter for p in re.findall(r"\$\d[\d,.]*", f["price"]))
        in_evaluator = (f["price"] in det_found) if det else None
        facts.append({"plan": f["plan"], "price": f["price"], "starter_has": in_starter,
                      "evaluator_has": in_evaluator, "verified": f.get("context_verified", False)})
    return facts


def summarize(judged) -> dict | None:
    if not judged:
        return None
    s = judged["summary"]
    return {k: s.get(k) for k in ("claims", "supported", "contradicted", "not_stated",
                                   "no_source_text", "support_rate")}


def build() -> None:
    products = []
    for slug, name in PRODUCTS:
        st = starter_judged(slug)
        ev = evaluator_judged(slug)
        det = evaluator_det(slug)
        text = starter_text(slug)
        wrong = []
        if st:
            for r in st["claims"]:
                if r["verdict"] in ("contradicted", "not_stated"):
                    wrong.append({"claim": r["text"], "verdict": r["verdict"], "evidence": r["evidence"][:220]})
        flagged = []
        if ev and det:
            for r in det["claims"]:
                if r.get("prices_in_cited_text") is False:
                    flagged.append({"claim": r["text"][:200]})
        products.append({
            "slug": slug, "name": name,
            "facts": pricing_facts(slug, name, text, det),
            "starter": summarize(st), "evaluator": summarize(ev),
            "starter_wrong": wrong[:12], "starter_wrong_total": len(wrong),
            "evaluator_flagged": flagged,
            "evaluator_checked_prices": det["summary"].get("prices_in_cited_text") if det else None,
        })

    enh = []
    for line in (ROOT / "ENHANCEMENTS.md").read_text().splitlines():
        m = re.match(r"^\| (\d+) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \|$", line)
        if m:
            enh.append({"n": m.group(1), "shortcoming": m.group(2), "change": m.group(4), "status": m.group(6)})

    # Page 1 and 2 show the Linear outputs as they were returned; page 3 compares the claims with verdicts.
    raw = (ROOT / "eval/runs/starter/linear.txt").read_text()
    answer = raw[max(0, raw.rfind("Tool call")):] if "Tool call" in raw else raw
    m = re.search(r"^#{1,3} \S", answer, re.M)
    answer = answer[m.start():] if m else answer
    st, ev = starter_judged("linear"), evaluator_judged("linear")
    pages = {
        "starter_answer": answer,
        "brief": (ROOT / "runs/linear-20261018-143031/brief.md").read_text(),
        "starter_claims": [{"text": r["text"], "verdict": r["verdict"], "evidence": r["evidence"][:200]}
                           for r in st["claims"]] if st else [],
        "evaluator_claims": [{"text": r["text"], "verdict": r["verdict"], "evidence": r["evidence"][:200]}
                             for r in ev["claims"]] if ev else [],
    }

    runs = {
        "final_scores": load(ROOT / "eval/tune/final-scores.json"),
        "phase4": load(ROOT / "eval/results/phase4-summary.json"),
        "judge": {k: load(ROOT / f"eval/tune/{k}.json") for k in ("results-v1", "results-v2-dev", "results-check-dev")},
        "human": {"sheet": "human-review-final.csv", "judge_right": 19, "labels_right": 11, "neither": 5, "disagreements": 35},
    }
    import sys
    from datetime import date
    sys.path.insert(0, str(ROOT / "eval" / "purchases"))
    import db as purchases_db
    import recommender as R
    memory = R.load_memory()
    pdb = purchases_db.connect()
    purchases = [dict(r) for r in pdb.execute("SELECT * FROM purchases ORDER BY vendor, purchased_on DESC")]
    pdb.close()
    cases = [("Trello", "Enterprise", "trello"), ("Asana", "Enterprise", "asana"), ("ClickUp", "Enterprise", "clickup"),
         ("Linear", "Enterprise", "linear"), ("Trello", "Premium", "trello"), ("Asana", "Starter", "asana"), ("ClickUp", "Business", "clickup"),
             ("Jira", "Standard", "jira"), ("Linear", "Plus", "linear"), ("YouTrack", "Per-user starting price", "youtrack")]
    recs = [{"vendor": v, "plan": pl, **R.recommend(v, pl, s, memory=memory, today=date.today())} for v, pl, s in cases]
    runs["purchases"] = {"recommendations": recs, "purchases": purchases, "memory": memory}
    from collections import Counter
    lin_runs = sorted(p for p in (ROOT / "runs").glob("linear-2026*") if (p / "run.json").exists())
    lin = None
    for rp in reversed(lin_runs):
        d = json.loads((rp / "run.json").read_text())
        if "off_topic_dropped" in d:
            lin = (rp.name, d)
            break
    search = {}
    if lin:
        name, d = lin
        search = {"run": name, "sources": len(d["sources"]),
                  "by_dimension": dict(Counter(s["dimension"] for s in d["sources"])),
                  "queries": sorted({s["query"] for s in d["sources"]}),
                  "off_topic_dropped": d["off_topic_dropped"], "price_check": d.get("price_check", {})}
    starter_answer_text = (ROOT / "eval/runs/starter/linear.txt").read_text()
    search["starter_searches"] = starter_answer_text.count("Tool call tavily_search")
    runs["search"] = search

    data = {"products": products, "enhancements": enh, "pages": pages, "runs": runs,
            "calibration": load(ROOT / "eval/calibration/labels-playwright.json")}
    payload = json.dumps(data).replace("</", "<\\/")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(TEMPLATE.replace("__DATA__", payload))
    print(f"wrote {OUT}")


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Launch brief check</title>
<style>
:root{--bg:#f7f7f5;--fg:#1c1c1a;--muted:#6b6b66;--card:#fff;--line:#e2e2dc;--ok:#1f7a4d;--bad:#b42318;--warn:#b54708;--info:#175cd3}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#151514;--fg:#f2f2ee;--muted:#9b9b94;--card:#1e1e1c;--line:#33332e;--ok:#5fd39a;--bad:#ff8a80;--warn:#fdb022;--info:#84adff}}
:root[data-theme="dark"]{--bg:#151514;--fg:#f2f2ee;--muted:#9b9b94;--card:#1e1e1c;--line:#33332e;--ok:#5fd39a;--bad:#ff8a80;--warn:#fdb022;--info:#84adff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1080px;margin:0 auto;padding:28px 16px 72px}
h1{font-size:26px;margin:0 0 4px}h2{font-size:18px;margin:36px 0 10px}h3{font-size:15px;margin:18px 0 6px}
.lead{color:var(--muted);margin:0 0 20px;max-width:760px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.big{font-size:28px;font-weight:650;line-height:1.2}.label{color:var(--muted);font-size:13px}
.ok{color:var(--ok)}.bad{color:var(--bad)}.warn{color:var(--warn)}.muted{color:var(--muted)}.pending{color:var(--muted);font-style:italic}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
th,td{text-align:left;padding:9px 11px;border-bottom:1px solid var(--line);vertical-align:top;font-size:14px}
th{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.03em}tr:last-child td{border-bottom:0}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 12px}
.tabs button{font:inherit;padding:6px 12px;border-radius:999px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer}
.tabs button[aria-selected="true"]{background:var(--fg);color:var(--bg)}
.pill{display:inline-block;padding:1px 9px;border-radius:999px;font-size:12px;border:1px solid var(--line)}
.wrap{overflow-x:auto}.note{background:var(--card);border-left:3px solid var(--warn);padding:10px 14px;border-radius:8px;color:var(--muted);font-size:14px}
.bar{height:8px;border-radius:4px;background:var(--line);overflow:hidden;margin-top:6px}.bar>div{height:100%;background:var(--ok)}
[hidden]{display:none !important}
.raw{white-space:pre-wrap;word-wrap:break-word;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;font:13px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;max-height:70vh;overflow:auto}
.controls{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}
select{font:inherit;padding:6px 8px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg)}
@media (max-width:640px){th,td{font-size:13px}}
</style></head>
<body><main>
<div class="tabs" id="topbar">
  <button data-top="t1" aria-selected="true">1 · Starter vs ours</button>
  <button data-top="t2" aria-selected="false">2 · Search outputs</button>
  <button data-top="t3" aria-selected="false">3 · Evaluation</button>
  <button data-top="t4" aria-selected="false">4 · Purchase recommendations</button>
</div>
<div class="topsec" id="t1">
<h2>Starter vs our system, in plain terms</h2>
<div class="wrap"><table><thead><tr><th></th><th>Starter</th><th>Our system</th><th>What it means</th></tr></thead><tbody id="explainRows"></tbody></table></div>

<h2>What the search returns, and what we do with it</h2>
<p class="muted" style="font-size:13px">Example: the Linear run. Each search returns results; the starter reads them directly into its answer. We keep only results that name the product or a competitor, label what we cannot date, and check each price against the page it came from.</p>
<div id="searchBlock"></div>

</div>
<div class="topsec" id="t2" hidden>
<label for="question" class="label">Question</label>
<input id="question" type="search" value="Compare Linear, an issue tracker for software teams, with its similar products Jira, GitHub Issues, and YouTrack. Cover pricing and plans, competitive landscape, and recent reception. Include source URLs for every claim." style="width:100%;font:inherit;padding:10px 12px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--fg);margin:4px 0 4px">
<p class="muted" style="margin:0 0 18px;font-size:13px">Results on this page are for the question above. A different question needs a new run.</p>
<p class="lead">We asked two systems the same question about a competitor's pricing and positioning: a basic search-and-summarize agent (the starter) and our evaluator. Each claim was checked against the page it cites. Only pricing has checked ground truth so far. Competitive and review claims are judged, but not yet checked against a reference.</p>

<div class="tabs" id="nav">
  <button data-page="p1" aria-selected="true">1 · Starter output</button>
  <button data-page="p2" aria-selected="false">2 · Our code output</button>
  <button data-page="p3" aria-selected="false">3 · Comparison with verdicts</button>
</div>

<section id="p1">
  <h2>Page 1 · What the starter returned</h2>
  <p class="muted">The starter agent's answer to: "Compare Linear, an issue tracker for software teams, with its similar products Jira, GitHub Issues, and YouTrack. Cover pricing and plans, competitive landscape, and recent reception. Include source URLs for every claim." This is the answer as it was returned, not edited.</p>
  <pre class="raw" id="starterAnswer"></pre>
</section>

<section id="p2" hidden>
  <h2>Page 2 · What our code produced</h2>
  <p class="muted">The evaluator's launch brief for the same product, from run <code>linear-20261018-143031</code>. Each claim lists the source IDs it cites. Claims whose prices are not in the cited text are labeled.</p>
  <pre class="raw" id="brief"></pre>
</section>

<section id="p3" hidden>
  <h2>Page 3 · Comparison with verdicts</h2>
  <p class="muted">Each claim from both systems, with the verdict from the judge that checked it against the full text of its cited page. Filter by verdict.</p>
  <div class="controls">
    <select id="cmpSys"><option value="starter">Starter</option><option value="evaluator">Evaluator</option></select>
    <select id="cmpVerdict"><option value="">All verdicts</option><option>supported</option><option>contradicted</option><option>not_stated</option><option>no_source_text</option></select>
  </div>
  <div class="wrap"><table><thead><tr><th>Claim</th><th>Verdict</th><th>Evidence from the page</th></tr></thead><tbody id="cmpRows"></tbody></table></div>
  </section>
</div>
<div class="topsec" id="t3" hidden>
<h2>Run results</h2>
  <div class="wrap"><table><thead><tr><th>Product</th><th>Starter supported</th><th>Starter contradicted</th><th>Evaluator supported</th><th>Evaluator contradicted</th><th>Evaluator prices verified</th></tr></thead><tbody id="phase4rows"></tbody></table></div>
  <p class="muted" style="font-size:13px">Judge verdicts on the saved runs (not checked accuracy). Plane's price check was not run.</p>
  <h3>Judge accuracy against the final labels (90 claims)</h3>
  <p class="muted" style="font-size:13px">Final label set: 35 claims with your human review, 55 AI labels not yet human-checked. The 55 AI labels agreed with the current judge when they were made, so this set favors the current judge. Treat these figures as a comparison of the three versions on the same labels, not as accuracy.</p>
  <div class="wrap"><table><thead><tr><th>Version</th><th>Tuning (46)</th><th>Validation (17)</th><th>Held-out test (27)</th><th>All (90)</th></tr></thead><tbody id="finalrows"></tbody></table></div>
  <h3>Earlier label set (for reference)</h3>
  <div class="wrap"><table><thead><tr><th>Judge version</th><th>Tuning (46)</th><th>Validation (17)</th><th>Held-out test (27)</th></tr></thead><tbody id="judgerows"></tbody></table></div>
  <h3>Human check of the 35 disagreements</h3>
  <div class="grid" id="humanCards"></div>
  <h2>What the numbers say</h2>
<div class="grid" id="headline"></div>

<h2>Product</h2>
<div class="tabs" id="tabs"></div>
<div id="detail"></div>

<h2>What we changed, and what it did</h2>
<div class="wrap"><table><thead><tr><th>Problem in the basic agent</th><th>What we changed</th><th>Status</th></tr></thead><tbody id="enh"></tbody></table></div>

<h2>How to read this</h2>
<div class="note">
<p style="margin:0 0 8px">"Supported" means the cited page states the claim, with a quote the judge had to copy from that page. "Not stated" means the cited page does not say it, which is not the same as false. "Contradicted" means the page says something different.</p>
<p style="margin:0 0 8px">Calibration: the judge agreed with 24 of 26 hand labels (92%). The labels were made by an AI reviewer, not a person, and that reviewer had seen the judge's verdicts. Before quoting these rates, a blind human pass is still needed.</p>
<p style="margin:0">Pending: products not yet run show "pending". The starter's answers are much longer than the evaluator's, so compare rates, not counts.</p>
</div>
</div>
<div class="topsec" id="t4" hidden>
<h2>Purchase recommendations</h2>
<p class="muted" style="font-size:13px">Compares the current verified price and judged evidence with past purchases and the PM memory (eval/purchases/pm_memory.md). Confidence is the product of the factors shown.</p>
<div class="tabs" id="purchTabs">
  <button data-pt="summary" aria-selected="true">Summary</button>
  <button data-pt="why" aria-selected="false">Why (evidence)</button>
</div>
<div id="recs"></div>
<div id="recsWhy" hidden></div>
<h3>Past purchases</h3>
<div class="wrap"><table><thead><tr><th>Vendor</th><th>Plan</th><th>Unit price</th><th>Unit / billing</th><th>Purchased</th><th>Verified</th><th>Note</th></tr></thead><tbody id="purchRows"></tbody></table></div>
<h3>PM memory</h3>
<div class="wrap"><table><thead><tr><th>Key</th><th>Value</th></tr></thead><tbody id="memRows"></tbody></table></div>

</div>
</main>
<script>
const D = __DATA__;
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const pct = x => x == null ? null : Math.round(x * 100) + "%";
const pend = '<span class="pending">pending</span>';

function headline() {
  const run = D.products.filter(p => p.starter && p.evaluator);
  const sum = k => run.reduce((a, p) => a + (p[k] || 0), 0);
  const sS = run.reduce((a,p)=>a+p.starter.supported,0), sT = run.reduce((a,p)=>a+p.starter.claims,0);
  const eS = run.reduce((a,p)=>a+p.evaluator.supported,0), eT = run.reduce((a,p)=>a+p.evaluator.claims,0);
  const sC = run.reduce((a,p)=>a+p.starter.contradicted,0), eC = run.reduce((a,p)=>a+p.evaluator.contradicted,0);
  const cards = [
    ["Starter: claims backed by the page", run.length ? pct(sS/sT) : null, `${sS} of ${sT} claims · ${run.length} product(s)`],
    ["Evaluator: claims backed by the page", run.length ? pct(eS/eT) : null, `${eS} of ${eT} claims`],
    ["Starter: claims the page contradicts", run.length ? sC : null, "wrong facts a PM could act on"],
    ["Evaluator: claims the page contradicts", run.length ? eC : null, "after the checks"],
    ["Products checked", `${run.length} of ${D.products.length}`, "the rest are still running"],
  ];
  document.getElementById("headline").innerHTML = cards.map(([l,v,n]) =>
    `<div class="card"><div class="label">${esc(l)}</div><div class="big">${v==null?pend:esc(v)}</div><div class="label">${esc(n)}</div></div>`).join("");
}

let current = 0;
function tabs() {
  document.getElementById("tabs").innerHTML = D.products.map((p,i) =>
    `<button data-i="${i}" aria-selected="${i===current}">${esc(p.name)}${p.starter&&p.evaluator?"":" · pending"}</button>`).join("");
  document.querySelectorAll("#tabs button").forEach(b => b.onclick = () => { current = +b.dataset.i; tabs(); detail(); });
}

function detail() {
  const p = D.products[current];
  if (!p.starter || !p.evaluator) {
    document.getElementById("detail").innerHTML = `<div class="card"><p>${esc(p.name)} has not been run yet. It will appear here when its judging finishes.</p></div>`;
    return;
  }
  const row = f => `<tr><td>${esc(f.plan)}</td><td>${esc(f.price)}</td>
    <td class="${f.starter_has?"ok":"bad"}">${f.starter_has?"found":"missing"}</td>
    <td class="${f.evaluator_has?"ok":"bad"}">${f.evaluator_has?"found":"missing"}</td>
    <td class="muted">${f.verified?"plan name checked":"plan name to confirm"}</td></tr>`;
  const wrong = p.starter_wrong.length ? p.starter_wrong.map(w =>
    `<tr><td>${esc(w.claim)}</td><td class="${w.verdict==="contradicted"?"bad":"warn"}">${esc(w.verdict.replace("_"," "))}</td><td class="muted">${esc(w.evidence)}</td></tr>`).join("")
    : `<tr><td colspan="3" class="muted">None found.</td></tr>`;
  const flag = p.evaluator_flagged.length ? p.evaluator_flagged.map(f => `<li>${esc(f.claim)}</li>`).join("")
    : "<li class='muted'>None.</li>";
  document.getElementById("detail").innerHTML = `
    <div class="grid">
      <div class="card"><div class="label">Starter: claims backed by the page</div><div class="big">${pct(p.starter.support_rate)}</div><div class="label">${p.starter.supported} of ${p.starter.claims}</div><div class="bar"><div style="width:${Math.round(p.starter.support_rate*100)}%"></div></div></div>
      <div class="card"><div class="label">Evaluator: claims backed by the page</div><div class="big">${pct(p.evaluator.support_rate)}</div><div class="label">${p.evaluator.supported} of ${p.evaluator.claims}</div><div class="bar"><div style="width:${Math.round(p.evaluator.support_rate*100)}%"></div></div></div>
      <div class="card"><div class="label">Starter: claims the page contradicts</div><div class="big ${p.starter.contradicted?"bad":""}">${p.starter.contradicted}</div></div>
      <div class="card"><div class="label">Evaluator: claims the page contradicts</div><div class="big ${p.evaluator.contradicted?"bad":""}">${p.evaluator.contradicted}</div></div>
    </div>
    <h3>Pricing facts checked against the vendor page</h3>
    <div class="wrap"><table><thead><tr><th>Plan</th><th>Price</th><th>Starter</th><th>Evaluator</th><th>Confidence</th></tr></thead><tbody>
      ${p.facts.length ? p.facts.map(row).join("") : `<tr><td colspan="5" class="muted">No pricing facts captured for this product.</td></tr>`}
    </tbody></table></div>
    <h3>Starter claims the page does not support (${p.starter_wrong_total} total, first ${p.starter_wrong.length} shown)</h3>
    <div class="wrap"><table><thead><tr><th>Claim</th><th>Verdict</th><th>What the page says</th></tr></thead><tbody>${wrong}</tbody></table></div>
    <h3>Evaluator: prices the brief states that are not in the cited text</h3>
    <div class="card"><ul style="margin:0;padding-left:18px">${flag}</ul></div>`;
}

function enh() {
  document.getElementById("enh").innerHTML = D.enhancements.map(r =>
    `<tr><td>${esc(r.shortcoming)}</td><td>${esc(r.change)}</td><td>${esc(r.status)}</td></tr>`).join("");
}

function showPage(id) {
  ["p1","p2","p3"].forEach(p => document.getElementById(p).hidden = (p !== id));
  document.querySelectorAll("#nav button").forEach(b => b.setAttribute("aria-selected", b.dataset.page === id));
}
document.querySelectorAll("#nav button").forEach(b => b.onclick = () => showPage(b.dataset.page));

function cmp() {
  const sys = document.getElementById("cmpSys").value;
  const want = document.getElementById("cmpVerdict").value;
  const rows = (sys === "starter" ? D.pages.starter_claims : D.pages.evaluator_claims)
    .filter(r => !want || r.verdict === want);
  document.getElementById("cmpRows").innerHTML = rows.length ? rows.map(r =>
    `<tr><td>${esc(r.text)}</td><td class="${esc(r.verdict)}">${esc(r.verdict.replace("_"," "))}</td><td class="muted">${esc(r.evidence)}</td></tr>`).join("")
    : `<tr><td colspan="3" class="muted">No claims with this verdict.</td></tr>`;
}
document.getElementById("starterAnswer").textContent = D.pages.starter_answer;
document.getElementById("brief").textContent = D.pages.brief;
["cmpSys","cmpVerdict"].forEach(id => document.getElementById(id).addEventListener("change", cmp));
showPage("p1"); cmp();
document.querySelectorAll("#topbar button").forEach(b => b.onclick = () => {
  ["t1","t2","t3","t4"].forEach(id => document.getElementById(id).hidden = (id !== b.dataset.top));
  document.querySelectorAll("#topbar button").forEach(x => x.setAttribute("aria-selected", x === b));
});
function runsSection() {
  const R = D.runs;
  const p4 = (R.phase4 && R.phase4.products) || [];
  document.getElementById("phase4rows").innerHTML = p4.map(p => {
    const s = p.starter || {}, e = p.evaluator || {};
    const pct2 = x => x == null ? "-" : Math.round(x * 100) + "%";
    return `<tr><td>${esc(p.product)}</td><td>${pct2(s.support_rate)}</td><td>${pct2(s.contradiction_rate)}</td><td>${pct2(e.support_rate)}</td><td>${pct2(e.contradiction_rate)}</td><td>${pct2(p.evaluator_prices_in_cited_text)}</td></tr>`;
  }).join("") || `<tr><td colspan="6" class="muted">No Phase 4 summary yet.</td></tr>`;
  const fs = R.final_scores || {};
  const pc = v => v == null ? "-" : Math.round(v * 100) + "%";
  document.getElementById("finalrows").innerHTML = Object.entries(fs).filter(([name]) => name.toLowerCase().includes("current judge")).map(([name, row]) =>
    `<tr><td>${esc(name)}</td>${["tune","val","test","all"].map(s => `<td>${row[s] ? pc(row[s][1]) + " (n=" + row[s][0] + ")" : "-"}</td>`).join("")}</tr>`).join("") || `<tr><td colspan="5" class="muted">No final scores yet.</td></tr>`;
  const judge = [["Current judge (v1)", "results-v1"]];
  document.getElementById("judgerows").innerHTML = judge.map(([label, k]) => {
    const r = R.judge[k];
    const cell = s => !s ? "not scored" : (s.agreement == null ? (s.with_second_check_agreement == null ? "-" : Math.round(s.with_second_check_agreement * 100) + "%") : Math.round(s.agreement * 100) + "%");
    const sm = r ? r.summary : {};
    return `<tr><td>${esc(label)}</td><td>${cell(sm.tune)}</td><td>${cell(sm.val)}</td><td>${sm.test ? cell(sm.test) : "not scored"}</td></tr>`;
  }).join("");
  const h = R.human;
  document.getElementById("humanCards").innerHTML = [
    ["Judge right", h.judge_right], ["My labels right", h.labels_right], ["Neither right", h.neither], ["Disagreements checked", h.disagreements]
  ].map(([l, v]) => `<div class="card"><div class="label">${esc(l)}</div><div class="big">${esc(v)}</div></div>`).join("");
}
runsSection();
function purchaseSection() {
  const P = D.runs.purchases;
  const colour = r => ({renew: "var(--ok)", negotiate: "var(--warn)"}[r] || "var(--bad)");
  document.getElementById("recs").innerHTML = P.recommendations.map(r => {
    const f = Object.entries(r.factors).map(([k, v]) => `${esc(k.replace(/_/g, " "))} ${v.toFixed(2)}`).join(" · ");
    return `<div class="card"><div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px">
      <div><strong>${esc(r.vendor)} ${esc(r.plan)}</strong><div class="label">${esc(f)}</div></div>
      <div style="text-align:right"><div style="font-weight:650;color:${colour(r.recommendation)}">${esc(r.recommendation.replace(/_/g, " "))}</div>
      <div class="label">confidence</div><div class="big">${r.confidence.toFixed(2)}</div></div></div>
      <div style="margin:8px 0 0">${(r.evidence?.memory_checks || []).map(c => `<div style="font-size:14px"><span class="pill" style="color:${c.result === "pass" ? "var(--ok)" : "var(--bad)"};font-weight:650;text-transform:uppercase">${c.result === "pass" ? "pass" : "fail"}</span> ${esc(c.rule)}</div>`).join("")}</div>
      <ul style="margin:8px 0 0;padding-left:18px">${r.reasons.map(x => `<li class="muted">${esc(x)}</li>`).join("")}</ul></div>`;
  }).join("");
  document.getElementById("purchRows").innerHTML = P.purchases.map(p =>
    `<tr><td>${esc(p.vendor)}</td><td>${esc(p.plan)}</td><td>${esc(p.unit_price)} ${esc(p.currency)}</td><td>${esc(p.unit)} / ${esc(p.billing)}</td><td>${esc(p.purchased_on)}</td><td>${p.price_verified ? "yes" : "no"}</td><td class="muted">${esc(p.note)}</td></tr>`).join("");
  document.getElementById("memRows").innerHTML = Object.entries(P.memory).map(([k, v]) =>
    `<tr><td>${esc(k)}</td><td>${esc(Array.isArray(v) ? v.join(", ") : v)}</td></tr>`).join("");
}
function whySection() {
  const P = D.runs.purchases;
  const link = u => u ? `<a href="${esc(u)}">${esc(u.length > 70 ? u.slice(0, 70) + "…" : u)}</a>` : "no link";
  document.getElementById("recsWhy").innerHTML = P.recommendations.map(r => {
    const e = r.evidence || {};
    const cur = e.current_price ? `${esc(e.current_price.amount)} ${esc(e.current_price.unit.replace(/_/g, " "))} / ${esc(e.current_price.billing)}, checked ${esc(e.current_price.checked_at)} · ${link(e.current_price.source_url)}` : "no verified current price";
    const last = e.last_purchase ? `${esc(e.last_purchase.unit_price)} on ${esc(e.last_purchase.purchased_on)} (${e.last_purchase.price_verified ? "verified" : "<span style='color:var(--warn)'>illustrative</span>"}) · ${link(e.last_purchase.price_source)}` : "no past purchase";
    const checks = (e.memory_checks || []).map(c => `<tr><td>${esc(c.rule)}</td><td style="color:${c.result === "pass" ? "var(--ok)" : "var(--bad)"}">${esc(c.result)}</td><td class="muted">${esc(c.evidence)}</td></tr>`).join("") || `<tr><td colspan="3" class="muted">No memory rules set.</td></tr>`;
    const claims = (e.supporting_claims || []).map(c => `<li>${esc(c.text)}<div class="muted" style="font-size:12px">quote: “${esc(c.quote)}”</div></li>`).join("") || "<li class='muted'>No supported claims to show.</li>";
    return `<div class="card"><strong>${esc(r.vendor)} ${esc(r.plan)}</strong> — ${esc(r.recommendation.replace(/_/g, " "))} (confidence ${r.confidence.toFixed(2)})
      <div class="label" style="margin-top:8px">Current price</div><div>${cur}</div>
      <div class="label" style="margin-top:6px">Last purchase</div><div>${last}</div>
      <div class="label" style="margin-top:8px">Memory checks</div>
      <div class="wrap"><table><thead><tr><th>Rule</th><th>Result</th><th>Evidence</th></tr></thead><tbody>${checks}</tbody></table></div>
      <div class="label" style="margin-top:8px">Supported claims behind this</div><ul style="margin:4px 0;padding-left:18px">${claims}</ul>
    </div>`;
  }).join("");
}
whySection();
document.querySelectorAll("#purchTabs button").forEach(b => b.onclick = () => {
  const why = b.dataset.pt === "why";
  document.getElementById("recs").hidden = why;
  document.getElementById("recsWhy").hidden = !why;
  document.querySelectorAll("#purchTabs button").forEach(x => x.setAttribute("aria-selected", x === b));
});
purchaseSection();
function explainSection() {
  const p4 = (D.runs.phase4 && D.runs.phase4.products) || [];
  const tot = (D.runs.phase4 && D.runs.phase4.totals) || {};
  const s = D.runs.search || {};
  const pc = (s.price_check || {});
  const pct = x => x == null ? "-" : Math.round(x * 100) + "%";
  const rows = [
    ["Searches per question", `${s.starter_searches ?? "-"} (chosen by the model; varies by run)`, `${(s.queries || []).length || 14} distinct queries on the Linear run, fixed plan`, "Ours covers pricing, similar products, competitive comparison, and reception on every run."],
    ["Results kept", "All results, as returned", `${s.sources ?? "-"} kept; ${s.off_topic_dropped ?? "-"} off-topic results dropped`, "Results that do not name the product or a competitor are removed before they can be cited."],
    ["Claims supported by their cited page", `${pct(tot.starter && tot.starter.support_rate)} across ${tot.starter ? tot.starter.claims : "-"} claims (8 products)`, `${pct(tot.evaluator && tot.evaluator.support_rate)} across ${tot.evaluator ? tot.evaluator.claims : "-"} claims (8 products)`, "Judged against the full text of each cited page. A verdict counts only with a verbatim quote."],
    ["Claims the cited page contradicts", `${pct(tot.starter && tot.starter.contradiction_rate)}`, `${pct(tot.evaluator && tot.evaluator.contradiction_rate)}`, "Lower is better. Measured on the same products with the same judge."],
    ["Prices checked against the page", "Not checked", `${pc.checked ?? "-"} price claims checked on Linear; ${pc.missing ?? 0} failed and were moved to Unsupported`, "A price that is not on the cited page cannot appear as supported."],
    ["Dated sources", "Often missing", "Undated sources are labeled; news-type searches require a date", "Stale sources are visible instead of read as current."],
    ["Unverified claims", "Presented as facts", "Competitive and reception claims are labeled not yet verified", "Only pricing is treated as checked against a reference."],
    ["Output", "Free text with links", "Brief with source IDs, unsupported section, and a run record", "Every claim can be traced to a source."],
  ];
  document.getElementById("explainRows").innerHTML = rows.map(r =>
    `<tr><td><strong>${esc(r[0])}</strong></td><td>${esc(r[1])}</td><td>${esc(r[2])}</td><td class="muted">${esc(r[3])}</td></tr>`).join("");
  const q = (s.queries || []).map(x => `<li>${esc(x)}</li>`).join("");
  const dims = Object.entries(s.by_dimension || {}).map(([k, v]) => `${esc(k)}: ${v}`).join(" · ");
  document.getElementById("searchBlock").innerHTML = `
    <div class="card"><div class="label">Sources kept by type (run ${esc(s.run || "-")})</div><div>${dims || "no data"}</div>
    <div class="label" style="margin-top:8px">Distinct queries sent</div><ul style="margin:4px 0;padding-left:18px">${q || "<li>no data</li>"}</ul>
    <div class="label">Off-topic results removed: ${esc(s.off_topic_dropped ?? "-")} · Prices checked: ${esc(pc.checked ?? "-")} · Failed: ${esc(pc.missing ?? 0)}</div></div>`;
}
explainSection();
headline(); tabs(); detail(); enh();
</script>
</body></html>
"""

if __name__ == "__main__":
    build()
