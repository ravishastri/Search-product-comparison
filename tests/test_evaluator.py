import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluator import (  # noqa: E402
    Claim,
    PlannedSearch,
    Source,
    add_sources,
    check_claims,
    parse_claims,
    parse_similar,
    parse_status,
    plan_discovery,
    plan_searches,
    render_brief,
    filter_relevant,
    verify_prices,
)


class PlanTests(unittest.TestCase):
    def test_discovery_query_includes_category(self):
        self.assertEqual(plan_discovery("Acme", "search API").query, "Acme alternatives competitors search API")

    def test_plan_covers_all_dimensions(self):
        plan = plan_searches("Acme", ["Beta", "Gamma"], date(2026, 10, 18))
        dims = [p.dimension for p in plan]
        self.assertEqual(dims.count("pricing"), 3)  # subject + 2 similar
        self.assertEqual(dims.count("competitive"), 2)  # one per similar product
        self.assertEqual(dims.count("reception"), 1)

    def test_each_must_have_gets_a_features_search(self):
        plan = plan_searches("Acme", ["Beta"], date(2026, 10, 18), must_have=["SSO", "time tracking"])
        queries = [p.query for p in plan if p.dimension == "features"]
        self.assertEqual(queries, ["Acme SSO plans", "Acme time tracking plans"])

    def test_competitive_searches_use_the_same_cutoff(self):
        plan = plan_searches("Acme", ["Beta"], date(2026, 10, 18))
        competitive = [p for p in plan if p.dimension == "competitive"]
        self.assertEqual(competitive[0].start_date, "2025-10-18")

    def test_reception_query_uses_year_and_start_date(self):
        reception = [p for p in plan_searches("Acme", [], date(2026, 10, 18)) if p.dimension == "reception"][0]
        self.assertIn("2026", reception.query)
        self.assertEqual(reception.start_date, "2025-10-18")
        self.assertIsNone(reception.time_range)


class SourceTests(unittest.TestCase):
    def test_reception_drops_results_dated_before_window(self):
        registry: list[Source] = []
        planned = PlannedSearch("reception", "q", start_date="2025-10-18")
        results = [
            {"url": "https://old.com", "title": "Old", "published_date": "2022-06-30"},
            {"url": "https://new.com", "title": "New", "published_date": "2026-03-01"},
            {"url": "https://undated.com", "title": "Undated"},
        ]
        added = add_sources(registry, planned, results)
        self.assertEqual([s.url for s in added], ["https://new.com", "https://undated.com"])

    def test_ids_are_sequential_and_urls_deduplicated(self):
        registry: list[Source] = []
        planned = PlannedSearch("pricing", "q")
        results = [
            {"url": "https://a.com", "title": "A", "content": "x  y"},
            {"url": "https://b.com", "title": "B", "content": ""},
            {"url": "https://a.com", "title": "A again", "content": "z"},
            {"url": "", "title": "no url"},
        ]
        added = add_sources(registry, planned, results)
        self.assertEqual([s.id for s in registry], ["S1", "S2"])
        self.assertEqual(len(added), 2)
        self.assertEqual(registry[0].content, "x y")

    def test_second_search_does_not_repeat_known_urls(self):
        registry: list[Source] = []
        add_sources(registry, PlannedSearch("pricing", "q1"), [{"url": "https://a.com", "title": "A"}])
        added = add_sources(registry, PlannedSearch("reception", "q2"), [{"url": "https://a.com"}, {"url": "https://c.com"}])
        self.assertEqual([s.url for s in added], ["https://c.com"])
        self.assertEqual(registry[1].id, "S2")

    def test_published_date_is_saved(self):
        registry: list[Source] = []
        add_sources(registry, PlannedSearch("reception", "q", start_date="2025-01-01"),
                    [{"url": "https://a.com", "title": "A", "published_date": "2026-02-03T10:00:00"}])
        self.assertEqual(registry[0].published, "2026-02-03")

    def test_require_date_drops_undated_results(self):
        registry: list[Source] = []
        planned = PlannedSearch("reception", "q", topic="news", require_date=True)
        add_sources(registry, planned, [
            {"url": "https://a.com", "title": "A", "published_date": "2026-02-03"},
            {"url": "https://b.com", "title": "B"},
        ])
        self.assertEqual([s.url for s in registry], ["https://a.com"])

    def test_undated_results_kept_without_require_date(self):
        registry: list[Source] = []
        add_sources(registry, PlannedSearch("pricing", "q"), [{"url": "https://b.com", "title": "B"}])
        self.assertEqual(len(registry), 1)

    def test_time_sensitive_searches_use_news_and_require_dates(self):
        plan = plan_searches("Acme", ["Beta"], date(2026, 10, 18))
        for p in plan:
            if p.dimension in ("competitive", "reception"):
                self.assertEqual(p.topic, "news")
                self.assertTrue(p.require_date)
            if p.dimension == "pricing":
                self.assertFalse(p.require_date)


