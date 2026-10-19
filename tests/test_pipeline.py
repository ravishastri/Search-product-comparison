import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import evaluator  # noqa: E402
from evaluator import Claim, Source, fetch_page_text, judge_claims, structure_prices  # noqa: E402


def src(i: str, url: str) -> Source:
    return Source(id=i, url=url, title=i, content="", dimension="pricing", query="q")


class FakeTavily:
    def __init__(self, texts: dict[str, str], fail_basic: set[str] = frozenset()):
        self.texts = texts
        self.fail_basic = fail_basic
        self.calls: list[tuple[str, list[str]]] = []

    def extract(self, urls, extract_depth, format):
        self.calls.append((extract_depth, list(urls)))
        out = []
        for u in urls:
            if extract_depth == "basic" and u in self.fail_basic:
                out.append({"url": u, "raw_content": ""})
            else:
                out.append({"url": u, "raw_content": self.texts.get(u, "")})
        return {"results": out}


class JudgeClaims(unittest.TestCase):
    def setUp(self):
        self.sources = {"S1": src("S1", "https://a"), "S2": src("S2", "https://b")}
        self.texts = {"https://a": "Basic is $10 per user per month.", "https://b": "Other page."}

    def run_judge(self, verdicts: dict[str, str], claims: list[Claim]):
        def fake(llm, text, page_texts):
            return verdicts[text], "quote"
        with mock.patch.object(evaluator, "judge_one", side_effect=fake):
            return judge_claims(claims, self.sources, self.texts, judge=None)

    def test_supported_is_kept_as_written(self):
        c = Claim("pricing", "Basic is $10.", ["S1"])
        kept, rejected, counts = self.run_judge({"Basic is $10.": "supported"}, [c])
        self.assertEqual([k.text for k in kept], ["Basic is $10."])
        self.assertEqual(rejected, [])
        self.assertEqual(counts, {"supported": 1})

    def test_not_stated_moves_to_unsupported_with_reason(self):
        c = Claim("pricing", "Enterprise is $99.", ["S1"])
        kept, rejected, _ = self.run_judge({"Enterprise is $99.": "not_stated"}, [c])
        self.assertEqual(kept, [])
        self.assertEqual(rejected[0].text, "Enterprise is $99. (judge: not_stated)")

    def test_contradicted_moves_to_unsupported(self):
        c = Claim("pricing", "Basic is $12.", ["S1"])
        _, rejected, counts = self.run_judge({"Basic is $12.": "contradicted"}, [c])
        self.assertEqual(rejected[0].text, "Basic is $12. (judge: contradicted)")
        self.assertEqual(counts, {"contradicted": 1})

    def test_no_source_text_is_kept_and_labeled(self):
        c = Claim("reception", "Fans like it.", ["S2"])
        self.texts["https://b"] = ""
        kept, rejected, counts = self.run_judge({}, [c])
        self.assertEqual(kept[0].text, "Fans like it. (source text unavailable, not judged)")
        self.assertEqual(rejected, [])
        self.assertEqual(counts, {"no_source_text": 1})

    def test_judge_error_is_kept_and_labeled(self):
        c = Claim("pricing", "Basic is $10.", ["S1"])
        def boom(llm, text, page_texts):
            raise TimeoutError("slow")
        with mock.patch.object(evaluator, "judge_one", side_effect=boom):
            kept, rejected, counts = judge_claims([c], self.sources, self.texts, judge=None)
        self.assertEqual(kept[0].text, "Basic is $10. (judge error, not judged)")
        self.assertEqual(rejected, [])
        self.assertEqual(counts, {"judge_error": 1})


class StructuredPrices(unittest.TestCase):
    def test_price_fields_are_parsed(self):
        claims = [
            Claim("pricing", "Basic is $10 per user per month, billed annually.", ["S1"]),
            Claim("pricing", "Enterprise is custom.", ["S2"]),
            Claim("reception", "Fans like it.", ["S3"]),
        ]
        facts = structure_prices(claims)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["amounts"], ["10"])
        self.assertEqual(facts[0]["unit"], "per_user")
        self.assertEqual(facts[0]["billing"], "annual")

    def test_unknown_fields_stay_unknown(self):
        facts = structure_prices([Claim("pricing", "Team plan costs $50.", ["S1"])])
        self.assertEqual(facts[0]["unit"], "unknown")
        self.assertEqual(facts[0]["billing"], "unknown")


class FetchRetry(unittest.TestCase):
    def test_empty_basic_fetch_is_retried_with_advanced(self):
        tv = FakeTavily({"https://a": "text A", "https://b": "text B"}, fail_basic={"https://b"})
        texts = fetch_page_text(tv, ["https://a", "https://b"])
        self.assertEqual(texts, {"https://a": "text A", "https://b": "text B"})
        self.assertEqual(tv.calls[-1], ("advanced", ["https://b"]))

    def test_page_that_stays_empty_is_reported_as_empty(self):
        tv = FakeTavily({}, fail_basic={"https://c"})
        texts = fetch_page_text(tv, ["https://c"])
        self.assertEqual(texts, {"https://c": ""})


if __name__ == "__main__":
    unittest.main()
