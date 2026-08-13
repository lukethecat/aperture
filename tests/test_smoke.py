"""
Smoke tests for aperture.

Run with: python -m pytest tests/test_smoke.py
Or:       python tests/test_smoke.py

All tests are offline and use a temporary tape directory.
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Add parent directory to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from engine import tape, profile, prescreen, dedup, scanner


class TestTape(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="aperture_test_")
        # Monkey-patch tape directory to tmp dir
        self._orig_tape_dir = tape._tape_dir
        tape._tape_dir = lambda: self.tmpdir

    def tearDown(self):
        tape._tape_dir = self._orig_tape_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_append_and_query(self):
        tape.append("test", {"type": "foo", "value": 1})
        tape.append("test", {"type": "foo", "value": 2})
        records = tape.query("test", type="foo")
        self.assertEqual(len(records), 2)
        self.assertEqual(records[-1]["value"], 2)

    def test_latest(self):
        tape.append("test", {"type": "bar", "value": 1})
        tape.append("test", {"type": "bar", "value": 2})
        latest = tape.latest("test", "bar")
        self.assertEqual(latest["value"], 2)


class TestProfile(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="aperture_test_")
        self._orig_tape_dir = tape._tape_dir
        tape._tape_dir = lambda: self.tmpdir

    def tearDown(self):
        tape._tape_dir = self._orig_tape_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_init_and_update(self):
        p = profile.init_profile(
            "v",
            keywords=[{"term": "AI", "weight": 5}],
            categories=[{"name": "policy", "keywords": ["regulation"], "bonus": 2}],
            negatives=[{"term": "sponsored", "weight": 3}],
        )
        self.assertEqual(p["version"], 1)
        pos, neg = profile.get_keyword_map("v")
        self.assertIn("AI", pos)
        self.assertIn("sponsored", neg)

        old, new = profile.update_profile(
            "v",
            [{"op": "add_keyword", "term": "Linux", "weight": 3}],
            reason="test update",
        )
        self.assertEqual(old["version"], 1)
        self.assertEqual(new["version"], 2)
        pos, _ = profile.get_keyword_map("v")
        self.assertIn("Linux", pos)


class TestPrescreen(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="aperture_test_")
        self._orig_tape_dir = tape._tape_dir
        tape._tape_dir = lambda: self.tmpdir
        profile.init_profile(
            "v",
            keywords=[{"term": "AI", "weight": 5}, {"term": "Linux", "weight": 3}],
            categories=[],
            negatives=[{"term": "sponsored", "weight": 10}],
        )

    def tearDown(self):
        tape._tape_dir = self._orig_tape_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_pass_and_reject(self):
        result = prescreen.prescreen_item("New AI model released", "http://example.com/1", "v")
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["score"], 5)

        result = prescreen.prescreen_item("Sponsored post about AI", "http://example.com/2", "v")
        self.assertEqual(result["status"], "reject")
        self.assertEqual(result["reject_reason"], "low_score")

    def test_borderline(self):
        # Score=5 must be borderline even when threshold is lower (e.g. 3),
        # so it is held for editorial review instead of auto-passing.
        profile.init_profile(
            "v2",
            keywords=[{"term": "AI", "weight": 5}],
            categories=[],
            negatives=[],
            threshold=3,
            editorial_review_scores=[5],
        )
        result = prescreen.prescreen_item("New AI model released", "http://example.com/1", "v2")
        self.assertEqual(result["status"], "borderline")
        self.assertEqual(result["score"], 5)
        self.assertIsNone(result["reject_reason"])

    def test_candidates(self):
        candidates = [
            {"title": "AI breakthrough", "url": "http://example.com/a", "url_norm": "http://example.com/a"},
            {"title": "Random daily update", "url": "http://example.com/b", "url_norm": "http://example.com/b"},
        ]
        stats = prescreen.prescreen_candidates(candidates, "v")
        self.assertEqual(stats["passed"], 1)
        self.assertEqual(stats["rejected"], 1)
        self.assertIn("low_score", stats["reject_reasons"])


class TestDedup(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="aperture_test_")
        self._orig_tape_dir = tape._tape_dir
        tape._tape_dir = lambda: self.tmpdir

    def tearDown(self):
        tape._tape_dir = self._orig_tape_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_url_dedup(self):
        items = [
            {"title": "AI news", "url": "http://example.com/x", "url_norm": "http://example.com/x", "stage": "verified", "scores": {"prescreen": 5}},
            {"title": "AI news again", "url": "http://example.com/x", "url_norm": "http://example.com/x", "stage": "verified", "scores": {"prescreen": 5}},
        ]
        result = dedup.dedup_and_cluster(items, "v")
        self.assertEqual(result["pooled_count"], 1)
        self.assertEqual(result["url_deduped"], 1)

    def test_simhash_clustering(self):
        items = [
            {"title": "OpenAI releases new model today", "url": "http://example.com/a", "url_norm": "http://example.com/a", "stage": "verified", "scores": {"prescreen": 5}},
            {"title": "OpenAI releases new model today", "url": "http://example.com/b", "url_norm": "http://example.com/b", "stage": "verified", "scores": {"prescreen": 5}},
        ]
        result = dedup.dedup_and_cluster(items, "v")
        self.assertEqual(result["pooled_count"], 2)
        self.assertEqual(result["cluster_count"], 1)


class TestScanner(unittest.TestCase):
    def test_normalize_url(self):
        self.assertEqual(
            scanner.normalize_url("https://example.com/path?utm_source=foo"),
            "https://example.com/path",
        )
        self.assertEqual(
            scanner.normalize_url("HTTP://WWW.Example.COM/Path/"),
            "https://example.com/path",
        )

    def test_extract_rss(self):
        raw = """<?xml version="1.0"?>
        <rss><channel>
          <item><title>Hello World</title><link>https://example.com/1</link></item>
          <item><title>Second Post</title><link>https://example.com/2</link></item>
        </channel></rss>"""
        items = scanner._extract_rss(raw, "https://example.com")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "Hello World")

    def test_extract_generic_links(self):
        raw = '<a href="/page/1">Short</a><a href="/page/2">This is a long enough title</a>'
        items = scanner._extract_generic_links(raw, "https://example.com")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "This is a long enough title")


class TestEcho(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="aperture_test_")
        self._orig_tape_dir = tape._tape_dir
        tape._tape_dir = lambda: self.tmpdir

    def tearDown(self):
        tape._tape_dir = self._orig_tape_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_echo_generates_question(self):
        from engine import echo
        profile.init_profile(
            "v",
            keywords=[{"term": "AI", "weight": 5}],
            categories=[],
            negatives=[],
        )
        items = [
            {"title": "Quantum breakthrough", "url": "http://example.com/1", "stage": "pooled"},
            {"title": "Quantum chips advance", "url": "http://example.com/2", "stage": "pooled"},
        ]
        questions = echo.generate_questions("v", items=items)
        self.assertTrue(len(questions) > 0)
        self.assertEqual(questions[0]["topic"], "Quantum")

    def test_echo_answer_adds_keyword(self):
        from engine import echo
        profile.init_profile(
            "v",
            keywords=[{"term": "AI", "weight": 5}],
            categories=[],
            negatives=[],
        )
        items = [
            {"title": "Quantum breakthrough", "url": "http://example.com/1", "stage": "pooled"},
            {"title": "Quantum chips advance", "url": "http://example.com/2", "stage": "pooled"},
        ]
        questions = echo.ask("v", items=items)
        self.assertTrue(len(questions) > 0)
        result = echo.apply_answer(questions[0]["id"], "v", "yes")
        self.assertEqual(result["status"], "applied")
        pos, _ = profile.get_keyword_map("v")
        self.assertIn("Quantum", pos)


if __name__ == "__main__":
    unittest.main()
