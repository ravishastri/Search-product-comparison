# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "langchain-nebius>=0.1.0",
#   "langfuse>=5.0.0",
#   "python-dotenv>=1.0.0",
#   "rich>=13.0.0",
#   "tavily-python>=0.5.0",
#   "typer>=0.12.0",
# ]
# ///
"""
Search product comparison: product launch evaluator.

Given a product, it finds similar products, runs a fixed set of Tavily searches
per dimension, and writes a Markdown brief. Every claim cites source IDs that
Tavily returned. Claims with no valid source ID go in a separate "unsupported"
section.

The source check confirms that a cited ID exists. It does not confirm that the
source says what the claim says. That is measured in the eval phase.

Usage:
  uv run evaluator.py --product "Acme Search" --description "Search API for AI agents"
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import typer
from dotenv import load_dotenv
from langchain_nebius import ChatNebius
from langfuse import get_client, observe
from rich.console import Console
from tavily import TavilyClient

sys.path.insert(0, str(Path(__file__).resolve().parent / "eval"))
from llm_judge import judge_one  # noqa: E402

load_dotenv()

app = typer.Typer(add_completion=False)
console = Console()

DEFAULT_MODEL = "moonshotai/Kimi-K2.6"
MAX_SIMILAR = 3
RESULTS_PER_QUERY = 5
SNIPPET_CHARS = 1500  # what the writer sees per source; claims are judged against the full page text
# Judge choice from the 50-claim blind check: Kimi 43/50, DeepSeek-V4-Pro 38/50, Qwen3-235B-Instruct 37/50.
# Kimi is the default even though the writer is also Kimi; the self-preference risk is untested.
PIPELINE_JUDGE_MODEL = os.environ.get("PIPELINE_JUDGE_MODEL", "moonshotai/Kimi-K2.6")
JUDGE_WORKERS = 4
SEARCH_ATTEMPTS = 3
DIMENSION_TITLES = {
    "pricing": "Pricing and plans",
    "competitive": "Competitive landscape",
    "reception": "Recent reception",
}

SIMILAR_PROMPT = """You identify similar products. Given a product and search results, name up to {limit} products in the same category that target the same kind of customer.
Use only product names that appear in the search results. Do not include the product itself.
Only name products that are currently available. Skip any product that the results describe as shut down, discontinued, or sunset.
Return only JSON: {{"products": ["Name 1", "Name 2"]}}"""

BRIEF_PROMPT = """You write a product launch brief using only the evidence below.
Rules:
- Use only facts stated in the evidence. Do not add outside knowledge.
- Each claim must list the IDs (for example "S1") of the sources that support it.
- Write short, specific claims. Do not predict sales or make causal claims.
- Write every price as digits with a dollar sign, for example $10 or $5,000, never as words like "ten dollars".
- Paraphrase every claim in your own words. Do not copy sentences from the evidence. Use no quotation marks.
- Never combine quotes or statements from different people into one claim. Attribute each opinion to its source.
- Dimensions: "pricing", "competitive", "reception". Skip a dimension if the evidence does not cover it.
Return only JSON: {"claims": [{"dimension": "pricing", "text": "...", "sources": ["S1"]}]}"""


@dataclass
class PlannedSearch:
    dimension: str
    query: str
    time_range: str | None = None
    start_date: str | None = None  # YYYY-MM-DD; results dated before this are dropped
    topic: str | None = None  # "news" returns published_date; general results often have none
    require_date: bool = False  # drop results with no published date (for time-sensitive claims)


@dataclass
class Source:
    id: str
    url: str
    title: str
    content: str
    dimension: str
    query: str
    published: str = ""  # YYYY-MM-DD from Tavily, if provided


@dataclass
class Claim:
    dimension: str
    text: str
    source_ids: list[str]


def plan_discovery(product: str, category: str) -> PlannedSearch:
    """Search that finds similar products."""
    suffix = f" {category}" if category else ""
    return PlannedSearch("discovery", f"{product} alternatives competitors{suffix}")


def plan_searches(product: str, similar: list[str], today: date) -> list[PlannedSearch]:
    """Fixed query plan for the three dimensions. Reception covers the last 365 days only."""
    cutoff = (today - timedelta(days=365)).isoformat()
    plan = [PlannedSearch("pricing", f"{name} pricing plans") for name in [product, *similar]]
    dated = {"start_date": cutoff, "topic": "news", "require_date": True}
    plan += [PlannedSearch("competitive", f"{product} vs {name} features", **dated) for name in similar]
    plan.append(PlannedSearch("reception", f"{product} launch reviews {today.year}", **dated))
    return plan


def mentions_any(result: dict[str, Any], names: list[str]) -> bool:
    """True if the result names one of the products: whole word, as capitalized (e.g. "Plane", not "plane")."""
    text = f"{result.get('title') or ''} {result.get('content') or ''}"
    return any(re.search(rf"(?<![A-Za-z]){re.escape(n)}(?![A-Za-z])", text) for n in names if n)


def filter_relevant(results: list[dict[str, Any]], names: list[str]) -> tuple[list[dict[str, Any]], int]:
    """Keep only results that name a product in scope. Returns (kept, number dropped)."""
    if not names:
        return results, 0
    kept = [r for r in results if mentions_any(r, names)]
    return kept, len(results) - len(kept)


def add_sources(registry: list[Source], planned: PlannedSearch, results: list[dict[str, Any]]) -> list[Source]:
    """Add results to the registry, skipping URLs already seen. Returns the new sources."""
    known = {source.url for source in registry}
    added: list[Source] = []
    for result in results:
        url = (result.get("url") or "").strip()
        if not url or url in known:
            continue
        published = (result.get("published_date") or "")[:10]
        if planned.require_date and not published:
            continue  # time-sensitive claims need a date to check
        if planned.start_date and published and published < planned.start_date:
            continue  # dated before the search window; undated results are kept unless require_date
        known.add(url)
        source = Source(
            id=f"S{len(registry) + 1}",
            url=url,
            title=result.get("title") or "Untitled",
            content=" ".join((result.get("content") or "").split()),
            dimension=planned.dimension,
            query=planned.query,
            published=published,
        )
        registry.append(source)
        added.append(source)
    return added


def evidence_block(sources: list[Source], snippet_chars: int = SNIPPET_CHARS) -> str:
    return "\n\n".join(
        f"[{s.id}] {s.title}\nURL: {s.url}\nDimension: {s.dimension}\n{s.content[:snippet_chars]}"
        for s in sources
    )


def parse_json(text: str) -> Any:
    """Parse the first JSON object or array in a model reply, even if it is wrapped in prose or code fences.

    Reasoning blocks (<think>...</think>) are removed first, since they can contain braces and quotes.
    """
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    match = re.search(r"[\[{].*[\]}]", cleaned, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON found in model reply: {cleaned[:300]!r}")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON in model reply ({exc}): {match.group(0)[:300]!r}") from exc


def parse_similar(text: str, product: str, limit: int = MAX_SIMILAR) -> list[str]:
    names = parse_json(text).get("products", [])
    seen: set[str] = {product.lower()}
    result: list[str] = []
    for name in names:
        if not isinstance(name, str):
            continue
        cleaned = name.strip()
        if not cleaned or cleaned.lower() in seen:
            continue
        seen.add(cleaned.lower())
        result.append(cleaned)
    return result[:limit]


STATUS_PROMPT = """You check whether a software product is still available. Use only the search results below.
Answer "retired" only if a result says the product itself was shut down, discontinued, or sunset.
A shutdown of one plan, deployment type, or feature is not the product being retired.
Answer "active" if the results show it is currently sold or used. Answer "unknown" if the results do not say.
Return only JSON: {"status": "active" | "retired" | "unknown", "source": "S#"}
Use the source ID of the result you relied on, or "" if none."""

STATUSES = {"active", "retired", "unknown"}


def parse_status(text: str) -> tuple[str, str]:
    """Return (status, source_id). Anything other than a known status becomes 'unknown'."""
    data = parse_json(text)
    status = str(data.get("status", "unknown")).strip().lower()
    if status not in STATUSES:
        status = "unknown"
    return status, str(data.get("source", "") or "")


SOURCE_ID = re.compile(r"^S\d+$")


def parse_claims_checked(text: str) -> tuple[list[Claim], int]:
    """Claims from the model's JSON, with malformed items dropped. Returns (claims, dropped count).

    An item is malformed if it is not an object, has no text, or has a dimension outside the three
    we ask for. Source IDs that do not look like S<number> are discarded before the citation check.
    """
    raw = parse_json(text).get("claims", [])
    claims: list[Claim] = []
    dropped = 0
    for item in raw:
        if not isinstance(item, dict) or not str(item.get("text", "")).strip() \
                or str(item.get("dimension", "")) not in DIMENSION_TITLES:
            dropped += 1
            continue
        ids = [str(i) for i in item.get("sources", []) if isinstance(i, str) and SOURCE_ID.match(i)]
        claims.append(Claim(dimension=str(item["dimension"]), text=str(item["text"]).strip(), source_ids=ids))
    return claims, dropped


def parse_claims(text: str) -> list[Claim]:
    return parse_claims_checked(text)[0]


def check_claims(claims: list[Claim], valid_ids: set[str]) -> tuple[list[Claim], list[Claim]]:
    """Split claims into supported (at least one cited ID exists) and unsupported."""
    supported: list[Claim] = []
    unsupported: list[Claim] = []
    for claim in claims:
        ids = [i for i in claim.source_ids if i in valid_ids]
        target = supported if ids else unsupported
        target.append(Claim(claim.dimension, claim.text, ids))
    return supported, unsupported


PRICE_RE = re.compile(r"\$\d[\d,]*(?:\.\d+)?")


def fetch_page_text(tavily: TavilyClient, urls: list[str]) -> dict[str, str]:
    """Full text of each URL via Tavily extract. A URL that cannot be fetched maps to ''."""
    texts = {url: "" for url in urls}
    for i in range(0, len(urls), 20):
        res = tavily.extract(urls=urls[i:i + 20], extract_depth="basic", format="text")
        for r in res.get("results", []):
            texts[r["url"]] = r.get("raw_content") or ""
    # A page that came back empty gets one more try with advanced extraction.
    missing = [u for u, t in texts.items() if not t]
    for i in range(0, len(missing), 20):
        try:
            res = tavily.extract(urls=missing[i:i + 20], extract_depth="advanced", format="text")
        except Exception:
            continue
        for r in res.get("results", []):
            texts[r["url"]] = r.get("raw_content") or texts.get(r["url"], "")
    return texts


def judge_claims(
    claims: list[Claim], sources_by_id: dict[str, Source], texts: dict[str, str], judge: Any
) -> tuple[list[Claim], list[Claim], dict[str, int]]:
    """Judge each claim against the full text of the pages it cites.

    Only a "supported" verdict is kept as written. Claims the judge rejects move to unsupported,
    with the verdict in the text. Claims that could not be judged (no page text, or a judge error)
    stay, labeled, so nothing disappears without a reason.
    """
    def run(claim: Claim) -> tuple[Claim, str, str]:
        urls = [sources_by_id[i].url for i in claim.source_ids if i in sources_by_id][:3]
        page_texts = {u: texts[u] for u in urls if texts.get(u)}
        if not page_texts:
            return claim, "no_source_text", ""
        try:
            verdict, evidence = judge_one(judge, claim.text, page_texts)
        except Exception as exc:  # one failed judge call must not stop the run
            return claim, "judge_error", str(exc)
        return claim, verdict, evidence

    with ThreadPoolExecutor(max_workers=JUDGE_WORKERS) as pool:
        results = list(pool.map(run, claims))

    kept: list[Claim] = []
    rejected: list[Claim] = []
    counts: dict[str, int] = {}
    for claim, verdict, _evidence in results:
        counts[verdict] = counts.get(verdict, 0) + 1
        if verdict == "supported":
            kept.append(claim)
        elif verdict in ("no_source_text", "judge_error"):
            note = "source text unavailable" if verdict == "no_source_text" else "judge error"
            kept.append(Claim(claim.dimension, f"{claim.text} ({note}, not judged)", claim.source_ids))
        else:
            rejected.append(Claim(claim.dimension, f"{claim.text} (judge: {verdict})", claim.source_ids))
    return kept, rejected, counts


PRICE_UNITS = (("per user", "per_user"), ("per seat", "per_user"), ("per month", "per_month"))


def structure_prices(claims: list[Claim]) -> list[dict[str, Any]]:
    """Pricing claims as fields (amounts, unit, billing) for the run record. Missing fields are 'unknown'."""
    facts = []
    for c in claims:
        if c.dimension != "pricing":
            continue
        amounts = [m[1:] for m in PRICE_RE.findall(c.text)]
        if not amounts:
            continue
        lower = c.text.lower()
        unit = next((u for phrase, u in PRICE_UNITS if phrase in lower), "unknown")
        if "annual" in lower or "per year" in lower:
            billing = "annual"
        elif "monthly" in lower or "per month" in lower:
            billing = "monthly"
        else:
            billing = "unknown"
        facts.append({"claim": c.text, "amounts": amounts, "unit": unit, "billing": billing,
                      "source_ids": c.source_ids})
    return facts


def verify_prices(
    supported: list[Claim], sources_by_id: dict[str, Source], texts: dict[str, str]
) -> tuple[list[Claim], list[Claim], dict[str, int]]:
    """Check each price in a pricing claim against the full text of its cited pages.

    A price that is not on any cited page moves the claim to rejected. A claim whose pages
    could not be fetched is kept and labeled, so nothing disappears without a reason.
    """
    kept: list[Claim] = []
    rejected: list[Claim] = []
    counts = {"checked": 0, "missing": 0, "unavailable": 0}
    for claim in supported:
        figures = [m[1:] for m in PRICE_RE.findall(claim.text)]  # drop the leading "$"
        if claim.dimension != "pricing" or not figures:
            kept.append(claim)
            continue
        counts["checked"] += 1
        pages = [texts.get(sources_by_id[i].url, "") for i in claim.source_ids if i in sources_by_id]
        if not any(pages):
            counts["unavailable"] += 1
            kept.append(Claim(claim.dimension, f"{claim.text} (price check unavailable)", claim.source_ids))
            continue
        combined = " ".join(pages)
        missing = [f for f in figures if not re.search(r"(?<!\d)" + re.escape(f) + r"(?!\d)", combined)]
        if missing:
            counts["missing"] += 1
            shown = ", ".join("$" + m for m in missing)
            rejected.append(Claim(claim.dimension, f"{claim.text} (price {shown} not found on the cited page)",
                                  claim.source_ids))
        else:
            kept.append(claim)
    return kept, rejected, counts


def render_brief(
    product: str,
    similar: list[str],
    supported: list[Claim],
    unsupported: list[Claim],
    sources: list[Source],
    run_date: str,
) -> str:
    lines = [
        f"# Launch brief: {product}",
        "",
        f"Generated {run_date}. Similar products (same category, same target customer): "
        f"{', '.join(similar) if similar else 'none found'}.",
        "",
    ]
    dated = {s.id: bool(s.published) for s in sources}
    text_by_id = {s.id: s.content for s in sources}
    for dimension, title in DIMENSION_TITLES.items():
        # Pricing is the verified part. Other dimensions are cited but not checked against a reference yet.
        verified = dimension == "pricing"
        heading = title if verified else f"{title} (not yet verified)"
        lines += [f"## {heading}", ""]
        if not verified:
            lines += ["These claims cite sources but have not been checked against a reference. Treat them as leads.", ""]
        items = [c for c in supported if c.dimension == dimension]
        if not items:
            lines += ["No sourced claims for this dimension.", ""]
            continue
        for claim in items:
            cites = "".join(f"[{i}]" for i in claim.source_ids)
            undated = not any(dated.get(i, False) for i in claim.source_ids)
            note = " (date unknown)" if undated else ""
            if not verified:
                note += " (unverified)"
            # A price in the claim must appear in the text of a cited source; otherwise flag it.
            cited_text = " ".join(text_by_id.get(i, "") for i in claim.source_ids)
            if any(p not in cited_text for p in re.findall(r"\$\d[\d,]*(?:\.\d+)?", claim.text)):
                note += " (price not in cited text)"
            lines.append(f"- {claim.text} {cites}{note}")
        lines.append("")

    lines += ["## Unsupported claims", ""]
    if unsupported:
        lines += [f"- {c.text} (no valid source)" for c in unsupported]
    else:
        lines.append("None.")
    lines.append("")

    lines += ["## Sources", ""]
    lines += [f"- [{s.id}] {s.title} ({s.published or 'date unknown'}): {s.url}" for s in sources]
    return "\n".join(lines) + "\n"


@observe(as_type="generation", capture_input=False)
def llm_reply(llm: ChatNebius, system: str, user: str) -> str:
    get_client().update_current_generation(
        name="llm_reply", model=llm.model_name, input=[system, user]
    )
    message = llm.invoke([{"role": "system", "content": system}, {"role": "user", "content": user}])
    content = message.content
    text = content if isinstance(content, str) else "".join(b.get("text", "") for b in content if isinstance(b, dict))
    get_client().update_current_generation(output=text)
    if not text.strip():
        meta = getattr(message, "response_metadata", {}) or {}
        usage = getattr(message, "usage_metadata", None)
        raise ValueError(f"Empty model reply (finish_reason={meta.get('finish_reason')}, usage={usage})")
    return text


@observe(as_type="tool", capture_input=False)
def search(tavily: TavilyClient, planned: PlannedSearch) -> list[dict[str, Any]]:
    kwargs: dict[str, Any] = {
        "query": planned.query,
        "max_results": RESULTS_PER_QUERY,
        "search_depth": "advanced",
    }
    if planned.time_range:
        kwargs["time_range"] = planned.time_range
    if planned.start_date:
        kwargs["start_date"] = planned.start_date
    if planned.topic:
        kwargs["topic"] = planned.topic
    get_client().update_current_span(
        name=f"tavily_search:{planned.dimension}",
        input={
            "query": planned.query,
            "time_range": planned.time_range,
            "start_date": planned.start_date,
            "topic": planned.topic,
            "search_depth": "advanced",
        },
    )
    results: list[dict[str, Any]] = []
    for attempt in range(SEARCH_ATTEMPTS):
        try:
            results = tavily.search(**kwargs).get("results", [])
            break
        except Exception:
            if attempt == SEARCH_ATTEMPTS - 1:
                raise
            time.sleep(2 ** attempt)
    get_client().update_current_span(
        output=[{"title": r.get("title"), "url": r.get("url")} for r in results]
    )
    return results


@app.command()
@observe(name="launch_evaluation")
def main(
    product: str = typer.Option(..., help="Product name to evaluate"),
    description: str = typer.Option("", help="One-line product description"),
    category: str = typer.Option("", help="Product category, used to find similar products"),
    model: str = typer.Option(DEFAULT_MODEL, help="Nebius model name"),
    out_dir: Path = typer.Option(Path("runs"), help="Where to write the brief and run record"),
) -> None:
    for name in ("TAVILY_API_KEY", "NEBIUS_API_KEY"):
        if not os.getenv(name):
            console.print(f"[bold red]Missing {name}[/bold red]. Set it in your shell or .env file.")
            raise typer.Exit(code=1)

    now = datetime.now()
    run_date = now.strftime("%Y-%m-%d")
    tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    # The model can use the whole output budget on reasoning before writing any text (finish_reason=length).
    # 16384 still ran out on the brief (run linear-20261018-112447), so the limit is doubled. Use --model to try another model.
    llm = ChatNebius(model=model, max_tokens=32768, max_retries=3)
    sources: list[Source] = []
    errors: list[str] = []
    off_topic = 0  # results dropped because they name none of the products in scope

    console.rule(f"[bold blue]Evaluating {product}")

    # 1. Find similar products.
    discovery = plan_discovery(product, category)
    console.print(f"Discovery: {discovery.query}")
    try:
        kept, dropped = filter_relevant(search(tavily, discovery), [product])
        off_topic += dropped
        add_sources(sources, discovery, kept)
    except Exception as exc:
        errors.append(f"discovery: {exc}")
    similar: list[str] = []
    excluded_retired: list[str] = []
    candidate_status: dict[str, dict[str, str]] = {}
    if sources:
        try:
            candidates = parse_similar(
                llm_reply(llm, SIMILAR_PROMPT.format(limit=MAX_SIMILAR + 2), f"Product: {product}. {description}\n\n{evidence_block(sources)}"),
                product,
                limit=MAX_SIMILAR + 2,
            )
            # Check each candidate's status with its own search, then ask the model to judge it.
            # The discovery results often say nothing about a shutdown, so the judge needs evidence
            # about the candidate itself.
            for name in candidates:
                status_search = PlannedSearch("status", f"{name} discontinued or shut down", topic="news", require_date=True)
                try:
                    kept, dropped = filter_relevant(search(tavily, status_search), [name])
                    off_topic += dropped
                    add_sources(sources, status_search, kept)
                except Exception as exc:
                    errors.append(f"status search '{name}': {exc}")
            for name in candidates:
                own = [s for s in sources if s.dimension == "status" and s.query == f"{name} discontinued or shut down"]
                verdict, evidence = "unknown", ""
                if own:
                    try:
                        verdict, evidence = parse_status(llm_reply(llm, STATUS_PROMPT, f"Product: {name}\n\n{evidence_block(own)}"))
                    except (ValueError, json.JSONDecodeError) as exc:
                        errors.append(f"status judge '{name}': {exc}")
                candidate_status[name] = {"status": verdict, "source": evidence}
            excluded_retired = [n for n in candidates if candidate_status[n]["status"] == "retired"]
            similar = [n for n in candidates if n not in excluded_retired][:MAX_SIMILAR]
        except (ValueError, json.JSONDecodeError) as exc:
            errors.append(f"similar products: {exc}")
    if excluded_retired:
        console.print(f"Excluded as retired: {', '.join(excluded_retired)}")
    console.print(f"Similar products: {', '.join(similar) or 'none found'}")

    # 2. Run the fixed query plan.
    plan = plan_searches(product, similar, now.date())
    for planned in plan:
        console.print(f"Search [{planned.dimension}]: {planned.query}")
        try:
            kept, dropped = filter_relevant(search(tavily, planned), [product, *similar])
            off_topic += dropped
            added = add_sources(sources, planned, kept)
            console.print(f"  {len(added)} new sources")
        except Exception as exc:
            errors.append(f"{planned.dimension} '{planned.query}': {exc}")
            console.print(f"  [red]failed: {exc}[/red]")

    # 3. Write the brief from the evidence, then check its citations.
    claims: list[Claim] = []
    malformed_claims = 0
    if sources:
        user_prompt = f"Product: {product}. {description}\nSimilar products: {', '.join(similar) or 'none'}\n\nEvidence:\n\n{evidence_block(sources)}"
        for attempt in range(2):
            try:
                claims, malformed_claims = parse_claims_checked(llm_reply(llm, BRIEF_PROMPT, user_prompt))
                break
            except (ValueError, json.JSONDecodeError) as exc:
                errors.append(f"brief attempt {attempt + 1}: {exc}")
    supported, unsupported = check_claims(claims, {s.id for s in sources})

    # Pricing claims are checked against the full text of their cited pages before the brief is written.
    sources_by_id = {s.id: s for s in sources}
    texts: dict[str, str] = {}
    try:  # full text of every cited page, used by the price check and the judge
        texts = fetch_page_text(tavily, list({s.url for s in sources}))
    except Exception as exc:  # the brief still gets written, with the checks marked unavailable
        errors.append(f"page text fetch: {exc}")
    supported, rejected, price_counts = verify_prices(supported, sources_by_id, texts)
    unsupported = unsupported + rejected

    # Every supported claim is judged against the full text of its cited pages (a second model family).
    judge_counts: dict[str, int] = {}
    if supported:
        judge = ChatNebius(model=PIPELINE_JUDGE_MODEL, max_tokens=32768, timeout=300, max_retries=2, temperature=0)
        supported, judged_out, judge_counts = judge_claims(supported, sources_by_id, texts, judge)
        unsupported = unsupported + judged_out

    # 4. Write the brief and the run record.
    run_dir = out_dir / f"{re.sub(r'[^a-z0-9]+', '-', product.lower()).strip('-')}-{now.strftime('%Y%m%d-%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    brief = render_brief(product, similar, supported, unsupported, sources, run_date)
    (run_dir / "brief.md").write_text(brief)
    record = {
        "product": product,
        "price_check": price_counts,
        "off_topic_dropped": off_topic,
        "description": description,
        "category": category,
        "model": model,
        "judge_model": PIPELINE_JUDGE_MODEL,
        "judge_counts": judge_counts,
        "search": {"depth": "advanced", "results_per_query": RESULTS_PER_QUERY},
        "snippet_chars": SNIPPET_CHARS,
        "pricing_facts": structure_prices(supported),
        "malformed_claims_dropped": malformed_claims,
        "pages_unfetched": sorted(u for u, t in texts.items() if not t),
        "run_date": run_date,
        "similar": similar,
        "candidate_status": candidate_status,
        "excluded_retired": excluded_retired,
        "queries": [discovery.query, *[p.query for p in plan]],
        "errors": errors,
        "sources": [asdict(s) for s in sources],
        "supported_claims": [asdict(c) for c in supported],
        "unsupported_claims": [asdict(c) for c in unsupported],
    }
    (run_dir / "run.json").write_text(json.dumps(record, indent=2))

    console.print(f"\n[green]Sources:[/green] {len(sources)}  [green]Supported claims:[/green] {len(supported)}  "
                  f"[yellow]Unsupported:[/yellow] {len(unsupported)}  [red]Errors:[/red] {len(errors)}")
    get_client().update_current_span(
        input={"product": product, "description": description, "category": category, "model": model},
        output={
            "similar": similar,
            "sources": len(sources),
            "supported_claims": len(supported),
            "unsupported_claims": len(unsupported),
            "errors": errors,
            "run_dir": str(run_dir),
        },
    )
    get_client().flush()

    console.print(f"Brief: {run_dir / 'brief.md'}")
    console.print(f"Run record: {run_dir / 'run.json'}")


if __name__ == "__main__":
    app()