class ParseTests(unittest.TestCase):
    def test_parse_similar_strips_prose_and_fences(self):
        reply = 'Here you go:\n```json\n{"products": ["Beta", " beta ", "Acme", "Gamma"]}\n```'
        self.assertEqual(parse_similar(reply, "Acme"), ["Beta", "Gamma"])

    def test_parse_similar_caps_count(self):
        reply = '{"products": ["A", "B", "C", "D", "E"]}'
        self.assertEqual(len(parse_similar(reply, "Acme", limit=3)), 3)

    def test_parse_similar_ignores_reasoning_blocks(self):
        reply = '<think>Maybe {"products": ["Wrong"]} or not</think>{"products": ["Right"]}'
        self.assertEqual(parse_similar(reply, "Acme"), ["Right"])

    def test_parse_claims_reads_fields(self):
        reply = '{"claims": [{"dimension": "pricing", "text": "Starts at $10.", "sources": ["S1"]}]}'
        claims = parse_claims(reply)
        self.assertEqual(claims[0].dimension, "pricing")
        self.assertEqual(claims[0].source_ids, ["S1"])

    def test_parse_claims_skips_empty_items(self):
        reply = '{"claims": [{"dimension": "pricing", "text": ""}, "bad", {"dimension": "pricing", "text": "ok"}]}'
        self.assertEqual([c.text for c in parse_claims(reply)], ["ok"])

    def test_parse_raises_when_no_json(self):
        with self.assertRaises(ValueError):
            parse_similar("no json here", "Acme")


class StatusTests(unittest.TestCase):
    def test_retired_with_source(self):
        self.assertEqual(parse_status('{"status": "retired", "source": "S40"}'), ("retired", "S40"))

    def test_active_is_read_case_insensitively(self):
        self.assertEqual(parse_status('{"status": "Active", "source": "S3"}'), ("active", "S3"))

    def test_unknown_status_value_becomes_unknown(self):
        self.assertEqual(parse_status('{"status": "dead-ish", "source": "S1"}'), ("unknown", "S1"))

    def test_missing_fields_become_unknown(self):
        self.assertEqual(parse_status("{}"), ("unknown", ""))

    def test_status_inside_prose_and_reasoning(self):
        reply = '<think>{"status": "active"}</think>Here: {"status": "retired", "source": "S2"}'
        self.assertEqual(parse_status(reply), ("retired", "S2"))


class CheckClaimsTests(unittest.TestCase):
    def test_claim_with_valid_id_is_supported(self):
        claims = [Claim("pricing", "Starts at $10.", ["S1"])]
        supported, unsupported = check_claims(claims, {"S1", "S2"})
        self.assertEqual(len(supported), 1)
        self.assertEqual(unsupported, [])

    def test_claim_with_only_unknown_ids_is_unsupported(self):
        claims = [Claim("pricing", "Costs $99.", ["S9"])]
        supported, unsupported = check_claims(claims, {"S1"})
        self.assertEqual(supported, [])
        self.assertEqual(len(unsupported), 1)

    def test_claim_with_no_ids_is_unsupported(self):
        supported, unsupported = check_claims([Claim("reception", "Well received.", [])], {"S1"})
        self.assertEqual(supported, [])
        self.assertEqual(len(unsupported), 1)

    def test_mixed_ids_keep_only_valid_ones(self):
        supported, _ = check_claims([Claim("pricing", "x", ["S1", "S9"])], {"S1"})
        self.assertEqual(supported[0].source_ids, ["S1"])


class RenderTests(unittest.TestCase):
    def test_price_not_in_cited_text_is_flagged(self):
        sources = [Source("S1", "https://a.com", "A", "Basic is $10 per user per month.", "pricing", "q")]
        claims = [
            Claim("pricing", "Basic costs $10 per user per month.", ["S1"]),
            Claim("pricing", "Plans range from $5,000 to $70,000.", ["S1"]),
        ]
        brief = render_brief("Acme", [], claims, [], sources, "2026-10-18")
        self.assertNotIn("Basic costs $10 per user per month. [S1] (date unknown) (price not in cited text)", brief)
        self.assertIn("Basic costs $10 per user per month. [S1] (date unknown)\n", brief)
        self.assertIn("(price not in cited text)", brief)

    def test_undated_sources_are_marked_in_brief(self):
        sources = [
            Source("S1", "https://a.com", "Dated", "", "reception", "q", published="2026-03-01"),
            Source("S2", "https://b.com", "Undated", "", "reception", "q"),
        ]
        supported = [
            Claim("reception", "Dated claim.", ["S1"]),
            Claim("reception", "Undated claim.", ["S2"]),
        ]
        brief = render_brief("Acme", [], supported, [], sources, "2026-10-18")
        self.assertIn("- Dated claim. [S1] (unverified)\n", brief)
        self.assertIn("- Undated claim. [S2] (date unknown) (unverified)", brief)
        self.assertIn("- [S1] Dated (2026-03-01): https://a.com", brief)
        self.assertIn("- [S2] Undated (date unknown): https://b.com", brief)

    def test_brief_has_citations_unsupported_section_and_sources(self):
        sources = [Source("S1", "https://a.com", "Acme pricing", "", "pricing", "q")]
        supported = [Claim("pricing", "Starts at $10.", ["S1"])]
        unsupported = [Claim("reception", "Loved by users.", [])]
        brief = render_brief("Acme", ["Beta"], supported, unsupported, sources, "2026-10-18")
        self.assertIn("- Starts at $10. [S1]", brief)
        self.assertIn("- Loved by users. (no valid source)", brief)
        self.assertIn("- [S1] Acme pricing (date unknown): https://a.com", brief)
        self.assertIn("No sourced claims for this dimension.", brief)


