import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("upstream_tags", Path(__file__).parents[1] / "scripts/upstream_tags.py")
tags = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tags)
A, B, C = "a" * 40, "b" * 40, "c" * 40


class TagTests(unittest.TestCase):
    def test_annotated_and_lightweight_tags(self):
        text = f"{A}\trefs/tags/v11.3.2\n{B}\trefs/tags/v11.3.2^{{}}\n{C}\trefs/tags/v11.4.0\n"
        self.assertEqual(tags.parse_refs(text), {"v11.3.2": B, "v11.4.0": C})

    def test_empty_response_fails(self):
        with self.assertRaises(ValueError): tags.parse_refs("")

    def test_all_new_tags_including_maintenance_and_beta(self):
        upstream = {"v11.3.2": A, "v11.4.0": B, "v11.3.3": C, "v11.5.0.beta": C}
        result = tags.plan(upstream, {"v11.3.2": A}, {})
        self.assertEqual({r["tag"] for r in result}, {"v11.4.0", "v11.3.3", "v11.5.0.beta"})
        self.assertEqual(len(tags.plan(upstream, {"v11.3.2": A}, {"v11.4.0": B})), 2)

    def test_historic_manual_build(self):
        self.assertEqual(tags.plan({"v11.3.2": A}, {"v11.3.2": A}, {}, "v11.3.2")[0]["commit"], A)

    def test_moved_tag_fails(self):
        with self.assertRaises(ValueError): tags.plan({"v11.3.2": B}, {"v11.3.2": A}, {})
        with self.assertRaises(ValueError): tags.plan({"v11.3.2": B}, {}, {"v11.3.2": A})

    def test_successful_tag_is_not_rebuilt(self):
        self.assertEqual(tags.plan({"v11.3.2": A}, {}, {"v11.3.2": A}), [])

    def test_explicit_rebuild_only_selects_requested_version(self):
        upstream = {"v11.3.2": A, "v11.4.0": B}
        result = tags.plan(upstream, {}, upstream, "v11.3.2", rebuild=True)
        self.assertEqual(result, [{"tag": "v11.3.2", "commit": A, "image_tag": "v11.3.2"}])

    def test_rebuild_requires_tag_and_rejects_moved_source(self):
        with self.assertRaises(ValueError): tags.plan({"v11.3.2": A}, {}, {}, rebuild=True)
        with self.assertRaises(ValueError):
            tags.plan({"v11.3.2": B}, {}, {"v11.3.2": A}, "v11.3.2", rebuild=True)

    def test_git_tag_without_published_sif_is_retried(self):
        # Includes historic tags (and the original OCI release) in the retry set.
        result = tags.plan({"v11.3.2": A}, {"v11.3.2": A}, {}, tagged={"v11.3.2": A})
        self.assertEqual(result[0]["image_tag"], "v11.3.2")
        self.assertEqual(tags.plan({"v11.3.2": A}, {}, {"v11.3.2": A}, tagged={"v11.3.2": A}), [])

    def test_invalid_names_and_missing_requested_tag_fail(self):
        for name in ("bad/tag", "v11.3.2;echo", "v11.3.2\nmalicious"):
            with self.assertRaises(ValueError): tags.plan({name: A}, {}, {})
        with self.assertRaises(ValueError): tags.plan({"v11.3.2": A}, {}, {}, "v11.9.0")

    def test_batches_do_not_mark_unbuilt_tags_as_done(self):
        upstream = {f"v11.3.{i}": A for i in range(20)}
        first = tags.plan(upstream, {}, {})
        self.assertEqual(len(first), 16)
        self.assertEqual(len(tags.plan(upstream, {}, {r["tag"]: A for r in first})), 4)


if __name__ == "__main__": unittest.main()
