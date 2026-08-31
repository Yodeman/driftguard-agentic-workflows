import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "benchmark" / "opencode_trace.py"
spec = importlib.util.spec_from_file_location("opencode_trace", MODULE_PATH)
trace = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(trace)


class VerdictParsingTests(unittest.TestCase):
    def test_markdown_heading(self):
        self.assertEqual(trace.extract_verdict("# Fail\nSchema drift remains."), "FAIL")

    def test_bold(self):
        self.assertEqual(trace.extract_verdict("**PASS**\nAll checks are clean."), "PASS")

    def test_label(self):
        self.assertEqual(trace.extract_verdict("Verdict: ABSTAIN\nEvidence is ambiguous."), "ABSTAIN")

    def test_machine_marker_anywhere(self):
        text = "Evidence first.\n\nDRIFTGUARD_VERDICT: FAIL\n"
        self.assertEqual(trace.extract_verdict(text), "FAIL")

    def test_json(self):
        self.assertEqual(trace.extract_verdict('{"verdict":"PASS","reason":"ok"}'), "PASS")

    def test_explanatory_word_does_not_trigger(self):
        self.assertIsNone(trace.extract_verdict("The build could fail if the contract changes."))

    def test_conflicting_markers_fail_closed(self):
        text = "DRIFTGUARD_VERDICT: PASS\nDRIFTGUARD_VERDICT: FAIL\n"
        self.assertIsNone(trace.extract_verdict(text))


class WebUrlTests(unittest.TestCase):
    def test_session_deep_link(self):
        url = trace.build_web_url("http://127.0.0.1:4096", "/tmp/my repo", "ses_123")
        self.assertTrue(url.startswith("http://127.0.0.1:4096/"))
        self.assertTrue(url.endswith("/session/ses_123"))
        self.assertNotIn(" ", url)


if __name__ == "__main__":
    unittest.main()