if __name__ == "__main__":
    unittest.main()


class PriceCheckTests(unittest.TestCase):
    def setUp(self):
        self.sources = {"S1": Source("S1", "https://a.com", "A", "", "pricing", "q")}

    def test_price_on_cited_page_is_kept(self):
        claims = [Claim("pricing", "Basic is $10 per user per month.", ["S1"])]
        kept, rejected, counts = verify_prices(claims, self.sources, {"https://a.com": "Basic $10 per user/month"})
        self.assertEqual(len(kept), 1)
        self.assertEqual(rejected, [])
        self.assertEqual(counts["checked"], 1)

    def test_price_not_on_cited_page_is_rejected(self):
        claims = [Claim("pricing", "Plans range from $5,000 to $70,000.", ["S1"])]
        kept, rejected, counts = verify_prices(claims, self.sources, {"https://a.com": "Plans from $70,000"})
        self.assertEqual(kept, [])
        self.assertEqual(len(rejected), 1)
        self.assertIn("$5,000 not found on the cited page", rejected[0].text)
        self.assertEqual(counts["missing"], 1)

    def test_unfetched_page_keeps_claim_with_label(self):
        claims = [Claim("pricing", "Basic is $10.", ["S1"])]
        kept, rejected, counts = verify_prices(claims, self.sources, {"https://a.com": ""})
        self.assertEqual(rejected, [])
        self.assertIn("(price check unavailable)", kept[0].text)
        self.assertEqual(counts["unavailable"], 1)

    def test_price_does_not_match_inside_a_longer_number(self):
        claims = [Claim("pricing", "Plan costs $10.", ["S1"])]
        kept, rejected, _ = verify_prices(claims, self.sources, {"https://a.com": "Plan costs $100 per month"})
        self.assertEqual(kept, [])
        self.assertEqual(len(rejected), 1)

    def test_non_pricing_claims_are_not_checked(self):
        claims = [Claim("competitive", "Jira costs $10.", ["S1"])]
        kept, rejected, counts = verify_prices(claims, self.sources, {"https://a.com": ""})
        self.assertEqual(len(kept), 1)
        self.assertEqual(counts["checked"], 0)


class RelevanceTests(unittest.TestCase):
    def test_keeps_results_that_name_a_product(self):
        results = [{"title": "Linear pricing", "content": "Basic plan"},
                   {"title": "Spirit Airlines shuts down", "content": "flights cancelled"}]
        kept, dropped = filter_relevant(results, ["Linear", "Jira"])
        self.assertEqual([r["title"] for r in kept], ["Linear pricing"])
        self.assertEqual(dropped, 1)

    def test_whole_word_only(self):
        results = [{"title": "10 airplanes discontinued", "content": ""}]
        kept, dropped = filter_relevant(results, ["Plane"])
        self.assertEqual(kept, [])
        self.assertEqual(dropped, 1)

    def test_lowercase_common_word_does_not_match_product(self):
        results = [{"title": "Spirit Airlines", "content": "A Spirit Airline plane sits on the tarmac"}]
        kept, dropped = filter_relevant(results, ["Plane"])
        self.assertEqual(kept, [])
        self.assertEqual(dropped, 1)

    def test_no_names_means_no_filter(self):
        results = [{"title": "anything", "content": ""}]
        kept, dropped = filter_relevant(results, [])
        self.assertEqual(kept, results)
        self.assertEqual(dropped, 0)


class VerifiedSectionTests(unittest.TestCase):
    def test_non_pricing_sections_are_marked_unverified(self):
        sources = [Source("S1", "https://a.com", "A", "Basic is $10 per user per month.", "pricing", "q")]
        claims = [
            Claim("pricing", "Basic costs $10 per user per month.", ["S1"]),
            Claim("competitive", "Rival X is faster.", ["S1"]),
        ]
        brief = render_brief("Acme", [], claims, [], sources, "2026-10-18")
        self.assertIn("## Pricing and plans\n", brief)
        self.assertIn("## Competitive landscape (not yet verified)", brief)
        self.assertIn("Rival X is faster. [S1] (date unknown) (unverified)", brief)
        self.assertNotIn("Basic costs $10 per user per month. [S1] (date unknown) (unverified)", brief)
