"""Fetch the full page text for URLs with Tavily extract. Results are cached on disk.

A failed or empty fetch is cached as an empty file, so the judge can report "no_source_text".
Cache lives in eval/cache/ and is not committed (it holds full page text).

Usage (from a module):
  from eval.fetch_sources import fetch
  texts = fetch(["https://..."])   # {url: text}
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()
CACHE = Path(__file__).resolve().parent / "cache"


def _path(url: str) -> Path:
    return CACHE / f"{hashlib.sha1(url.encode()).hexdigest()}.txt"


def fetch(urls: list[str]) -> dict[str, str]:
    CACHE.mkdir(parents=True, exist_ok=True)
    todo = [u for u in dict.fromkeys(urls) if not _path(u).exists()]
    if todo:
        client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
        for i in range(0, len(todo), 20):
            batch = todo[i:i + 20]
            res = client.extract(urls=batch, extract_depth="basic", format="text")
            for r in res.get("results", []):
                _path(r["url"]).write_text(r.get("raw_content") or "")
            for f in res.get("failed_results", []):
                url = f.get("url") if isinstance(f, dict) else str(f)
                if url:
                    _path(url).write_text("")
            for u in batch:  # anything not returned at all is also cached as empty
                if not _path(u).exists():
                    _path(u).write_text("")
    return {u: _path(u).read_text() for u in urls}
